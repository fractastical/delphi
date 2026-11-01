() => {
  const out = [];
  document.querySelectorAll("#main table").forEach((t, i) => {
    const wrap = t.closest(".tablewrap") || t.parentElement; const wr = wrap.getBoundingClientRect(); const tr = t.getBoundingClientRect();
    const stacked = getComputedStyle(t.querySelector("tbody td") || t.querySelector("td,th") || t).display === "block";
    let pw = 0, clipped = 0, split = 0;
    t.querySelectorAll(".pill, [class*=pill]").forEach((p) => { const r = p.getClientRects(); if (r.length > 1 || p.getBoundingClientRect().height > parseFloat(getComputedStyle(p).lineHeight || 20) * 1.7) pw++; });
    if (!stacked) t.querySelectorAll("td,th").forEach((c) => { if (c.getBoundingClientRect().right > wr.right + 1) clipped++; });
    const scrolls = wrap.scrollWidth > wrap.clientWidth + 1;
    const cue = scrolls ? (getComputedStyle(wrap).backgroundImage !== "none" || !!wrap.dataset.scrollcue) : null;
    out.push({ i, cols: (t.rows[0] || {cells: []}).cells.length, rows: t.rows.length, stacked, pillWraps: pw, clipped, scrolls, cue, hidden: Math.round(Math.max(0, wrap.scrollWidth - wrap.clientWidth)), wrapW: Math.round(wr.width), cap: (t.caption && t.caption.textContent || "").slice(0, 40) });
  });
  return out;
}
