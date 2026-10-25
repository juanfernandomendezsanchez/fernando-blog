"""Autenticacion de un solo usuario (Fernando), protegida por contraseña.

No hay tabla de usuarios ni permisos: solo la contraseña que pones en .env.
"""

import hmac

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app.configuracion import CONTRASENA
from app.plantillas_util import plantillas

enrutador = APIRouter()


class NoAutenticado(Exception):
    """Se lanza cuando se visita una ruta protegida sin haber iniciado sesion."""


def requerir_autenticacion(request: Request) -> None:
    if not request.session.get("autenticado"):
        raise NoAutenticado()


@enrutador.get("/login")
def mostrar_login(request: Request):
    return plantillas.TemplateResponse("login.html", {"request": request, "error": None})


@enrutador.post("/login")
def procesar_login(request: Request, contrasena: str = Form(...)):
    if hmac.compare_digest(contrasena, CONTRASENA):
        request.session["autenticado"] = True
        return RedirectResponse("/hoy", status_code=303)
    return plantillas.TemplateResponse(
        "login.html",
        {"request": request, "error": "Contraseña incorrecta."},
        status_code=401,
    )


@enrutador.get("/logout")
def cerrar_sesion(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
