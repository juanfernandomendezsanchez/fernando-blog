"""Ruta /contactos: tabla filtrable, alta rapida, busqueda global,
sincronizacion manual con Google Sheets, ficha de cada contacto (datos,
oportunidades, conversaciones, tareas, documentos e historial) y
exportacion a CSV.
"""

import csv
import io
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlmodel import Session, select

from app.base_datos import obtener_sesion
from app.bitacora import registrar_cambio
from app.errores import ErrorDeNegocio
from app.eventos import emitir_evento
from app.modelos import (
    Bitacora,
    Contacto,
    Documento,
    Empresa,
    Interaccion,
    Oportunidad,
    Servicio,
    Tarea,
    dividir_etiquetas,
    hora_actual_utc,
    unir_etiquetas,
)
from app.plantillas_util import convertir_monto, plantillas
from app.reglas_embudo import cargar_reglas_embudo, color_semaforo
from app.sincronizar_sheets import sincronizar_leads_desde_sheets

enrutador = APIRouter()

ORIGENES = ["referido", "instagram", "whatsapp", "correo", "web", "evento", "otro"]
CANALES = ["correo", "whatsapp", "instagram"]


def _renderizar_contactos(request: Request, sesion: Session, contactos: list[Contacto], **contexto_extra):
    servicios = sesion.exec(select(Servicio)).all()
    contexto = {
        "request": request,
        "contactos": contactos,
        "servicios": servicios,
        "etiqueta_seleccionada": "",
        "origen_seleccionado": "",
        "mensaje_sincronizacion": "",
        "origenes": ORIGENES,
        "etiquetas_usadas": sorted(
            {e for c in sesion.exec(select(Contacto)).all() for e in dividir_etiquetas(c.etiquetas)}
        ),
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
    consulta = select(Contacto).order_by(Contacto.creado_en.desc())
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
                    | (Contacto.usuario_instagram.ilike(texto))
                    | (Contacto.etiquetas.ilike(texto))
                    | (Contacto.notas.ilike(texto))
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
    correo: str = Form(""),
    telefono: str = Form(""),
    sesion: Session = Depends(obtener_sesion),
):
    """Alta rapida: nombre, canal y servicio de interes (correo y telefono
    opcionales). Crea el contacto y su primera oportunidad en la etapa Nuevo.
    Si el correo o el telefono ya existen, avisa en vez de duplicar."""
    correo = correo.strip().lower()
    telefono = telefono.strip()
    for campo, valor in (("correo", correo), ("telefono", telefono)):
        if not valor:
            continue
        existente = sesion.exec(select(Contacto).where(getattr(Contacto, campo) == valor)).first()
        if existente is not None:
            raise ErrorDeNegocio(
                f"Ya tienes a {existente.nombre} con ese {campo} ({valor}). "
                f"Abre su ficha en /contactos/{existente.id} y agrega ahí la oportunidad nueva."
            )

    contacto = Contacto(
        nombre=nombre.strip(),
        canal_preferido=canal_preferido or None,
        origen=origen,
        correo=correo or None,
        telefono=telefono or None,
    )
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
    return RedirectResponse(f"/contactos/{contacto.id}", status_code=303)


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


