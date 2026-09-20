"""Ruta /embudo: tablero por etapas, con boton para mover de etapa."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.base_datos import obtener_sesion
from app.errores import ErrorDeNegocio
from app.modelos import Contacto, Oportunidad, Servicio
from app.plantillas_util import plantillas
from app.reglas_embudo import color_semaforo, etapas_permitidas_desde, mover_etapa

enrutador = APIRouter()

# Etapas que se muestran como columnas del tablero (Ganado/Perdido/Descartado
# quedan fuera: viven en el historial de cada oportunidad, no en el tablero activo).
ETAPAS_DEL_TABLERO = ["Nuevo", "Calificado", "Diagnostico", "Propuesta", "Negociacion", "Dormido"]
LINEAS_DE_SERVICIO = ["asesoria", "consultoria", "venta"]


@enrutador.get("/embudo")
def ver_embudo(request: Request, linea: str = "", sesion: Session = Depends(obtener_sesion)):
    oportunidades = sesion.exec(select(Oportunidad).where(Oportunidad.etapa.in_(ETAPAS_DEL_TABLERO))).all()

    if linea:
        servicios_de_la_linea = {
            servicio.id for servicio in sesion.exec(select(Servicio).where(Servicio.linea == linea)).all()
        }
        oportunidades = [o for o in oportunidades if o.servicio_id in servicios_de_la_linea]

    columnas: dict[str, list[dict]] = {etapa: [] for etapa in ETAPAS_DEL_TABLERO}
    for oportunidad in oportunidades:
        contacto = sesion.get(Contacto, oportunidad.contacto_id)
        servicio = sesion.get(Servicio, oportunidad.servicio_id)
        columnas[oportunidad.etapa].append(
            {
                "oportunidad": oportunidad,
                "contacto": contacto,
                "semaforo": color_semaforo(oportunidad),
                "siguientes_etapas": etapas_permitidas_desde(oportunidad.etapa, servicio.linea),
            }
        )

    return plantillas.TemplateResponse(
        "embudo.html",
        {
            "request": request,
            "columnas": columnas,
            "etapas": ETAPAS_DEL_TABLERO,
            "linea_seleccionada": linea,
            "lineas": LINEAS_DE_SERVICIO,
        },
    )


@enrutador.post("/oportunidades/{oportunidad_id}/mover-etapa")
def mover_etapa_de_oportunidad(
    oportunidad_id: int,
    etapa_nueva: str = Form(...),
    motivo_perdida: str = Form(""),
    pago_recibido: bool = Form(False),
    sesion: Session = Depends(obtener_sesion),
):
    oportunidad = sesion.get(Oportunidad, oportunidad_id)
    if oportunidad is None:
        raise ErrorDeNegocio("Esa oportunidad no existe. Actualiza la pagina e intenta de nuevo.")

    mover_etapa(
        sesion,
        oportunidad,
        etapa_nueva,
        motivo_perdida=motivo_perdida or None,
        pago_recibido=pago_recibido,
    )
    return RedirectResponse("/embudo", status_code=303)
