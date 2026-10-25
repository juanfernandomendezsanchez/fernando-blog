"""Ruta /biblioteca: tu archivo personal de documentos.

Aqui guardas lo que quieras tener a mano: plantillas, contratos, guias,
presentaciones, facturas, recursos para clientes o cosas solo tuyas. Cada
documento puede ser un archivo subido, un enlace externo (Drive, Notion,
Canva...) o ambos, y opcionalmente quedar ligado a un contacto u oportunidad.

Los archivos se guardan en CARPETA_BIBLIOTECA (por defecto crm/datos/biblioteca)
con un nombre aleatorio, para que dos archivos con el mismo nombre nunca se
pisen; el nombre original queda en la base de datos.
"""

import mimetypes
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from sqlmodel import Session, select

from app import configuracion
from app.base_datos import obtener_sesion
from app.bitacora import registrar_cambio
from app.errores import ErrorDeNegocio
from app.modelos import Contacto, Documento, Oportunidad, dividir_etiquetas, hora_actual_utc, unir_etiquetas
from app.plantillas_util import plantillas, ruta_de_regreso

enrutador = APIRouter()

CATEGORIAS_SUGERIDAS = [
    "general",
    "plantillas",
    "contratos",
    "propuestas",
    "facturas",
    "guias",
    "presentaciones",
    "recursos para clientes",
    "personal",
]

# Tipos que el navegador puede mostrar sin riesgo. Todo lo demas (incluido
# HTML y SVG, que pueden traer codigo) se descarga en vez de abrirse.
TIPOS_QUE_SE_PUEDEN_VER = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
    "text/plain",
    "audio/mpeg",
    "video/mp4",
}

TAMANO_BLOQUE = 1024 * 1024


def _carpeta_biblioteca() -> Path:
    carpeta = configuracion.CARPETA_BIBLIOTECA
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def _guardar_archivo(archivo: UploadFile) -> tuple[str, int]:
    """Copia el archivo subido a la biblioteca por bloques, cortando si pasa
    del tamano maximo. Devuelve (nombre_en_disco, tamano_en_bytes)."""
    extension = Path(archivo.filename or "").suffix.lower()[:10]
    nombre_en_disco = f"{uuid.uuid4().hex}{extension}"
    destino = _carpeta_biblioteca() / nombre_en_disco
    maximo = configuracion.TAMANO_MAXIMO_DOCUMENTO_MB * 1024 * 1024

    tamano = 0
    try:
        with open(destino, "wb") as salida:
            while bloque := archivo.file.read(TAMANO_BLOQUE):
                tamano += len(bloque)
                if tamano > maximo:
                    raise ErrorDeNegocio(
                        f"El archivo pesa mas de {configuracion.TAMANO_MAXIMO_DOCUMENTO_MB} MB. "
                        "Comprimelo, o guardalo en Drive y agrega aqui el enlace."
                    )
                salida.write(bloque)
    except Exception:
        destino.unlink(missing_ok=True)
        raise
    return nombre_en_disco, tamano


def _borrar_archivo_de_disco(documento: Documento) -> None:
    if documento.archivo_guardado:
        (_carpeta_biblioteca() / documento.archivo_guardado).unlink(missing_ok=True)


def _obtener_documento(sesion: Session, documento_id: int) -> Documento:
    documento = sesion.get(Documento, documento_id)
    if documento is None:
        raise ErrorDeNegocio("Ese documento ya no existe. Actualiza la pagina e intenta de nuevo.")
    return documento


def _id_opcional(texto: str) -> Optional[int]:
    return int(texto) if texto and texto.isdigit() else None


def _limpiar_etiquetas(texto: str) -> Optional[str]:
    return unir_etiquetas(dividir_etiquetas(texto.lower())) or None


