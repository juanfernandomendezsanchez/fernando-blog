"""Ruta /cifras: los numeros del negocio.

Todo se calcula en el momento a partir de las oportunidades y la Bitacora
(la fecha en que algo paso a Ganado sale de la Bitacora, no de modificado_en,
que cambia con cualquier edicion).
"""

from collections import Counter, defaultdict

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session, select

from app.base_datos import obtener_sesion
from app.configuracion import convertir_a_hora_local
from app.modelos import Bitacora, Contacto, Oportunidad, Servicio, hora_actual_utc
from app.plantillas_util import plantillas
from app.rutas.embudo import ETAPAS_DEL_TABLERO

enrutador = APIRouter()

MESES_A_MOSTRAR = 6
NOMBRES_DE_MES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def _ultimos_meses(ahora, cantidad: int) -> list[tuple[int, int]]:
    local = convertir_a_hora_local(ahora)
    anio, mes = local.year, local.month
    meses = []
    for _ in range(cantidad):
        meses.append((anio, mes))
        mes -= 1
        if mes == 0:
            anio, mes = anio - 1, 12
    return list(reversed(meses))


def calcular_cifras(sesion: Session) -> dict:
    ahora = hora_actual_utc()
    oportunidades = sesion.exec(select(Oportunidad)).all()
    servicios = {s.id: s for s in sesion.exec(select(Servicio)).all()}
    contactos = sesion.exec(select(Contacto)).all()

    # Fecha en que cada oportunidad paso a Ganado / Perdido.
    fecha_de_cierre = {}
    for fila in sesion.exec(
        select(Bitacora).where(
            Bitacora.entidad == "Oportunidad",
            Bitacora.campo == "etapa",
            Bitacora.valor_nuevo.in_(["Ganado", "Perdido"]),
        )
    ).all():
        fecha_de_cierre[fila.entidad_id] = fila.fecha

    ganadas = [o for o in oportunidades if o.etapa == "Ganado"]
    perdidas = [o for o in oportunidades if o.etapa == "Perdido"]
    abiertas = [o for o in oportunidades if o.etapa in ETAPAS_DEL_TABLERO]

    por_etapa = []
    for etapa in ETAPAS_DEL_TABLERO:
        de_la_etapa = [o for o in abiertas if o.etapa == etapa]
        por_etapa.append(
            {
                "etapa": etapa,
                "cantidad": len(de_la_etapa),
                "valor": sum(o.valor_estimado or 0 for o in de_la_etapa),
                "ponderado": sum((o.valor_estimado or 0) * o.probabilidad / 100 for o in de_la_etapa),
            }
        )

    meses = _ultimos_meses(ahora, MESES_A_MOSTRAR)
    ganado_por_mes = {mes: 0.0 for mes in meses}
    for oportunidad in ganadas:
        fecha = fecha_de_cierre.get(oportunidad.id)
        if fecha is None:
            continue
        local = convertir_a_hora_local(fecha)
        clave = (local.year, local.month)
        if clave in ganado_por_mes:
            ganado_por_mes[clave] += oportunidad.valor_estimado or 0
    serie_meses = [
        {"etiqueta": f"{NOMBRES_DE_MES[mes - 1]} {str(anio)[2:]}", "valor": ganado_por_mes[(anio, mes)]}
        for anio, mes in meses
    ]

    dias_para_ganar = [
        (fecha_de_cierre[o.id] - o.creado_en).days for o in ganadas if o.id in fecha_de_cierre
    ]

    por_origen = defaultdict(lambda: {"contactos": 0, "ganadas": 0, "valor_ganado": 0.0})
    for contacto in contactos:
        por_origen[contacto.origen]["contactos"] += 1
    for oportunidad in ganadas:
        por_origen[oportunidad.origen]["ganadas"] += 1
        por_origen[oportunidad.origen]["valor_ganado"] += oportunidad.valor_estimado or 0

    por_linea = defaultdict(lambda: {"abiertas": 0, "valor_abierto": 0.0, "ganadas": 0, "valor_ganado": 0.0})
    for oportunidad in abiertas + ganadas:
        servicio = servicios.get(oportunidad.servicio_id)
        linea = servicio.linea if servicio else "sin servicio"
        if oportunidad.etapa == "Ganado":
            por_linea[linea]["ganadas"] += 1
            por_linea[linea]["valor_ganado"] += oportunidad.valor_estimado or 0
        else:
            por_linea[linea]["abiertas"] += 1
            por_linea[linea]["valor_abierto"] += oportunidad.valor_estimado or 0

    cerradas = len(ganadas) + len(perdidas)
    return {
        "total_contactos": len(contactos),
        "total_abiertas": len(abiertas),
        "valor_abierto": sum(o.valor_estimado or 0 for o in abiertas),
        "valor_ponderado": sum(fila["ponderado"] for fila in por_etapa),
        "tasa_de_cierre": round(100 * len(ganadas) / cerradas) if cerradas else None,
        "ticket_promedio": (sum(o.valor_estimado or 0 for o in ganadas) / len(ganadas)) if ganadas else None,
        "dias_promedio_para_ganar": round(sum(dias_para_ganar) / len(dias_para_ganar)) if dias_para_ganar else None,
        "por_etapa": por_etapa,
        "serie_meses": serie_meses,
        "maximo_mes": max((m["valor"] for m in serie_meses), default=0),
        "por_origen": dict(sorted(por_origen.items(), key=lambda par: -par[1]["contactos"])),
        "por_linea": dict(por_linea),
        "motivos_perdida": Counter(o.motivo_perdida or "sin motivo" for o in perdidas).most_common(),
    }


@enrutador.get("/cifras")
def ver_cifras(request: Request, sesion: Session = Depends(obtener_sesion)):
    cifras = calcular_cifras(sesion)
    return plantillas.TemplateResponse("cifras.html", {"request": request, **cifras})
