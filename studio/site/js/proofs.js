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

  function family(f) {
    const st = STATUS[f.status] || ["unknown status", "no"]; const ok = f.status === "current";
    const downloads = [...(f.files || []), ...(f.display_artifacts || []).filter((x) => x.status === "verified")];
    const head = html`<h2 id="${"proof-" + f.id + "-h"}">${f.title}</h2><p>${U.pill(st[0], st[1])} ${f.versions ? html`<span class="small faint">${f.versions.lean_version.split(",")[0]} · Mathlib ${String(f.versions.mathlib_rev || "").slice(0, 10)}</span>` : ""}</p>`;
    if (!ok) return html`<section class="panel proof" id="proof-${f.id}" aria-labelledby="proof-${f.id}-h">${head}<p class="note warn small"><b>Withheld.</b> ${f.summary}</p><ul class="small">${(f.reasons || []).map((r) => html`<li>${r}</li>`)}</ul><p class="small faint">A new Lean run, and a new receipt, are needed before this family is shown as compiled again.</p></section>`;
    const run = f.run, pos = run.positive, neg = run.negative;
    return html`<section class="panel proof" id="proof-${f.id}" aria-labelledby="proof-${f.id}-h">${head}
      <p>${f.summary}</p>
      <div class="proofeq">${f.equations.map((e) => html`<div class="eqcard"><h4>${e.label}</h4><div class="eq-math">${DF.texSpan(e.tex, true)}</div></div>`)}</div>
      ${f.figure_href ? html`<figure class="prooffigure"><img src="${f.figure_href}" alt="Sphere and one-sided slab geometry with normalized model-only center oxygen response curves and diffusion limits"><figcaption class="small">Pinned geometry/control figure. Its threshold curves are conditional model implications, not biological measurements.</figcaption></figure>` : ""}
      <h3>Assumptions</h3><ul class="small">${f.assumptions.map((a) => html`<li>${a}</li>`)}</ul>
      ${f.proves ? html`<p class="small"><b>Proves:</b> ${f.proves}</p>` : ""}
      ${f.check_results ? html`<h3>Recorded positive checks (${f.check_results.length})</h3><ul class="small proofchecks">${f.check_results.map((x) => html`<li><b>${x.name}</b> — ${x.status}; axioms: ${x.axioms.join(", ")}</li>`)}</ul>` : ""}
      ${f.contextual_reuse ? html`<h3>Contextual reuse</h3><p class="small"><b>${f.contextual_reuse.status}.</b> These are exact Project-version links for a shared model rule; they do not imply that oxygen parameters or a project simulation exist.</p><div class="proofcontexts">${f.contextual_reuse.contexts.map((x) => html`<article class="panel"><h4>${x.title}</h4><p class="small"><code>${x.project_ref.namespace}/${x.project_ref.id}@${x.project_ref.version.slice(0, 12)}</code> · ${x.publication_status}</p><p class="small">${x.use}</p><p class="small"><b>Unknown:</b> ${Object.entries(x.parameter_status).map(([k, v]) => `${k}=${v}`).join(", ")}</p><p class="small"><b>Not established:</b> ${x.not_established.join(", ")}</p></article>`)}</div>` : ""}
      <h3>What the Lean statements say</h3>
      <div class="proofthms">${f.theorems.map((t) => html`<details><summary><b>${t.kind} ${t.name}</b> <span class="small faint">line ${t.line}</span></summary>${t.doc ? html`<p class="small">${t.doc}</p>` : ""}${code(t.statement, "Lean statement of " + t.name)}</details>`)}</div>
      <details class="proofsrc"><summary><b>Read the Lean source</b> <span class="small faint">${f.source_name}, ${lines(f.source).length} lines</span></summary>${code(f.source, "Lean source " + f.source_name)}</details>
      <h3>Receipt of the recorded run</h3>
      <div class="tablewrap"><table class="qtable"><caption class="sr">Recorded Lean run for ${f.title}</caption><thead><tr><th scope="col">Run</th><th scope="col">Exit</th><th scope="col">Time</th><th scope="col">Axioms used</th><th scope="col">Meaning</th></tr></thead><tbody>
        <tr><td data-label="Run">Positive: the theorems compile</td><td data-label="Exit">${pos.exit}</td><td data-label="Time">${sec(pos.seconds)}</td><td data-label="Axioms">${(pos.axioms || []).join(", ")}${pos.only_standard_axioms ? html` ${U.pill("standard axioms only", "ok")}` : html` ${U.pill("non-standard axioms", "no")}`}</td><td data-label="Meaning" class="small">Lean accepted every theorem; exit 0.</td></tr>
        <tr><td data-label="Run">Negative: mutated statements</td><td data-label="Exit">${neg.exit}</td><td data-label="Time">${sec(neg.seconds)}</td><td data-label="Axioms">not applicable</td><td data-label="Meaning" class="small">Exit 1 is the expected result: every mutated block must fail to compile.</td></tr></tbody></table></div>
      <p class="small">Receipt <a href="${f.receipt.href}">${f.receipt.path.split("/").pop()}</a> ${sha(f.receipt.sha256)}${f.assembled_sources_match === true ? html` · the sources that were compiled were rebuilt from the current files and match the receipt` : ""}. Every pinned input still has its pinned bytes.</p>
      ${f.certificate ? html`<h3>A solver conflict certificate, checked by Lean</h3><p class="small">The constraint solver reported <b>${f.certificate.solver.status}</b> on ${(f.certificate.solver.conflict || []).join(", ")}. Its certificate was compiled ${f.certificate.compiled}. ${f.certificate.solver.scope}</p>${code(f.certificate.lean, "Solver certificate in Lean")}
        <p class="small">A certificate with the speed cap changed from 10 to 20 is rejected:</p><details><summary class="small">Show the corrupted certificate</summary>${code(f.certificate.corrupted_lean, "Corrupted certificate")}</details>` : ""}
      <h3>Mutants Lean rejected (${f.negative_blocks.filter((b) => b.rejected).length} of ${f.negative_blocks.length})</h3>
      <ul class="proofneg">${f.negative_blocks.map((b) => html`<li><details><summary><b>${b.id.replace(/_/g, " ")}</b> ${b.rejected ? U.pill("rejected by Lean", "ok") : U.pill("NOT rejected", "no")}${b.first_error ? html` <span class="small faint">${b.first_error}</span>` : ""}</summary>${code(b.code, "Mutated Lean block " + b.id)}</details></li>`)}</ul>
      ${f.does_not_prove ? html`<h3>What it does not prove</h3><ul class="small">${f.does_not_prove.map((x) => html`<li>${x}</li>`)}</ul>` : ""}
      ${f.statement_origin ? html`<p class="small faint">${f.statement_origin}.</p>` : ""}
      <h3>Downloads</h3><ul class="small prooffiles">${downloads.map((x) => html`<li><a href="${x.path}" download>${x.name}</a> <span class="faint">${x.role}</span> ${sha(x.sha256)}</li>`)}</ul>
    </section>`;
  }

  DF.views.proofs = function (snap) {
    const G = snap.lean_gallery;
    if (!G) return { html: html`<section class="pagehead"><h1>Lean proofs</h1><p class="empty">The Lean gallery is not in this snapshot, so no proof is shown.</p></section>` };
    return {
      html: html`<section class="pagehead"><p class="eyebrow">Evidence</p><h1>Lean proofs</h1><p class="lede">Real Lean 4 source, the receipts of the runs that compiled it, and the mutated statements Lean refused. Four bounded families of mathematics with their assumptions and scope.</p></section>
        <section class="panel"><p class="note warn small"><span class="pillrow">${U.pill("recorded runs", "warn")} ${U.pill("mathematics, not biology", "warn")}</span> ${G.kind}.</p><ul class="small">${G.scope.map((s) => html`<li>${s}</li>`)}</ul>
          ${G.toolchain ? html`<p class="small">Toolchain: ${G.toolchain.lean_version}; Mathlib revision ${G.toolchain.mathlib_rev}; ${G.toolchain.toolchain}.</p>` : ""}
          <p class="small">The <a href="${DF.href("/formalize")}">proposal checker</a> writes Lean text for a request but does not compile it; it is a separate path from these hand-written theorems.</p></section>
        <nav class="panel" aria-label="Proof families"><ul class="proofindex">${G.families.map((f) => html`<li><a href="#/proofs?f=${f.id}" data-f="${f.id}">${f.title}</a> ${U.pill((STATUS[f.status] || ["?", "no"])[1] === "ok" ? "compiled, recorded" : "stale or failed", (STATUS[f.status] || ["?", "no"])[1])}</li>`)}</ul></nav>
        ${G.families.map(family)}`,
      async after(root) {
        DF.renderMath(root);
        const go = (id) => { const t = root.querySelector("#proof-" + id); if (t) { t.scrollIntoView({ block: "start" }); const h = t.querySelector("h2"); if (h) { h.setAttribute("tabindex", "-1"); h.focus({ preventScroll: true }); } } };
        const f = new URLSearchParams((location.hash.split("?")[1] || "")).get("f"); if (f) go(f);
        root.querySelectorAll(".proofindex a").forEach((a) => a.addEventListener("click", (e) => { e.preventDefault(); history.replaceState(null, "", a.getAttribute("href")); go(a.dataset.f); }));
      },
    };
  };
})();
