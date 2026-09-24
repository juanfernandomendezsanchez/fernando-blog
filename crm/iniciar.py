"""Lanzador local del CRM para una PC nueva (Windows, Mac o Linux).

Hace todo lo necesario para tener el CRM corriendo: clona o actualiza el
repositorio, crea el entorno virtual, instala las dependencias, genera el
archivo .env (pidiendo una contrasena la primera vez), carga los servicios
de ejemplo, levanta el servidor y abre el navegador.

Uso:

    python iniciar.py

No usa nada fuera de la libreria estandar de Python, porque corre ANTES de
que exista el entorno virtual del proyecto.
"""

import os
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

REPOSITORIO_URL = "https://github.com/juanfernandomendezsanchez/fernando-blog.git"
RAMA = "claude/fernando-personal-crm-jzi3yk"
CARPETA_BASE = Path.home() / "Documents" / "fernando-blog"
DIRECCION_SERVIDOR = "http://127.0.0.1:8000"


def ejecutar(comando, carpeta=None):
    """Corre un comando externo y falla con un mensaje claro si algo sale mal.
    Recibe el comando como lista (nunca como texto), asi no hay riesgo de que
    caracteres especiales se interpreten mal."""
    print("> " + " ".join(str(parte) for parte in comando))
    resultado = subprocess.run(comando, cwd=carpeta)
    if resultado.returncode != 0:
        raise RuntimeError(
            "El comando anterior fallo (codigo %s). Revisa el mensaje de arriba."
            % resultado.returncode
        )


def clonar_o_actualizar_repositorio():
    if not CARPETA_BASE.exists():
        print("Descargando el proyecto por primera vez...")
        CARPETA_BASE.parent.mkdir(parents=True, exist_ok=True)
        ejecutar(["git", "clone", REPOSITORIO_URL, str(CARPETA_BASE)])
    else:
        print("El proyecto ya existia, actualizando...")
        ejecutar(["git", "fetch", "origin"], carpeta=CARPETA_BASE)

    ejecutar(["git", "checkout", RAMA], carpeta=CARPETA_BASE)
    ejecutar(["git", "pull", "origin", RAMA], carpeta=CARPETA_BASE)


def obtener_ejecutable_venv(carpeta_venv, nombre):
    """Devuelve la ruta al python o pip DENTRO del entorno virtual,
    sin necesitar activarlo. La carpeta interna se llama distinto en
    Windows (Scripts) y en Mac/Linux (bin)."""
    if os.name == "nt":
        return carpeta_venv / "Scripts" / (nombre + ".exe")
    return carpeta_venv / "bin" / nombre


def crear_entorno_virtual_si_hace_falta(carpeta_crm):
    carpeta_venv = carpeta_crm / ".venv"
    if not carpeta_venv.exists():
        print("Creando el entorno de Python, unos segundos...")
        ejecutar([sys.executable, "-m", "venv", str(carpeta_venv)])
    return carpeta_venv


def instalar_dependencias(python_venv, carpeta_crm):
    print("Instalando dependencias, puede tardar un par de minutos la primera vez...")
    ejecutar(
        [str(python_venv), "-m", "pip", "install", "--quiet", "-r", "requirements.txt"],
        carpeta=carpeta_crm,
    )


def generar_env_si_hace_falta(carpeta_crm):
    archivo_env = carpeta_crm / ".env"
    if archivo_env.exists():
        return

    print()
    print("Primera vez que corres el CRM: elige una contrasena para entrar.")
    contrasena = input("Escribe la contrasena que quieras usar: ").strip()
    while not contrasena:
        contrasena = input("La contrasena no puede quedar vacia, escribe una: ").strip()

    import secrets

    clave_secreta = secrets.token_hex(32)

    contenido = (
        "CRM_CONTRASENA=%s\n" % contrasena
        + "CRM_CLAVE_SECRETA=%s\n" % clave_secreta
        + "CRM_ZONA_HORARIA=America/Caracas\n"
        + "CRM_BASE_DATOS_URL=sqlite:///./datos/crm.db\n"
        + "CRM_META_MENSUAL_USD=0\n"
    )
    archivo_env.write_text(contenido, encoding="utf-8")
    print("Contrasena guardada en .env")


def sembrar_datos(python_venv, carpeta_crm):
    print("Cargando servicios de ejemplo...")
    ejecutar([str(python_venv), "sembrar_datos.py"], carpeta=carpeta_crm)


def esperar_servidor_listo(segundos_maximo=20):
    inicio = time.time()
    while time.time() - inicio < segundos_maximo:
        try:
            urllib.request.urlopen(DIRECCION_SERVIDOR, timeout=1)
            return True
        except Exception:
            time.sleep(0.5)
    return False


def iniciar_servidor_y_navegador(python_venv, carpeta_crm):
    print()
    print("Iniciando el servidor...")
    proceso = subprocess.Popen(
        [str(python_venv), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=carpeta_crm,
    )

    if esperar_servidor_listo():
        print()
        print("Abriendo el CRM en el navegador...")
        try:
            webbrowser.open(DIRECCION_SERVIDOR)
        except Exception:
            print("No se pudo abrir el navegador solo. Entra tu mismo a: " + DIRECCION_SERVIDOR)
    else:
        print("El servidor esta tardando mas de lo normal. Entra manualmente a: " + DIRECCION_SERVIDOR)

    print()
    print("El CRM esta corriendo. NO CIERRES ESTA VENTANA mientras lo uses.")
    print("Para apagarlo, cierra esta ventana o presiona Ctrl+C.")
    print()

    proceso.wait()


def main():
    carpeta_crm = CARPETA_BASE / "crm"
    try:
        clonar_o_actualizar_repositorio()
        python_venv = obtener_ejecutable_venv(
            crear_entorno_virtual_si_hace_falta(carpeta_crm), "python"
        )
        instalar_dependencias(python_venv, carpeta_crm)
        generar_env_si_hace_falta(carpeta_crm)
        sembrar_datos(python_venv, carpeta_crm)
        iniciar_servidor_y_navegador(python_venv, carpeta_crm)
    except KeyboardInterrupt:
        print("\nCRM detenido.")
    except Exception as error:
        print()
        print("=" * 60)
        print("OCURRIO UN ERROR:")
        print(error)
        print("=" * 60)
    finally:
        input("\nPresiona ENTER para salir...")


if __name__ == "__main__":
    main()
