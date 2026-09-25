"""Ruta /contactos: tabla filtrable, alta rapida, busqueda global y
sincronizacion manual con Google Sheets.

Nota de Fase 1: importar y exportar por archivo queda para mas adelante.
"""

from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.base_datos import obtener_sesion
from app.bitacora import registrar_cambio
from app.errores import ErrorDeNegocio
from app.eventos import emitir_evento
from app.modelos import Contacto, Oportunidad, Servicio, dividir_etiquetas, hora_actual_utc
from app.plantillas_util import plantillas
from app.reglas_embudo import cargar_reglas_embudo
from app.sincronizar_sheets import sincronizar_leads_desde_sheets

enrutador = APIRouter()


def _renderizar_contactos(request: Request, sesion: Session, contactos: list[Contacto], **contexto_extra):
    servicios = sesion.exec(select(Servicio)).all()
    contexto = {
        "request": request,
        "contactos": contactos,
        "servicios": servicios,
        "etiqueta_seleccionada": "",
        "origen_seleccionado": "",
        "mensaje_sincronizacion": "",
    }
    contexto.update(contexto_extra)
    return plantillas.TemplateResponse("contactos.html", contexto)


@enrutador.get("/contactos")
def ver_contactos(
    request: Request,
    etiqueta: str = "",
    origen: str = "",
    sincronizado: str = "",
    sesion: Session = Depends(obtener_sesion),
):
    consulta = select(Contacto)
    if origen:
        consulta = consulta.where(Contacto.origen == origen)
    contactos = list(sesion.exec(consulta).all())

    if etiqueta:
        contactos = [c for c in contactos if etiqueta in dividir_etiquetas(c.etiquetas)]

    return _renderizar_contactos(
        request,
        sesion,
        contactos,
        etiqueta_seleccionada=etiqueta,
        origen_seleccionado=origen,
        mensaje_sincronizacion=sincronizado,
    )


@enrutador.get("/buscar")
def buscar_contactos(request: Request, q: str = "", sesion: Session = Depends(obtener_sesion)):
    contactos: list[Contacto] = []
    if q:
        texto = f"%{q}%"
        contactos = list(
            sesion.exec(
                select(Contacto).where(
                    (Contacto.nombre.ilike(texto))
                    | (Contacto.correo.ilike(texto))
                    | (Contacto.telefono.ilike(texto))
                )
            ).all()
        )
    return _renderizar_contactos(request, sesion, contactos, busqueda=q)


@enrutador.post("/contactos/nuevo-rapido")
def crear_contacto_rapido(
    nombre: str = Form(...),
    canal_preferido: str = Form(""),
    servicio_id: int = Form(...),
    origen: str = Form("otro"),
    sesion: Session = Depends(obtener_sesion),
):
    """Alta rapida: solo nombre, canal y servicio de interes. Crea el
    contacto y su primera oportunidad en la etapa Nuevo."""
    contacto = Contacto(nombre=nombre, canal_preferido=canal_preferido or None, origen=origen)
    sesion.add(contacto)
    sesion.flush()

    reglas = cargar_reglas_embudo()
    oportunidad = Oportunidad(
        contacto_id=contacto.id,
        servicio_id=servicio_id,
        etapa="Nuevo",
        probabilidad=reglas["probabilidad_inicial"]["Nuevo"],
        origen=origen,
        ultima_actividad_en=hora_actual_utc(),
    )
    sesion.add(oportunidad)
    sesion.flush()

    registrar_cambio(sesion, "Contacto", contacto.id, "creado", None, nombre, "yo")
    emitir_evento(
        sesion,
        tipo="contacto.creado",
        clave_unica=f"contacto.creado:{contacto.id}",
        datos={"contacto_id": contacto.id},
        origen="yo",
    )

    sesion.commit()
    return RedirectResponse("/embudo", status_code=303)


@enrutador.post("/contactos/sincronizar-sheets")
def sincronizar_contactos_desde_sheets(sesion: Session = Depends(obtener_sesion)):
    try:
        resumen = sincronizar_leads_desde_sheets(sesion)
    except Exception as error:
        raise ErrorDeNegocio(
            "No se pudo sincronizar con Google Sheets: "
            + str(error)
            + ". Revisa que crm/credenciales_google.json exista y que la hoja este compartida con esa cuenta."
        )

    if not resumen["configurado"]:
        mensaje = "Google Sheets todavia no esta configurado (revisa GOOGLE_CREDENCIALES_JSON y GOOGLE_SHEETS_ID en tu .env)."
    else:
        mensaje = (
            f"Sincronizado: {resumen['creados']} creados, "
            f"{resumen['actualizados']} actualizados, {resumen['omitidos']} omitidos."
        )

    return RedirectResponse(f"/contactos?sincronizado={quote(mensaje)}", status_code=303)
