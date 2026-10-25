"""Pruebas de punta a punta de las pantallas nuevas: Biblioteca, ficha de
contacto, ficha de oportunidad, Tareas, Cifras y respaldo. Usan el
TestClient de FastAPI contra una base de datos en memoria y una carpeta
temporal para la biblioteca (nunca tocan crm/datos)."""

import io
import zipfile
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app import configuracion
from app.base_datos import obtener_sesion
from app.main import app
from app.modelos import Documento, Interaccion, Oportunidad, Propuesta, Tarea, hora_actual_utc


@pytest.fixture
def cliente(sesion, tmp_path, monkeypatch):
    monkeypatch.setattr(configuracion, "CARPETA_BIBLIOTECA", tmp_path / "biblioteca")
    app.dependency_overrides[obtener_sesion] = lambda: sesion
    cliente_de_prueba = TestClient(app)
    respuesta = cliente_de_prueba.post(
        "/login", data={"contrasena": configuracion.CONTRASENA}, follow_redirects=False
    )
    assert respuesta.status_code == 303
    yield cliente_de_prueba
    app.dependency_overrides.clear()


@pytest.fixture
def oportunidad(sesion, contacto, servicio_consultoria):
    oportunidad = Oportunidad(
        contacto_id=contacto.id, servicio_id=servicio_consultoria.id, origen=contacto.origen
    )
    sesion.add(oportunidad)
    sesion.commit()
    sesion.refresh(oportunidad)
    return oportunidad


def test_sin_sesion_redirige_al_login(sesion):
    app.dependency_overrides[obtener_sesion] = lambda: sesion
    respuesta = TestClient(app).get("/biblioteca", follow_redirects=False)
    app.dependency_overrides.clear()
    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/login"


# ---------- Biblioteca ----------

def test_subir_ver_y_descargar_un_documento(cliente, sesion):
    respuesta = cliente.post(
        "/biblioteca/subir",
        data={"titulo": "Contrato base", "categoria": "Contratos", "etiquetas": "Legal, 2026"},
        files={"archivo": ("contrato.pdf", b"%PDF-1.4 contenido", "application/pdf")},
        follow_redirects=False,
    )
    assert respuesta.status_code == 303

    documento = sesion.query(Documento).one()
    assert documento.categoria == "contratos"
    assert documento.etiquetas == "legal,2026"
    assert documento.nombre_archivo == "contrato.pdf"
    assert documento.tamano_bytes == len(b"%PDF-1.4 contenido")
    assert (configuracion.CARPETA_BIBLIOTECA / documento.archivo_guardado).exists()

    pagina = cliente.get("/biblioteca")
    assert "Contrato base" in pagina.text

    # Los PDF se abren en el navegador...
    archivo = cliente.get(f"/biblioteca/{documento.id}/archivo")
    assert archivo.content == b"%PDF-1.4 contenido"
    assert archivo.headers["content-disposition"].startswith("inline")
    # ...salvo que pidas descargarlo.
    descarga = cliente.get(f"/biblioteca/{documento.id}/archivo?descargar=true")
    assert descarga.headers["content-disposition"].startswith("attachment")


def test_un_html_subido_nunca_se_abre_en_el_navegador(cliente, sesion):
    cliente.post(
        "/biblioteca/subir",
        files={"archivo": ("pagina.html", b"<script>alert(1)</script>", "text/html")},
    )
    documento = sesion.query(Documento).one()
    respuesta = cliente.get(f"/biblioteca/{documento.id}/archivo")
    assert respuesta.headers["content-disposition"].startswith("attachment")
    assert respuesta.headers["content-type"] == "application/octet-stream"


def test_guardar_solo_un_enlace(cliente, sesion):
    cliente.post(
        "/biblioteca/subir",
        data={"enlace_externo": "https://drive.google.com/abc", "titulo": "Brandbook"},
    )
    documento = sesion.query(Documento).one()
    assert documento.archivo_guardado is None
    assert documento.enlace_externo == "https://drive.google.com/abc"


def test_sin_archivo_ni_enlace_da_error_claro(cliente):
    respuesta = cliente.post("/biblioteca/subir", data={"titulo": "Nada"})
    assert respuesta.status_code == 400
    assert "archivo" in respuesta.text


