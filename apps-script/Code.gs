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
 *
 * ─── NOTAS DE SEGURIDAD ───────────────────────────────────────────
 * - No hay ninguna API key en este proyecto (no se usa ningún
 *   servicio de terceros de pago), por lo tanto no hay ninguna que
 *   ocultar.
 * - No se usan cookies en ningún punto del sitio ni de este script.
 * - "Seguridad a nivel de fila" y "consultas parametrizadas" son
 *   conceptos de bases de datos SQL; Google Sheets no es una base
 *   SQL, así que no aplican tal cual. El riesgo real y equivalente
 *   en Sheets es la inyección de fórmulas (alguien escribe "=ALGO()"
 *   como su nombre) — por eso sanitize() neutraliza esos casos antes
 *   de guardar cualquier campo.
 * - El acceso de lectura a la hoja sigue siendo privado (solo tu
 *   cuenta de Google): este script únicamente permite ESCRIBIR una
 *   fila nueva vía POST, nunca leer datos existentes.
 * - Cifrado: Google ya cifra los datos en reposo y en tránsito
 *   (HTTPS) a nivel de infraestructura. Cifrar además campos
 *   individuales aquí te impediría leer tus propios leads sin
 *   construir una pantalla de descifrado — no vale la pena para
 *   este caso de uso.
 * ────────────────────────────────────────────────────────────────
 */

// ─── CONFIGURACIÓN ───────────────────────────────────────────────
const SHEET_ID = '1xiI72IZpZs4FZYhVOSt0_uo5QPdJbaZqMAVzrB7dgvw';
const SHEET_NAME = 'leads';
const NOTIFY_EMAIL = 'juanfernandomendezsanchez@gmail.com';
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
    console.log('doPost recibido. postData:', e.postData ? e.postData.contents : '(sin postData)');
    console.log('e.parameter:', JSON.stringify(e.parameter));

    const data = parseRequest(e);
    console.log('Datos interpretados:', JSON.stringify(data));

    // ─── Protección anti-bot (gratis, sin servicios de terceros) ───
    // 1. Honeypot: un campo oculto que los humanos nunca llenan, pero
    //    los bots que rellenan formularios automáticamente sí.
    if (data.sitio_web) {
      console.log('Honeypot activado — descartado silenciosamente (probable bot).');
      return respond({ ok: true }); // Respondemos éxito falso para no delatar el filtro al bot.
    }
    // 2. Tiempo mínimo: un humano tarda al menos unos segundos en
    //    llenar el formulario; un bot lo hace casi instantáneamente.
    const cargaTs = parseInt(data.form_ts, 10);
    if (cargaTs && (Date.now() - cargaTs) < 2000) {
      console.log('Envío demasiado rápido — descartado silenciosamente (probable bot).');
      return respond({ ok: true });
    }

    const errors = validate(data);
    if (errors.length > 0) {
      console.log('Validación falló:', JSON.stringify(errors));
      return respond({ ok: false, errors: errors });
    }

    // Sanear cada campo: recorta longitud y neutraliza inyección de
    // fórmulas en Sheets (si alguien escribe "=ALGO(...)" como nombre,
    // por ejemplo, Sheets lo ejecutaría como fórmula si no se escapa).
    const clean = {
      nombre: sanitize(data.nombre, 120),
      empresa: sanitize(data.empresa, 120),
      email: sanitize(data.email, 160),
      telefono: sanitize(data.telefono, 40),
      necesidad: sanitize(data.necesidad, 120),
      descripcion: sanitize(data.descripcion, 200),
      mensaje: sanitize(data.mensaje, 200)
    };

    console.log('Abriendo sheet con SHEET_ID:', SHEET_ID);
    const sheet = SpreadsheetApp.openById(SHEET_ID).getSheetByName(SHEET_NAME);
    if (!sheet) {
      console.log('ERROR: no se encontró una pestaña llamada "' + SHEET_NAME + '"');
      return respond({ ok: false, error: 'sheet_no_encontrada' });
    }
    ensureHeaders(sheet);

    const estadoInicial = classifyLead(clean);

    sheet.appendRow([
      new Date(),
      clean.nombre,
      clean.empresa || '',
      clean.email,
      clean.telefono || '',
      clean.necesidad || '',
      clean.descripcion || '',
      clean.mensaje || '',
      estadoInicial
    ]);
    console.log('Fila agregada correctamente.');

    sendOwnerNotification(clean);
    console.log('Correo de notificación enviado a', NOTIFY_EMAIL);

    if (SEND_USER_CONFIRMATION && clean.email) {
      sendConfirmationToUser(clean);
      console.log('Correo de confirmación enviado a', clean.email);
    }

    return respond({ ok: true });

  } catch (err) {
    console.log('ERROR atrapado en doPost:', String(err));
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
  if (!data.nombre || data.nombre.toString().trim().length < 2) errors.push('nombre');
  if (!data.email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email)) errors.push('email');
  // Límite generoso de longitud contra abuso (nadie legítimo escribe
  // un nombre de 5000 caracteres).
  if (data.nombre && data.nombre.toString().length > 300) errors.push('nombre_muy_largo');
  if (data.mensaje && data.mensaje.toString().length > 3000) errors.push('mensaje_muy_largo');
  return errors;
}

/**
 * Recorta a un largo máximo y neutraliza inyección de fórmulas en
 * Google Sheets: si un campo empieza con =, +, -, @ (los caracteres
 * que Sheets interpreta como inicio de fórmula), le antepone un
 * apóstrofe para forzar que se guarde como texto plano, nunca como
 * fórmula ejecutable. Es el equivalente, en este stack, a "escapar"
 * o "parametrizar" una consulta en una base de datos SQL.
 */
function sanitize(value, maxLength) {
  if (value === undefined || value === null) return '';
  let text = value.toString().trim();
  if (/^[=+\-@]/.test(text)) {
    text = "'" + text;
  }
  if (maxLength && text.length > maxLength) {
    text = text.substring(0, maxLength);
  }
  return text;
}

/**
 * Crea la fila de encabezados si la hoja está vacía.
 */
/**
 * Crea la fila de encabezados si la hoja está vacía, o migra una hoja
 * ya existente (creada antes de que agregáramos Teléfono) insertando
 * esa columna en el lugar correcto — sin tocar los leads ya guardados.
 */
function ensureHeaders(sheet) {
  const fullHeaders = ['Fecha', 'Nombre', 'Empresa', 'Email', 'Teléfono', 'Necesidad', 'Descripción', 'Mensaje', 'Estado'];

  if (sheet.getLastRow() === 0) {
    sheet.appendRow(fullHeaders);
    return;
  }

  const currentHeaders = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  if (currentHeaders.indexOf('Teléfono') === -1) {
    // La hoja es de antes de agregar este campo: insertamos la columna
    // Teléfono justo después de Email (columna D = 4), sin mover ni
    // borrar ninguna fila existente.
    sheet.insertColumnAfter(4);
    sheet.getRange(1, 5).setValue('Teléfono');
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
    `Teléfono: ${data.telefono || '—'}\n` +
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
