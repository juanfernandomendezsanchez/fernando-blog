/* Comportamiento compartido: formularios de newsletter + filtros del blog.
   Sin dependencias. El endpoint es el mismo Apps Script de los formularios. */
(function () {
  var ENDPOINT = "https://script.google.com/macros/s/AKfycbx5i8XMYxFKpF6WBA0KzsKM-nyVudr5Qgn9AxVWcgi_GqYcEQ2XSsv7sSO71ugtxLIL3A/exec";
  var loadedAt = Date.now();

  function setStatus(el, msg, cls) {
    if (!el) return;
    el.textContent = msg;
    el.className = "news-status" + (cls ? " " + cls : "");
  }

  // Envío clásico por iframe oculto: no depende de CORS (mismo fallback que el formulario de diagnóstico).
  function viaIframe(payload) {
    var name = "nl-frame-" + Date.now();
    var iframe = document.createElement("iframe");
    iframe.name = name; iframe.style.display = "none"; iframe.title = "envío en segundo plano";
    var f = document.createElement("form");
    f.method = "POST"; f.action = ENDPOINT; f.target = name; f.style.display = "none";
    Object.keys(payload).forEach(function (k) {
      var i = document.createElement("input");
      i.type = "hidden"; i.name = k; i.value = payload[k]; f.appendChild(i);
    });
    document.body.appendChild(iframe); document.body.appendChild(f); f.submit();
    setTimeout(function () { f.remove(); iframe.remove(); }, 4000);
  }

  function initNewsletter(form) {
    var input = form.querySelector('input[type="email"]');
    var button = form.querySelector("button");
    var status = form.querySelector(".news-status");
    var hp = form.querySelector(".news-hp input");
    var label = button.textContent;

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var email = input.value.trim();
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        setStatus(status, "Revisa tu correo e inténtalo de nuevo.", "err"); return;
      }
      var payload = {
        tipo: "newsletter", email: email,
        fuente: form.getAttribute("data-fuente") || location.pathname,
        sitio_web: hp ? hp.value : "", form_ts: String(loadedAt)
      };
      button.disabled = true; button.textContent = "Enviando…"; setStatus(status, "");

      var done = function (ok) {
        button.disabled = false; button.textContent = label;
        if (ok) {
          document.dispatchEvent(new CustomEvent("newsletter:ok"));
          form.reset();
          setStatus(status, "Listo. Te escribo cuando publique el próximo artículo. Mientras tanto, ", "ok");
          // Siguiente paso del embudo: quien se suscribe ya confía un poco; se le muestra cómo trabajo.
          var next = document.createElement("a");
          next.href = (location.pathname.indexOf("/articulos/") > -1 ? "../" : "") + "trabaja-conmigo.html";
          next.textContent = "mira cómo trabajo";
          if (status) status.appendChild(next);
        }
        else { setStatus(status, "No pude guardarlo. Escríbeme a frnandosoy@gmail.com y te agrego a mano.", "err"); }
      };

      fetch(ENDPOINT, { method: "POST", body: JSON.stringify(payload) })
        .then(function (r) { return r.json(); })
        .then(function (res) { done(!!(res && res.ok)); })
        .catch(function () { viaIframe(payload); setTimeout(function () { done(true); }, 1200); });
    });
  }

  function initFilters(root) {
    var buttons = root.querySelectorAll("[data-filter]");
    var cards = document.querySelectorAll("[data-circulo]");
    buttons.forEach(function (b) {
      b.addEventListener("click", function () {
        var v = b.getAttribute("data-filter");
        buttons.forEach(function (x) { x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
        var shown = 0;
        cards.forEach(function (c) {
          c.hidden = !(v === "todos" || c.getAttribute("data-circulo") === v);
          if (!c.hidden) shown++;
        });
        var empty = document.querySelector("[data-filter-empty]");
        if (empty) empty.hidden = shown > 0;
      });
    });
    // /blog.html?circulo=marca abre el filtro ya aplicado
    try {
      var pre = new URLSearchParams(location.search).get("circulo");
      var target = pre && root.querySelector('[data-filter="' + pre + '"]');
      if (target) target.click();
    } catch (e) {}
  }

  document.querySelectorAll("form[data-newsletter]").forEach(initNewsletter);
  var f = document.querySelector("[data-filters]"); if (f) initFilters(f);
})();

/* ---------- Modo oscuro: toggle + persistencia ---------- */
(function () {
  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    try { localStorage.setItem("theme", theme); } catch (e) {}
  }
  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".theme-toggle").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var current = document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
        applyTheme(current === "dark" ? "light" : "dark");
      });
    });
  });
})();