@enrutador.get("/contactos/exportar.csv")
def exportar_contactos_csv(sesion: Session = Depends(obtener_sesion)):
    """Descarga todos los contactos en un CSV que abre bien en Excel y Google Sheets."""
    empresas = {e.id: e.nombre for e in sesion.exec(select(Empresa)).all()}
    salida = io.StringIO()
    # El BOM hace que Excel reconozca los acentos (UTF-8) al abrir el archivo.
    salida.write("﻿")
    escritor = csv.writer(salida)
    escritor.writerow(
        ["id", "nombre", "correo", "telefono", "instagram", "canal_preferido", "origen",
         "empresa", "etiquetas", "puntuacion", "no_contactar", "notas", "creado_en"]
    )
    for c in sesion.exec(select(Contacto).order_by(Contacto.id)).all():
        escritor.writerow(
            [c.id, c.nombre, c.correo or "", c.telefono or "", c.usuario_instagram or "",
             c.canal_preferido or "", c.origen, empresas.get(c.empresa_id, ""), c.etiquetas or "",
             c.puntuacion, "si" if c.no_contactar else "no", c.notas or "", c.creado_en.isoformat()]
        )
    return StreamingResponse(
        iter([salida.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="contactos.csv"'},
    )


def _obtener_contacto(sesion: Session, contacto_id: int) -> Contacto:
    contacto = sesion.get(Contacto, contacto_id)
    if contacto is None:
        raise ErrorDeNegocio("Ese contacto no existe. Vuelve a /contactos y búscalo de nuevo.")
    return contacto


@enrutador.get("/contactos/{contacto_id}")
def ver_ficha_contacto(request: Request, contacto_id: int, sesion: Session = Depends(obtener_sesion)):
    contacto = _obtener_contacto(sesion, contacto_id)
    empresa = sesion.get(Empresa, contacto.empresa_id) if contacto.empresa_id else None
    referido_por = sesion.get(Contacto, contacto.referido_por_id) if contacto.referido_por_id else None

    oportunidades = sesion.exec(
        select(Oportunidad).where(Oportunidad.contacto_id == contacto.id).order_by(Oportunidad.creado_en.desc())
    ).all()
    ids_oportunidades = [o.id for o in oportunidades]
    servicios = {s.id: s for s in sesion.exec(select(Servicio)).all()}

    interacciones, tareas_pendientes = [], []
    if ids_oportunidades:
        interacciones = sesion.exec(
            select(Interaccion)
            .where(Interaccion.oportunidad_id.in_(ids_oportunidades))
            .order_by(Interaccion.fecha.desc())
        ).all()
        tareas_pendientes = sesion.exec(
            select(Tarea)
            .where(Tarea.oportunidad_id.in_(ids_oportunidades), Tarea.estado == "pendiente")
            .order_by(Tarea.fecha_limite)
        ).all()

    documentos = sesion.exec(
        select(Documento).where(Documento.contacto_id == contacto.id).order_by(Documento.creado_en.desc())
    ).all()
    historial = sesion.exec(
        select(Bitacora)
        .where(Bitacora.entidad == "Contacto", Bitacora.entidad_id == contacto.id)
        .order_by(Bitacora.fecha.desc())
        .limit(30)
    ).all()

    return plantillas.TemplateResponse(
        "contacto.html",
        {
            "request": request,
            "contacto": contacto,
            "empresa": empresa,
            "referido_por": referido_por,
            "oportunidades": oportunidades,
            "semaforos": {o.id: color_semaforo(o) for o in oportunidades},
            "servicios": servicios,
            "interacciones": interacciones,
            "tareas_pendientes": tareas_pendientes,
            "documentos": documentos,
            "historial": historial,
            "valor_ganado": sum(o.valor_estimado or 0 for o in oportunidades if o.etapa == "Ganado"),
            "origenes": ORIGENES,
            "canales": CANALES,
            "otros_contactos": sesion.exec(
                select(Contacto).where(Contacto.id != contacto.id).order_by(Contacto.nombre)
            ).all(),
            "ahora": hora_actual_utc(),
        },
    )


def _buscar_o_crear_empresa(sesion: Session, nombre: str) -> Optional[int]:
    nombre = nombre.strip()
    if not nombre:
        return None
    empresa = sesion.exec(select(Empresa).where(Empresa.nombre == nombre)).first()
    if empresa is None:
        empresa = Empresa(nombre=nombre)
        sesion.add(empresa)
        sesion.flush()
        registrar_cambio(sesion, "Empresa", empresa.id, "creado", None, nombre, "yo")
    return empresa.id


@enrutador.post("/contactos/{contacto_id}/editar")
def editar_contacto(
    contacto_id: int,
    nombre: str = Form(...),
    correo: str = Form(""),
    telefono: str = Form(""),
    usuario_instagram: str = Form(""),
    canal_preferido: str = Form(""),
    origen: str = Form("otro"),
    empresa: str = Form(""),
    referido_por_id: str = Form(""),
    etiquetas: str = Form(""),
    no_contactar: bool = Form(False),
    notas: str = Form(""),
    sesion: Session = Depends(obtener_sesion),
):
    contacto = _obtener_contacto(sesion, contacto_id)
    if not nombre.strip():
        raise ErrorDeNegocio("El contacto necesita un nombre.")

    correo = correo.strip().lower()
    if correo:
        repetido = sesion.exec(
            select(Contacto).where(Contacto.correo == correo, Contacto.id != contacto.id)
        ).first()
        if repetido is not None:
            raise ErrorDeNegocio(
                f"Ya tienes otro contacto con el correo {correo}: {repetido.nombre} (#{repetido.id}). "
                "Revisa si es la misma persona antes de guardarlo."
            )

    cambios = {
        "nombre": nombre.strip(),
        "correo": correo or None,
        "telefono": telefono.strip() or None,
        "usuario_instagram": usuario_instagram.strip().lstrip("@") or None,
        "canal_preferido": canal_preferido if canal_preferido in CANALES else None,
        "origen": origen if origen in ORIGENES else "otro",
        "empresa_id": _buscar_o_crear_empresa(sesion, empresa),
        "referido_por_id": int(referido_por_id) if referido_por_id.isdigit() else None,
        "etiquetas": unir_etiquetas(dividir_etiquetas(etiquetas.lower())) or None,
        "no_contactar": no_contactar,
        "notas": notas.strip() or None,
    }
    for campo, valor_nuevo in cambios.items():
        valor_anterior = getattr(contacto, campo)
        if valor_anterior != valor_nuevo:
            registrar_cambio(sesion, "Contacto", contacto.id, campo, valor_anterior, valor_nuevo, "yo")
            setattr(contacto, campo, valor_nuevo)

    contacto.modificado_en = hora_actual_utc()
    sesion.add(contacto)
    sesion.commit()
    return RedirectResponse(f"/contactos/{contacto.id}", status_code=303)


@enrutador.post("/contactos/{contacto_id}/nueva-oportunidad")
def crear_oportunidad_para_contacto(
    contacto_id: int,
    servicio_id: int = Form(...),
    valor_estimado: str = Form(""),
    sesion: Session = Depends(obtener_sesion),
):
    contacto = _obtener_contacto(sesion, contacto_id)
    servicio = sesion.get(Servicio, servicio_id)
    if servicio is None:
        raise ErrorDeNegocio("Elige un servicio válido para la oportunidad.")

    reglas = cargar_reglas_embudo()
    oportunidad = Oportunidad(
        contacto_id=contacto.id,
        servicio_id=servicio.id,
        etapa="Nuevo",
        probabilidad=reglas["probabilidad_inicial"]["Nuevo"],
        valor_estimado=convertir_monto(valor_estimado) or servicio.precio_base or None,
        moneda=servicio.moneda,
        origen=contacto.origen,
        ultima_actividad_en=hora_actual_utc(),
    )
    sesion.add(oportunidad)
    sesion.flush()
    registrar_cambio(sesion, "Oportunidad", oportunidad.id, "creado", None, servicio.nombre, "yo")
    emitir_evento(
        sesion,
        tipo="oportunidad.creada",
        clave_unica=f"oportunidad.creada:{oportunidad.id}",
        datos={"oportunidad_id": oportunidad.id, "contacto_id": contacto.id},
        origen="yo",
    )
    sesion.commit()
    return RedirectResponse(f"/oportunidades/{oportunidad.id}", status_code=303)
