"""Reglas del embudo de ventas.

Las reglas en si (etapas, saltos permitidos, dias maximos, probabilidades,
requisitos y atajos por linea) viven en reglas/embudo.yaml, no aqui. Este
archivo solo sabe leer ese YAML y aplicarlo.
"""

from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml
from sqlmodel import Session, select

from app.bitacora import registrar_cambio
from app.errores import ErrorDeNegocio
from app.eventos import emitir_evento
from app.modelos import Oportunidad, Propuesta, Servicio, hora_actual_utc

CARPETA_REGLAS = Path(__file__).resolve().parent.parent / "reglas"


@lru_cache
def cargar_reglas_embudo() -> dict:
    with open(CARPETA_REGLAS / "embudo.yaml", encoding="utf-8") as archivo:
        return yaml.safe_load(archivo)


def obtener_linea_del_servicio(sesion: Session, oportunidad: Oportunidad) -> str:
    servicio = sesion.get(Servicio, oportunidad.servicio_id)
    if servicio is None:
        raise ErrorDeNegocio(
            "Esta oportunidad no tiene un servicio valido asociado. "
            "Revisa el servicio_id antes de mover la etapa."
        )
    return servicio.linea


def etapas_permitidas_desde(etapa_actual: str, linea: str) -> list[str]:
    """Devuelve a que etapas se puede mover una oportunidad, combinando los
    saltos normales del embudo con los atajos de su linea de servicio."""
    reglas = cargar_reglas_embudo()
    permitidas = list(reglas["saltos_permitidos"].get(etapa_actual, []))

    atajos = reglas.get("atajos_por_linea", {}).get(linea, {})
    saltos_extra = atajos.get("saltos_extra", {}).get(etapa_actual, [])
    for etapa in saltos_extra:
        if etapa not in permitidas:
            permitidas.append(etapa)

    return permitidas


def _validar_requisitos_propuesta(sesion: Session, oportunidad: Oportunidad) -> None:
    faltantes = []
    if oportunidad.valor_estimado is None:
        faltantes.append("el valor estimado")
    if oportunidad.fecha_cierre_esperada is None:
        faltantes.append("la fecha de cierre esperada")

    tiene_alcance = sesion.exec(
        select(Propuesta).where(
            Propuesta.oportunidad_id == oportunidad.id,
            Propuesta.alcance.is_not(None),
            Propuesta.alcance != "",
        )
    ).first()
    if tiene_alcance is None:
        faltantes.append("una propuesta con el alcance descrito")

    if faltantes:
        raise ErrorDeNegocio(
            "Para pasar esta oportunidad a Propuesta primero completa: "
            + ", ".join(faltantes)
            + "."
        )


def _validar_requisitos_ganado(
    sesion: Session, oportunidad: Oportunidad, pago_recibido: bool
) -> None:
    propuesta_aceptada_con_documento = sesion.exec(
        select(Propuesta).where(
            Propuesta.oportunidad_id == oportunidad.id,
            Propuesta.estado == "aceptada",
            Propuesta.documento_adjunto_url.is_not(None),
        )
    ).first()

    if not pago_recibido and propuesta_aceptada_con_documento is None:
        raise ErrorDeNegocio(
            "Para marcar esta oportunidad como Ganada necesitas un pago recibido "
            "o una propuesta aceptada con su documento adjunto. Registra uno de "
            "los dos antes de continuar."
        )


def _validar_motivo_perdida(motivo_perdida: Optional[str]) -> None:
    reglas = cargar_reglas_embudo()
    motivos_validos = reglas["motivos_perdida_validos"]
    if motivo_perdida not in motivos_validos:
        raise ErrorDeNegocio(
            "Para marcar esta oportunidad como Perdida elige un motivo de esta "
            f"lista: {', '.join(motivos_validos)}."
        )


