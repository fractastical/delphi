/* Demo videos: the narrated cuts published with this snapshot. A cut is listed only when root's snapshot.demo_videos names it (complete, hash-checked
 * outputs only); with none, the page says so. Nothing here is a result: the videos describe the site, they do not add evidence. */
(function () {
  const DF = window.DF; const { html, esc } = DF; const U = DF.ui;
  const mmss = (s) => (typeof s === "number" ? Math.floor(s / 60) + ":" + String(Math.round(s % 60)).padStart(2, "0") : "length not stated");

  DF.views.demo = function (snap, route) {
    const D = snap.demo_videos; const cuts = (D && D.cuts) || [];
    const head = html`<section class="pagehead"><h1>Watch the demo</h1><p class="lede">A short narrated tour of the workspace: a design goal worked across scales, the evidence and gaps behind it, and the open questions it creates. Every scene shows the pages as they are, including what is unknown.</p></section>`;
    if (!cuts.length) return { html: html`${head}<section class="panel"><p class="empty">No demo video is published in this snapshot yet. A cut appears here only once its file and hashes are verified; nothing is shown in its place.</p></section>` };
    const cur = cuts.find((c) => c.id === (route.params || {}).cut) || cuts[0];
    return {
      html: html`${head}<section class="panel demo" aria-labelledby="demo-h"><h2 id="demo-h" class="sr">Demo cuts</h2>
        <nav class="subnav demotabs" aria-label="Demo length">${cuts.map((c) => html`<a href="${DF.href("/demo", { cut: c.id })}" aria-current="${c.id === cur.id ? "page" : "false"}">${esc(c.title)} <span class="faint small">${mmss(c.duration_s)}</span></a>`)}</nav>
        <figure class="demofig"><video id="demo-video" controls preload="metadata" playsinline ${cur.poster_href ? html`poster="${cur.poster_href}"` : ""} aria-label="${esc(cur.title)}"><source src="${cur.href}" type="video/mp4">${cur.subtitles_href ? html`<track kind="captions" srclang="en" label="English" src="${cur.subtitles_href}">` : ""}Your browser cannot play this video; use the download link.</video>
          <figcaption class="small">${esc(cur.title)}, ${mmss(cur.duration_s)}. ${cur.subtitles_href ? "Captions are on in the player controls." : "No caption file is published for this cut."}</figcaption></figure>
        <p class="demolinks"><a class="btn" href="${cur.href}" download>Download MP4</a> ${cur.manifest_href ? html`<a class="btn ghost" href="${cur.manifest_href}">Provenance (JSON)</a>` : ""} ${cur.subtitles_href ? html`<a class="btn ghost" href="${cur.subtitles_href}">Captions</a>` : ""}</p></section>
        ${(D.limits || []).length ? html`<section class="panel" aria-labelledby="demo-l"><h2 id="demo-l">What the video does not show</h2><ul class="small">${D.limits.map((l) => html`<li>${esc(typeof l === "string" ? l : JSON.stringify(l))}</li>`)}</ul></section>` : ""}`,
      async after(root) { const v = root.querySelector("#demo-video"); if (v) window.addEventListener("hashchange", () => { try { v.pause(); } catch (e) { /* leaving the page */ } }, { once: true }); }
    };
  };
})();
