"""Instancia compartida de Jinja2Templates, con un filtro para mostrar
fechas guardadas en UTC en la hora de Caracas (o la zona configurada)."""

from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.configuracion import convertir_a_hora_local

CARPETA_APP = Path(__file__).resolve().parent
plantillas = Jinja2Templates(directory=str(CARPETA_APP / "plantillas"))


def _formatear_fecha_local(fecha_utc, formato: str = "%d/%m/%Y %H:%M") -> str:
    if fecha_utc is None:
        return ""
    return convertir_a_hora_local(fecha_utc).strftime(formato)


plantillas.env.filters["hora_local"] = _formatear_fecha_local