def test_buscar_filtrar_y_marcar_favorito(cliente, sesion):
    cliente.post("/biblioteca/subir", data={"enlace_externo": "https://a.com", "titulo": "Guía de precios", "categoria": "guias"})
    cliente.post("/biblioteca/subir", data={"enlace_externo": "https://b.com", "titulo": "Factura marzo", "categoria": "facturas"})

    assert "Factura marzo" not in cliente.get("/biblioteca?q=precios").text
    assert "Guía de precios" not in cliente.get("/biblioteca?categoria=facturas").text

    factura = sesion.query(Documento).filter(Documento.titulo == "Factura marzo").one()
    cliente.post(f"/biblioteca/{factura.id}/favorito")
    sesion.refresh(factura)
    assert factura.favorito is True
    assert "Guía de precios" not in cliente.get("/biblioteca?favoritos=1").text


def test_editar_y_eliminar_borra_tambien_el_archivo(cliente, sesion):
    cliente.post("/biblioteca/subir", files={"archivo": ("notas.txt", b"hola", "text/plain")})
    documento = sesion.query(Documento).one()
    ruta = configuracion.CARPETA_BIBLIOTECA / documento.archivo_guardado

    cliente.post(f"/biblioteca/{documento.id}/editar", data={"titulo": "Notas personales", "categoria": "personal"})
    sesion.refresh(documento)
    assert documento.titulo == "Notas personales"

    cliente.post(f"/biblioteca/{documento.id}/eliminar")
    assert sesion.query(Documento).count() == 0
    assert not ruta.exists()


def test_archivo_demasiado_grande_no_se_guarda(cliente, sesion, monkeypatch):
    monkeypatch.setattr(configuracion, "TAMANO_MAXIMO_DOCUMENTO_MB", 0)
    respuesta = cliente.post("/biblioteca/subir", files={"archivo": ("grande.zip", b"x" * 10, "application/zip")})
    assert respuesta.status_code == 400
    assert sesion.query(Documento).count() == 0
    assert not any(configuracion.CARPETA_BIBLIOTECA.iterdir())


def test_volver_no_acepta_direcciones_externas(cliente):
    respuesta = cliente.post(
        "/biblioteca/subir",
        data={"enlace_externo": "https://a.com", "volver": "//sitio-malo.com"},
        follow_redirects=False,
    )
    assert respuesta.headers["location"] == "/biblioteca"


# ---------- Contactos ----------

def test_ficha_de_contacto_y_editar(cliente, sesion, contacto):
    assert contacto.nombre in cliente.get(f"/contactos/{contacto.id}").text

    cliente.post(
        f"/contactos/{contacto.id}/editar",
        data={"nombre": "Ana Pérez", "correo": "ANA@example.com", "empresa": "Café Ana", "etiquetas": "Marca, VIP"},
    )
    sesion.refresh(contacto)
    assert contacto.nombre == "Ana Pérez"
    assert contacto.correo == "ana@example.com"
    assert contacto.etiquetas == "marca,vip"
    assert contacto.empresa_id is not None


def test_alta_rapida_no_duplica_por_correo(cliente, contacto, servicio_consultoria):
    respuesta = cliente.post(
        "/contactos/nuevo-rapido",
        data={"nombre": "Otra Ana", "correo": "ana@example.com", "servicio_id": servicio_consultoria.id},
    )
    assert respuesta.status_code == 400
    assert "Ana Perez" in respuesta.text


def test_exportar_contactos_csv(cliente, contacto):
    respuesta = cliente.get("/contactos/exportar.csv")
    assert respuesta.status_code == 200
    assert "ana@example.com" in respuesta.text


# ---------- Oportunidades ----------

def test_camino_completo_hasta_propuesta(cliente, sesion, oportunidad):
    cliente.post(f"/oportunidades/{oportunidad.id}/mover-etapa", data={"etapa_nueva": "Calificado"})
    cliente.post(f"/oportunidades/{oportunidad.id}/mover-etapa", data={"etapa_nueva": "Diagnostico"})

    cliente.post(
        f"/oportunidades/{oportunidad.id}/editar",
        data={"valor_estimado": "1,500.00", "fecha_cierre_esperada": "2026-12-15", "siguiente_paso": "Enviar propuesta"},
    )
    cliente.post(f"/oportunidades/{oportunidad.id}/propuestas", data={"alcance": "Manual de marca + 10 piezas"})
    respuesta = cliente.post(
        f"/oportunidades/{oportunidad.id}/mover-etapa",
        data={"etapa_nueva": "Propuesta", "volver": f"/oportunidades/{oportunidad.id}"},
        follow_redirects=False,
    )
    assert respuesta.headers["location"] == f"/oportunidades/{oportunidad.id}"

    sesion.refresh(oportunidad)
    assert oportunidad.etapa == "Propuesta"
    assert oportunidad.valor_estimado == 1500.0
    propuesta = sesion.query(Propuesta).one()
    assert propuesta.monto == 1500.0

    cliente.post(f"/propuestas/{propuesta.id}/estado", data={"estado": "enviada"})
    sesion.refresh(propuesta)
    assert propuesta.fecha_envio is not None
    assert "Manual de marca" in cliente.get(f"/oportunidades/{oportunidad.id}").text


