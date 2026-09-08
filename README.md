# Fernando — Estrategia de marca

Sitio tipo blog para Fernando, estratega de marca. Landing editorial con hero, pilares de contenido, blog, biblioteca de recursos, formulario de diagnóstico y captura de newsletter.

## Estructura del repositorio

```
/
├── landing/              ← el sitio web (esto es lo que Netlify publica)
│   ├── index.html        ← página de inicio
│   ├── recursos.html     ← biblioteca de recursos (acordeón)
│   ├── 404.html          ← página de error personalizada
│   ├── robots.txt
│   ├── sitemap.xml
│   ├── assets/           ← logos, favicon, ilustraciones
│   └── articulos/        ← cada entrada del blog, un archivo .html
│       └── territorio-de-marca-cashea.html
│
├── automatizaciones/     ← backend, nunca se publica como web
│   ├── Code.gs           ← Google Apps Script (Sheets + Gmail)
│   └── SETUP.md          ← guía paso a paso para desplegarlo
│
├── netlify.toml          ← le dice a Netlify que publique landing/
└── README.md
```

**¿Por qué esta separación?** `landing/` contiene únicamente archivos que Netlify sirve como parte del sitio. `automatizaciones/` es código que corre en Google Apps Script, no en el navegador — nunca debe quedar accesible como página web, así que vive fuera de la carpeta publicada.

## Publicar un artículo nuevo

1. Crea el archivo en `landing/articulos/tu-articulo.html` (puedes copiar la estructura de `territorio-de-marca-cashea.html` como plantilla: mismo head SEO, mismo header/footer, mismo sistema de valoración por estrellas).
2. Todos los enlaces internos (`href="/index.html"`, `href="/recursos.html"`, `src="/assets/..."`) usan **ruta absoluta desde la raíz** (empiezan con `/`) — así no importa la profundidad de carpetas, siempre apuntan al mismo lugar.
3. Agrega la tarjeta del artículo en `landing/index.html`, dentro de `<section class="articles" id="articulos">`.
4. Agrega la URL nueva a `landing/sitemap.xml`.

## Hosting

El sitio se publica en **GitHub Pages** vía GitHub Actions (`.github/workflows/deploy-pages.yml`), que toma solo la carpeta `landing/` y la publica en cada push a `main`. Se usa Actions en vez de la configuración clásica de Pages porque esta última solo admite publicar desde la raíz del repo o desde `/docs`, y aquí el sitio vive en `/landing`.

URL: `https://juanfernandomendezsanchez.github.io/fernando-blog/`

Para activarlo (una sola vez): **Settings → Pages → Source: GitHub Actions** (no "Deploy from a branch").

## Uso local

Abrir `landing/index.html` directamente en el navegador, o servir la carpeta `landing/` con cualquier servidor estático.

## Backend del formulario ($0)

Para que "Agendar diagnóstico" y las valoraciones de artículos funcionen de verdad, sigue `automatizaciones/SETUP.md` — toma unos 10 minutos y no requiere ningún servicio de pago (Google Apps Script + Google Sheets + Gmail, dentro de las cuotas gratuitas).
