"""Errores de negocio: se muestran en español y dicen que hacer (regla 7)."""


class ErrorDeNegocio(Exception):
    """Se lanza cuando una accion no cumple una regla del negocio.
    El mensaje debe explicar, en español, que paso y que hacer para corregirlo."""
