#!/usr/bin/env python3
"""Genera las imágenes Open Graph (1200x630 PNG) de cada página.
Uso:  python3 tools/make_og.py
Requiere: playwright + chromium (pip install playwright && python -m playwright install chromium).
Usa las fuentes autoalojadas de landing/assets/fonts, así que funciona sin red.
Para una página nueva, agrega una fila a PAGES y vuelve a correr el script.
"""
import pathlib, re, os, base64
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent / "landing"
OUT = ROOT / "assets" / "og"
OUT.mkdir(parents=True, exist_ok=True)


# (archivo, antetítulo, lo que se tacha, el «Haz», subtítulo)
PAGES = [
  ("home", "Marca y negocio en Venezuela", "Hacer una marca bonita", "una marca que te vuelvan a elegir", "Negocios en los que la gente confía, que recuerda y que vuelve a elegir."),
  ("blog", "Blog", "Publicar por publicar", "que cada pieza te acerque a que te elijan", "Casos reales de negocios venezolanos, con cada dato citado."),
  ("trabaja-conmigo", "Diagnóstico en Público", "Pagar por una promesa", "mira primero el caso publicado", "Tu primer resultado en 24 a 48 horas, sin costo en esta etapa."),
  ("territorio-de-marca-cashea", "Caso real", "Prometer lo que no haces en el mostrador", "reconoce a tu cliente más cumplido", "Territorio de marca: qué es realmente (el caso Cashea)."),
  ("cuando-tu-funnel-traiciona-tu-marca", "Ensayo", "Contestar primero al que todavía no te compró", "responde primero a quien ya te pagó", "Cuando tu embudo de ventas traiciona tu marca."),
  ("recursos", "Recursos", "Copiar lo que dice un libro", "toma una idea y pruébala en tu mostrador", "Mi biblioteca, con lo que tomo de cada libro."),
]

FONTS = ROOT / "assets" / "fonts"
def font_css():
    """Incrusta las mismas fuentes autoalojadas del sitio (no depende de la red)."""
    out = ""
    for fam, w, f in [("Space Grotesk", 500, "space-grotesk-latin-500-normal"), ("Space Grotesk", 700, "space-grotesk-latin-700-normal"),
                      ("Poppins", 400, "poppins-latin-400-normal"), ("Poppins", 500, "poppins-latin-500-normal")]:
        b64 = base64.b64encode((FONTS / f"{f}.woff2").read_bytes()).decode()
        out += "@font-face{font-family:'%s';font-weight:%d;src:url(data:font/woff2;base64,%s) format('woff2')}" % (fam, w, b64)
    return out

TRAZO = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 10' preserveAspectRatio='none'%3E%3Cpath d='M2 6 C 40 2, 70 9, 110 5 S 170 3, 198 6' fill='none' stroke='%232E6F40' stroke-width='3' stroke-linecap='round'/%3E%3C/svg%3E"
GRANO = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E"

# Manual de marca: crema de fondo, firma del tachado con su «Haz», logo = la palabra «Fernando» abajo a la derecha.
HTML = """<!doctype html><html><head><meta charset="utf-8"><style>%(fontcss)s
*{margin:0;padding:0;box-sizing:border-box}
body{width:1200px;height:630px;background:#F1EDE3;color:#16213A;font-family:'Poppins',sans-serif;position:relative;overflow:hidden}
body::before{content:"";position:absolute;inset:0;background-image:url("%(grano)s");opacity:.10;mix-blend-mode:multiply}
.wrap{position:absolute;inset:80px;display:flex;flex-direction:column;justify-content:space-between}
.ante{font-family:'Space Grotesk',sans-serif;font-weight:500;font-size:22px;letter-spacing:.14em;text-transform:uppercase;color:#4B5468}
.tachado{font-family:'Space Grotesk',sans-serif;font-weight:500;font-size:32px;color:#4B5468}
.tachado span{background:url("%(trazo)s") no-repeat 0 58%%/100%% 12px}
h1{font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:%(fs)spx;line-height:1.04;letter-spacing:-.02em;max-width:1000px;margin-top:10px}
h1 b{color:#2E6F40}
.pie{display:flex;justify-content:space-between;align-items:flex-end}
.sub{font-size:24px;color:#4B5468;max-width:760px;line-height:1.35}
.logo{font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:40px;letter-spacing:-.02em;color:#2E6F40}
</style></head><body>
<div class="wrap">
  <div class="ante">%(ante)s</div>
  <div><p class="tachado"><span>%(tacha)s</span></p><h1><b>Haz:</b> %(haz)s</h1></div>
  <div class="pie"><p class="sub">%(sub)s</p><span class="logo">Fernando</span></div>
</div></body></html>"""

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width":1200,"height":630})
    css = font_css()
    for name, ante, tacha, haz, sub in PAGES:
        fs = 72 if len(haz) < 34 else 60
        pg.set_content(HTML % dict(fontcss=css, grano=GRANO, trazo=TRAZO, ante=ante, tacha=tacha, haz=haz, sub=sub, fs=fs))
        pg.evaluate("document.fonts.ready")
        pg.wait_for_timeout(300)
        pg.screenshot(path=str(OUT/f"{name}.png"))
        print("ok", name)
    # Logo PNG cuadrado (para schema.org publisher.logo): la palabra «Fernando», sin ícono
    pg2 = b.new_page(viewport={"width":512,"height":512})
    pg2.set_content("<style>%s body{margin:0;width:512px;height:512px;background:#F1EDE3;display:flex;align-items:center;justify-content:center}"
                    " span{font-family:'Space Grotesk';font-weight:700;font-size:104px;letter-spacing:-.02em;color:#2E6F40}</style><body><span>Fernando</span></body>" % css)
    pg2.evaluate("document.fonts.ready"); pg2.wait_for_timeout(300)
    pg2.screenshot(path=str(ROOT/"assets"/"logo-512.png"))
    print("ok logo-512")
    b.close()
