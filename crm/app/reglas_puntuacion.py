"""Reglas de puntuacion de contactos.

Los puntos y el umbral viven en reglas/puntuacion.yaml, no aqui.
"""

from functools import lru_cache
from pathlib import Path

import yaml
from sqlmodel import Session

from app.bitacora import registrar_cambio
from app.modelos import Contacto, dividir_etiquetas, unir_etiquetas

CARPETA_REGLAS = Path(__file__).resolve().parent.parent / "reglas"


@lru_cache
def cargar_reglas_puntuacion() -> dict:
    with open(CARPETA_REGLAS / "puntuacion.yaml", encoding="utf-8") as archivo:
        return yaml.safe_load(archivo)


def calcular_puntuacion(senales: dict[str, bool]) -> int:
    """Suma los puntos de cada senal presente y verdadera en 'senales'.
    Las senales posibles son las claves de reglas/puntuacion.yaml -> puntos.
    El resultado queda entre puntuacion_minima y puntuacion_maxima."""
    reglas = cargar_reglas_puntuacion()
    puntos_por_senal = reglas["puntos"]

    total = 0
    for senal, es_verdadera in senales.items():
        if es_verdadera and senal in puntos_por_senal:
            total += puntos_por_senal[senal]

    minimo = reglas["puntuacion_minima"]
    maximo = reglas["puntuacion_maxima"]
    return max(minimo, min(maximo, total))


def debe_pasar_a_calificado(puntuacion: int) -> bool:
    reglas = cargar_reglas_puntuacion()
    return puntuacion >= reglas["umbral_calificado"]


def actualizar_puntuacion_contacto(
    sesion: Session, contacto: Contacto, senales: dict[str, bool], origen: str = "regla"
) -> Contacto:
    """Recalcula la puntuacion del contacto a partir de las senales dadas,
    guarda el cambio en la Bitacora y, si queda por debajo del umbral, le
    agrega la etiqueta de nutricion (sin duplicarla si ya la tiene)."""
    reglas = cargar_reglas_puntuacion()
    puntuacion_nueva = calcular_puntuacion(senales)

    if puntuacion_nueva != contacto.puntuacion:
        registrar_cambio(
            sesion, "Contacto", contacto.id, "puntuacion", contacto.puntuacion, puntuacion_nueva, origen
        )
        contacto.puntuacion = puntuacion_nueva

    if not debe_pasar_a_calificado(puntuacion_nueva):
        etiquetas = dividir_etiquetas(contacto.etiquetas)
        etiqueta_nutricion = reglas["etiqueta_nutricion"]
        if etiqueta_nutricion not in etiquetas:
            etiquetas.append(etiqueta_nutricion)
            contacto.etiquetas = unir_etiquetas(etiquetas)

    sesion.add(contacto)
    sesion.commit()
    sesion.refresh(contacto)
    return contacto
