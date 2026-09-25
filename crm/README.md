# CRM de Fernando

CRM propio para la marca personal de Fernando (asesorías, consultorías y venta de
productos). Un solo usuario, base de datos como única fuente de verdad, reglas de
negocio en YAML y todo pensado para correr primero en tu laptop y después en un
servidor, sin Docker.

Este README documenta la **Fase 1**, que es lo que ya está construido.

## Qué hay en la Fase 1

- Modelo de datos completo (`app/modelos.py`): Contacto, Empresa, Servicio,
  Oportunidad, Interaccion, Tarea, Propuesta, Proyecto, Hito, Pago, Borrador,
  Evento y Bitacora.
- Reglas del embudo (`reglas/embudo.yaml` + `app/reglas_embudo.py`): saltos de
  etapa permitidos, requisitos para Propuesta/Ganado/Perdido, atajos por línea
  de servicio (asesoría y venta), probabilidad por etapa, semáforo de días sin
  movimiento. Función `mover_etapa(...)`.
- Reglas de puntuación (`reglas/puntuacion.yaml` + `app/reglas_puntuacion.py`):
  función `calcular_puntuacion(...)` y `actualizar_puntuacion_contacto(...)`.
- Bitácora (`app/bitacora.py`) y Eventos idempotentes (`app/eventos.py`).
- Autenticación de un solo usuario por contraseña (`app/autenticacion.py`).
- Interfaz web mínima, mobile-first, con HTMX y CSS propio: `/hoy`, `/embudo`
  (tablero con semáforo y botón para mover etapa) y `/contactos` (tabla,
  búsqueda global y alta rápida).
- 23 pruebas con pytest, con ejemplos realistas, para las reglas de embudo,
  de puntuación y la sincronización con Sheets.
- El catálogo completo de automatizaciones ya está escrito en
  `reglas/automatizaciones.yaml` (todas en modo "sombra"), listo para cuando
  se construya el motor que las ejecuta.
- Sincronización de contactos desde Google Sheets (`app/sincronizar_sheets.py`):
  lee la pestaña de leads, crea o actualiza Contactos sin duplicar (busca por
  correo o teléfono), y guarda en notas todo lo que no tiene un campo propio
  (empresa, necesidad, descripción, mensaje, estado). Corre sola cada vez que
  arrancas con `iniciar.py`, y también hay un botón "Sincronizar con Google
  Sheets ahora" en `/contactos`. Ver la sección de abajo para configurarla.

## Qué falta (Fase 2, no está construido todavía)

- El motor que lee cada Evento, busca en `reglas/automatizaciones.yaml` y
  ejecuta las acciones (crear borrador, crear tarea, etc.). Hoy los eventos
  se guardan en la tabla Evento pero nadie los procesa todavía.
- El reloj con APScheduler (recordatorios, seguimientos, resúmenes, cierre
  de mes).
- Sincronización con Gmail (correo.nuevo) y Google Calendar (reuniones).
- Que la sincronización de Sheets también cree Oportunidades automáticamente
  (hoy a propósito solo sincroniza Contactos: adivinar el servicio a partir
  del texto de "Necesidad" podría crear datos incorrectos sin que te des
  cuenta).
- Rutas `/aprobacion` (bandeja de borradores), `/cobros` y `/cifras`.
- Página de detalle `/oportunidades/{id}` con línea de tiempo, generar
  propuesta y registrar pago.
- Respaldo diario de la base de datos.

## Configurar la sincronización con Google Sheets

1. En Google Cloud (mismo proyecto que uses para el CRM), habilita la
   **Google Sheets API** y crea una **cuenta de servicio** (sin ningún rol
   de administrador ni de proyecto — el acceso se da compartiendo la hoja,
   como con una persona más). Descarga su clave en formato JSON.
2. Guarda ese archivo como `crm/credenciales_google.json` (ese nombre ya
   está protegido en `.gitignore`, nunca se sube al repositorio).
3. Comparte tu Google Sheet con el correo de la cuenta de servicio (se ve
   como `algo@tu-proyecto.iam.gserviceaccount.com`), con rol de Lector.
4. En tu `.env`, completa:
   ```
   GOOGLE_CREDENCIALES_JSON=credenciales_google.json
   GOOGLE_SHEETS_ID=el-id-de-tu-hoja
   GOOGLE_SHEETS_PESTANA_LEADS=leads
   ```
