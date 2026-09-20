"""Ruta /contactos: tabla filtrable, alta rapida y busqueda global.

Nota de Fase 1: importar y exportar (por ejemplo desde Google Sheets) queda
para la Fase 2, cuando se conecte esa integracion.
"""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.base_datos import obtener_sesion
from app.bitacora import registrar_cambio
from app.eventos import emitir_evento
from app.modelos import Contacto, Oportunidad, Servicio, dividir_etiquetas, hora_actual_utc
from app.plantillas_util import plantillas
from app.reglas_embudo import cargar_reglas_embudo

enrutador = APIRouter()


def _renderizar_contactos(request: Request, sesion: Session, contactos: list[Contacto], **contexto_extra):
    servicios = sesion.exec(select(Servicio)).all()
    contexto = {
        "request": request,
        "contactos": contactos,
        "servicios": servicios,
        "etiqueta_seleccionada": "",
        "origen_seleccionado": "",
    }
    contexto.update(contexto_extra)
    return plantillas.TemplateResponse("contactos.html", contexto)


@enrutador.get("/contactos")
def ver_contactos(
    request: Request,
    etiqueta: str = "",
    origen: str = "",
    sesion: Session = Depends(obtener_sesion),
):
    consulta = select(Contacto)
    if origen:
        consulta = consulta.where(Contacto.origen == origen)
    contactos = list(sesion.exec(consulta).all())

    if etiqueta:
        contactos = [c for c in contactos if etiqueta in dividir_etiquetas(c.etiquetas)]

    return _renderizar_contactos(
        request, sesion, contactos, etiqueta_seleccionada=etiqueta, origen_seleccionado=origen
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
