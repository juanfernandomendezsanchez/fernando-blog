#!/usr/bin/env python3
"""Genera las imágenes Open Graph (1200x630 PNG) de cada página.
Uso:  python3 tools/make_og.py
Requiere: playwright + chromium. Las fuentes se cargan de Google Fonts.
Sin red: define SPACE_GROTESK_DIR con la carpeta de @fontsource/space-grotesk/files
(npm i @fontsource/space-grotesk) y se incrustan en base64.
Para una página nueva, agrega una fila a PAGES y vuelve a correr el script.
"""
import pathlib, re, os, base64
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent / "landing"
OUT = ROOT / "assets" / "og"
OUT.mkdir(parents=True, exist_ok=True)

logo = re.search(r'<path[^>]*d="([^"]+)"', (ROOT/"assets/logo-verde.svg").read_text(encoding="utf8")).group(1)

# (archivo, kicker, título, subtítulo)
PAGES = [
  ("home", "Estrategia de marca", "Marcas que se vuelven <em>inevitables</em>.", "Posicionamiento, identidad verbal y casos reales de marcas venezolanas."),
  ("blog", "Blog", "Estrategia de marca, sin relleno.", "Casos reales, marcos aplicables y datos con fuente."),
  ("trabaja-conmigo", "Diagnóstico en Público", "Postula tu marca. La analizo en público.", "Estrategia de marca con el razonamiento a la vista."),
  ("territorio-de-marca-cashea", "Caso · Territorio de marca", "Territorio de marca: qué es realmente <em>(el caso Cashea)</em>", "Una batidora, un señor de 75 años y una app venezolana."),
  ("cuando-tu-funnel-traiciona-tu-marca", "Ensayo · Funnel y marca", "Cuando tu funnel <em>traiciona</em> tu marca", "Con datos de Amazon, Ticketmaster y Edelman."),
  ("recursos", "Recursos", "Los libros detrás del método.", "Ventas, branding y estrategia."),
]

def font_css():
    d = os.environ.get("SPACE_GROTESK_DIR")
    if not d:
        return ""
    out = ""
    for w in (500, 700):
        f = pathlib.Path(d) / f"space-grotesk-latin-{w}-normal.woff2"
        b64 = base64.b64encode(f.read_bytes()).decode()
        out += "@font-face{font-family:'Space Grotesk';font-weight:%d;src:url(data:font/woff2;base64,%s) format('woff2')}" % (w, b64)
    return out

HTML = """<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Poppins:wght@400;600&display=swap" rel="stylesheet">
<style>%(fontcss)s
*{margin:0;padding:0;box-sizing:border-box}
body{width:1200px;height:630px;background:#FAF8F3;color:#16213A;font-family:'Poppins',sans-serif;position:relative;overflow:hidden}
.bar{position:absolute;left:0;top:0;bottom:0;width:22px;background:#2E6F40}
.mark{position:absolute;right:-120px;bottom:-170px;width:620px;height:620px;opacity:.09}
.wrap{position:absolute;left:84px;right:84px;top:64px;bottom:64px;display:flex;flex-direction:column;justify-content:space-between}
.kicker{font-size:22px;letter-spacing:.16em;text-transform:uppercase;color:#2E6F40;font-weight:600}
h1{font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:%(fs)spx;line-height:1.08;letter-spacing:-.02em;max-width:930px}
h1 em{font-style:normal;color:#2E6F40}
.sub{font-size:27px;color:#4B5468;margin-top:22px;max-width:820px;line-height:1.35}
.foot{display:flex;align-items:center;gap:16px;font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:30px}
.foot svg{width:54px;height:54px;fill:#2E6F40}
.foot span{font-weight:500;color:#4B5468;font-size:22px;font-family:'Poppins',sans-serif}
</style></head><body>
<div class="bar"></div>
<svg class="mark" viewBox="0 0 1080 1080"><path fill="#2E6F40" d="%(logo)s"/></svg>
<div class="wrap">
  <div class="kicker">%(kicker)s</div>
  <div><h1>%(title)s</h1><p class="sub">%(sub)s</p></div>
  <div class="foot"><svg viewBox="0 0 1080 1080"><path d="%(logo)s"/></svg>Fernando<span>Estrategia de marca</span></div>
</div></body></html>"""

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width":1200,"height":630})
    for name, kicker, title, sub in PAGES:
        plain = re.sub(r"<[^>]+>", "", title)
        fs = 76 if len(plain) < 45 else 62
        pg.set_content(HTML % dict(fontcss=font_css(), logo=logo, kicker=kicker, title=title, sub=sub, fs=fs), wait_until="networkidle")
        pg.wait_for_timeout(400)
        pg.screenshot(path=str(OUT/f"{name}.png"))
        print("ok", name)
    # Logo PNG cuadrado (para schema.org publisher.logo)
    pg2 = b.new_page(viewport={"width":512,"height":512})
    pg2.set_content('<body style="margin:0;background:#fff"><svg viewBox="0 0 1080 1080" width="512" height="512"><path fill="#2E6F40" d="%s"/></svg></body>' % logo)
    pg2.screenshot(path=str(ROOT/"assets"/"logo-512.png"))
    print("ok logo-512")
    b.close()
