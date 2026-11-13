# fernando-blog (redirecciones)

Este repo solo existe para que las direcciones viejas
`https://juanfernandomendezsanchez.github.io/fernando-blog/…` lleven a **https://dimefernando.com/**.
El sitio real vive en el repo privado `dimefernando-web`.

Cada página tiene meta refresh de 0 segundos (Google lo trata como redirección permanente),
`rel="canonical"` al destino, `noindex` y un enlace visible por si el navegador no redirige.
`404.html` manda cualquier otra dirección a la portada.

Se genera desde el repo del sitio con `python3 tools/make_redirects.py` (lee `landing/sitemap.xml`).
No lo edites a mano: regenera y copia.

## Pasos (en este orden)

Lo importante es el orden: el repo nuevo no puede llamarse `fernando-blog` mientras el viejo tenga ese nombre,
y apenas renombras el viejo, la dirección github.io deja de responder hasta que publiques el nuevo.
Hazlo todo seguido (son unos 10 minutos).

### 1. Renombrar el repo actual

1. GitHub → `juanfernandomendezsanchez/fernando-blog` → **Settings → General → Repository name** →
   `dimefernando-web` → **Rename**.
2. En el mismo repo: **Settings → Pages** → si aparece una publicación activa, **Unpublish site**
   (o en *Source* elige *None*). Si no, GitHub seguiría publicando una copia en `/dimefernando-web/`.
3. Cloudflare Pages: **Workers & Pages → el proyecto → Settings → Builds → Git repository**.
   Confirma que sigue conectado (GitHub avisa del cambio de nombre; si dice desconectado, vuelve a conectarlo
   a `dimefernando-web`). Haz un *Retry deployment* para comprobar.
4. Actualiza los remotos de cada copia local **antes** del paso 2 (cuando exista el repo nuevo,
   la redirección automática de GitHub del nombre viejo desaparece y `git push` iría al repo de redirecciones):

   ```bash
   git remote set-url origin https://github.com/juanfernandomendezsanchez/dimefernando-web.git
   git remote -v
   ```

   Hay copias en `Documents/fernando-blog` y `proyectos/fernando-blog`.
   `crm/iniciar.py` ya apunta a `dimefernando-web`.

### 2. Crear el repo nuevo

1. GitHub → **New repository** → nombre `fernando-blog`, **Public**, sin README ni licencia.
2. Desde la carpeta `redirect-repo/` del repo del sitio:

   ```bash
   cd redirect-repo
   git init -b main
   git add .
   git commit -m "Redirecciones de github.io a dimefernando.com"
   git remote add origin https://github.com/juanfernandomendezsanchez/fernando-blog.git
   git push -u origin main
   ```

   (O copia el contenido de `redirect-repo/` a una carpeta aparte y haz ahí el `git init`,
   para no tener un repo dentro de otro.)

### 3. Activar GitHub Pages

**Settings → Pages → Build and deployment → Source: Deploy from a branch → Branch: `main` / `(root)` → Save.**
Espera 1 o 2 minutos hasta que diga *Your site is live at …github.io/fernando-blog/*.

### 4. Comprobar con curl

Cada URL vieja debe responder `200` y traer el refresh al destino correcto:

```bash
while read u; do
  printf '%s\n  -> ' "$u"
  curl -s "$u" | grep -o 'url=[^"]*' || echo "SIN REDIRECCIÓN"
done < urls.txt
```

Esperado (la última línea es una dirección inventada; GitHub responde 404 con `404.html`, que lleva a la portada):

```
https://juanfernandomendezsanchez.github.io/fernando-blog/index.html
  -> url=https://dimefernando.com/
https://juanfernandomendezsanchez.github.io/fernando-blog/blog.html
  -> url=https://dimefernando.com/blog.html
…
https://juanfernandomendezsanchez.github.io/fernando-blog/no-existe.html
  -> url=https://dimefernando.com/
```

Para ver el código HTTP: `curl -s -o /dev/null -w '%{http_code}\n' URL` (200 en las páginas, 404 en la inventada).

### 5. Después

- Search Console: agrega o revisa la propiedad `https://dimefernando.com/` y envía `sitemap.xml`.
  (La propiedad de github.io no admite la herramienta *Cambio de dirección*: es un subdirectorio.)
- Deja este repo público y sin tocar al menos un año.
- Ya puedes poner `dimefernando-web` en privado.
