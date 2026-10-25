"""Ruta /respaldo.zip: descarga en un solo archivo la base de datos y todos
los documentos de la Biblioteca. Guardalo en Drive o en un disco externo de
vez en cuando; para restaurar, descomprime crm.db en crm/datos/ y la carpeta
biblioteca/ en crm/datos/biblioteca/.
"""

import sqlite3
import tempfile
import zipfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import FileResponse

from app import configuracion
from app.base_datos import motor
from app.errores import ErrorDeNegocio
from app.modelos import hora_actual_utc

enrutador = APIRouter()


@enrutador.get("/respaldo.zip")
def descargar_respaldo(tareas_de_fondo: BackgroundTasks):
    ruta_base_datos = motor.url.database
    if motor.url.get_backend_name() != "sqlite" or not ruta_base_datos:
        raise ErrorDeNegocio(
            "El respaldo desde el navegador solo funciona con SQLite. "
            "Con PostgreSQL usa pg_dump en el servidor."
        )

    carpeta_temporal = Path(tempfile.mkdtemp(prefix="respaldo_crm_"))
    copia_base_datos = carpeta_temporal / "crm.db"
    # La API de backup de SQLite copia la base de forma consistente aunque el
    # servidor este escribiendo en ese momento (un simple copy podria no serlo).
    origen = sqlite3.connect(ruta_base_datos)
    destino = sqlite3.connect(copia_base_datos)
    try:
        origen.backup(destino)
    finally:
        # Cerrar explicitamente: en Windows un archivo abierto no se puede borrar.
        destino.close()
        origen.close()

    fecha = configuracion.convertir_a_hora_local(hora_actual_utc()).strftime("%Y-%m-%d_%H%M")
    ruta_zip = carpeta_temporal / f"respaldo_crm_{fecha}.zip"
    with zipfile.ZipFile(ruta_zip, "w", zipfile.ZIP_DEFLATED) as archivo_zip:
        archivo_zip.write(copia_base_datos, "crm.db")
        carpeta_biblioteca = configuracion.CARPETA_BIBLIOTECA
        if carpeta_biblioteca.exists():
            for archivo in carpeta_biblioteca.iterdir():
                if archivo.is_file():
                    archivo_zip.write(archivo, f"biblioteca/{archivo.name}")

    def borrar_temporales():
        for archivo in carpeta_temporal.iterdir():
            archivo.unlink(missing_ok=True)
        carpeta_temporal.rmdir()

    tareas_de_fondo.add_task(borrar_temporales)
    return FileResponse(ruta_zip, media_type="application/zip", filename=ruta_zip.name)
