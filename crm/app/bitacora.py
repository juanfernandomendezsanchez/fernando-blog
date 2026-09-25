"""Registro de cambios: la regla 4 del negocio dice que todo cambio de datos
deja una fila en Bitacora (que cambio, cuando, y origen: yo, regla o sincronizacion).
"""

from typing import Optional

from sqlmodel import Session

from app.modelos import Bitacora


def registrar_cambio(
    sesion: Session,
    entidad: str,
    entidad_id: int,
    campo: str,
    valor_anterior,
    valor_nuevo,
    origen: str = "yo",
) -> Bitacora:
    """Guarda una fila en la Bitacora. No hace commit: queda dentro de la
    misma transaccion que el cambio que la origino, para que ambos se guarden
    juntos o ninguno se guarde."""
    fila = Bitacora(
        entidad=entidad,
        entidad_id=entidad_id,
        campo=campo,
        valor_anterior=None if valor_anterior is None else str(valor_anterior),
        valor_nuevo=None if valor_nuevo is None else str(valor_nuevo),
        origen=origen,
    )
    sesion.add(fila)
    return fila
