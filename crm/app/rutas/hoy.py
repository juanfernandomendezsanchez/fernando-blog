"""Ruta /hoy: resumen del dia.

Nota de Fase 1: como todavia no existe el motor de automatizaciones ni la
sincronizacion con Gmail/Calendario, "reuniones de hoy" no se muestra aqui
todavia (queda para cuando se conecte Google Calendar en la Fase 2).
"""

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session, select

from app.base_datos import obtener_sesion
from app.configuracion import META_MENSUAL_USD
from app.modelos import Borrador, Oportunidad, Pago, Tarea, hora_actual_utc
from app.plantillas_util import plantillas

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

    etapas_cerradas = ["Ganado", "Perdido", "Descartado"]
    oportunidades_abiertas = sesion.exec(
        select(Oportunidad).where(Oportunidad.etapa.not_in(etapas_cerradas))
    ).all()
    embudo_ponderado = sum(
        (oportunidad.valor_estimado or 0) * oportunidad.probabilidad / 100
        for oportunidad in oportunidades_abiertas
    )

    borradores_para_aprobar = sesion.exec(select(Borrador).where(Borrador.estado == "pendiente")).all()

    tareas_vencidas = sesion.exec(
        select(Tarea).where(Tarea.estado == "pendiente", Tarea.fecha_limite < ahora)
    ).all()

    oportunidades_en_riesgo = sesion.exec(select(Oportunidad).where(Oportunidad.en_riesgo == True)).all()  # noqa: E712

    return plantillas.TemplateResponse(
        "hoy.html",
        {
            "request": request,
            "cobrado_del_mes": cobrado_del_mes,
            "meta_mensual": META_MENSUAL_USD,
            "monto_vencido": monto_vencido,
            "embudo_ponderado": embudo_ponderado,
            "borradores_para_aprobar": borradores_para_aprobar,
            "tareas_vencidas": tareas_vencidas,
            "oportunidades_en_riesgo": oportunidades_en_riesgo,
        },
    )
