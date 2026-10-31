/* Typed autocomplete for the header search: debounced, stale requests cancelled, keyboard operable (ARIA combobox).
 * It says which engine ran. A lexical fallback is never presented as semantic search. */
(function () {
  const DF = window.DF; const { esc } = DF;
  const GROUPS = [["question", "Questions"], ["record", "Records"], ["artifact", "Artifacts"], ["action", "Models and actions"]];
  let ctl = null; let timer = null;

  function target(it) {
    if (it.type === "artifact" || !it.ref) return it.ref ? DF.href("/entity/" + it.ref.kind + "/" + it.ref.id, { v: it.ref.version, ns: it.ref.namespace }) : DF.href("/search", { q: it.title, tab: "catalog" });
    return DF.href("/entity/" + it.ref.kind + "/" + it.ref.id, { v: it.ref.version, ns: it.ref.namespace });
  }

  DF.attachSearch = function () {
    const input = document.getElementById("gq"); const form = document.getElementById("gs"); if (!input || !form) return;
    const box = document.createElement("div"); box.className = "ac"; box.id = "ac-list"; box.hidden = true; box.setAttribute("role", "listbox"); box.setAttribute("aria-label", "Search suggestions");
    form.style.position = "relative"; form.appendChild(box);
    input.setAttribute("role", "combobox"); input.setAttribute("aria-autocomplete", "list"); input.setAttribute("aria-controls", "ac-list"); input.setAttribute("aria-expanded", "false"); input.autocomplete = "off";
    const status = document.createElement("div"); status.className = "sr"; status.setAttribute("role", "status"); status.setAttribute("aria-live", "polite"); form.appendChild(status);
    let items = []; let active = -1;

    const close = () => { box.hidden = true; input.setAttribute("aria-expanded", "false"); input.removeAttribute("aria-activedescendant"); active = -1; };
    const setActive = (i) => {
      const els = [...box.querySelectorAll("[role=option]")]; if (!els.length) return; active = (i + els.length) % els.length;
      els.forEach((e, k) => { e.setAttribute("aria-selected", k === active ? "true" : "false"); e.classList.toggle("on", k === active); });
      input.setAttribute("aria-activedescendant", els[active].id); els[active].scrollIntoView({ block: "nearest" });
    };
    const render = (r, q) => {
      items = r.items || [];
      let h = "";
      GROUPS.forEach(([t, label]) => {
        const g = items.filter((x) => x.type === t); if (!g.length) return;
        h += `<div class="acg" role="presentation">${esc(label)}</div>` + g.map((x) => { const i = items.indexOf(x);
          return `<a role="option" id="ac-${i}" aria-selected="false" class="aci" href="${esc(target(x))}" data-i="${i}"><span class="act">${esc(x.title || x.ref && x.ref.id || "(untitled)")}</span><span class="acm">${esc(x.kind || "")}${x.local_status ? " · " + esc(String(x.local_status).replace(/_/g, " ")) : ""}${x.score !== null && x.score !== undefined ? " · " + esc(x.score_kind || "score") + " " + esc(String(x.score)) : ""}</span>${x.snippet ? `<span class="acs">${esc(x.snippet)}</span>` : ""}</a>`; }).join("");
      });
      const engine = r.source === "discovery" ? `Engine: ${r.mode}${r.index ? " (" + (r.index.name || "index") + ")" : ""}` : "Engine: lexical text match" + (r.unavailable_reason ? `; ${r.unavailable_reason}` : "");
      if (!items.length) h = `<div class="ace">No match for “${esc(q)}”. ${esc(engine)}.</div>`;
      h += `<div class="acf"><a href="${esc(DF.href("/search", { q, tab: "catalog" }))}">All results for “${esc(q)}”</a><span>${esc(engine)}</span></div>`;
      box.innerHTML = h; box.hidden = false; input.setAttribute("aria-expanded", "true"); status.textContent = items.length ? `${items.length} suggestions. ${engine}.` : `No suggestions. ${engine}.`; active = -1;
    };
    const run = async (q) => {
      if (ctl) ctl.abort(); ctl = new AbortController(); const mine = ctl;
      box.hidden = false; box.innerHTML = `<div class="ace" role="status">Searching…</div>`; input.setAttribute("aria-expanded", "true");
      try { const r = await DF.api.discovery(q, { limit: 12, signal: mine.signal }); if (mine.signal.aborted) return; render(r, q); }
      catch (e) { if (e.name === "AbortError" || mine.signal.aborted) return; box.innerHTML = `<div class="ace" role="alert">Suggestions could not be loaded: ${esc(e.message)}. Press Enter to search the catalog instead.</div>`; }
    };
    input.addEventListener("input", () => { clearTimeout(timer); const q = input.value.trim(); if (q.length < 2) { if (ctl) ctl.abort(); close(); return; } timer = setTimeout(() => run(q), 220); });
    input.addEventListener("keydown", (e) => {
      if (box.hidden) { if (e.key === "ArrowDown" && input.value.trim().length >= 2) { run(input.value.trim()); e.preventDefault(); } return; }
      if (e.key === "ArrowDown") { e.preventDefault(); setActive(active + 1); } else if (e.key === "ArrowUp") { e.preventDefault(); setActive(active - 1); }
      else if (e.key === "Escape") { close(); } else if (e.key === "Enter" && active >= 0) { e.preventDefault(); const a = box.querySelectorAll("[role=option]")[active]; if (a) { close(); location.hash = a.getAttribute("href"); } }
    });
    box.addEventListener("mousedown", (e) => e.preventDefault());
    box.addEventListener("click", (e) => { if (e.target.closest("a")) setTimeout(close, 0); });
    input.addEventListener("blur", () => setTimeout(close, 120));
    form.addEventListener("submit", () => { if (ctl) ctl.abort(); clearTimeout(timer); close(); });
  };
})();
