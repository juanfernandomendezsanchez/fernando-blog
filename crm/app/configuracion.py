"""Carga la configuracion desde el archivo .env y ofrece la conversion de
fechas de UTC a la hora de Caracas (o la zona que elijas)."""

import os
from datetime import datetime
from pathlib import Path
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


def convertir_a_hora_local(fecha_utc: datetime) -> datetime:
    """Convierte una fecha guardada en UTC a la zona horaria configurada, para mostrarla."""
    if fecha_utc.tzinfo is None:
        fecha_utc = fecha_utc.replace(tzinfo=ZoneInfo("UTC"))
    return fecha_utc.astimezone(ZoneInfo(ZONA_HORARIA))
