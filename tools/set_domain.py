#!/usr/bin/env python3
"""Cambia el dominio base de todo el sitio (canonical, og:*, JSON-LD, sitemap, robots, feed).
Uso:  python3 tools/set_domain.py https://tudominio.com/
Después:  python3 tools/build.py && python3 tools/check_site.py
Además crea landing/CNAME (necesario para dominio propio en GitHub Pages).
Nota: con dominio propio en la raíz, robots.txt y sitemap.xml SÍ son leídos por Google
(en github.io/fernando-blog/ no, porque robots.txt debe vivir en la raíz del host)."""
import json, pathlib, sys
from urllib.parse import urlparse

ROOT = pathlib.Path(__file__).resolve().parent.parent
if len(sys.argv) != 2 or not sys.argv[1].startswith("https://"):
    sys.exit("Uso: python3 tools/set_domain.py https://tudominio.com/")
new = sys.argv[1].rstrip("/") + "/"
cfgp = ROOT / "tools/pages.json"
cfg = json.loads(cfgp.read_text(encoding="utf8"))
old = cfg["base"]
if old == new:
    sys.exit("Ya está configurado ese dominio.")
n = 0
for p in list((ROOT / "landing").rglob("*")) + [cfgp, ROOT / "README.md"]:
    if p.is_file() and p.suffix in {".html", ".xml", ".txt", ".json", ".md", ".js"}:
        t = p.read_text(encoding="utf8")
        if old in t:
            p.write_text(t.replace(old, new), encoding="utf8"); n += 1
(ROOT / "landing/CNAME").write_text(urlparse(new).netloc + "\n", encoding="utf8")
print(f"{n} archivos actualizados. Base: {new}")