@enrutador.get("/biblioteca")
def ver_biblioteca(
    request: Request,
    q: str = "",
    categoria: str = "",
    etiqueta: str = "",
    favoritos: str = "",
    sesion: Session = Depends(obtener_sesion),
):
    consulta = select(Documento)
    if q:
        texto = f"%{q}%"
        consulta = consulta.where(
            Documento.titulo.ilike(texto)
            | Documento.descripcion.ilike(texto)
            | Documento.nombre_archivo.ilike(texto)
            | Documento.etiquetas.ilike(texto)
        )
    if categoria:
        consulta = consulta.where(Documento.categoria == categoria)
    if favoritos:
        consulta = consulta.where(Documento.favorito == True)  # noqa: E712
    consulta = consulta.order_by(Documento.favorito.desc(), Documento.creado_en.desc())
    documentos = list(sesion.exec(consulta).all())
    if etiqueta:
        documentos = [d for d in documentos if etiqueta in dividir_etiquetas(d.etiquetas)]

    todos = sesion.exec(select(Documento)).all()
    categorias_usadas = sorted({d.categoria for d in todos})
    conteo_por_categoria = {c: sum(1 for d in todos if d.categoria == c) for c in categorias_usadas}
    etiquetas_usadas = sorted({e for d in todos for e in dividir_etiquetas(d.etiquetas)})

    contactos = {c.id: c for c in sesion.exec(select(Contacto).order_by(Contacto.nombre)).all()}

    return plantillas.TemplateResponse(
        "biblioteca.html",
        {
            "request": request,
            "documentos": documentos,
            "total_documentos": len(todos),
            "espacio_usado": sum(d.tamano_bytes for d in todos),
            "q": q,
            "categoria_seleccionada": categoria,
            "etiqueta_seleccionada": etiqueta,
            "solo_favoritos": bool(favoritos),
            "categorias_usadas": categorias_usadas,
            "conteo_por_categoria": conteo_por_categoria,
            "categorias_sugeridas": sorted(set(CATEGORIAS_SUGERIDAS) | set(categorias_usadas)),
            "etiquetas_usadas": etiquetas_usadas,
            "contactos": contactos,
            "tamano_maximo_mb": configuracion.TAMANO_MAXIMO_DOCUMENTO_MB,
        },
    )


@enrutador.post("/biblioteca/subir")
def subir_documento(
    titulo: str = Form(""),
    categoria: str = Form("general"),
    descripcion: str = Form(""),
    etiquetas: str = Form(""),
    enlace_externo: str = Form(""),
    contacto_id: str = Form(""),
    oportunidad_id: str = Form(""),
    volver: str = Form(""),
    archivo: Optional[UploadFile] = File(None),
    sesion: Session = Depends(obtener_sesion),
):
    tiene_archivo = archivo is not None and bool(archivo.filename)
    enlace_externo = enlace_externo.strip()
    if not tiene_archivo and not enlace_externo:
        raise ErrorDeNegocio("Elige un archivo para subir o pega un enlace (o ambos).")
    if enlace_externo and not enlace_externo.startswith(("http://", "https://")):
        raise ErrorDeNegocio("El enlace debe empezar con http:// o https://.")

    documento = Documento(
        titulo=titulo.strip() or (Path(archivo.filename).stem if tiene_archivo else enlace_externo),
        categoria=categoria.strip().lower() or "general",
        descripcion=descripcion.strip() or None,
        etiquetas=_limpiar_etiquetas(etiquetas),
        enlace_externo=enlace_externo or None,
        contacto_id=_id_opcional(contacto_id),
        oportunidad_id=_id_opcional(oportunidad_id),
    )

    if documento.oportunidad_id and not documento.contacto_id:
        oportunidad = sesion.get(Oportunidad, documento.oportunidad_id)
        if oportunidad is not None:
            documento.contacto_id = oportunidad.contacto_id

    if tiene_archivo:
        documento.archivo_guardado, documento.tamano_bytes = _guardar_archivo(archivo)
        documento.nombre_archivo = Path(archivo.filename).name
        documento.tipo_contenido = (
            archivo.content_type
            or mimetypes.guess_type(archivo.filename)[0]
            or "application/octet-stream"
        )

    sesion.add(documento)
    sesion.flush()
    registrar_cambio(sesion, "Documento", documento.id, "creado", None, documento.titulo, "yo")
    sesion.commit()
    return RedirectResponse(ruta_de_regreso(volver, "/biblioteca"), status_code=303)


