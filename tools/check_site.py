#!/usr/bin/env python3
"""Revisión automática del sitio antes de publicar.
Uso:  python3 tools/build.py && python3 tools/check_site.py
Sale con código 1 si encuentra errores (los avisos no fallan)."""
import json, pathlib, re, sys, html
from urllib.parse import urlparse, unquote

ROOT = pathlib.Path(__file__).resolve().parent.parent
L = ROOT / "landing"
cfg = json.loads((ROOT / "tools/pages.json").read_text(encoding="utf8"))
BASE = cfg["base"]
errors, warns = [], []
E = lambda p, m: errors.append(f"[ERROR] {p}: {m}")
W = lambda p, m: warns.append(f"[aviso] {p}: {m}")

pages = sorted(L.rglob("*.html"))
ids_by_file = {}
for f in pages:
    t = f.read_text(encoding="utf8")
    ids_by_file[f] = set(re.findall(r'\bid="([^"]+)"', t))

BANNED = [r"60\+", r"8 años", r"31%\s*uplift", r"uplift prom", r"marcas posicionadas"]

for f in pages:
    rel = f.relative_to(L).as_posix()
    t = f.read_text(encoding="utf8")
    is404 = rel == "404.html"

    # --- head ---
    m = re.search(r"<title>(.*?)</title>", t, re.S)
    if not m: E(rel, "sin <title>")
    else:
        n = len(html.unescape(m.group(1)))
        if n > 65: W(rel, f"title largo ({n})")
    d = re.search(r'<meta name="description" content="([^"]*)"', t)
    if not d: E(rel, "sin meta description")
    else:
        n = len(html.unescape(d.group(1)))
        if n > 165: W(rel, f"meta description larga ({n})")
        if n < 70: W(rel, f"meta description corta ({n})")
    if not is404:
        c = re.search(r'<link rel="canonical" href="([^"]+)"', t)
        expected = BASE + ("" if rel == "index.html" else rel)
        if not c: E(rel, "sin canonical")
        elif c.group(1) != expected: E(rel, f"canonical {c.group(1)} != {expected}")
        og = re.search(r'<meta property="og:image" content="([^"]+)"', t)
        if not og: E(rel, "sin og:image")
        else:
            local = L / og.group(1).replace(BASE, "")
            if not local.exists(): E(rel, f"og:image no existe: {local.name}")
            elif not local.suffix == ".png": E(rel, "og:image no es PNG")
        for req in ["og:title", "og:description", "og:url", "og:type"]:
            if f'property="{req}"' not in t: E(rel, f"falta {req}")
        if 'name="twitter:card"' not in t: E(rel, "falta twitter:card")
    else:
        if "noindex" not in t: E(rel, "404 debe ser noindex")
    if not is404 and "noindex" in t: E(rel, "noindex inesperado")

    # --- JSON-LD ---
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', t, re.S):
        try: json.loads(block)
        except Exception as e: E(rel, f"JSON-LD inválido: {e}")
    if not is404 and "application/ld+json" not in t: E(rel, "sin JSON-LD")

    # --- estructura ---
    body = t[t.find("<body"):]
    h1 = len(re.findall(r"<h1[\s>]", body))
    if h1 != 1: E(rel, f"{h1} etiquetas <h1> (debe ser 1)")
    for im in re.findall(r"<img\b[^>]*>", body):
        if "alt=" not in im: E(rel, f"<img> sin alt: {im[:60]}")

    # --- texto visible ---
    vis = re.sub(r"<(script|style|svg)[^>]*>.*?</\1>", " ", body, flags=re.S)
    vis = re.sub(r"<[^>]+>", " ", vis)
    for pat in BANNED:
        if re.search(pat, vis, re.I): E(rel, f"cifra/afirmación no verificable presente: {pat}")
    # guiones largos en prosa (regla de estilo del proyecto)
    prose = re.sub(r"<(footer|cite)[^>]*>.*?</\1>", "", body, flags=re.S)
    prose = re.sub(r"<(script|style|svg|title)[^>]*>.*?</\1>", " ", prose, flags=re.S)
    prose = re.sub(r"<[^>]+>", " ", prose)
    if "—" in prose: W(rel, f"{prose.count('—')} guion(es) largo(s) en prosa")

    # --- enlaces y recursos internos ---
    for attr, val in re.findall(r'\b(href|src)="([^"]*)"', t):
        if val.startswith(("http://", "https://", "mailto:", "tel:", "javascript:", "data:")) or val == "":
            if val.startswith("http://"): W(rel, f"enlace http sin TLS: {val[:60]}")
            if BASE in val and val.startswith(BASE):
                tgt = val.replace(BASE, "").split("#")[0]
                if tgt and not (L / tgt).exists(): E(rel, f"enlace absoluto roto: {val}")
            continue
        u = urlparse(val)
        path = unquote(u.path)
        target = f if path == "" else (f.parent / path).resolve()
        if target.is_dir(): target = target / "index.html"
        if not target.exists():
            E(rel, f"{attr} roto: {val}")
            continue
        if u.fragment and target.suffix == ".html":
            ids = ids_by_file.get(target) or set(re.findall(r'\bid="([^"]+)"', target.read_text(encoding="utf8")))
            if u.fragment not in ids: E(rel, f"ancla inexistente: {val}")

# --- sitemap / feed ---
sm = (L / "sitemap.xml").read_text(encoding="utf8")
for loc in re.findall(r"<loc>(.*?)</loc>", sm):
    tgt = loc.replace(BASE, "")
    if not (L / (tgt or "index.html")).exists(): E("sitemap.xml", f"URL sin archivo: {loc}")
for f in pages:
    rel = f.relative_to(L).as_posix()
    if rel == "404.html": continue
    url = BASE + ("" if rel == "index.html" else rel)
    if url not in sm: E("sitemap.xml", f"falta {rel}")
if not (L / "feed.xml").exists(): E("feed.xml", "no existe")

for w in warns: print(w)
for e in errors: print(e)
print(f"\n{len(pages)} páginas revisadas · {len(errors)} errores · {len(warns)} avisos")
sys.exit(1 if errors else 0)
