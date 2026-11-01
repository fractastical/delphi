/* Shared helpers. Everything interpolated into markup is escaped unless wrapped in raw(). */
(function () {
  const DF = (window.DF = window.DF || {}); DF.views = DF.views || {};

  class Raw { constructor(s) { this.s = s; } toString() { return this.s; } }
  const raw = (s) => new Raw(String(s));
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const part = (v) => (v instanceof Raw ? v.s : Array.isArray(v) ? v.map(part).join("") : esc(v));
  function html(strings, ...vals) {
    let out = strings[0];
    vals.forEach((v, i) => { out += part(v) + strings[i + 1]; });
    return new Raw(out);
  }
  const safeUrl = (u) => (/^https?:\/\//i.test(String(u || "")) ? String(u) : null);
  const fmt = (x, d = 3) => (x === null || x === undefined || !isFinite(x) ? "unknown" : Number(x).toPrecision(d).replace(/\.?0+$/, (m) => (m.includes(".") ? "" : m)));
  const num = (x, d = 1) => (x === null || x === undefined || !isFinite(x) ? "unknown" : Number(x).toFixed(d));

  /* ---------- math ---------- */
  const MATHWORDS = new Set(["tr", "det", "ln", "exp", "log", "min", "max", "Cov", "sin", "cos"]);
  const isProse = (t) => (/^\(?[A-Za-z][A-Za-z'-]*[,.:;)]*$/.test(t) && !MATHWORDS.has(t.replace(/[(),.:;]/g, "")) && t.replace(/[(),.:;]/g, "").length >= 2) || /^\d{4}\)?[,.]?$/.test(t);
  function tex(el, src, display) {
    if (window.katex) {
      try { window.katex.render(src, el, { throwOnError: true, displayMode: !!display, strict: "ignore" }); el.setAttribute("aria-label", src); return true; }
      catch (e) { /* fall through to source */ }
    }
    el.textContent = src; el.classList.add("tex-fallback"); el.title = "KaTeX could not render this expression; showing its TeX source"; el.setAttribute("data-unsupported", "1"); el.setAttribute("aria-label", "Unsupported expression, TeX source: " + src);
    return false;
  }
  /* Split a claim's "math" field (formula with embedded prose) into text and TeX runs. */
  function mixed(src) {
    const toks = String(src).split(/\s+/).filter(Boolean);
    const runs = []; let cur = null;
    toks.forEach((t) => {
      const kind = isProse(t) ? "t" : "m";
      if (cur && cur.kind === kind) cur.parts.push(t); else { cur = { kind, parts: [t] }; runs.push(cur); }
    });
    return runs.map((r) => ({ kind: r.kind, text: r.parts.join(" ") }));
  }
  function mathBlock(src) {
    const wrap = document.createElement("div"); wrap.className = "mathmix";
    String(src).split(/;\s+/).forEach((seg) => {
      const line = document.createElement("div"); line.className = "mathline";
      mixed(seg).forEach((r) => {
        const s = document.createElement("span");
        if (r.kind === "t") { s.className = "mathtext"; s.textContent = r.text + " "; } else tex(s, r.text.replace(/[,;]$/, ""), false);
        line.appendChild(s);
      });
      wrap.appendChild(line);
    });
    return wrap;
  }
  function renderMath(root) {
    root.querySelectorAll("[data-tex]").forEach((el) => { if (!el.dataset.done) { tex(el, el.dataset.tex, el.dataset.display === "1"); el.dataset.done = "1"; } });
    root.querySelectorAll("[data-mixed]").forEach((el) => { if (!el.dataset.done) { el.appendChild(mathBlock(el.dataset.mixed)); el.dataset.done = "1"; } });
  }
  const texSpan = (src, display) => html`<span class="tex" data-tex="${src}" data-display="${display ? 1 : 0}"></span>`;
  const mixedSpan = (src) => html`<div class="mixed" data-mixed="${src}"></div>`;

  /* ---------- tiny markdown (escape first; headings, lists, tables, code, bold, links) ---------- */
  function inline(s) {
    let t = esc(s);
    t = t.replace(/`([^`]+)`/g, "<code>$1</code>");
    t = t.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    t = t.replace(/(^|[\s(])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>");
    t = t.replace(/\[([^\]]+)\]\((#\/[^)\s]+)\)/g, '<a href="$2">$1</a>');   // in-site hash routes only
    t = t.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
    return t;
  }
  function markdown(src) {
    const lines = String(src).replace(/\r/g, "").split("\n");
    const out = []; let i = 0; let para = []; let list = null;
    const flush = () => { if (para.length) { out.push("<p>" + inline(para.join(" ")) + "</p>"); para = []; } };
    const endList = () => { if (list) { out.push(`</${list}>`); list = null; } };
    while (i < lines.length) {
      const l = lines[i];
      if (/^```/.test(l)) {
        flush(); endList(); const buf = []; i++;
        while (i < lines.length && !/^```/.test(lines[i])) buf.push(lines[i++]);
        out.push("<pre><code>" + esc(buf.join("\n")) + "</code></pre>"); i++; continue;
      }
      const h = /^(#{1,6})\s+(.*)$/.exec(l);
      if (h) { flush(); endList(); const n = Math.min(h[1].length + 1, 6); out.push(`<h${n}>${inline(h[2])}</h${n}>`); i++; continue; }
      if (/^\|.*\|\s*$/.test(l) && i + 1 < lines.length && /^\|[\s:|-]+\|\s*$/.test(lines[i + 1])) {
        flush(); endList();
        const cells = (r) => r.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
        const head = cells(l); i += 2; const rows = [];
        while (i < lines.length && /^\|.*\|\s*$/.test(lines[i])) rows.push(cells(lines[i++]));
        out.push('<div class="tablewrap"><table><thead><tr>' + head.map((c) => `<th>${inline(c)}</th>`).join("") + "</tr></thead><tbody>" +
          rows.map((r) => "<tr>" + r.map((c) => `<td>${inline(c)}</td>`).join("") + "</tr>").join("") + "</tbody></table></div>");
        continue;
      }
      const li = /^\s*([-*]|\d+\.)\s+(.*)$/.exec(l);
      if (li) {
        flush(); const kind = /\d/.test(li[1]) ? "ol" : "ul";
        if (list !== kind) { endList(); out.push(`<${kind}>`); list = kind; }
        out.push("<li>" + inline(li[2]) + "</li>"); i++; continue;
      }
      if (/^>\s?/.test(l)) { flush(); endList(); out.push("<blockquote>" + inline(l.replace(/^>\s?/, "")) + "</blockquote>"); i++; continue; }
      if (!l.trim()) { flush(); endList(); i++; continue; }
      if (/^---+$/.test(l.trim())) { flush(); endList(); out.push("<hr>"); i++; continue; }
      para.push(l.trim()); i++;
    }
    flush(); endList();
    return new Raw(out.join("\n"));
  }

  /* Exact rational parser for strings like "3/10", "0.25" or "7": no float round trip until display. */
  function rational(s) {
    const m = /^(-?\d+)(?:\/(\d+))?$/.exec(String(s).trim()) || /^(-?\d+)\.(\d+)$/.exec(String(s).trim());
    if (!m) return null;
    let n, d;
    if (String(s).includes("/")) { n = BigInt(m[1]); d = BigInt(m[2]); } else if (String(s).includes(".")) { d = 10n ** BigInt(m[2].length); n = BigInt(m[1] + m[2]) * (m[1].startsWith("-") ? 1n : 1n); if (m[1].startsWith("-")) n = BigInt(m[1]) * d - BigInt(m[2]); } else { n = BigInt(m[1]); d = 1n; }
    if (d === 0n) return null;
    const gcd = (a, b) => { a = a < 0n ? -a : a; while (b) [a, b] = [b, a % b]; return a || 1n; }; const g = gcd(n, d); n /= g; d /= g;
    const approx = Number(n * 1000000n / d) / 1e6;
    return { n, d, text: d === 1n ? String(n) : `${n}/${d}`, approx };
  }
  const exact = (s) => { const r = rational(s); return r ? (r.d === 1n ? r.text : `${r.text} (≈ ${DF.fmt(r.approx, 6)})`) : String(s); };

  const slug = (s) => String(s).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  Object.assign(DF, { rational, exact, raw, esc, html, safeUrl, fmt, num, tex, texSpan, mixedSpan, mixed, renderMath, markdown, slug, Raw, isProse });
})();
