/* Demo videos: the narrated cuts published with this snapshot. A cut is listed only when root's snapshot.demo_videos names it (complete, hash-checked
 * outputs only); with none, the page says so. The videos describe the site; they add no evidence. The compact cut plays by default. */
(function () {
  const DF = window.DF; const { html } = DF; const U = DF.ui;
  const mmss = (s) => (typeof s === "number" ? Math.floor(s / 60) + ":" + String(Math.round(s % 60)).padStart(2, "0") : "length not stated");
  const STORY = [["Goal", "State a design goal plainly: a computational prototype of a flying fish, not a built one."], ["Multiscale evidence", "See the models, sources and gaps at eleven scales, each with its evidence kind and what is still unknown."],
    ["Next experiment", "Compare candidate measurements by how much each would reduce uncertainty. A calculation under stated assumptions, not a result."], ["Reusable agent work", "Checked simulations, receipts and open questions stay attached, so the next project starts from them."]];

  DF.views.demo = function (snap, route) {
    const D = snap.demo_videos; const cuts = ((D && D.cuts) || []).slice().sort((a, b) => (a.duration_s || 0) - (b.duration_s || 0));
    const head = html`<section class="pagehead demohead"><p class="eyebrow">Demo</p><h1>Watch the demo</h1><p class="lede">From a design goal to the evidence behind it, the next experiment worth running, and work other projects can reuse. About a minute, or two for the full tour.</p></section>`;
    if (!cuts.length) return { html: html`${head}<section class="panel"><p class="empty">No demo video is published in this snapshot yet. A cut appears here only once its file and hashes are verified; nothing is shown in its place.</p></section>` };
    const cur = cuts.find((c) => c.id === (route.params || {}).cut) || cuts[0]; const other = cuts.find((c) => c.id !== cur.id);
    const label = (c) => (c.duration_s <= 90 ? "1 minute" : "2 minutes");
    return {
      html: html`${head}
        <ol class="demostory" aria-label="What the demo shows">${STORY.map(([t, d], i) => html`<li><span class="n">${i + 1}</span><b>${t}</b><span class="small">${d}</span></li>`)}</ol>
        <section class="panel demo" aria-labelledby="demo-h"><h2 id="demo-h" class="sr">Player</h2>
          <nav class="demotabs" aria-label="Choose a cut">${cuts.map((c) => html`<a class="democut" href="${DF.href("/demo", { cut: c.id })}" aria-current="${c.id === cur.id ? "page" : "false"}"><b>${label(c)}</b><span class="small">${c.title} · ${mmss(c.duration_s)}</span></a>`)}</nav>
          <figure class="demofig"><div class="demostage" id="demo-stage"><video id="demo-video" controls preload="metadata" playsinline ${cur.poster_href ? html`poster="${cur.poster_href}"` : ""} aria-label="${cur.title}"><source src="${cur.href}" type="video/mp4">${cur.subtitles_href ? html`<track kind="captions" srclang="en" label="English" src="${cur.subtitles_href}">` : ""}Your browser cannot play this video; use the download link.</video></div>
            <figcaption class="small">${cur.title}, ${mmss(cur.duration_s)}. Captions are burned into the video. ${cur.subtitles_href ? "An optional English caption track can also be turned on in the player controls." : "No separate caption track is published for this cut."}</figcaption></figure>
          <p class="demoactions"><button type="button" class="btn" id="demo-fs" hidden aria-label="Fullscreen: ${cur.title}">Fullscreen</button>
            ${other ? html`<a class="btn ghost" id="demo-switch" href="${DF.href("/demo", { cut: other.id })}">${other.duration_s > cur.duration_s ? "Watch the full 2-minute tour" : "Watch the 1-minute version"}</a>` : ""}</p>
          <h3 class="demoh3">Downloads</h3>
          <ul class="demodl">${cuts.map((c) => html`<li><b>${label(c)}</b> <a href="${c.href}" download>Download MP4</a>${c.subtitles_href ? html` · <a href="${c.subtitles_href}">Captions (VTT)</a>` : ""}${c.transcript_href ? html` · <a href="${c.transcript_href}" download>Transcript (TXT)</a>` : ""}${c.manifest_href ? html` · <a href="${c.manifest_href}">Provenance (JSON)</a>` : ""}</li>`)}</ul></section>
        ${(D.limits || []).length ? html`<details class="panel demolimits"><summary>What the video does not show, and where it comes from</summary><ul class="small">${D.limits.map((l) => html`<li>${typeof l === "string" ? l : JSON.stringify(l)}</li>`)}</ul><p class="small faint">Each cut's file hashes and sources are in its provenance JSON above.</p></details>` : ""}`,
      async after(root) {
        const v = root.querySelector("#demo-video"), fs = root.querySelector("#demo-fs"), stage = root.querySelector("#demo-stage");
        if (fs && stage && document.fullscreenEnabled && stage.requestFullscreen) {
          fs.hidden = false;
          fs.addEventListener("click", () => { (document.fullscreenElement ? document.exitFullscreen() : stage.requestFullscreen()).catch(() => { fs.textContent = "Fullscreen not available"; fs.disabled = true; }); });
        }
        if (v) window.addEventListener("hashchange", () => { try { v.pause(); } catch (e) { /* leaving the page */ } }, { once: true });
      }
    };
  };
})();
