"""Sincroniza los contactos desde Google Sheets a la base de datos.

Uso (desde la carpeta crm/, con el entorno virtual activado):

    python sincronizar_datos.py

Se puede correr solo, aparte del resto del CRM, para probar la conexion
a Google Sheets de forma aislada (por ejemplo, la primera vez que
configuras las credenciales).
"""

from sqlmodel import Session

from app.base_datos import crear_tablas, motor
from app.sincronizar_sheets import sincronizar_leads_desde_sheets


def main() -> None:
    crear_tablas()
    with Session(motor) as sesion:
        try:
            resumen = sincronizar_leads_desde_sheets(sesion)
        except Exception as error:
            print("No se pudo sincronizar con Google Sheets:")
            print(error)
            return

    if not resumen["configurado"]:
        print("Google Sheets todavia no esta configurado (falta GOOGLE_CREDENCIALES_JSON o GOOGLE_SHEETS_ID en .env). Se omite la sincronizacion.")
        return

    print(
        "Sincronizacion con Google Sheets: %s creados, %s actualizados, %s omitidos"
        % (resumen["creados"], resumen["actualizados"], resumen["omitidos"])
    )


if __name__ == "__main__":
    main()