5. Pruébalo aislado antes de correr todo el CRM:
   ```bash
   python sincronizar_datos.py
   ```
   Si algo falla (credencial mal puesta, hoja no compartida, nombre de
   pestaña distinto), el error aparece ahí, claro y aislado.

## Cómo correrlo en tu laptop

### Opción rápida: `iniciar.py`

Si ya tienes Python y Git instalados, `crm/iniciar.py` hace todo esto por ti:
clona o actualiza el repositorio, crea el entorno virtual, instala las
dependencias, te pide una contraseña la primera vez, carga los servicios de
ejemplo, levanta el servidor y abre el navegador cuando ya está listo (espera
a que el servidor responda antes de abrirlo, para evitar el clásico "no se
pudo establecer conexión").

```bash
python iniciar.py
```

Solo usa librerías estándar de Python (no depende de que ya exista el
entorno virtual, porque corre antes de crearlo). Deja la ventana abierta
mientras usas el CRM; para apagarlo, ciérrala o presiona Ctrl+C.

### Paso a paso manual

1. Crea el entorno virtual e instala las dependencias:

   ```bash
   cd crm
   python3 -m venv .venv
   source .venv/bin/activate        # en Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Copia `.env.example` a `.env` y completa tu contraseña y tu clave secreta:

   ```bash
   cp .env.example .env
   ```

   Genera una clave secreta con:

   ```bash
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```

3. Carga los servicios de ejemplo (o los tuyos, editando antes
   `reglas/servicios.yaml`):

   ```bash
   python sembrar_datos.py
   ```

4. Corre el servidor:

   ```bash
   uvicorn app.main:app --reload
   ```

   Abre `http://127.0.0.1:8000`, te pedirá la contraseña de tu `.env`.

## Cómo correr las pruebas

```bash
cd crm
source .venv/bin/activate
pytest -v
```

## Estructura

```
crm/
├── app/
│   ├── main.py                 ← arma la app FastAPI y las rutas
│   ├── configuracion.py        ← lee el .env, conversion UTC -> Caracas
│   ├── base_datos.py           ← conexion SQLite/SQLModel
│   ├── modelos.py               ← todas las tablas
│   ├── autenticacion.py        ← login de un solo usuario
│   ├── bitacora.py             ← registrar_cambio(...)
│   ├── eventos.py              ← emitir_evento(...) idempotente
│   ├── errores.py              ← ErrorDeNegocio (mensajes en español)
│   ├── reglas_embudo.py        ← mover_etapa(...), esta_en_riesgo(...)
│   ├── reglas_puntuacion.py    ← calcular_puntuacion(...)
│   ├── plantillas_util.py      ← instancia de Jinja2Templates + filtro de fecha
│   ├── rutas/                  ← hoy.py, embudo.py, contactos.py
│   ├── plantillas/             ← HTML (Jinja2)
│   └── estaticos/              ← estilos.css
├── reglas/                     ← embudo.yaml, puntuacion.yaml, servicios.yaml,
│                                  automatizaciones.yaml (catalogo, Fase 2)
├── pruebas/                    ← pytest
├── datos/                      ← aqui vive crm.db (no se sube al repo)
├── sembrar_datos.py
├── requirements.txt
└── .env.example
```

## Decisiones simples que vale la pena que conozcas

- Los montos se guardan como `float`, no como tipo `Decimal`. Para un CRM
  personal es suficiente y más fácil de leer; si algún día importa el
  centavo exacto, se puede migrar campo por campo.
- El requisito de "pago recibido" para marcar una oportunidad como Ganada
  se pasa como parámetro (`pago_recibido=True`) a `mover_etapa(...)`, en vez
  de buscarlo en la tabla Pago: la tabla Pago cuelga de un Proyecto, y el
  Proyecto recién se crea *después* de marcar Ganado. Para asesorías (que
  cobran antes de ganar) esto evita una dependencia circular.
- La contraseña se compara con `hmac.compare_digest` contra el valor plano
  del `.env` (no hay hash). Es aceptable para un solo usuario con acceso
  local/privado; si el servidor queda expuesto a internet, conviene
  agregarle hash (por ejemplo con `passlib`) más adelante.
