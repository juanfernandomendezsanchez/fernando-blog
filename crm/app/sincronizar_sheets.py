"""Sincronizacion de contactos desde Google Sheets.

Cada vez que se corre, lee la pestaña de leads y por cada fila busca si ya
existe un Contacto (por correo, y si no hay correo, por telefono). Si no
existe, lo crea. Si existe, actualiza lo que cambio. Nunca duplica: es la
misma regla de idempotencia que ya usan mover_etapa() y calcular_puntuacion().

Esta version solo sincroniza Contactos, a proposito no crea Oportunidades:
adivinar a que servicio corresponde el texto libre de "Necesidad" podria
crear datos incorrectos. Eso lo decide Fernando desde la interfaz.
"""

from typing import Optional

import gspread
from sqlmodel import Session, select

from app.bitacora import registrar_cambio
from app.configuracion import (
    CREDENCIALES_GOOGLE_SHEETS,
    ID_HOJA_GOOGLE_SHEETS,
    PESTANA_LEADS_GOOGLE_SHEETS,
)
from app.eventos import emitir_evento
from app.modelos import Contacto


def cargar_cliente_sheets() -> gspread.Client:
    if not CREDENCIALES_GOOGLE_SHEETS:
        raise RuntimeError(
            "No configuraste GOOGLE_CREDENCIALES_JSON en tu .env. "
            "Sin eso no se puede conectar a Google Sheets."
        )
    return gspread.service_account(filename=CREDENCIALES_GOOGLE_SHEETS)


def leer_filas_de_leads(cliente: gspread.Client) -> list[dict]:
    if not ID_HOJA_GOOGLE_SHEETS:
        raise RuntimeError("No configuraste GOOGLE_SHEETS_ID en tu .env.")

    hoja = cliente.open_by_key(ID_HOJA_GOOGLE_SHEETS)
    pestana = hoja.worksheet(PESTANA_LEADS_GOOGLE_SHEETS)
    return pestana.get_all_records()


def construir_notas_desde_fila(fila: dict) -> str:
    """Junta en un solo texto legible todo lo que la fila trae y que no
    tiene un campo propio en Contacto, para no perder nada."""
    lineas = []
    etiquetas_por_columna = [
        ("Fecha", "Fecha del formulario"),
        ("Empresa", "Empresa"),
        ("Necesidad", "Necesidad"),
        ("Descripcion", "Descripcion"),
        ("Descripción", "Descripcion"),
        ("Mensaje", "Mensaje"),
        ("Estado", "Estado en la hoja"),
    ]
    vistas = set()
    for columna, etiqueta in etiquetas_por_columna:
        if etiqueta in vistas:
            continue
        valor = str(fila.get(columna, "")).strip()
        if valor:
            lineas.append(f"{etiqueta}: {valor}")
            vistas.add(etiqueta)
    return "\n".join(lineas)


def _buscar_contacto_existente(sesion: Session, correo: str, telefono: str) -> Optional[Contacto]:
    if correo:
        contacto = sesion.exec(select(Contacto).where(Contacto.correo == correo)).first()
        if contacto is not None:
            return contacto
    if telefono:
        return sesion.exec(select(Contacto).where(Contacto.telefono == telefono)).first()
    return None


def sincronizar_contacto_desde_fila(
    sesion: Session, fila: dict, origen: str = "web"
) -> tuple[Optional[Contacto], str]:
    """Crea o actualiza un Contacto a partir de una fila de la hoja.

    Devuelve (contacto, resultado), donde resultado es "creado",
    "actualizado" u "omitido" (fila sin correo ni telefono: no hay forma
    segura de identificarla sin arriesgar un duplicado)."""
    nombre = str(fila.get("Nombre", "")).strip()
    correo = str(fila.get("Email", "")).strip()
    telefono = str(fila.get("Telefono", fila.get("Teléfono", ""))).strip()
    notas_nuevas = construir_notas_desde_fila(fila)

    if not correo and not telefono:
        return None, "omitido"

    contacto_existente = _buscar_contacto_existente(sesion, correo, telefono)

    if contacto_existente is None:
        contacto = Contacto(
            nombre=nombre or "Sin nombre",
            correo=correo or None,
            telefono=telefono or None,
            origen=origen,
            notas=notas_nuevas or None,
        )
        sesion.add(contacto)
        sesion.flush()

        registrar_cambio(sesion, "Contacto", contacto.id, "creado", None, nombre, "sincronizacion")
        emitir_evento(
            sesion,
            tipo="contacto.creado",
            clave_unica=f"contacto.creado:sheets:{correo or telefono}",
            datos={"contacto_id": contacto.id, "origen": "google_sheets"},
            origen="sincronizacion",
        )
        sesion.commit()
        sesion.refresh(contacto)
        return contacto, "creado"

    hubo_cambio = False
    if nombre and contacto_existente.nombre != nombre:
        registrar_cambio(
            sesion, "Contacto", contacto_existente.id, "nombre",
            contacto_existente.nombre, nombre, "sincronizacion",
        )
        contacto_existente.nombre = nombre
        hubo_cambio = True

    if notas_nuevas and contacto_existente.notas != notas_nuevas:
        registrar_cambio(
            sesion, "Contacto", contacto_existente.id, "notas",
            contacto_existente.notas, notas_nuevas, "sincronizacion",
        )
        contacto_existente.notas = notas_nuevas
        hubo_cambio = True

    if hubo_cambio:
        sesion.add(contacto_existente)
        sesion.commit()
        sesion.refresh(contacto_existente)

    return contacto_existente, "actualizado"


def sincronizar_leads_desde_sheets(sesion: Session) -> dict:
    """Orquesta todo: conecta, lee la hoja y sincroniza cada fila.
    Si Google Sheets no esta configurado todavia, no falla: devuelve un
    resumen que lo dice."""
    if not CREDENCIALES_GOOGLE_SHEETS or not ID_HOJA_GOOGLE_SHEETS:
        return {"configurado": False, "creados": 0, "actualizados": 0, "omitidos": 0}

    cliente = cargar_cliente_sheets()
    filas = leer_filas_de_leads(cliente)

    resumen = {"configurado": True, "creados": 0, "actualizados": 0, "omitidos": 0}
    for fila in filas:
        _contacto, resultado = sincronizar_contacto_desde_fila(sesion, fila)
        if resultado == "creado":
            resumen["creados"] += 1
        elif resultado == "actualizado":
            resumen["actualizados"] += 1
        else:
            resumen["omitidos"] += 1

    return resumen
