"""Instancia compartida de Jinja2Templates, con filtros para mostrar fechas
guardadas en UTC en la hora de Caracas (o la zona configurada), montos y
tamanos de archivo. Tambien trae ruta_de_regreso(...), que usan los
formularios que se envian desde varias pantallas."""

from pathlib import Path
from typing import Optional

from fastapi.templating import Jinja2Templates

from app.configuracion import convertir_a_hora_local
from app.errores import ErrorDeNegocio

CARPETA_APP = Path(__file__).resolve().parent
plantillas = Jinja2Templates(directory=str(CARPETA_APP / "plantillas"))


def _formatear_fecha_local(fecha_utc, formato: str = "%d/%m/%Y %H:%M") -> str:
    if fecha_utc is None:
        return ""
    return convertir_a_hora_local(fecha_utc).strftime(formato)


def _formatear_dinero(monto) -> str:
    """1234.5 -> "1,234.50". Vacio si no hay monto."""
    if monto is None:
        return ""
    return f"{monto:,.2f}"


def _formatear_tamano(tamano_bytes) -> str:
    if not tamano_bytes:
        return ""
    for unidad in ["B", "KB", "MB"]:
        if tamano_bytes < 1024:
            return f"{tamano_bytes:.0f} {unidad}" if unidad == "B" else f"{tamano_bytes:.1f} {unidad}"
        tamano_bytes /= 1024
    return f"{tamano_bytes:.1f} GB"


plantillas.env.filters["hora_local"] = _formatear_fecha_local
plantillas.env.filters["dinero"] = _formatear_dinero
plantillas.env.filters["tamano"] = _formatear_tamano


def convertir_monto(texto: str) -> Optional[float]:
    """Lee un monto escrito en un formulario ("1500", "1,500.50", "1500,5").
    Devuelve None si viene vacio; lanza ErrorDeNegocio si no es un numero."""
    texto = (texto or "").strip().replace(" ", "").replace("$", "")
    if not texto:
        return None
    if "," in texto and "." in texto:
        texto = texto.replace(",", "")
    else:
        texto = texto.replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        raise ErrorDeNegocio(f"'{texto}' no es un monto valido. Escribe solo el numero, por ejemplo 1500.")


def ruta_de_regreso(volver: str, por_defecto: str) -> str:
    """Devuelve a donde redirigir despues de un formulario. Solo acepta rutas
    internas del CRM ("/contactos/3"), nunca una direccion externa."""
    if volver and volver.startswith("/") and not volver.startswith("//"):
        return volver
    return por_defecto
