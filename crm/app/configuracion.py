"""Carga la configuracion desde el archivo .env y ofrece la conversion de
fechas de UTC a la hora de Caracas (o la zona que elijas)."""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

CARPETA_CRM = Path(__file__).resolve().parent.parent
load_dotenv(CARPETA_CRM / ".env")


def obtener_variable(nombre: str, valor_por_defecto: str = "") -> str:
    return os.environ.get(nombre, valor_por_defecto)


CONTRASENA = obtener_variable("CRM_CONTRASENA", "cambia-esta-contrasena")
CLAVE_SECRETA = obtener_variable("CRM_CLAVE_SECRETA", "cambia-esta-clave-secreta")
ZONA_HORARIA = obtener_variable("CRM_ZONA_HORARIA", "America/Caracas")
BASE_DATOS_URL = obtener_variable(
    "CRM_BASE_DATOS_URL", f"sqlite:///{CARPETA_CRM / 'datos' / 'crm.db'}"
)
META_MENSUAL_USD = float(obtener_variable("CRM_META_MENSUAL_USD", "0") or "0")

# Sincronizacion con Google Sheets (Fase 2). Si CREDENCIALES_GOOGLE_SHEETS
# queda vacio, la sincronizacion simplemente se salta (ver sincronizar_sheets.py).
CREDENCIALES_GOOGLE_SHEETS = obtener_variable("GOOGLE_CREDENCIALES_JSON", "")
ID_HOJA_GOOGLE_SHEETS = obtener_variable("GOOGLE_SHEETS_ID", "")
PESTANA_LEADS_GOOGLE_SHEETS = obtener_variable("GOOGLE_SHEETS_PESTANA_LEADS", "leads")


# Biblioteca: carpeta donde se guardan los documentos que subes. Vive dentro
# de datos/ para que nunca se suba al repositorio (ver .gitignore).
CARPETA_BIBLIOTECA = Path(
    obtener_variable("CRM_CARPETA_BIBLIOTECA") or str(CARPETA_CRM / "datos" / "biblioteca")
)
TAMANO_MAXIMO_DOCUMENTO_MB = int(obtener_variable("CRM_TAMANO_MAXIMO_DOCUMENTO_MB", "50") or "50")


def convertir_a_hora_local(fecha_utc: datetime) -> datetime:
    """Convierte una fecha guardada en UTC a la zona horaria configurada, para mostrarla."""
    if fecha_utc.tzinfo is None:
        fecha_utc = fecha_utc.replace(tzinfo=ZoneInfo("UTC"))
    return fecha_utc.astimezone(ZoneInfo(ZONA_HORARIA))


def convertir_fecha_local_a_utc(texto_fecha: str, hora: str = "12:00") -> Optional[datetime]:
    """Convierte la fecha de un formulario ("2026-09-30", en hora local) a un
    datetime en UTC sin zona, que es como se guarda en la base de datos.
    Devuelve None si el texto viene vacio."""
    if not texto_fecha:
        return None
    local = datetime.fromisoformat(f"{texto_fecha}T{hora}").replace(tzinfo=ZoneInfo(ZONA_HORARIA))
    return local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
