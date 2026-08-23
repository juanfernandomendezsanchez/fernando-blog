# Backend de diagnósticos — coste $0

Stack: **Google Sheets + Google Apps Script + Gmail**. Todo dentro de las cuotas gratuitas de tu cuenta de Google normal. Sin Resend, sin SendGrid, sin Supabase, sin planes premium.

Esto lo tienes que hacer tú, una sola vez, porque requiere tu cuenta de Google y una autorización manual que Google exige por seguridad (no se puede automatizar desde fuera).

## 1. Crea el Google Sheet

1. Ve a [sheets.google.com](https://sheets.google.com) → hoja en blanco.
2. Nómbrala como quieras (ej. `Fernando — Leads`).
3. Renombra la primera pestaña (abajo) a **`Leads`** exactamente así.
4. Copia el **ID de la hoja**: es la parte de la URL entre `/d/` y `/edit`.
   `https://docs.google.com/spreadsheets/d/`**`ESTE_ES_EL_ID`**`/edit`

No hace falta que escribas los encabezados a mano — el script los crea solo la primera vez que llega un lead.

## 2. Crea el proyecto de Apps Script

1. En la misma hoja: **Extensiones → Apps Script**.
2. Borra el contenido de `Código.gs` y pega todo el contenido de `apps-script/Code.gs` de este repo.
3. Arriba del archivo, edita estas tres líneas con tus datos:
   ```js
   const SHEET_ID = 'ESTE_ES_EL_ID';           // el que copiaste en el paso 1
   const SHEET_NAME = 'Leads';
   const NOTIFY_EMAIL = 'tu-correo@gmail.com';  // donde quieres recibir cada lead
   ```
4. Guarda (ícono de disquete o `Ctrl+S`).

## 3. Despliega como Web App

1. Arriba a la derecha: **Implementar → Nueva implementación**.
2. Selecciona el tipo: **Aplicación web**.
3. Configuración:
   - **Ejecutar como:** Yo (tu cuenta)
   - **Quién tiene acceso:** Cualquier usuario
4. Clic en **Implementar**.
5. Google te pedirá autorizar permisos (acceso a Sheets y a enviar Gmail en tu nombre). Es normal — es tu propio script actuando dentro de tu propia cuenta. Acepta.
6. Copia la **URL de la aplicación web** que te da (termina en `/exec`).

Esa URL **no es secreta** — es el endpoint público de tu formulario, diseñado para ser llamado desde el navegador de cualquier visitante. Por eso no hay ninguna API key en el frontend: el propio Apps Script actúa como intermediario seguro entre tu web y tu cuenta de Google.

## 4. Conecta la web

Abre `index.html`, busca esta línea cerca del final del `<script>`:

```js
const DIAGNOSTIC_ENDPOINT = "PON_AQUI_TU_URL_DE_APPS_SCRIPT";
```

Reemplázala por la URL que copiaste en el paso 3, súbelo a GitHub, y el formulario ya queda funcionando de verdad.

## 5. Probar

Llena el formulario "Agendar diagnóstico" en la web con datos de prueba. Deberías ver:
- Una fila nueva en tu Google Sheet, con estado `Nuevo`.
- Un correo en tu Gmail con los datos del lead.
- Un correo de confirmación en la bandeja del email que usaste en la prueba.

## Notas

- **Cuota gratuita de Gmail:** 100 correos/día en una cuenta de Gmail normal — de sobra para la fase inicial.
- **Clasificación con IA (futuro):** la función `classifyLead()` en `Code.gs` ya está aislada y comentada con un ejemplo de cómo conectarla a un modelo más adelante, sin tener que tocar el resto del flujo. Cualquier API key que uses ahí se guarda en **Project Settings → Script Properties** de Apps Script (no en el código ni en el frontend).
- **Exportar a Excel cuando quieras:** en el Google Sheet, `Archivo → Descargar → Microsoft Excel (.xlsx)`.
