/**
 * Fernando — Backend de diagnósticos (coste $0)
 * Stack: Google Apps Script + Google Sheets + Gmail
 *
 * Flujo:
 *   Formulario web (fetch POST) → doPost() → validar → guardar en Sheets
 *   → notificar por Gmail a Fernando → (opcional) confirmar al usuario
 *
 * No requiere API keys de terceros. Todo corre dentro de la cuenta
 * de Google de Fernando, dentro de las cuotas gratuitas estándar
 * (Gmail: 100 correos/día en cuentas normales de Gmail).
 */

// ─── CONFIGURACIÓN ───────────────────────────────────────────────
// 1. Pega aquí el ID de tu Google Sheet (está en la URL de la hoja,
//    entre /d/ y /edit).
const SHEET_ID = 'PON_AQUI_EL_ID_DE_TU_GOOGLE_SHEET';

// 2. Nombre exacto de la pestaña dentro de esa hoja.
const SHEET_NAME = 'Leads';

// 3. El Gmail donde quieres recibir la notificación de cada lead.
const NOTIFY_EMAIL = 'PON_AQUI_TU_CORREO@gmail.com';

// 4. ¿Enviar también un correo de confirmación automático al usuario?
const SEND_USER_CONFIRMATION = true;
// ──────────────────────────────────────────────────────────────────


/**
 * Punto de entrada: recibe el POST del formulario de la web.
 * Acepta dos formatos, para ser resistente a bloqueos de CORS:
 *   1. JSON (cuando el navegador pudo usar fetch normalmente)
 *   2. application/x-www-form-urlencoded (fallback vía formulario/iframe,
 *      que nunca depende de CORS porque es una navegación real)
 */
function doPost(e) {
  try {
    const data = parseRequest(e);

    const errors = validate(data);
    if (errors.length > 0) {
      return respond({ ok: false, errors: errors });
    }

    const sheet = SpreadsheetApp.openById(SHEET_ID).getSheetByName(SHEET_NAME);
    ensureHeaders(sheet);

    const estadoInicial = classifyLead(data);

    sheet.appendRow([
      new Date(),
      data.nombre,
      data.empresa || '',
      data.email,
      data.necesidad || '',
      data.descripcion || '',
      data.mensaje || '',
      estadoInicial
    ]);

    sendOwnerNotification(data);

    if (SEND_USER_CONFIRMATION && data.email) {
      sendConfirmationToUser(data);
    }

    return respond({ ok: true });

  } catch (err) {
    return respond({ ok: false, error: String(err) });
  }
}

/**
 * Permite verificar que el endpoint está activo abriendo la URL
 * directamente en el navegador (GET).
 */
function doGet(e) {
  return respond({ ok: true, message: 'Endpoint de diagnósticos activo.' });
}

/**
 * Interpreta el payload venga como venga: JSON (fetch) o
 * form-urlencoded (envío clásico de formulario / fallback iframe).
 */
function parseRequest(e) {
  if (e.postData && e.postData.contents) {
    try {
      return JSON.parse(e.postData.contents);
    } catch (err) {
      // No era JSON — seguimos e intentamos con e.parameter abajo.
    }
  }
  if (e.parameter && Object.keys(e.parameter).length > 0) {
    return e.parameter;
  }
  return {};
}

/**
 * Validación mínima de servidor. Nunca confíes solo en la
 * validación del navegador — el navegador se puede saltar.
 */
function validate(data) {
  const errors = [];
  if (!data || typeof data !== 'object') {
    errors.push('payload_invalido');
    return errors;
  }
  if (!data.nombre || data.nombre.trim().length < 2) errors.push('nombre');
  if (!data.email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email)) errors.push('email');
  return errors;
}

/**
 * Crea la fila de encabezados si la hoja está vacía.
 */
function ensureHeaders(sheet) {
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(['Fecha', 'Nombre', 'Empresa', 'Email', 'Necesidad', 'Descripción', 'Mensaje', 'Estado']);
  }
}

/**
 * ─── PUNTO DE EXTENSIÓN FUTURO: clasificación con IA ───
 *
 * Hoy simplemente devuelve 'Nuevo'. Más adelante, aquí se puede
 * llamar a un modelo (Claude, Gemini, etc.) vía UrlFetchApp para
 * que sugiera una categoría, prioridad o el arquetipo que mejor
 * encaja con la necesidad descrita, y devolver ese valor en vez
 * de 'Nuevo' — sin tocar el resto del flujo.
 *
 * Ejemplo de cómo se vería (comentado, no activo):
 *
 * function classifyLead(data) {
 *   const prompt = `Clasifica este lead en una palabra ` +
 *     `(Urgente / Explorando / Bajo presupuesto): ${data.mensaje}`;
 *   const response = UrlFetchApp.fetch('https://api.anthropic.com/v1/messages', {
 *     method: 'post',
 *     headers: { 'x-api-key': PropertiesService.getScriptProperties().getProperty('ANTHROPIC_API_KEY') },
 *     contentType: 'application/json',
 *     payload: JSON.stringify({ model: 'claude-sonnet-5', max_tokens: 20, messages: [{ role: 'user', content: prompt }] })
 *   });
 *   return JSON.parse(response.getContentText()).content[0].text.trim();
 * }
 *
 * Nota: la API key nunca va en el frontend ni en este archivo —
 * se guarda en Project Settings → Script Properties, y se lee con
 * PropertiesService, que es donde Apps Script guarda secretos.
 */
function classifyLead(data) {
  return 'Nuevo';
}

function sendOwnerNotification(data) {
  const subject = `Nuevo diagnóstico solicitado — ${data.nombre}`;
  const body =
    'Has recibido una nueva solicitud de diagnóstico de marca:\n\n' +
    `Nombre: ${data.nombre}\n` +
    `Empresa: ${data.empresa || '—'}\n` +
    `Email: ${data.email}\n` +
    `Necesidad: ${data.necesidad || '—'}\n` +
    `Descripción: ${data.descripcion || '—'}\n` +
    `Mensaje: ${data.mensaje || '—'}\n\n` +
    'Este lead ya quedó guardado en tu Google Sheet con estado "Nuevo".';

  GmailApp.sendEmail(NOTIFY_EMAIL, subject, body);
}

function sendConfirmationToUser(data) {
  const primerNombre = (data.nombre || '').trim().split(' ')[0];
  const subject = `Recibí tu solicitud, ${primerNombre}`;
  const body =
    `¡Hola ${primerNombre}!\n\n` +
    'Gracias por escribirme. Recibí tu solicitud de diagnóstico de marca ' +
    'y te voy a responder personalmente en las próximas 48 horas.\n\n' +
    '— Fernando';

  GmailApp.sendEmail(data.email, subject, body);
}

function respond(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
