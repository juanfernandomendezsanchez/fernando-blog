#!/usr/bin/env python3
"""Regenera lo que se deriva de tools/pages.json:
  - landing/sitemap.xml
  - landing/feed.xml (RSS)
  - las tarjetas de artículos en landing/index.html (últimos 3) y landing/blog.html (todos)

Flujo para publicar un artículo nuevo:
  1. Copia un artículo existente en landing/articulos/ y edítalo.
  2. Agrega su entrada en tools/pages.json (la más reciente arriba).
  3. Agrega su imagen OG en tools/make_og.py y corre make_og.py.
  4. python3 tools/build.py   y luego   python3 tools/check_site.py
"""
import json, pathlib, re, html
from datetime import datetime
from email.utils import format_datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
LANDING = ROOT / "landing"
cfg = json.loads((ROOT / "tools/pages.json").read_text(encoding="utf8"))
BASE = cfg["base"]
MESES = ["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"]

def fecha_es(iso):
    y, m, d = iso.split("-")
    return f"{int(d)} {MESES[int(m)-1]} {y}"

def esc(s): return html.escape(s, quote=True)

def card(a, prefix=""):
    circ = a["circle"]
    return f'''      <a href="{prefix}articulos/{a["slug"]}.html" class="card" data-circulo="{circ}">
        <div class="thumb thumb-illustrated"><img src="{prefix}{a["cover"]}" alt="" width="400" height="460" loading="lazy"></div>
        <span class="chip chip-{circ}">{cfg["circles"][circ]}</span>
        <h3>{esc(a["title"])}</h3>
        <p>{esc(a["description"])}</p>
        <div class="meta"><span>{fecha_es(a["date"])}</span><span>·</span><span>{a["read_min"]} min</span></div>
      </a>'''

GHOST = '''      <div class="card card-ghost">
        <div class="thumb thumb-ghost"><span>Identidad verbal</span></div>
        <h3 class="ghost-title">Próximamente</h3>
      </div>'''

def replace_block(path, start, end, content):
    p = LANDING / path
    t = p.read_text(encoding="utf8")
    pat = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    if not pat.search(t):
        raise SystemExit(f"Marcadores no encontrados en {path}: {start}")
    t = pat.sub(lambda m: start + "\n" + content + "\n      " + end, t)
    p.write_text(t, encoding="utf8")

arts = sorted(cfg["articles"], key=lambda a: a["date"], reverse=True)

# --- tarjetas ---
home = [card(a) for a in arts[:3]]
if len(home) < 3: home.append(GHOST)
replace_block("index.html", "<!-- ARTICLES:START -->", "<!-- ARTICLES:END -->", "\n".join(home))
replace_block("blog.html", "<!-- ARTICLES:START -->", "<!-- ARTICLES:END -->", "\n".join(card(a) for a in arts))

# --- sitemap ---
urls = []
for s in cfg["static"]:
    urls.append((BASE + s["path"], s["lastmod"]))
for a in arts:
    urls.append((f'{BASE}articulos/{a["slug"]}.html', a["modified"]))
sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
for loc, last in urls:
    sm.append(f"  <url>\n    <loc>{esc(loc)}</loc>\n    <lastmod>{last}</lastmod>\n  </url>")
sm.append("</urlset>\n")
(LANDING / "sitemap.xml").write_text("\n".join(sm), encoding="utf8")

# --- robots ---
(LANDING / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {BASE}sitemap.xml\n", encoding="utf8")

# --- RSS ---
items = []
for a in arts:
    dt = datetime.fromisoformat(a["date"] + "T09:00:00-04:00")
    link = f'{BASE}articulos/{a["slug"]}.html'
    items.append(f'''    <item>
      <title>{esc(a["title"])}</title>
      <link>{esc(link)}</link>
      <guid isPermaLink="true">{esc(link)}</guid>
      <pubDate>{format_datetime(dt)}</pubDate>
      <description>{esc(a["description"])}</description>
    </item>''')
last = format_datetime(datetime.fromisoformat(arts[0]["modified"] + "T09:00:00-04:00"))
feed = f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{esc(cfg["site_name"])}</title>
    <link>{esc(BASE)}</link>
    <atom:link href="{esc(BASE)}feed.xml" rel="self" type="application/rss+xml"/>
    <description>Blog de estrategia de marca para negocios venezolanos: posicionamiento, identidad verbal y casos analizados en público.</description>
    <language>es</language>
    <lastBuildDate>{last}</lastBuildDate>
{chr(10).join(items)}
  </channel>
</rss>
'''
(LANDING / "feed.xml").write_text(feed, encoding="utf8")
print("build ok:", len(arts), "artículos,", len(urls), "URLs en sitemap")