def mover_etapa(
    sesion: Session,
    oportunidad: Oportunidad,
    etapa_nueva: str,
    motivo_perdida: Optional[str] = None,
    pago_recibido: bool = False,
    origen: str = "yo",
) -> Oportunidad:
    """Mueve una oportunidad a una etapa nueva, validando el salto y los
    requisitos de esa etapa. Guarda el cambio en la Bitacora y emite el
    evento oportunidad.cambio_etapa.

    Es idempotente: si la oportunidad ya esta en etapa_nueva, no hace nada
    y la devuelve tal cual (asi procesar el mismo pedido dos veces no
    duplica bitacora ni eventos).
    """
    etapa_actual = oportunidad.etapa

    if etapa_actual == etapa_nueva:
        return oportunidad

    reglas = cargar_reglas_embudo()
    if etapa_nueva not in reglas["etapas"]:
        raise ErrorDeNegocio(f"'{etapa_nueva}' no es una etapa valida del embudo.")

    linea = obtener_linea_del_servicio(sesion, oportunidad)
    permitidas = etapas_permitidas_desde(etapa_actual, linea)
    if etapa_nueva not in permitidas:
        raise ErrorDeNegocio(
            f"No puedes mover esta oportunidad de {etapa_actual} a {etapa_nueva}. "
            f"Desde {etapa_actual} solo puedes pasar a: {', '.join(permitidas) or 'ninguna etapa'}."
        )

    if etapa_nueva == "Propuesta":
        _validar_requisitos_propuesta(sesion, oportunidad)
    if etapa_nueva == "Ganado":
        _validar_requisitos_ganado(sesion, oportunidad, pago_recibido)
    if etapa_nueva == "Perdido":
        _validar_motivo_perdida(motivo_perdida)

    ahora = hora_actual_utc()
    registrar_cambio(sesion, "Oportunidad", oportunidad.id, "etapa", etapa_actual, etapa_nueva, origen)

    oportunidad.etapa = etapa_nueva
    oportunidad.probabilidad = reglas["probabilidad_inicial"].get(etapa_nueva, oportunidad.probabilidad)
    oportunidad.ultima_actividad_en = ahora
    oportunidad.en_riesgo = False
    oportunidad.motivo_perdida = motivo_perdida if etapa_nueva == "Perdido" else None
    oportunidad.modificado_en = ahora

    sesion.add(oportunidad)
    sesion.flush()

    emitir_evento(
        sesion,
        tipo="oportunidad.cambio_etapa",
        clave_unica=f"oportunidad.cambio_etapa:{oportunidad.id}:{etapa_actual}:{etapa_nueva}:{ahora.isoformat()}",
        datos={"oportunidad_id": oportunidad.id, "etapa_anterior": etapa_actual, "etapa_nueva": etapa_nueva},
        origen=origen,
    )

    sesion.commit()
    sesion.refresh(oportunidad)
    return oportunidad


def dias_sin_movimiento(oportunidad: Oportunidad, ahora: Optional[datetime] = None) -> int:
    ahora = ahora or hora_actual_utc()
    return (ahora - oportunidad.ultima_actividad_en).days


def esta_en_riesgo(oportunidad: Oportunidad, ahora: Optional[datetime] = None) -> bool:
    """Una oportunidad esta en riesgo si paso el limite de dias sin
    movimiento de su etapa actual. Las etapas sin limite (Ganado, Perdido,
    Descartado) nunca estan en riesgo."""
    reglas = cargar_reglas_embudo()
    limite = reglas["dias_maximos_sin_movimiento"].get(oportunidad.etapa)
    if limite is None:
        return False
    return dias_sin_movimiento(oportunidad, ahora) > limite


def color_semaforo(oportunidad: Oportunidad, ahora: Optional[datetime] = None) -> Optional[str]:
    """verde/ambar/rojo segun cuanto falta para el limite de dias sin
    movimiento. None si la etapa no tiene limite (Ganado, Perdido, Descartado)."""
    reglas = cargar_reglas_embudo()
    limite = reglas["dias_maximos_sin_movimiento"].get(oportunidad.etapa)
    if limite is None:
        return None

    dias = dias_sin_movimiento(oportunidad, ahora)
    if dias > limite:
        return "rojo"
    if dias > limite / 2:
        return "ambar"
    return "verde"
