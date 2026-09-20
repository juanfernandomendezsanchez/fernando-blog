"""Pruebas de las reglas del embudo, con ejemplos realistas de los tres
tipos de servicio: consultoria (ciclo largo), asesoria (salta la propuesta)
y venta de producto (un solo paso)."""

from datetime import timedelta

import pytest

from app.errores import ErrorDeNegocio
from app.modelos import Oportunidad, Propuesta, hora_actual_utc
from app.reglas_embudo import color_semaforo, esta_en_riesgo, mover_etapa


def _crear_oportunidad(sesion, contacto, servicio, etapa="Nuevo", **campos):
    campos.setdefault("ultima_actividad_en", hora_actual_utc())
    oportunidad = Oportunidad(
        contacto_id=contacto.id,
        servicio_id=servicio.id,
        etapa=etapa,
        origen=contacto.origen,
        **campos,
    )
    sesion.add(oportunidad)
    sesion.commit()
    sesion.refresh(oportunidad)
    return oportunidad


def test_no_se_puede_saltar_de_nuevo_a_propuesta(sesion, contacto, servicio_consultoria):
    oportunidad = _crear_oportunidad(sesion, contacto, servicio_consultoria)

    with pytest.raises(ErrorDeNegocio):
        mover_etapa(sesion, oportunidad, "Propuesta")


def test_entrar_a_propuesta_exige_valor_alcance_y_fecha(sesion, contacto, servicio_consultoria):
    oportunidad = _crear_oportunidad(sesion, contacto, servicio_consultoria)
    mover_etapa(sesion, oportunidad, "Calificado")
    mover_etapa(sesion, oportunidad, "Diagnostico")

    with pytest.raises(ErrorDeNegocio):
        mover_etapa(sesion, oportunidad, "Propuesta")

    oportunidad.valor_estimado = 1500
    oportunidad.fecha_cierre_esperada = hora_actual_utc() + timedelta(days=30)
    sesion.add(oportunidad)
    sesion.commit()

    sesion.add(
        Propuesta(oportunidad_id=oportunidad.id, monto=1500, moneda="USD", alcance="Diagnostico + brand book")
    )
    sesion.commit()

    oportunidad = mover_etapa(sesion, oportunidad, "Propuesta")
    assert oportunidad.etapa == "Propuesta"
    assert oportunidad.probabilidad == 50


def test_ganado_exige_pago_o_propuesta_aceptada_con_documento(sesion, contacto, servicio_consultoria):
    oportunidad = _crear_oportunidad(
        sesion,
        contacto,
        servicio_consultoria,
        etapa="Propuesta",
        valor_estimado=1500,
        fecha_cierre_esperada=hora_actual_utc() + timedelta(days=10),
    )

    with pytest.raises(ErrorDeNegocio):
        mover_etapa(sesion, oportunidad, "Ganado")

    oportunidad = mover_etapa(sesion, oportunidad, "Ganado", pago_recibido=True)
    assert oportunidad.etapa == "Ganado"
    assert oportunidad.probabilidad == 100


def test_perdido_exige_un_motivo_de_la_lista_cerrada(sesion, contacto, servicio_consultoria):
    oportunidad = _crear_oportunidad(sesion, contacto, servicio_consultoria, etapa="Diagnostico")

    with pytest.raises(ErrorDeNegocio):
        mover_etapa(sesion, oportunidad, "Perdido", motivo_perdida="no me gusto")

    oportunidad = mover_etapa(sesion, oportunidad, "Perdido", motivo_perdida="precio")
    assert oportunidad.etapa == "Perdido"
    assert oportunidad.motivo_perdida == "precio"


def test_atajo_de_asesoria_salta_la_propuesta(sesion, contacto, servicio_asesoria):
    oportunidad = _crear_oportunidad(sesion, contacto, servicio_asesoria, etapa="Diagnostico")

    oportunidad = mover_etapa(sesion, oportunidad, "Ganado", pago_recibido=True)
    assert oportunidad.etapa == "Ganado"


def test_atajo_de_venta_es_de_un_solo_paso(sesion, contacto, servicio_venta):
    oportunidad = _crear_oportunidad(sesion, contacto, servicio_venta, etapa="Nuevo")

    oportunidad = mover_etapa(sesion, oportunidad, "Ganado", pago_recibido=True)
    assert oportunidad.etapa == "Ganado"


def test_mover_a_la_misma_etapa_no_hace_nada(sesion, contacto, servicio_consultoria):
    oportunidad = _crear_oportunidad(sesion, contacto, servicio_consultoria)
    modificado_antes = oportunidad.modificado_en

    resultado = mover_etapa(sesion, oportunidad, "Nuevo")

    assert resultado.etapa == "Nuevo"
    assert resultado.modificado_en == modificado_antes


def test_oportunidad_en_riesgo_cuando_pasa_el_limite_de_dias(sesion, contacto, servicio_consultoria):
    hace_diez_dias = hora_actual_utc() - timedelta(days=10)
    oportunidad = _crear_oportunidad(
        sesion, contacto, servicio_consultoria, ultima_actividad_en=hace_diez_dias
    )

    assert esta_en_riesgo(oportunidad) is True
    assert color_semaforo(oportunidad) == "rojo"


def test_oportunidad_recien_creada_no_esta_en_riesgo(sesion, contacto, servicio_consultoria):
    oportunidad = _crear_oportunidad(sesion, contacto, servicio_consultoria)

    assert esta_en_riesgo(oportunidad) is False
    assert color_semaforo(oportunidad) == "verde"
