"""Punto de entrada de la aplicacion. Para correrla localmente:

    uvicorn app.main:app --reload

(desde la carpeta crm/, con el entorno virtual activado).
"""

from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.autenticacion import NoAutenticado, requerir_autenticacion
from app.autenticacion import enrutador as enrutador_autenticacion
from app.base_datos import crear_tablas
from app.configuracion import CLAVE_SECRETA
from app.errores import ErrorDeNegocio
from app.rutas.contactos import enrutador as enrutador_contactos
from app.rutas.embudo import enrutador as enrutador_embudo
from app.rutas.hoy import enrutador as enrutador_hoy

CARPETA_APP = Path(__file__).resolve().parent

app = FastAPI(title="CRM de Fernando")
app.add_middleware(SessionMiddleware, secret_key=CLAVE_SECRETA)
app.mount("/estaticos", StaticFiles(directory=str(CARPETA_APP / "estaticos")), name="estaticos")


@app.exception_handler(NoAutenticado)
def redirigir_a_login(request: Request, excepcion: NoAutenticado):
    return RedirectResponse("/login", status_code=303)


@app.exception_handler(ErrorDeNegocio)
def mostrar_error_de_negocio(request: Request, excepcion: ErrorDeNegocio):
    # Fase 1: un mensaje de texto simple en español, explicando que corregir.
    # En una fase futura esto puede mostrarse como una notificacion en pantalla.
    return PlainTextResponse(str(excepcion), status_code=400)


@app.on_event("startup")
def al_iniciar() -> None:
    crear_tablas()


app.include_router(enrutador_autenticacion)
app.include_router(enrutador_hoy, dependencies=[Depends(requerir_autenticacion)])
app.include_router(enrutador_embudo, dependencies=[Depends(requerir_autenticacion)])
app.include_router(enrutador_contactos, dependencies=[Depends(requerir_autenticacion)])


@app.get("/")
def raiz():
    return RedirectResponse("/hoy")