/* ---------- La firma animada: el tachado se dibuja una sola vez al verse (manual, regla 7) ---------- */
(function () {
  var els = document.querySelectorAll("[data-anim]");
  if (!els.length) return;
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduce || !("IntersectionObserver" in window)) {
    els.forEach(function (el) { el.classList.add("is-on"); });
    return;
  }
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (e.isIntersecting) { e.target.classList.add("is-on"); io.unobserve(e.target); }
    });
  }, { threshold: 0.4 });
  els.forEach(function (el) { el.classList.add("anim-lista"); io.observe(el); });
})();

/* ---------- Teléfono: desplegables cerrados y barra fija de acción ---------- */
(function () {
  var telefono = window.matchMedia && window.matchMedia("(max-width:760px)");
  if (telefono && telefono.matches) {
    document.querySelectorAll("details[data-abierto-escritorio]").forEach(function (d) { d.removeAttribute("open"); });
  }

  var cta = document.querySelector(".masthead .nav-cta");
  if (!cta) return;
  var wa = document.querySelector(".wa-float");
  var bar = document.createElement("div");
  bar.className = "barra-accion bloque-marino grano";
  bar.setAttribute("role", "region");
  bar.setAttribute("aria-label", "Acciones rápidas");
  bar.innerHTML =
    '<a class="btn" href="' + cta.getAttribute("href") + '">Postula al Diagnóstico</a>' +
    '<a class="wa" href="' + (wa ? wa.getAttribute("href") : "https://wa.me/584221234881") + '" target="_blank" rel="noopener" aria-label="Escribir por WhatsApp">' +
    '<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M16 3C9.1 3 3.5 8.6 3.5 15.5c0 2.4.7 4.7 1.9 6.6L3 29l7.1-2.3a12.4 12.4 0 0 0 5.9 1.5c6.9 0 12.5-5.6 12.5-12.5S22.9 3 16 3zm7.3 17.9c-.3.9-1.5 1.6-2.5 1.8-.7.1-1.5.3-4.5-1-3.8-1.6-6.2-5.4-6.4-5.6-.2-.2-1.5-2-1.5-3.9 0-1.8 1-2.8 1.3-3.1.3-.4.7-.5 1-.5h.7c.2 0 .6-.1.9.7.3.8 1.1 2.7 1.2 2.9.1.2.2.4 0 .7-.1.3-.2.4-.4.6l-.6.7c-.2.2-.4.4-.2.8.2.4 1 1.6 2.1 2.6 1.5 1.3 2.7 1.7 3.1 1.9.4.2.6.2.8-.1.2-.3 1-1.1 1.2-1.5.3-.4.5-.3.9-.2.4.1 2.2 1.1 2.6 1.2.4.2.6.3.7.4.1.2.1 1-.2 1.8z"/></svg></a>';
  document.body.appendChild(bar);

  var portada = document.querySelector(".portada");
  var formulario = document.getElementById("diagnostico");
  var formularioVisible = false;
  function actualizar() {
    var paso = portada ? portada.getBoundingClientRect().bottom < 90 : window.scrollY > 260;
    bar.classList.toggle("visible", paso && !formularioVisible);
  }
  if (formulario && "IntersectionObserver" in window) {
    new IntersectionObserver(function (es) { formularioVisible = es[0].isIntersecting; actualizar(); }, { threshold: 0.02 }).observe(formulario);
  }
  window.addEventListener("scroll", actualizar, { passive: true });
  actualizar();
})();

/* ---------- Google Analytics 4: eventos propios ----------
   clic_whatsapp (con la ubicación del botón), sign_up (newsletter).
   generate_lead (formulario del Diagnóstico) se envía desde index.html. */
(function () {
  function evento(nombre, datos) { if (typeof window.gtag === "function") window.gtag("event", nombre, datos || {}); }
  document.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest('a[href*="wa.me/"]');
    if (!a) return;
    var ubicacion = a.closest(".barra-accion") ? "barra_fija"
      : a.closest(".wa-postular") ? "diagnostico"
      : a.classList.contains("wa-float") ? "boton_flotante"
      : a.closest("footer") ? "pie"
      : "contenido";
    evento("clic_whatsapp", { ubicacion: ubicacion, pagina: location.pathname });
  });
  document.addEventListener("newsletter:ok", function () { evento("sign_up", { method: "newsletter" }); });
})();
