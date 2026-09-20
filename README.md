# Fernando — Estrategia de marca

Blog y sitio personal de Fernando, estratega de marca. Estructura del sitio organizada por el método de tres círculos
(Marca, Función, Contenido): home, blog, Diagnóstico en Público (`trabaja-conmigo.html`), recursos, artículos.

## Estructura del repositorio

```
/
├── landing/                 ← el sitio web (lo único que se publica)
│   ├── index.html · blog.html · trabaja-conmigo.html · recursos.html · privacidad.html · 404.html
│   ├── articulos/           ← un .html por artículo
│   ├── assets/
│   │   ├── site.css · site.js   ← estilos y comportamiento compartidos (newsletter, filtros)
│   │   ├── fonts/               ← Poppins + Space Grotesk autoalojadas (sin Google Fonts)
│   │   └── og/                  ← imágenes 1200x630 PNG para compartir en WhatsApp/LinkedIn/X
│   ├── sitemap.xml · feed.xml · robots.txt   ← GENERADOS por tools/build.py (no editar a mano)
├── automatizaciones/        ← Google Apps Script (Code.gs) + SETUP.md
├── tools/                   ← scripts de mantenimiento (ver abajo)
├── crm/                     ← CRM propio de la marca personal (app Python aparte, ver crm/README.md)
└── .github/workflows/deploy-pages.yml
```

## Publicar un artículo nuevo (5 pasos)

1. Copia un artículo existente de `landing/articulos/` y edítalo (título, texto, fuentes con enlace).
2. Agrega su entrada en `tools/pages.json` (slug, título, descripción de 120 a 155 caracteres, fecha, minutos, círculo, portada).
3. Agrega su imagen OG en `tools/make_og.py` (lista `PAGES`) y corre `python3 tools/make_og.py`.
4. Corre `python3 tools/build.py` (regenera sitemap, feed y tarjetas de home y blog).
5. Corre `python3 tools/check_site.py`: debe decir 0 errores. Luego haz push a `main`.

Regla editorial: ningún dato sin fuente enlazada.

## Herramientas (`tools/`)

- `build.py`: sitemap, feed RSS, robots y tarjetas de artículos a partir de `pages.json`.
- `check_site.py`: revisa títulos, descripciones, canonical, OG, JSON-LD, enlaces rotos, anclas y cifras no verificables.
- `make_og.py`: genera las imágenes OG (requiere playwright; ver comentarios del archivo).
- `set_domain.py`: cambia el dominio base cuando compres uno propio.

## Hosting

GitHub Pages vía GitHub Actions: publica solo `landing/` en cada push a `main`.
URL actual: `https://juanfernandomendezsanchez.github.io/fernando-blog/`

## Backend de formularios ($0)

Diagnóstico en Público, newsletter y valoraciones de artículos van al mismo Google Apps Script
(`automatizaciones/Code.gs`). Tras cambiar `Code.gs` hay que **republicar una nueva versión** (ver `SETUP.md`).
Pestañas del Sheet: `leads`, `valoraciones` y `newsletter` (se crea sola con la primera suscripción).

## CRM (`crm/`)

Aplicación Python aparte (FastAPI + SQLModel) para gestionar leads, oportunidades, propuestas
y cobros de la marca personal. No se publica junto al sitio: corre local o en su propio servidor.
Ver `crm/README.md` para instalarlo, correrlo y saber qué está construido y qué falta.
