"""Pruebas de las reglas de puntuacion, con ejemplos realistas de leads
que llegan por distintos canales."""

from app.modelos import dividir_etiquetas
from app.reglas_puntuacion import actualizar_puntuacion_contacto, calcular_puntuacion, debe_pasar_a_calificado


def test_referido_que_responde_rapido_no_llega_solo_a_calificado():
    # Un referido que responde rapido suma 25 + 10 = 35, por debajo del umbral de 50.
    puntuacion = calcular_puntuacion(
        {"llego_por_referido": True, "respondio_en_menos_de_24_horas": True}
    )
    assert puntuacion == 35
    assert debe_pasar_a_calificado(puntuacion) is False


def test_referido_que_pregunta_precio_y_tiene_negocio_activo_llega_a_calificado():
    puntuacion = calcular_puntuacion(
        {
            "llego_por_referido": True,
            "declara_presupuesto_o_pregunta_precios": True,
            "negocio_activo_con_clientes": True,
        }
    )
    assert puntuacion == 60
    assert debe_pasar_a_calificado(puntuacion) is True


def test_sin_ninguna_senal_positiva_la_puntuacion_es_cero():
    assert calcular_puntuacion({}) == 0


def test_la_puntuacion_nunca_baja_de_cero():
    # -20 + -15 = -35, pero el piso es 0.
    puntuacion = calcular_puntuacion(
        {"fuera_de_perfil_ideal": True, "solo_pide_gratis_o_ideas": True}
    )
    assert puntuacion == 0


def test_la_puntuacion_no_pasa_del_maximo_de_95():
    puntuacion = calcular_puntuacion(
        {
            "llego_por_referido": True,
            "declara_presupuesto_o_pregunta_precios": True,
            "negocio_activo_con_clientes": True,
            "marca_debil_o_inconsistente": True,
            "respondio_en_menos_de_24_horas": True,
            "tiene_redes_activas": True,
        }
    )
    assert puntuacion == 95


def test_contacto_bajo_el_umbral_recibe_etiqueta_de_nutricion(sesion, contacto):
    contacto_actualizado = actualizar_puntuacion_contacto(sesion, contacto, {"llego_por_referido": True})

    assert contacto_actualizado.puntuacion == 25
    assert "nutricion" in dividir_etiquetas(contacto_actualizado.etiquetas)


def test_contacto_calificado_no_recibe_etiqueta_de_nutricion(sesion, contacto):
    senales = {
        "llego_por_referido": True,
        "declara_presupuesto_o_pregunta_precios": True,
        "negocio_activo_con_clientes": True,
    }
    contacto_actualizado = actualizar_puntuacion_contacto(sesion, contacto, senales)

    assert contacto_actualizado.puntuacion == 60
    assert "nutricion" not in dividir_etiquetas(contacto_actualizado.etiquetas)
