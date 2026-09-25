"""Fixtures comunes: una base de datos SQLite en memoria por prueba, y
algunos contactos/servicios de ejemplo para no repetirlos en cada archivo."""

import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app import modelos  # noqa: F401  (registra las tablas en SQLModel.metadata)
from app.modelos import Contacto, Servicio


@pytest.fixture
def sesion():
    motor = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(motor)
    with Session(motor) as sesion_de_prueba:
        yield sesion_de_prueba


@pytest.fixture
def contacto(sesion):
    contacto = Contacto(nombre="Ana Perez", correo="ana@example.com", origen="referido")
    sesion.add(contacto)
    sesion.commit()
    sesion.refresh(contacto)
    return contacto


@pytest.fixture
def servicio_consultoria(sesion):
    servicio = Servicio(nombre="Consultoria de marca", linea="consultoria", precio_base=1500, moneda="USD")
    sesion.add(servicio)
    sesion.commit()
    sesion.refresh(servicio)
    return servicio


@pytest.fixture
def servicio_asesoria(sesion):
    servicio = Servicio(nombre="Asesoria puntual", linea="asesoria", precio_base=80, moneda="USD")
    sesion.add(servicio)
    sesion.commit()
    sesion.refresh(servicio)
    return servicio


@pytest.fixture
def servicio_venta(sesion):
    servicio = Servicio(nombre="Plantilla de marca", linea="venta", precio_base=20, moneda="USD")
    sesion.add(servicio)
    sesion.commit()
    sesion.refresh(servicio)
    return servicio
