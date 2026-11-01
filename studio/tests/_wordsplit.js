() => {
  const bad = [];
  document.querySelectorAll("#main table td, #main table th").forEach((td) => {
    if (td.closest("table") && getComputedStyle(td).display === "block" && false) return;
    const w = document.createTreeWalker(td, NodeFilter.SHOW_TEXT);
    let n; while ((n = w.nextNode())) {
      if (n.parentElement.closest("a, code")) continue;
      const re = /[A-Za-z]{6,}/g; let m;
      while ((m = re.exec(n.nodeValue))) { const r = document.createRange(); r.setStart(n, m.index); r.setEnd(n, m.index + m[0].length); if (r.getClientRects().length > 1) bad.push(m[0]); }
    }
  });
  return bad;
}
