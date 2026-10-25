"""Ruta /hoy: resumen del dia.

Nota: "reuniones de hoy" todavia no se muestra aqui (queda para cuando se
conecte Google Calendar en la Fase 2).

Las oportunidades en riesgo se calculan aqui mismo con esta_en_riesgo(...)
en vez de leer el campo en_riesgo, porque ese campo lo iba a marcar el reloj
de automatizaciones, que todavia no existe.
"""

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session, select

from app.base_datos import obtener_sesion
from app.configuracion import META_MENSUAL_USD, convertir_a_hora_local
from app.modelos import Borrador, Contacto, Documento, Interaccion, Oportunidad, Pago, Tarea, hora_actual_utc
from app.plantillas_util import plantillas
from app.reglas_embudo import dias_sin_movimiento, esta_en_riesgo
from app.rutas.embudo import ETAPAS_DEL_TABLERO
from app.rutas.tareas import agrupar_tareas_pendientes, nombres_por_oportunidad

enrutador = APIRouter()


@enrutador.get("/hoy")
def ver_hoy(request: Request, sesion: Session = Depends(obtener_sesion)):
    ahora = hora_actual_utc()
    inicio_del_mes = ahora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    pagos_del_mes = sesion.exec(
        select(Pago).where(Pago.estado == "recibido", Pago.fecha >= inicio_del_mes)
    ).all()
    cobrado_del_mes = sum(pago.monto for pago in pagos_del_mes)

    pagos_vencidos = sesion.exec(select(Pago).where(Pago.estado == "vencido")).all()
    monto_vencido = sum(pago.monto for pago in pagos_vencidos)

    oportunidades_abiertas = sesion.exec(
        select(Oportunidad).where(Oportunidad.etapa.in_(ETAPAS_DEL_TABLERO))
    ).all()
    embudo_ponderado = sum(
        (oportunidad.valor_estimado or 0) * oportunidad.probabilidad / 100
        for oportunidad in oportunidades_abiertas
    )

    borradores_para_aprobar = sesion.exec(select(Borrador).where(Borrador.estado == "pendiente")).all()

    tareas_pendientes = list(sesion.exec(select(Tarea).where(Tarea.estado == "pendiente")).all())
    grupos = agrupar_tareas_pendientes(tareas_pendientes, ahora)

    contactos = {c.id: c for c in sesion.exec(select(Contacto)).all()}
    hoy_local = convertir_a_hora_local(ahora).date()

    oportunidades_en_riesgo = sorted(
        (o for o in oportunidades_abiertas if esta_en_riesgo(o, ahora)),
        key=lambda o: -dias_sin_movimiento(o, ahora),
    )
    siguientes_pasos = sorted(
        (
            o
            for o in oportunidades_abiertas
            if o.fecha_siguiente_paso and convertir_a_hora_local(o.fecha_siguiente_paso).date() <= hoy_local
        ),
        key=lambda o: o.fecha_siguiente_paso,
    )

    por_responder = sesion.exec(
        select(Interaccion).where(Interaccion.requiere_respuesta == True).order_by(Interaccion.fecha)  # noqa: E712
    ).all()
    contacto_de_oportunidad = {
        o.id: contactos.get(o.contacto_id) for o in sesion.exec(select(Oportunidad)).all()
    }

    documentos_favoritos = sesion.exec(
        select(Documento).where(Documento.favorito == True).order_by(Documento.titulo).limit(8)  # noqa: E712
    ).all()

    return plantillas.TemplateResponse(
        "hoy.html",
        {
            "request": request,
            "cobrado_del_mes": cobrado_del_mes,
            "meta_mensual": META_MENSUAL_USD,
            "monto_vencido": monto_vencido,
            "embudo_ponderado": embudo_ponderado,
            "borradores_para_aprobar": borradores_para_aprobar,
            "tareas_vencidas": grupos["vencidas"],
            "tareas_de_hoy": grupos["hoy"],
            "nombres_tareas": nombres_por_oportunidad(sesion, grupos["vencidas"] + grupos["hoy"]),
            "oportunidades_en_riesgo": oportunidades_en_riesgo,
            "siguientes_pasos": siguientes_pasos,
            "por_responder": por_responder,
            "contactos": contactos,
            "contacto_de_oportunidad": contacto_de_oportunidad,
            "dias_sin_movimiento": {o.id: dias_sin_movimiento(o, ahora) for o in oportunidades_en_riesgo},
            "documentos_favoritos": documentos_favoritos,
        },
    )
