"""Ruta /oportunidades/{id}: la ficha de una oportunidad.

Reune en un solo lugar lo que necesitas para moverla: datos editables
(valor, cierre esperado, siguiente paso), conversaciones registradas,
tareas, propuestas, documentos de la biblioteca y el historial de cambios.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.base_datos import obtener_sesion
from app.bitacora import registrar_cambio
from app.configuracion import convertir_fecha_local_a_utc
from app.errores import ErrorDeNegocio
from app.eventos import emitir_evento
from app.modelos import (
    Bitacora,
    Contacto,
    Documento,
    Interaccion,
    Oportunidad,
    Propuesta,
    Servicio,
    Tarea,
    hora_actual_utc,
)
from app.plantillas_util import convertir_monto, plantillas, ruta_de_regreso
from app.reglas_embudo import (
    cargar_reglas_embudo,
    color_semaforo,
    dias_sin_movimiento,
    etapas_permitidas_desde,
)

enrutador = APIRouter()

CANALES_INTERACCION = ["whatsapp", "correo", "instagram", "llamada", "reunion"]
ESTADOS_PROPUESTA = ["borrador", "enviada", "vista", "aceptada", "rechazada"]


def _obtener_oportunidad(sesion: Session, oportunidad_id: int) -> Oportunidad:
    oportunidad = sesion.get(Oportunidad, oportunidad_id)
    if oportunidad is None:
        raise ErrorDeNegocio("Esa oportunidad no existe. Vuelve al embudo y búscala de nuevo.")
    return oportunidad


def registrar_actividad(sesion: Session, oportunidad: Oportunidad) -> None:
    """Cualquier conversacion o propuesta nueva cuenta como movimiento:
    reinicia el contador de dias sin movimiento del semaforo."""
    oportunidad.ultima_actividad_en = hora_actual_utc()
    oportunidad.modificado_en = oportunidad.ultima_actividad_en
    oportunidad.en_riesgo = False
    sesion.add(oportunidad)


@enrutador.get("/oportunidades/{oportunidad_id}")
def ver_oportunidad(request: Request, oportunidad_id: int, sesion: Session = Depends(obtener_sesion)):
    oportunidad = _obtener_oportunidad(sesion, oportunidad_id)
    contacto = sesion.get(Contacto, oportunidad.contacto_id)
    servicio = sesion.get(Servicio, oportunidad.servicio_id)

    interacciones = sesion.exec(
        select(Interaccion).where(Interaccion.oportunidad_id == oportunidad.id).order_by(Interaccion.fecha.desc())
    ).all()
    tareas = sesion.exec(
        select(Tarea).where(Tarea.oportunidad_id == oportunidad.id).order_by(Tarea.estado.desc(), Tarea.fecha_limite)
    ).all()
    propuestas = sesion.exec(
        select(Propuesta).where(Propuesta.oportunidad_id == oportunidad.id).order_by(Propuesta.version.desc())
    ).all()
    documentos = sesion.exec(
        select(Documento)
        .where((Documento.oportunidad_id == oportunidad.id) | (Documento.contacto_id == oportunidad.contacto_id))
        .order_by(Documento.creado_en.desc())
    ).all()
    historial = sesion.exec(
        select(Bitacora)
        .where(Bitacora.entidad == "Oportunidad", Bitacora.entidad_id == oportunidad.id)
        .order_by(Bitacora.fecha.desc())
        .limit(30)
    ).all()

    return plantillas.TemplateResponse(
        "oportunidad.html",
        {
            "request": request,
            "oportunidad": oportunidad,
            "contacto": contacto,
            "servicio": servicio,
            "semaforo": color_semaforo(oportunidad),
            "dias_sin_movimiento": dias_sin_movimiento(oportunidad),
            "siguientes_etapas": etapas_permitidas_desde(oportunidad.etapa, servicio.linea if servicio else ""),
            "motivos_perdida": cargar_reglas_embudo()["motivos_perdida_validos"],
            "interacciones": interacciones,
            "tareas": tareas,
            "propuestas": propuestas,
            "documentos": documentos,
            "historial": historial,
            "canales": CANALES_INTERACCION,
            "estados_propuesta": ESTADOS_PROPUESTA,
            "ahora": hora_actual_utc(),
        },
    )


@enrutador.post("/oportunidades/{oportunidad_id}/editar")
def editar_oportunidad(
    oportunidad_id: int,
    valor_estimado: str = Form(""),
    moneda: str = Form("USD"),
    fecha_cierre_esperada: str = Form(""),
    siguiente_paso: str = Form(""),
    fecha_siguiente_paso: str = Form(""),
    sesion: Session = Depends(obtener_sesion),
):
    oportunidad = _obtener_oportunidad(sesion, oportunidad_id)
    cambios = {
        "valor_estimado": convertir_monto(valor_estimado),
        "moneda": (moneda.strip() or "USD").upper(),
        "fecha_cierre_esperada": convertir_fecha_local_a_utc(fecha_cierre_esperada),
        "siguiente_paso": siguiente_paso.strip() or None,
        "fecha_siguiente_paso": convertir_fecha_local_a_utc(fecha_siguiente_paso, "09:00"),
    }
    for campo, valor_nuevo in cambios.items():
        valor_anterior = getattr(oportunidad, campo)
        if valor_anterior != valor_nuevo:
            registrar_cambio(sesion, "Oportunidad", oportunidad.id, campo, valor_anterior, valor_nuevo, "yo")
            setattr(oportunidad, campo, valor_nuevo)

    oportunidad.modificado_en = hora_actual_utc()
    sesion.add(oportunidad)
    sesion.commit()
    return RedirectResponse(f"/oportunidades/{oportunidad.id}", status_code=303)


@enrutador.post("/oportunidades/{oportunidad_id}/interacciones")
def registrar_interaccion(
    oportunidad_id: int,
    canal: str = Form(...),
    direccion: str = Form("saliente"),
    resumen: str = Form(""),
    fecha: str = Form(""),
    requiere_respuesta: bool = Form(False),
    volver: str = Form(""),
    sesion: Session = Depends(obtener_sesion),
):
    oportunidad = _obtener_oportunidad(sesion, oportunidad_id)
    if canal not in CANALES_INTERACCION:
        raise ErrorDeNegocio(f"El canal debe ser uno de: {', '.join(CANALES_INTERACCION)}.")
    if direccion not in ("entrante", "saliente"):
        raise ErrorDeNegocio("La dirección debe ser entrante (te escribieron) o saliente (escribiste tú).")

    interaccion = Interaccion(
        oportunidad_id=oportunidad.id,
        canal=canal,
        direccion=direccion,
        resumen=resumen.strip() or None,
        requiere_respuesta=requiere_respuesta,
        fecha=convertir_fecha_local_a_utc(fecha) if fecha else hora_actual_utc(),
    )
    sesion.add(interaccion)
    sesion.flush()
    registrar_actividad(sesion, oportunidad)
    emitir_evento(
        sesion,
        tipo="interaccion.registrada",
        clave_unica=f"interaccion.registrada:{interaccion.id}",
        datos={"oportunidad_id": oportunidad.id, "canal": canal, "direccion": direccion},
        origen="yo",
    )
    sesion.commit()
    return RedirectResponse(ruta_de_regreso(volver, f"/oportunidades/{oportunidad.id}"), status_code=303)


@enrutador.post("/interacciones/{interaccion_id}/respondida")
def marcar_interaccion_respondida(interaccion_id: int, sesion: Session = Depends(obtener_sesion)):
    interaccion = sesion.get(Interaccion, interaccion_id)
    if interaccion is None:
        raise ErrorDeNegocio("Esa conversación ya no existe.")
    interaccion.requiere_respuesta = False
    interaccion.modificado_en = hora_actual_utc()
    sesion.add(interaccion)
    sesion.commit()
    return RedirectResponse(f"/oportunidades/{interaccion.oportunidad_id}", status_code=303)


def _enlace_documento(sesion: Session, documento_id: str, enlace: str) -> Optional[str]:
    """La propuesta puede apuntar a un documento de la biblioteca o a un enlace pegado."""
    if documento_id and documento_id.isdigit():
        documento = sesion.get(Documento, int(documento_id))
        if documento is not None:
            if documento.archivo_guardado:
                return f"/biblioteca/{documento.id}/archivo"
            return documento.enlace_externo
    enlace = enlace.strip()
    return enlace or None


@enrutador.post("/oportunidades/{oportunidad_id}/propuestas")
def crear_propuesta(
    oportunidad_id: int,
    monto: str = Form(""),
    moneda: str = Form(""),
    alcance: str = Form(""),
    vigencia_hasta: str = Form(""),
    documento_id: str = Form(""),
    documento_adjunto_url: str = Form(""),
    sesion: Session = Depends(obtener_sesion),
):
    oportunidad = _obtener_oportunidad(sesion, oportunidad_id)
    version_anterior = sesion.exec(
        select(Propuesta).where(Propuesta.oportunidad_id == oportunidad.id).order_by(Propuesta.version.desc())
    ).first()

    monto_numero = convertir_monto(monto)
    propuesta = Propuesta(
        oportunidad_id=oportunidad.id,
        version=(version_anterior.version + 1) if version_anterior else 1,
        monto=monto_numero if monto_numero is not None else (oportunidad.valor_estimado or 0.0),
        moneda=(moneda.strip() or oportunidad.moneda).upper(),
        alcance=alcance.strip() or None,
        vigencia_hasta=convertir_fecha_local_a_utc(vigencia_hasta),
        documento_adjunto_url=_enlace_documento(sesion, documento_id, documento_adjunto_url),
    )
    sesion.add(propuesta)
    sesion.flush()
    registrar_cambio(sesion, "Oportunidad", oportunidad.id, "propuesta", None, f"v{propuesta.version}", "yo")

    # Si la oportunidad no tenia valor, la propuesta se lo da (lo pide la etapa Propuesta).
    if oportunidad.valor_estimado is None and propuesta.monto:
        registrar_cambio(sesion, "Oportunidad", oportunidad.id, "valor_estimado", None, propuesta.monto, "yo")
        oportunidad.valor_estimado = propuesta.monto
    registrar_actividad(sesion, oportunidad)
    sesion.commit()
    return RedirectResponse(f"/oportunidades/{oportunidad.id}#propuestas", status_code=303)


@enrutador.post("/propuestas/{propuesta_id}/estado")
def cambiar_estado_propuesta(
    propuesta_id: int,
    estado: str = Form(...),
    documento_id: str = Form(""),
    documento_adjunto_url: str = Form(""),
    sesion: Session = Depends(obtener_sesion),
):
    propuesta = sesion.get(Propuesta, propuesta_id)
    if propuesta is None:
        raise ErrorDeNegocio("Esa propuesta ya no existe.")
    if estado not in ESTADOS_PROPUESTA:
        raise ErrorDeNegocio(f"El estado debe ser uno de: {', '.join(ESTADOS_PROPUESTA)}.")

    if estado != propuesta.estado:
        registrar_cambio(sesion, "Propuesta", propuesta.id, "estado", propuesta.estado, estado, "yo")
        propuesta.estado = estado
        if estado == "enviada" and propuesta.fecha_envio is None:
            propuesta.fecha_envio = hora_actual_utc()

    nuevo_enlace = _enlace_documento(sesion, documento_id, documento_adjunto_url)
    if nuevo_enlace and nuevo_enlace != propuesta.documento_adjunto_url:
        registrar_cambio(
            sesion, "Propuesta", propuesta.id, "documento_adjunto_url", propuesta.documento_adjunto_url, nuevo_enlace, "yo"
        )
        propuesta.documento_adjunto_url = nuevo_enlace

    propuesta.modificado_en = hora_actual_utc()
    sesion.add(propuesta)
    oportunidad = sesion.get(Oportunidad, propuesta.oportunidad_id)
    registrar_actividad(sesion, oportunidad)
    sesion.commit()
    return RedirectResponse(f"/oportunidades/{propuesta.oportunidad_id}#propuestas", status_code=303)
