"""Conexion a la base de datos y utilidades para crear las tablas."""

from sqlmodel import Session, SQLModel, create_engine

from app.configuracion import BASE_DATOS_URL

argumentos_conexion = {}
if BASE_DATOS_URL.startswith("sqlite"):
    # Necesario porque FastAPI puede usar la conexion desde otro hilo.
    argumentos_conexion = {"check_same_thread": False}

motor = create_engine(BASE_DATOS_URL, connect_args=argumentos_conexion)


def crear_tablas() -> None:
    # Importa los modelos aqui para que SQLModel los conozca antes de crear las tablas.
    from app import modelos  # noqa: F401

    SQLModel.metadata.create_all(motor)


def obtener_sesion():
    """Dependencia de FastAPI: entrega una sesion y la cierra al terminar la peticion."""
    with Session(motor) as sesion:
        yield sesion