def test_registrar_conversacion_reinicia_el_semaforo(cliente, sesion, oportunidad):
    oportunidad.ultima_actividad_en = hora_actual_utc() - timedelta(days=10)
    sesion.add(oportunidad)
    sesion.commit()

    cliente.post(
        f"/oportunidades/{oportunidad.id}/interacciones",
        data={"canal": "whatsapp", "direccion": "entrante", "resumen": "Pregunta precios", "requiere_respuesta": "true"},
    )
    sesion.refresh(oportunidad)
    assert (hora_actual_utc() - oportunidad.ultima_actividad_en).days == 0

    interaccion = sesion.query(Interaccion).one()
    assert interaccion.requiere_respuesta is True
    assert "Pregunta precios" in cliente.get("/hoy").text

    cliente.post(f"/interacciones/{interaccion.id}/respondida")
    sesion.refresh(interaccion)
    assert interaccion.requiere_respuesta is False


def test_documento_de_oportunidad_queda_ligado_al_contacto(cliente, sesion, oportunidad):
    cliente.post(
        "/biblioteca/subir",
        data={"oportunidad_id": oportunidad.id, "enlace_externo": "https://canva.com/propuesta"},
    )
    documento = sesion.query(Documento).one()
    assert documento.contacto_id == oportunidad.contacto_id
    assert "canva.com/propuesta" in cliente.get(f"/contactos/{oportunidad.contacto_id}").text


# ---------- Tareas ----------

def test_crear_completar_y_reabrir_tarea(cliente, sesion, oportunidad):
    cliente.post(
        "/tareas/nueva",
        data={"descripcion": "Llamar a Ana", "fecha_limite": "2020-01-01", "oportunidad_id": oportunidad.id},
    )
    tarea = sesion.query(Tarea).one()
    pagina = cliente.get("/tareas")
    assert "Vencidas" in pagina.text and "Llamar a Ana" in pagina.text
    assert "Llamar a Ana" in cliente.get("/hoy").text

    cliente.post(f"/tareas/{tarea.id}/completar")
    sesion.refresh(tarea)
    assert tarea.estado == "hecha"

    cliente.post(f"/tareas/{tarea.id}/reabrir")
    sesion.refresh(tarea)
    assert tarea.estado == "pendiente"


# ---------- Cifras y respaldo ----------

def test_cifras_cuenta_lo_ganado(cliente, sesion, contacto, servicio_venta):
    oportunidad = Oportunidad(contacto_id=contacto.id, servicio_id=servicio_venta.id, valor_estimado=20)
    sesion.add(oportunidad)
    sesion.commit()
    cliente.post(
        f"/oportunidades/{oportunidad.id}/mover-etapa", data={"etapa_nueva": "Ganado", "pago_recibido": "true"}
    )

    from app.rutas.cifras import calcular_cifras

    cifras = calcular_cifras(sesion)
    assert cifras["tasa_de_cierre"] == 100
    assert cifras["serie_meses"][-1]["valor"] == 20
    assert cliente.get("/cifras").status_code == 200


def test_respaldo_incluye_base_de_datos_y_documentos(cliente, tmp_path, monkeypatch):
    import sqlite3

    from app.rutas import respaldo

    ruta_db = tmp_path / "crm.db"
    sqlite3.connect(ruta_db).close()

    class MotorFalso:
        class url:
            database = str(ruta_db)

            @staticmethod
            def get_backend_name():
                return "sqlite"

    monkeypatch.setattr(respaldo, "motor", MotorFalso)
    cliente.post("/biblioteca/subir", files={"archivo": ("a.txt", b"hola", "text/plain")})

    respuesta = cliente.get("/respaldo.zip")
    assert respuesta.status_code == 200
    nombres = zipfile.ZipFile(io.BytesIO(respuesta.content)).namelist()
    assert "crm.db" in nombres
    assert any(n.startswith("biblioteca/") for n in nombres)
