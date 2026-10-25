"""Ruta /tareas: tu lista de pendientes, agrupada por urgencia.

Una tarea puede colgar de una oportunidad (por ejemplo "enviar propuesta a
Ana") o ser suelta ("renovar el dominio del blog").
"""

from datetime import timedelta

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.base_datos import obtener_sesion
from app.bitacora import registrar_cambio
from app.configuracion import convertir_a_hora_local, convertir_fecha_local_a_utc
from app.errores import ErrorDeNegocio
from app.modelos import Contacto, Oportunidad, Tarea, hora_actual_utc
from app.plantillas_util import plantillas, ruta_de_regreso

enrutador = APIRouter()

PRIORIDADES = ["alta", "media", "baja"]


def agrupar_tareas_pendientes(tareas: list[Tarea], ahora) -> dict[str, list[Tarea]]:
    """Separa las tareas pendientes en vencidas, hoy, proximos 7 dias, mas
    adelante y sin fecha, usando el dia en tu zona horaria (no en UTC)."""
    hoy_local = convertir_a_hora_local(ahora).date()
    grupos = {"vencidas": [], "hoy": [], "esta_semana": [], "mas_adelante": [], "sin_fecha": []}
    for tarea in tareas:
        if tarea.fecha_limite is None:
            grupos["sin_fecha"].append(tarea)
            continue
        dia = convertir_a_hora_local(tarea.fecha_limite).date()
        if dia < hoy_local:
            grupos["vencidas"].append(tarea)
        elif dia == hoy_local:
            grupos["hoy"].append(tarea)
        elif dia <= hoy_local + timedelta(days=7):
            grupos["esta_semana"].append(tarea)
        else:
            grupos["mas_adelante"].append(tarea)

    orden_prioridad = {p: i for i, p in enumerate(PRIORIDADES)}
    for lista in grupos.values():
        lista.sort(key=lambda t: (t.fecha_limite or ahora, orden_prioridad.get(t.prioridad, 1)))
    return grupos


def nombres_por_oportunidad(sesion: Session, tareas: list[Tarea]) -> dict[int, str]:
    """{oportunidad_id: nombre del contacto}, para mostrar de quien es cada tarea."""
    ids = {t.oportunidad_id for t in tareas if t.oportunidad_id}
    if not ids:
        return {}
    nombres = {}
    for oportunidad in sesion.exec(select(Oportunidad).where(Oportunidad.id.in_(ids))).all():
        contacto = sesion.get(Contacto, oportunidad.contacto_id)
        nombres[oportunidad.id] = contacto.nombre if contacto else f"Oportunidad #{oportunidad.id}"
    return nombres


@enrutador.get("/tareas")
def ver_tareas(request: Request, sesion: Session = Depends(obtener_sesion)):
    ahora = hora_actual_utc()
    pendientes = list(sesion.exec(select(Tarea).where(Tarea.estado == "pendiente")).all())
    hechas_recientes = list(
        sesion.exec(
            select(Tarea)
            .where(Tarea.estado.in_(["hecha", "cancelada"]), Tarea.modificado_en >= ahora - timedelta(days=7))
            .order_by(Tarea.modificado_en.desc())
        ).all()
    )

    oportunidades_abiertas = sesion.exec(
        select(Oportunidad).where(Oportunidad.etapa.not_in(["Ganado", "Perdido", "Descartado"]))
    ).all()
    opciones_oportunidad = []
    for oportunidad in oportunidades_abiertas:
        contacto = sesion.get(Contacto, oportunidad.contacto_id)
        opciones_oportunidad.append((oportunidad.id, f"{contacto.nombre if contacto else '?'} — {oportunidad.etapa}"))
    opciones_oportunidad.sort(key=lambda par: par[1].lower())

    return plantillas.TemplateResponse(
        "tareas.html",
        {
            "request": request,
            "grupos": agrupar_tareas_pendientes(pendientes, ahora),
            "total_pendientes": len(pendientes),
            "hechas_recientes": hechas_recientes,
            "nombres": nombres_por_oportunidad(sesion, pendientes + hechas_recientes),
            "opciones_oportunidad": opciones_oportunidad,
            "prioridades": PRIORIDADES,
        },
    )


@enrutador.post("/tareas/nueva")
def crear_tarea(
    descripcion: str = Form(...),
    fecha_limite: str = Form(""),
    prioridad: str = Form("media"),
    oportunidad_id: str = Form(""),
    volver: str = Form(""),
    sesion: Session = Depends(obtener_sesion),
):
    if not descripcion.strip():
        raise ErrorDeNegocio("Escribe qué hay que hacer.")
    tarea = Tarea(
        descripcion=descripcion.strip(),
        fecha_limite=convertir_fecha_local_a_utc(fecha_limite, "18:00"),
        prioridad=prioridad if prioridad in PRIORIDADES else "media",
        oportunidad_id=int(oportunidad_id) if oportunidad_id.isdigit() else None,
        creada_por="yo",
    )
    sesion.add(tarea)
    sesion.flush()
    registrar_cambio(sesion, "Tarea", tarea.id, "creado", None, tarea.descripcion, "yo")
    sesion.commit()
    return RedirectResponse(ruta_de_regreso(volver, "/tareas"), status_code=303)


def _cambiar_estado(sesion: Session, tarea_id: int, estado_nuevo: str) -> Tarea:
    tarea = sesion.get(Tarea, tarea_id)
    if tarea is None:
        raise ErrorDeNegocio("Esa tarea ya no existe. Actualiza la página.")
    if tarea.estado != estado_nuevo:
        registrar_cambio(sesion, "Tarea", tarea.id, "estado", tarea.estado, estado_nuevo, "yo")
        tarea.estado = estado_nuevo
        tarea.modificado_en = hora_actual_utc()
        sesion.add(tarea)
        sesion.commit()
    return tarea


@enrutador.post("/tareas/{tarea_id}/completar")
def completar_tarea(tarea_id: int, volver: str = Form(""), sesion: Session = Depends(obtener_sesion)):
    _cambiar_estado(sesion, tarea_id, "hecha")
    return RedirectResponse(ruta_de_regreso(volver, "/tareas"), status_code=303)


@enrutador.post("/tareas/{tarea_id}/cancelar")
def cancelar_tarea(tarea_id: int, volver: str = Form(""), sesion: Session = Depends(obtener_sesion)):
    _cambiar_estado(sesion, tarea_id, "cancelada")
    return RedirectResponse(ruta_de_regreso(volver, "/tareas"), status_code=303)


@enrutador.post("/tareas/{tarea_id}/reabrir")
def reabrir_tarea(tarea_id: int, volver: str = Form(""), sesion: Session = Depends(obtener_sesion)):
    _cambiar_estado(sesion, tarea_id, "pendiente")
    return RedirectResponse(ruta_de_regreso(volver, "/tareas"), status_code=303)
