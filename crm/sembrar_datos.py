"""Carga los servicios de ejemplo desde reglas/servicios.yaml a la base de datos.

Es idempotente: si un servicio con ese nombre ya existe, no lo duplica.
Uso (desde la carpeta crm/, con el entorno virtual activado):

    python sembrar_datos.py
"""

from pathlib import Path

import yaml
from sqlmodel import Session, select

from app.base_datos import crear_tablas, motor
from app.modelos import Servicio

CARPETA_CRM = Path(__file__).resolve().parent


def sembrar_servicios(sesion: Session) -> None:
    with open(CARPETA_CRM / "reglas" / "servicios.yaml", encoding="utf-8") as archivo:
        datos = yaml.safe_load(archivo)

    for datos_servicio in datos["servicios"]:
        servicio_existente = sesion.exec(
            select(Servicio).where(Servicio.nombre == datos_servicio["nombre"])
        ).first()
        if servicio_existente is not None:
            print(f"Ya existe: {datos_servicio['nombre']} (no se duplica)")
            continue

        sesion.add(Servicio(**datos_servicio))
        print(f"Creado: {datos_servicio['nombre']}")

    sesion.commit()


if __name__ == "__main__":
    crear_tablas()
    with Session(motor) as sesion:
        sembrar_servicios(sesion)
