/* Lean proofs: the real Lean source, the exact receipts of the runs that compiled it, and the mutants Lean rejected. Recorded runs only: this page
 * does not run Lean. A family whose files changed since its receipt is shown as stale and its source is withheld. Lean checks the stated mathematics,
 * not organism viability, a genotype-to-fin link or any empirical fact. All file text is inserted by the renderer's escaping, never as HTML. */
(function () {
  const DF = window.DF; const { html } = DF; const U = DF.ui;
  const STATUS = { current: ["recorded compile matches these files", "ok"], stale: ["stale: the files changed since the receipt, so nothing is shown as compiled", "no"], receipt_failed: ["the recorded run did not pass", "no"], missing: ["receipt or source missing", "no"] };
  const sec = (s) => (typeof s === "number" ? s.toFixed(1) + " s" : "time not recorded");
  const lines = (text) => String(text).replace(/\n$/, "").split("\n");
  const code = (text, label) => html`<div class="lcode" role="region" tabindex="0" aria-label="${label}">${lines(text).map((l, i) => html`<div class="ll"><span class="ln" aria-hidden="true">${i + 1}</span><code>${l}</code></div>`)}</div>`;
  const sha = (h) => U.sha(h);

  /* One-sentence plain-language gloss per family; editorial, the theorem statements below are authoritative. */
  const PLAIN = {
    "geometric-similarity": "If you scale a fish up or down while keeping its shape, how do the load on its wings and the speed it needs to stay aloft change? Lean proves the answer from the definitions, for every size.",
    "unit-algebra": "A small system that tracks units as part of a quantity's type, so a conversion or an interval mapping is checked instead of trusted. The other families lean on it.",
    "cantilever-guard": "A fin ray bending under a small load. The theorem gives a bound, and a second theorem shows that its conditions can actually be met, so the bound is not true only because nothing qualifies.",
    "steady-oxygen-bound": "How low can oxygen get at the center of a sphere or slab of tissue that takes it up while it diffuses in from outside? A bound, under stated assumptions and with no tissue-specific numbers supplied.",
    "scaled-threshold-intervals": "Two recorded simulation intervals are shown to rule out a factor-of-two scaling band over a fixed horizon. It is a checked statement about those intervals, not about tissue."};
  function family(f) {
    const st = STATUS[f.status] || ["unknown status", "no"]; const ok = f.status === "current";
    const downloads = [...(f.files || []), ...(f.display_artifacts || []).filter((x) => x.status === "verified")];
    const head = html`<h2 id="${"proof-" + f.id + "-h"}">${f.title}</h2><p>${U.pill(st[0], st[1])} ${f.versions ? html`<span class="small faint">${f.versions.lean_version.split(",")[0]} · Mathlib ${String(f.versions.mathlib_rev || "").slice(0, 10)}</span>` : ""}</p>`;
    if (!ok) return html`<section class="panel proof" id="proof-${f.id}" aria-labelledby="proof-${f.id}-h">${head}<p class="note warn small"><b>Withheld.</b> ${f.summary}</p><ul class="small">${(f.reasons || []).map((r) => html`<li>${r}</li>`)}</ul><p class="small faint">A new Lean run, and a new receipt, are needed before this family is shown as compiled again.</p></section>`;
    const run = f.run, pos = run.positive, neg = run.negative, rejected = f.negative_blocks.filter((b) => b.rejected).length;
    const fold = (title, meta, body, open) => html`<details class="pfold"${open ? " open" : ""}><summary><b>${title}</b>${meta ? html` <span class="small faint">${meta}</span>` : ""}</summary><div class="pfold-body">${body}</div></details>`;
    return html`<section class="panel proof" id="proof-${f.id}" aria-labelledby="proof-${f.id}-h">${head}
      <p class="proof-sum">${f.summary}</p>
      ${PLAIN[f.id] ? html`<p class="proof-plain"><span class="eyebrow">In plain terms</span> ${PLAIN[f.id]}</p>` : ""}
      <p class="proof-badges">${U.pill(f.theorems.length + " statements", "ev")} ${U.pill(rejected + " of " + f.negative_blocks.length + " mutants rejected", rejected === f.negative_blocks.length ? "ok" : "no")} ${U.pill("exit " + pos.exit + " (positive run)", pos.exit === 0 ? "ok" : "no")}${pos.only_standard_axioms ? html` ${U.pill("standard axioms only", "ok")}` : ""}</p>
      <div class="proofeq">${f.equations.map((e) => html`<div class="eqcard"><h4>${e.label}</h4><div class="eq-math">${DF.texSpan(e.tex, true)}</div></div>`)}</div>
      ${f.figure_href ? html`<figure class="prooffigure"><img src="${f.figure_href}" alt="Sphere and one-sided slab geometry with normalized model-only center oxygen response curves and diffusion limits"><figcaption class="small">Pinned geometry/control figure. Its threshold curves are conditional model implications, not biological measurements.</figcaption></figure>` : ""}
      <div class="proof-cols"><div><h3>Assumptions</h3><ul class="small">${f.assumptions.map((a) => html`<li>${a}</li>`)}</ul>${f.proves ? html`<p class="small"><b>Proves:</b> ${f.proves}</p>` : ""}</div>
        ${f.does_not_prove ? html`<div><h3>What it does not prove</h3><ul class="small">${f.does_not_prove.map((x) => html`<li>${x}</li>`)}</ul></div>` : ""}</div>
      ${fold("What the Lean statements say", f.theorems.length + " definitions and theorems", html`<div class="proofthms">${f.theorems.map((x) => html`<details><summary><b>${x.kind} ${x.name}</b> <span class="small faint">line ${x.line}</span></summary>${x.doc ? html`<p class="small">${x.doc}</p>` : ""}${code(x.statement, "Lean statement of " + x.name)}</details>`)}</div>`, true)}
      ${fold("Read the Lean source", f.source_name + ", " + lines(f.source).length + " lines", code(f.source, "Lean source " + f.source_name))}
      ${fold("Mutants Lean rejected", rejected + " of " + f.negative_blocks.length, html`<p class="small">Each block is the theory with one law deliberately wrong. If Lean accepted it, the original statement would not be pinning the law down.</p><ul class="proofneg">${f.negative_blocks.map((b) => html`<li><details><summary><b>${b.id.replace(/_/g, " ")}</b> ${b.rejected ? U.pill("rejected by Lean", "ok") : U.pill("NOT rejected", "no")}${b.first_error ? html` <span class="small faint">${b.first_error}</span>` : ""}</summary>${code(b.code, "Mutated Lean block " + b.id)}</details></li>`)}</ul>`)}
      ${f.certificate ? fold("A solver conflict certificate, checked by Lean", f.certificate.solver.status, html`<p class="small">The constraint solver reported <b>${f.certificate.solver.status}</b> on ${(f.certificate.solver.conflict || []).join(", ")}. Its certificate was compiled ${f.certificate.compiled}. ${f.certificate.solver.scope}</p>${code(f.certificate.lean, "Solver certificate in Lean")}<p class="small">A certificate with the speed cap changed from 10 to 20 is rejected:</p><details><summary class="small">Show the corrupted certificate</summary>${code(f.certificate.corrupted_lean, "Corrupted certificate")}</details>`) : ""}
      ${f.check_results ? fold("Recorded positive checks", f.check_results.length + " theorems", html`<ul class="small proofchecks">${f.check_results.map((x) => html`<li><b>${x.name}</b> — ${x.status}; axioms: ${x.axioms.join(", ")}</li>`)}</ul>`) : ""}
      ${f.contextual_reuse ? fold("Contextual reuse", f.contextual_reuse.status, html`<p class="small">These are exact Project-version links for a shared model rule; they do not imply that oxygen parameters or a project simulation exist.</p><div class="proofcontexts">${f.contextual_reuse.contexts.map((x) => html`<article class="panel"><h4>${x.title}</h4><p class="small"><code>${x.project_ref.namespace}/${x.project_ref.id}@${x.project_ref.version.slice(0, 12)}</code> · ${x.publication_status}</p><p class="small">${x.use}</p><p class="small"><b>Unknown:</b> ${Object.entries(x.parameter_status).map(([k, v]) => `${k}=${v}`).join(", ")}</p><p class="small"><b>Not established:</b> ${x.not_established.join(", ")}</p></article>`)}</div>`) : ""}
      ${fold("Receipt of the recorded run", "exit " + pos.exit + " / " + neg.exit, html`<div class="tablewrap"><table class="qtable"><caption class="sr">Recorded Lean run for ${f.title}</caption><thead><tr><th scope="col">Run</th><th scope="col">Exit</th><th scope="col">Time</th><th scope="col">Axioms used</th><th scope="col">Meaning</th></tr></thead><tbody>
        <tr><td data-label="Run">Positive: the theorems compile</td><td data-label="Exit">${pos.exit}</td><td data-label="Time">${sec(pos.seconds)}</td><td data-label="Axioms">${(pos.axioms || []).join(", ")}${pos.only_standard_axioms ? html` ${U.pill("standard axioms only", "ok")}` : html` ${U.pill("non-standard axioms", "no")}`}</td><td data-label="Meaning" class="small">Lean accepted every theorem; exit 0.</td></tr>
        <tr><td data-label="Run">Negative: mutated statements</td><td data-label="Exit">${neg.exit}</td><td data-label="Time">${sec(neg.seconds)}</td><td data-label="Axioms">not applicable</td><td data-label="Meaning" class="small">Exit 1 is the expected result: every mutated block must fail to compile.</td></tr></tbody></table></div>
      <p class="small">Receipt <a href="${f.receipt.href}">${f.receipt.path.split("/").pop()}</a> ${sha(f.receipt.sha256)}${f.assembled_sources_match === true ? html` · the sources that were compiled were rebuilt from the current files and match the receipt` : ""}. Every pinned input still has its pinned bytes.</p>`)}
      ${fold("Downloads", downloads.length + " files", html`<ul class="small prooffiles">${downloads.map((x) => html`<li><a href="${x.path}" download>${x.name}</a> <span class="faint">${x.role}</span> ${sha(x.sha256)}</li>`)}</ul>${f.statement_origin ? html`<p class="small faint">${f.statement_origin}.</p>` : ""}`)}
    </section>`;
  }

  DF.views.proofs = function (snap) {
    const G = snap.lean_gallery;
    if (!G) return { html: html`<section class="pagehead"><h1>Lean proofs</h1><p class="empty">The Lean gallery is not in this snapshot, so no proof is shown.</p></section>` };
    return {
      html: html`<section class="pagehead proofs-head"><p class="eyebrow">Evidence</p><h1>Lean proofs</h1><p class="lede">The mathematics underneath the design, written in Lean 4 so a machine checks every step. ${G.families.length} small families, each with its assumptions, the receipt of the run that compiled it, and the deliberately wrong versions Lean refused.</p></section>
        <section class="proof-how" aria-label="How to read this page"><div><b>1 · Read the claim</b><p class="small">Each family opens with a plain-language summary and its equations. Assumptions are listed beside what it does not prove.</p></div><div><b>2 · Check the proof</b><p class="small">Open the statements or the full source. Numbered lines scroll inside their own box.</p></div><div><b>3 · Check the checks</b><p class="small">The receipt records the run. Mutants show the statements fail when the law is changed.</p></div></section>
        <section class="panel proof-scope"><p class="pillrow">${U.pill("recorded runs", "warn")} ${U.pill("mathematics, not biology", "warn")}</p><p><b>Lean checks the mathematics of each statement for all values that satisfy its hypotheses.</b> It does not check that the statement models a fish, that a parameter is right, or that anything is true of an organism.</p>
          <details class="pfold"><summary><b>All scope notes and the toolchain</b></summary><div class="pfold-body"><p class="small faint">${G.kind}.</p><ul class="small">${G.scope.map((s) => html`<li>${s}</li>`)}</ul>${G.toolchain ? html`<p class="small">Toolchain: ${G.toolchain.lean_version}; Mathlib revision ${G.toolchain.mathlib_rev}; ${G.toolchain.toolchain}.</p>` : ""}<p class="small">The <a href="${DF.href("/formalize")}">proposal checker</a> writes Lean text for a request but does not compile it; it is a separate path from these hand-written theorems. For the reasoning behind this approach, read the <a href="${DF.href("/about/blog/lean-for-biology")}">blog post</a>.</p></div></details></section>
        <nav class="proofindex-cards" aria-label="Proof families">${G.families.map((f) => html`<a href="#/proofs?f=${f.id}" data-f="${f.id}"><b>${f.title}</b><span class="small">${PLAIN[f.id] ? PLAIN[f.id].split(/(?<=\.)\s/)[0] : ""}</span>${U.pill((STATUS[f.status] || ["?", "no"])[1] === "ok" ? "compiled, recorded" : "stale or failed", (STATUS[f.status] || ["?", "no"])[1])}</a>`)}</nav>
        ${G.families.map(family)}`,
      async after(root) {
        DF.renderMath(root);
        const go = (id) => { const t = root.querySelector("#proof-" + id); if (t) { t.scrollIntoView({ block: "start" }); const h = t.querySelector("h2"); if (h) { h.setAttribute("tabindex", "-1"); h.focus({ preventScroll: true }); } } };
        const f = new URLSearchParams((location.hash.split("?")[1] || "")).get("f"); if (f) go(f);
        root.querySelectorAll(".proofindex a, .proofindex-cards a").forEach((a) => a.addEventListener("click", (e) => { e.preventDefault(); history.replaceState(null, "", a.getAttribute("href")); go(a.dataset.f); }));
      },
    };
  };
})();
