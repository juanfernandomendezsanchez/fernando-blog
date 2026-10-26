// Fernando · Backend de la web (Google Apps Script + Sheets + Gmail)
const SHEET_ID = '1xiI72IZpZs4FZYhVOSt0_uo5QPdJbaZqMAVzrB7dgvw';
const SHEET_NAME = 'Leads';
const RATING_SHEET_NAME = 'valoraciones';
const NEWSLETTER_SHEET_NAME = 'newsletter';
const NOTIFY_EMAIL = 'frnandosoy@gmail.com';
const SEND_USER_CONFIRMATION = true;
const SENDER_NAME = 'Fernando';
const WHATSAPP = '+58 422-123-4881';

function doPost(e) {
  try {
    const data = parseRequest(e);
    if (data.sitio_web) return respond({ ok: true });                       // anti-bot
    const ts = parseInt(data.form_ts, 10);
    if (ts && (Date.now() - ts) < 2000) return respond({ ok: true });     // anti-bot
    if (data.tipo === 'valoracion') return handleRating(data);
    if (data.tipo === 'newsletter') return handleNewsletter(data);

    const errors = validate(data);
    if (errors.length) return respond({ ok: false, errors: errors });

    const c = {
      nombre: sanitize(data.nombre, 120), empresa: sanitize(data.empresa, 120),
      email: sanitize(data.email, 160), telefono: sanitize(data.telefono, 40),
      necesidad: sanitize(data.necesidad, 120), descripcion: sanitize(data.descripcion, 200),
      mensaje: sanitize(data.mensaje, 200)
    };

    const book = SpreadsheetApp.openById(SHEET_ID);
    let sheet = book.getSheetByName(SHEET_NAME) || book.getSheetByName(SHEET_NAME.toLowerCase());
    if (!sheet) sheet = book.insertSheet(SHEET_NAME);
    ensureHeaders(sheet);
    sheet.setFrozenRows(1);
    sheet.appendRow([new Date(), c.nombre, c.empresa, c.email, c.telefono, c.necesidad, c.descripcion, c.mensaje, 'Nuevo']);

    sendOwnerNotification(c);
    if (SEND_USER_CONFIRMATION && c.email) sendConfirmationToUser(c);
    return respond({ ok: true });
  } catch (err) {
    console.log('ERROR doPost:', String(err));
    return respond({ ok: false, error: String(err) });
  }
}

function doGet() {
  return respond({ ok: true, message: 'Endpoint de diagnósticos activo.' });
}

function parseRequest(e) {
  if (e.postData && e.postData.contents) {
    try { return JSON.parse(e.postData.contents); } catch (err) {}
  }
  return (e.parameter && Object.keys(e.parameter).length) ? e.parameter : {};
}

function handleRating(data) {
  const p = parseInt(data.puntuacion, 10), art = sanitize(data.articulo, 200);
  if (!art || !p || p < 1 || p > 5) return respond({ ok: false, error: 'valoracion_invalida' });
  const book = SpreadsheetApp.openById(SHEET_ID);
  let s = book.getSheetByName(RATING_SHEET_NAME);
  if (!s) { s = book.insertSheet(RATING_SHEET_NAME); s.appendRow(['Fecha', 'Artículo', 'Puntuación']); s.setFrozenRows(1); }
  s.appendRow([new Date(), art, p]);
  return respond({ ok: true });
}

function handleNewsletter(data) {
  const email = sanitize(data.email, 160).toLowerCase(), fuente = sanitize(data.fuente, 80);
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return respond({ ok: false, error: 'email_invalido' });
  const book = SpreadsheetApp.openById(SHEET_ID);
  let s = book.getSheetByName(NEWSLETTER_SHEET_NAME);
  if (!s) { s = book.insertSheet(NEWSLETTER_SHEET_NAME); s.appendRow(['Fecha', 'Email', 'Fuente']); s.setFrozenRows(1); }
  const last = s.getLastRow();
  if (last > 1) {
    const ya = s.getRange(2, 2, last - 1, 1).getValues().map(function (f) { return f[0].toString().toLowerCase(); });
    if (ya.indexOf(email) !== -1) return respond({ ok: true, duplicado: true });
  }
  s.appendRow([new Date(), email, fuente]);
  return respond({ ok: true });
}

function validate(d) {
  const e = [];
  if (!d || typeof d !== 'object') return ['payload_invalido'];
  if (!d.nombre || d.nombre.toString().trim().length < 2) e.push('nombre');
  if (!d.email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(d.email)) e.push('email');
  if (d.nombre && d.nombre.toString().length > 300) e.push('nombre_muy_largo');
  if (d.mensaje && d.mensaje.toString().length > 3000) e.push('mensaje_muy_largo');
  return e;
}

function sanitize(v, max) {
  if (v === undefined || v === null) return '';
  let t = v.toString().trim();
  if (/^[=+\-@]/.test(t)) t = "'" + t;          // evita fórmulas en Sheets
  return (max && t.length > max) ? t.substring(0, max) : t;
}

function ensureHeaders(sheet) {
  const h = ['Fecha', 'Nombre', 'Empresa', 'Email', 'Teléfono', 'Necesidad', 'Descripción', 'Mensaje', 'Estado'];
  if (sheet.getLastRow() === 0) { sheet.appendRow(h); return; }
  const actuales = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  if (actuales.indexOf('Teléfono') === -1) { sheet.insertColumnAfter(4); sheet.getRange(1, 5).setValue('Teléfono'); }
}

function sendOwnerNotification(d) {
  const body =
    'Nueva postulación al Diagnóstico en Público:\n\n' +
    'Nombre: ' + d.nombre + '\nEmpresa: ' + (d.empresa || '—') + '\nEmail: ' + d.email +
    '\nTeléfono: ' + (d.telefono || '—') + '\nNecesidad: ' + (d.necesidad || '—') +
    '\nDescripción: ' + (d.descripcion || '—') + '\nMensaje: ' + (d.mensaje || '—') +
    '\n\nYa quedó guardado en la pestaña Leads con estado "Nuevo".';
  GmailApp.sendEmail(NOTIFY_EMAIL, 'Nueva postulación: ' + d.nombre, body, { name: SENDER_NAME, replyTo: d.email });
}

function sendConfirmationToUser(d) {
  const nombre = (d.nombre || '').trim().split(' ')[0];
  const body =
    '¡Hola ' + nombre + '!\n\n' +
    'Gracias por escribirme. Recibí tu postulación al Diagnóstico en Público. ' +
    'La reviso personalmente y en 24 a 48 horas te envío tu primer resultado: ' +
    'las mejoras que tu marca necesita primero. Después agendamos una llamada corta ' +
    'para conocer tu negocio y tu cliente.\n\n' +
    'Si quieres adelantar algo, escríbeme por WhatsApp al ' + WHATSAPP + ' o responde este correo.\n\n' +
    'Fernando';
  GmailApp.sendEmail(d.email, 'Recibí tu solicitud, ' + nombre, body, { name: SENDER_NAME, replyTo: NOTIFY_EMAIL });
}

function respond(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

// Ejecuta esta función una vez desde el editor para autorizar permisos y probar.
function probar() {
  const r = doPost({ postData: { contents: JSON.stringify({
    nombre: 'Prueba Fernando', email: NOTIFY_EMAIL, telefono: WHATSAPP,
    necesidad: 'Prueba', descripcion: 'Prueba', mensaje: 'Prueba desde el editor' }) } });
  console.log(r.getContent());
}
