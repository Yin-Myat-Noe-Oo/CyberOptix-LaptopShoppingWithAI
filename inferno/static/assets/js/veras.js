/* Veras AI shopping assistant widget */
(function () {
  "use strict";

  const root = document.getElementById("veras");
  if (!root || root.dataset.ready) return;
  root.dataset.ready = "1";

  const endpoint = root.dataset.endpoint || "/veras/api/";
  const fab = document.getElementById("veras-fab");
  const panel = document.getElementById("veras-panel");
  const log = document.getElementById("veras-log");
  const form = document.getElementById("veras-form");
  const input = document.getElementById("veras-input");
  const suggestBox = document.getElementById("veras-suggest");
  const resetBtn = document.getElementById("veras-reset");
  const STORE = "veras-history-v2-" + (root.dataset.lang || "en");
  const fullPage = document.body.classList.contains("veras-page");

  const LANG = root.dataset.lang || document.documentElement.lang || "en";
  let DEFAULT_SUGGESTIONS = [];
  try { DEFAULT_SUGGESTIONS = JSON.parse(document.getElementById("veras-suggestions").textContent); } catch (e) { /* ignore */ }
  const WELCOME = root.dataset.welcome || "Hi! I'm **Veras**, your AI shopping assistant.";
  const ERROR_TEXT = root.dataset.error || "Sorry, I couldn't reach the assistant right now.";
  const MATCH_TEXT = root.dataset.match || "match";

  let history = [];
  let busy = false;

  function csrfToken() {
    const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : root.dataset.csrf || "";
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  // Tiny, safe markdown: escape first, then **bold**, line breaks and "- " bullets.
  function md(s) {
    return escapeHtml(s)
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/^- (.*)$/gm, "&bull; $1")
      .replace(/\n/g, "<br>");
  }

  function money(n) {
    return "$" + Number(n || 0).toLocaleString(undefined, { maximumFractionDigits: 0 });
  }

  function safeUrl(u) {
    return typeof u === "string" && (u.startsWith("/") || u.startsWith("http")) ? u : "#";
  }

  function scrollDown() {
    log.scrollTop = log.scrollHeight;
  }

  function addMessage(role, text, products, save = true) {
    const el = document.createElement("div");
    el.className = "veras-msg " + role;
    el.innerHTML = md(text);
    log.appendChild(el);

    if (products && products.length) {
      const wrap = document.createElement("div");
      wrap.className = "veras-cards";
      products.forEach((p) => {
        const a = document.createElement("a");
        a.className = "veras-card";
        a.href = safeUrl(p.url);
        const real = (v) => v && !["none", "intel", "amd"].includes(String(v).toLowerCase()) ? v : "";
        const meta = [p.brand, real(p.cpu), real(p.ram)]
          .filter(Boolean)
          .join(" · ");
        a.innerHTML =
          (p.image ? `<img src="${escapeHtml(safeUrl(p.image))}" alt="" loading="lazy">` : "") +
          `<div class="veras-card-body"><div class="veras-card-title">${escapeHtml(p.title)}</div>` +
          `<div class="veras-card-meta">${escapeHtml(meta || p.shop || "")}</div></div>` +
          `<div class="veras-card-side"><div class="veras-card-price">${money(p.price)}</div>` +
          (p.score != null ? `<span class="veras-card-score">${escapeHtml(p.score)}% ${escapeHtml(MATCH_TEXT)}</span>` : "") +
          `</div>`;
        wrap.appendChild(a);
      });
      log.appendChild(wrap);
    }
    if (save) {
      history.push({ role, text, products: products || [] });
      history = history.slice(-30);
      try { sessionStorage.setItem(STORE, JSON.stringify(history)); } catch (e) { /* storage unavailable */ }
    }
    scrollDown();
  }

  function setSuggestions(list) {
    suggestBox.innerHTML = "";
    (list && list.length ? list : DEFAULT_SUGGESTIONS).forEach((s) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "veras-chip";
      b.textContent = s;
      b.addEventListener("click", () => send(s));
      suggestBox.appendChild(b);
    });
  }

  function typing(on) {
    let t = document.getElementById("veras-typing");
    if (on && !t) {
      t = document.createElement("div");
      t.id = "veras-typing";
      t.className = "veras-msg bot veras-typing";
      t.innerHTML = "<i></i><i></i><i></i>";
      log.appendChild(t);
      scrollDown();
    } else if (!on && t) {
      t.remove();
    }
  }

  async function send(text, opts = {}) {
    text = (text || "").trim();
    if (!text || busy) return;
    busy = true;
    form.querySelector("button").disabled = true;
    addMessage("user", text);
    input.value = "";
    typing(true);
    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
        credentials: "same-origin",
        body: JSON.stringify({
          message: text,
          lang: LANG,
          reset: !!opts.reset,
          history: history.slice(-8).map((h) => ({ role: h.role, text: h.text })),
        }),
      });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      typing(false);
      addMessage("bot", data.reply || data.response || "…", data.products);
      setSuggestions(data.suggestions);
    } catch (err) {
      typing(false);
      addMessage("bot", ERROR_TEXT, null, false);
      console.error("Veras error:", err);
    } finally {
      busy = false;
      form.querySelector("button").disabled = false;
      input.focus();
    }
  }

  function restore() {
    log.innerHTML = "";
    try { history = JSON.parse(sessionStorage.getItem(STORE) || "[]"); } catch (e) { history = []; }
    if (!history.length) {
      addMessage("bot", WELCOME, null, false);
    } else {
      history.forEach((h) => addMessage(h.role, h.text, h.products, false));
    }
    setSuggestions();
  }

  function open() {
    panel.hidden = false;
    root.classList.add("is-open");
    fab.setAttribute("aria-expanded", "true");
    scrollDown();
    setTimeout(() => input.focus(), 50);
  }
  function close() {
    panel.hidden = true;
    root.classList.remove("is-open");
    fab.setAttribute("aria-expanded", "false");
  }

  fab.addEventListener("click", () => (panel.hidden ? open() : close()));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !panel.hidden && !fullPage) close(); });
  form.addEventListener("submit", (e) => { e.preventDefault(); send(input.value); });
  resetBtn.addEventListener("click", () => {
    history = [];
    try { sessionStorage.removeItem(STORE); } catch (e) { /* ignore */ }
    fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
      credentials: "same-origin",
      body: JSON.stringify({ message: "", reset: true }),
    }).catch(() => {});
    restore();
  });

  // Any element with data-veras-open (or data-veras-ask="question") opens the assistant.
  document.addEventListener("click", (e) => {
    const t = e.target.closest("[data-veras-open],[data-veras-ask]");
    if (!t) return;
    e.preventDefault();
    if (fullPage) { input.focus(); } else { open(); }
    if (t.dataset.verasAsk) send(t.dataset.verasAsk);
  });

  window.Veras = { open, close, ask: (q) => { open(); send(q); } };

  restore();
  if (fullPage) open();
})();
