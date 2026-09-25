"""Pruebas de la sincronizacion de contactos desde Google Sheets.

Estas pruebas no tocan la red: usan diccionarios de ejemplo como si fueran
filas ya leidas de la hoja (lo que devolveria gspread), y verifican solo la
logica de negocio (crear, actualizar, omitir, idempotencia)."""

from sqlmodel import select

from app.modelos import Contacto
from app.sincronizar_sheets import construir_notas_desde_fila, sincronizar_contacto_desde_fila

FILA_EJEMPLO = {
    "Fecha": "2026-09-01",
    "Nombre": "Carlos Rodriguez",
    "Empresa": "Panaderia Dulce Trigo",
    "Email": "carlos@dulcetrigo.com",
    "Teléfono": "+58 412 1234567",
    "Necesidad": "Mejorar redes sociales",
    "Descripción": "Tiene 3 años en el mercado, quiere subir ventas",
    "Mensaje": "Vi el Diagnostico en Publico y quiero aplicar",
    "Estado": "Nuevo",
}


def test_crea_un_contacto_nuevo_cuando_el_correo_no_existe(sesion):
    contacto, resultado = sincronizar_contacto_desde_fila(sesion, FILA_EJEMPLO)

    assert resultado == "creado"
    assert contacto.nombre == "Carlos Rodriguez"
    assert contacto.correo == "carlos@dulcetrigo.com"
    assert contacto.telefono == "+58 412 1234567"
    assert contacto.origen == "web"
    assert "Panaderia Dulce Trigo" in contacto.notas
    assert "Mejorar redes sociales" in contacto.notas


def test_actualiza_un_contacto_existente_encontrado_por_correo_sin_duplicar(sesion):
    contacto_previo = Contacto(nombre="Carlos R.", correo="carlos@dulcetrigo.com")
    sesion.add(contacto_previo)
    sesion.commit()
    sesion.refresh(contacto_previo)

    contacto, resultado = sincronizar_contacto_desde_fila(sesion, FILA_EJEMPLO)

    assert resultado == "actualizado"
    assert contacto.id == contacto_previo.id
    assert contacto.nombre == "Carlos Rodriguez"

    total_contactos = sesion.exec(select(Contacto)).all()
    assert len(total_contactos) == 1


def test_empareja_por_telefono_cuando_la_fila_no_trae_email(sesion):
    fila_sin_correo = dict(FILA_EJEMPLO)
    fila_sin_correo["Email"] = ""

    contacto_previo = Contacto(nombre="Carlos", telefono="+58 412 1234567")
    sesion.add(contacto_previo)
    sesion.commit()
    sesion.refresh(contacto_previo)

    contacto, resultado = sincronizar_contacto_desde_fila(sesion, fila_sin_correo)

    assert resultado == "actualizado"
    assert contacto.id == contacto_previo.id


def test_omite_una_fila_sin_correo_y_sin_telefono(sesion):
    fila_incompleta = dict(FILA_EJEMPLO)
    fila_incompleta["Email"] = ""
    fila_incompleta["Teléfono"] = ""

    contacto, resultado = sincronizar_contacto_desde_fila(sesion, fila_incompleta)

    assert resultado == "omitido"
    assert contacto is None


def test_correr_la_misma_fila_dos_veces_no_duplica(sesion):
    sincronizar_contacto_desde_fila(sesion, FILA_EJEMPLO)
    sincronizar_contacto_desde_fila(sesion, FILA_EJEMPLO)

    total_contactos = sesion.exec(select(Contacto)).all()
    assert len(total_contactos) == 1


def test_construir_notas_desde_fila_junta_los_campos_sin_columna_propia():
    notas = construir_notas_desde_fila(FILA_EJEMPLO)

    assert "Fecha del formulario: 2026-09-01" in notas
    assert "Empresa: Panaderia Dulce Trigo" in notas
    assert "Necesidad: Mejorar redes sociales" in notas
    assert "Descripcion: Tiene 3" in notas
    assert "Mensaje: Vi el Diagnostico" in notas
    assert "Estado en la hoja: Nuevo" in notas


def test_construir_notas_desde_fila_vacia_no_falla():
    assert construir_notas_desde_fila({}) == ""
