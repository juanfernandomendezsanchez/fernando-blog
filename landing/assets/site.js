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
          form.reset();
          setStatus(status, "Listo. Te escribo cuando publique el próximo artículo. Mientras tanto, ", "ok");
          // Siguiente paso del embudo: quien se suscribe ya confía un poco; se le muestra cómo trabajo.
          var next = document.createElement("a");
          next.href = (location.pathname.indexOf("/articulos/") > -1 ? "../" : "") + "trabaja-conmigo.html";
          next.textContent = "mira cómo trabajo →";
          if (status) status.appendChild(next);
        }
        else { setStatus(status, "No pude guardarlo. Escríbeme a juanfernandomendezsanchez@gmail.com y te agrego a mano.", "err"); }
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
