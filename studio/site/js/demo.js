/* Demo videos: the narrated cuts published with this snapshot. A cut is listed only when root's snapshot.demo_videos names it (complete, hash-checked
 * outputs only); with none, the page says so. The videos describe the site; they add no evidence. New science cuts are featured when published; earlier cuts remain available. */
(function () {
  const DF = window.DF; const { html } = DF; const U = DF.ui;
  const mmss = (s) => (typeof s === "number" ? Math.floor(s / 60) + ":" + String(Math.round(s % 60)).padStart(2, "0") : "length not stated");
  const STORY = [["Goal", "State a design goal plainly: a computational prototype of a flying fish, not a built one."], ["Multiscale evidence", "See the models, sources and gaps at eleven scales, each with its evidence kind and what is still unknown."],
    ["Next experiment", "Compare candidate measurements by how much each would reduce uncertainty. A calculation under stated assumptions, not a result."], ["Reusable agent work", "Checked simulations, receipts and open questions stay attached, so the next project starts from them."]];
  const SCIENCE_STORY = [["Formalize the claim", "Carry the source, context and assumptions into a mathematical statement."], ["Check the implication", "Inspect Lean source, compiler receipts and deliberately corrupted controls. Empirical premises still need evidence."], ["Design across scales", "Connect genetic hypotheses, tissue mechanics and organism requirements. Show where a calibrated connection is missing."], ["Share the next question", "Reuse the evidence through the commons and MCP, contest results, and choose the next measurement."]];

  DF.views.demo = function (snap, route) {
    const D = snap.demo_videos; const cuts = ((D && D.cuts) || []).slice().sort((a, b) => (a.duration_s || 0) - (b.duration_s || 0));
    const science = cuts.filter((c) => c.id.startsWith("frontier-science-"));
    const archived = science.length ? cuts.filter((c) => !science.includes(c)) : [];
    const featured = science.length ? science : cuts;
    const latest = science.find((c) => c.duration_s === 60) || science[0] || cuts.find((c) => c.id === "frontier-90s");
    const head = html`<section class="pagehead demohead"><p class="eyebrow">${science.length ? "New science films · one minute or two" : latest ? "Demo films · new 90-second tour" : "Demo films · one minute or two"}</p><h1 class="demotitle">${science.length ? html`Lean for biology.<br><span class="accent">A foundation for design.</span>` : html`A design studio for<br><span class="accent">biology's next frontier.</span>`}</h1><p class="lede">${science.length ? "Make biological claims inspectable: sources, assumptions, equations and checks. Then use a flying-fish design to discover what connects across scales—and what still needs an experiment." : "Start with a flying fish. Connect claims, equations and simulations from molecules to behavior. Every missing link becomes a question agents can work on together."}</p></section>`;
    if (!cuts.length) return { html: html`${head}<section class="panel"><p class="empty">No demo video is published in this snapshot yet. A cut appears here only once its file and hashes are verified; nothing is shown in its place.</p></section>` };
    const cur = cuts.find((c) => c.id === (route.params || {}).cut) || latest || cuts[0];
    const other = featured.find((c) => c.id !== cur.id && c.duration_s === (cur.duration_s === 120 ? 60 : 120)) || featured.find((c) => c.id !== cur.id);
    const label = (c) => (c.duration_s === 90 ? "90 seconds" : c.duration_s === 60 ? "1 minute" : c.duration_s === 120 ? "2 minutes" : mmss(c.duration_s));
    const cutLink = (c) => html`<a class="democut" href="${DF.href("/demo", { cut: c.id })}" aria-current="${c.id === cur.id ? "page" : "false"}"><b>${label(c)}</b><span class="small">${c.title} · ${mmss(c.duration_s)}</span></a>`;
    return {
      html: html`${head}
        <section class="demolayout" aria-labelledby="demo-h"><h2 id="demo-h" class="sr">Player</h2>
          <figure class="demofig"><div class="demostage" id="demo-stage"><video id="demo-video" controls preload="metadata" playsinline ${cur.poster_href ? html`poster="${cur.poster_href}"` : ""} aria-label="${cur.title}"><source src="${cur.href}" type="video/mp4">${cur.subtitles_href ? html`<track kind="captions" srclang="en" label="English" src="${cur.subtitles_href}">` : ""}Your browser cannot play this video; use the download link.</video></div>
            <figcaption class="small">${cur.title}, ${mmss(cur.duration_s)}. Captions are burned into the video. ${cur.subtitles_href ? "An optional English caption track can also be turned on in the player controls." : "No separate caption track is published for this cut."}</figcaption></figure>
          <aside class="demoside" aria-label="Watch your way"><h2>Watch your way.</h2>
            <p class="small">${science.length ? "One minute on the foundation. Two minutes through the science, design studio and validation. Earlier films are preserved below." : latest ? "Watch the new 90-second tour with faster British female narration, or revisit either earlier cut. All include captions." : "Start with the one-minute tour, or take the full two minutes. Both are narrated, with captions burned in."}</p>
            <nav class="demotabs" aria-label="Choose a cut">${featured.map(cutLink)}</nav>
            ${archived.length ? html`<details class="demoarchive" ${archived.includes(cur) ? DF.raw("open") : ""}><summary>Earlier films · ${archived.length} preserved cuts</summary><nav class="demotabs" aria-label="Earlier cuts">${archived.map(cutLink)}</nav></details>` : ""}
            <p class="small faint demometa">Runtime ${mmss(cur.duration_s)} · 16:9</p>
            <p class="demoactions"><button type="button" class="btn ghost" id="demo-fs" hidden aria-label="Fullscreen: ${cur.title}">Fullscreen</button>
              ${other ? html`<a class="btn ghost" id="demo-switch" href="${DF.href("/demo", { cut: other.id })}">${other.duration_s > cur.duration_s ? "Watch the full 2-minute tour" : "Watch the 1-minute version"}</a>` : ""}
              <a class="btn" href="${DF.href("/studio/flying-fish")}">Explore the flying-fish studio</a></p>
            <h3 class="demoh3">Downloads</h3>
            <ul class="demodl small">${[...featured, ...archived].map((c) => html`<li><b>${science.length ? c.title : label(c)}</b> <a href="${c.href}" download>Download MP4</a>${c.subtitles_href ? html` · <a href="${c.subtitles_href}">Captions (VTT)</a>` : ""}${c.transcript_href ? html` · <a href="${c.transcript_href}" download>Transcript (TXT)</a>` : ""}${c.manifest_href ? html` · <a href="${c.manifest_href}">Provenance (JSON)</a>` : ""}</li>`)}</ul></aside></section>
        <ol class="demostory" aria-label="What the demo shows">${(science.length ? SCIENCE_STORY : STORY).map(([t, d], i) => html`<li><span class="n">0${i + 1}</span><b>${t}</b><span class="small">${d}</span></li>`)}</ol>
        <section class="democta"><div><h2>Start with a flying fish. Carry the gaps to work.</h2><p>Open the studio to see each scale's evidence and unknowns, or take an open question from the frontier.</p></div><p><a class="btn" href="${DF.href("/studio/flying-fish")}">Open the studio</a> <a class="btn ghost" href="${DF.href("/frontier")}">Browse open questions</a></p></section>
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
