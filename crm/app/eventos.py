"""Emision de eventos para el futuro motor de automatizaciones (Fase 2).

Cada evento tiene una clave_unica: si el mismo hecho llega dos veces (por
ejemplo, un correo que se vuelve a sincronizar), no se crea un evento
duplicado. Esto es lo que exige la regla 6 del negocio (idempotencia).
"""

import json
from typing import Optional

from sqlmodel import Session, select

from app.modelos import Evento


def emitir_evento(
    sesion: Session,
    tipo: str,
    clave_unica: str,
    datos: Optional[dict] = None,
    origen: str = "sincronizacion",
) -> Evento:
    """Crea el evento si no existe todavia uno con la misma clave_unica.
    Si ya existe, simplemente lo devuelve sin crear otro (idempotente)."""
    evento_existente = sesion.exec(
        select(Evento).where(Evento.clave_unica == clave_unica)
    ).first()
    if evento_existente is not None:
        return evento_existente

    evento = Evento(
        tipo=tipo,
        clave_unica=clave_unica,
        datos=json.dumps(datos or {}, ensure_ascii=False),
        origen=origen,
    )
    sesion.add(evento)
    sesion.flush()
    return evento