@enrutador.get("/biblioteca/{documento_id}/archivo")
def abrir_archivo(documento_id: int, descargar: bool = False, sesion: Session = Depends(obtener_sesion)):
    documento = _obtener_documento(sesion, documento_id)
    if not documento.archivo_guardado:
        raise ErrorDeNegocio("Este documento es solo un enlace, no tiene archivo guardado.")

    ruta = _carpeta_biblioteca() / documento.archivo_guardado
    if not ruta.exists():
        raise ErrorDeNegocio(
            "No encuentro el archivo en la carpeta de la biblioteca. "
            "Puede que se haya borrado a mano de crm/datos/biblioteca."
        )

    tipo = documento.tipo_contenido or "application/octet-stream"
    se_puede_ver = tipo in TIPOS_QUE_SE_PUEDEN_VER and not descargar
    return FileResponse(
        ruta,
        media_type=tipo if se_puede_ver else "application/octet-stream",
        filename=documento.nombre_archivo or documento.archivo_guardado,
        content_disposition_type="inline" if se_puede_ver else "attachment",
    )


@enrutador.post("/biblioteca/{documento_id}/editar")
def editar_documento(
    documento_id: int,
    titulo: str = Form(...),
    categoria: str = Form("general"),
    descripcion: str = Form(""),
    etiquetas: str = Form(""),
    enlace_externo: str = Form(""),
    contacto_id: str = Form(""),
    volver: str = Form(""),
    sesion: Session = Depends(obtener_sesion),
):
    documento = _obtener_documento(sesion, documento_id)
    enlace_externo = enlace_externo.strip()
    if enlace_externo and not enlace_externo.startswith(("http://", "https://")):
        raise ErrorDeNegocio("El enlace debe empezar con http:// o https://.")
    if not enlace_externo and not documento.archivo_guardado:
        raise ErrorDeNegocio("Este documento no tiene archivo: no puedes dejarlo tambien sin enlace.")

    cambios = {
        "titulo": titulo.strip() or documento.titulo,
        "categoria": categoria.strip().lower() or "general",
        "descripcion": descripcion.strip() or None,
        "etiquetas": _limpiar_etiquetas(etiquetas),
        "enlace_externo": enlace_externo or None,
        "contacto_id": _id_opcional(contacto_id),
    }
    for campo, valor_nuevo in cambios.items():
        valor_anterior = getattr(documento, campo)
        if valor_anterior != valor_nuevo:
            registrar_cambio(sesion, "Documento", documento.id, campo, valor_anterior, valor_nuevo, "yo")
            setattr(documento, campo, valor_nuevo)

    documento.modificado_en = hora_actual_utc()
    sesion.add(documento)
    sesion.commit()
    return RedirectResponse(ruta_de_regreso(volver, "/biblioteca"), status_code=303)


@enrutador.post("/biblioteca/{documento_id}/favorito")
def alternar_favorito(documento_id: int, volver: str = Form(""), sesion: Session = Depends(obtener_sesion)):
    documento = _obtener_documento(sesion, documento_id)
    documento.favorito = not documento.favorito
    documento.modificado_en = hora_actual_utc()
    sesion.add(documento)
    sesion.commit()
    return RedirectResponse(ruta_de_regreso(volver, "/biblioteca"), status_code=303)


@enrutador.post("/biblioteca/{documento_id}/eliminar")
def eliminar_documento(documento_id: int, volver: str = Form(""), sesion: Session = Depends(obtener_sesion)):
    documento = _obtener_documento(sesion, documento_id)
    registrar_cambio(sesion, "Documento", documento.id, "eliminado", documento.titulo, None, "yo")
    sesion.delete(documento)
    sesion.commit()
    # El archivo se borra despues del commit: si la base de datos falla, no
    # queremos quedarnos con la fila apuntando a un archivo que ya no existe.
    _borrar_archivo_de_disco(documento)
    return RedirectResponse(ruta_de_regreso(volver, "/biblioteca"), status_code=303)
