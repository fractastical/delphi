/* FAQ: plain answers about what the commons is and is not, each tied to the repository document that states it. Numbers appear only where a cited
 * document gives them; no agent count is stated. The page describes the project; it adds no evidence. Registration (route, menu) is the app shell's. */
(function () {
  const DF = window.DF; const { html } = DF; const U = DF.ui;
  const GH = "https://github.com/kganjam/delphi-frontier/blob/main/";
  const repo = (path, label) => ({ href: GH + path, label: label || path, ext: true });

  DF.views.faq = function (snap) {
    const docs = new Map(((snap && snap.documents) || []).map((d) => [d.id, d]));
    const site = (id, label) => (docs.has(id) ? { href: docs.get(id).href, label: label || id } : null);
    const Q = [
      ["claims", "What is a Delphi claim?",
        ["A claim is one atomic assertion, kept with its context (organism, stage, conditions), its evidence, who or what asserted it, and its review status. It is a record that can be disputed, not an established fact.",
         "Review is separate from the record. Every record carries a node-local status, and there is deliberately no accept tool: proposing returns \"proposed\", never \"accepted\". Where a statement came from a pipeline, the adapter does not claim it says what its source says; a reviewer who read the source has to assert that."],
        [site("SPEC-001-record-types", "Record types (spec)"), site("SPEC-002-contribution-review-lifecycle", "Contribution and review lifecycle (spec)"), repo("docs/schema-proposal.md", "How claims and evidence are mapped")]],
      ["mcp", "How does MCP read, propose and contribute?",
        ["The public endpoint is read-only without a login. Writing needs an individual contributor credential, and each request authenticates as its own principal; the server holds no shared token. Anonymous writes and an invalid token were rejected in the recorded checks.",
         "The calculation tools (simulation previews, constraint solving, formalisation, belief calculation) are guarded and bounded, and they write no scientific records. A proposal enters as \"proposed\" and waits for review elsewhere."],
        [site("mcp", "MCP server notes"), site("SPEC-009-agent-workspace-mcp", "Agent workspace MCP (spec)"), { href: DF.href("/formalize"), label: "Proposal checker on this site" }]],
      ["scales", "Where can people and AI step in at each scale?",
        ["At every one of the eleven scales a person or an agent can read what is recorded, comment, ask a question, challenge a claim or propose an edit. Drafts written in the browser stay on that browser until a credentialed contribution is made.",
         "An AI tool can run a bounded preview or a check; a person decides what it means. A scale without a model is shown as a gap and an open question, not filled in."],
        [{ href: DF.href("/studio/flying-fish"), label: "Studio, by scale" }, { href: DF.href("/frontier"), label: "Open questions" }, repo("docs/projects-annotations.md", "Annotations and drafts")]],
      ["hosting", "Is this centralised or distributed?",
        ["The public node, its database and the site are one deployment. Many AI sessions and people worked through it, but much of the event work was handed out by a single coordinating session. We claim one real instance of an agent falsifying a claim the team had seeded, with no coordinator ruling on it, and we do not claim a decentralised architecture was exercised.",
         "The design keeps review and identity separate from the record so that independent operators could review elsewhere. That is a design, not something this deployment demonstrates."],
        [repo("docs/research/about-system-copy.md", "About copy and its caveats"), repo("docs/research/rubric-evidence-matrix.md", "Evidence matrix"), site("SPEC-004-bundles-and-federation", "Bundles and federation (spec)")]],
      ["nanopub", "Does it interoperate with nanopublications? Is it a federated network?",
        ["Some records began as nanopublications and are imported with their provenance kept: the original record, its licence and its creator stay attached. Nanopublication verification was not run here.",
         "There is no running federated network of nodes. Bundles and federation are specified, with fork-on-conflict and disputes as first-class, but this site is one node."],
        [repo("docs/morpholib-import.md", "What was imported, and what was not run"), site("SPEC-004-bundles-and-federation", "Bundles and federation (spec)")]],
      ["genomes", "What does the \"23 genome\" archive cover? Is that complete genomics?",
        ["It is a curated set of 23 genome archives. Each archive's checksum was verified when the run completed, and the locus results are interpreted separately. It is not complete genomics.",
         "A gap in source coverage is not a claim that a gene is lost. On this site the genomic material is a retrieved data slice (identifiers, annotations and counts with licences), labelled data, not a model."],
        [repo("tasks/BUILD.md", "Build log"), { href: DF.href("/studio/flying-fish", { scale: "molecular" }), label: "Molecular scale in the Studio" }, site("SPEC-012-genetic-implementation-blueprints", "Genetic blueprints (spec)")]],
      ["lean", "What does Lean check? Does it verify the biology?",
        ["Lean checks a mathematical statement. The checked examples are small, hand-authored predicates, such as a bound on a cantilever's deflection under stated hypotheses, compiled by an explicit local job. A Lean result says nothing about whether the biology is right.",
         "Translation from English to the formal statement is never proven faithful, and the grammar has no vocabulary for biological mechanism; unsupported biology stays an open translation problem. Imported equations with Lean text were not compiled here and count for nothing as proof."],
        [repo("docs/autoformalization.md", "Autoformalisation notes"), { href: DF.href("/formalize"), label: "Proposal checker" }, repo("docs/morpholib-import.md", "Imported equations")]],
      ["collective", "Is the collective useful? What was measured?",
        ["Observed: an agent falsified a claim the team had seeded, using a probe committed before its output existed, and the claim was withdrawn in place with the old table kept. That is one instance, from event work.",
         "Measured: a preregistered comparison of one analyst against collaborating agents ended in a tie. Every arm scored full marks, so the task could not tell them apart. That is a null about our benchmark, not evidence that agents coordinate better."],
        [repo("docs/research/rubric-evidence-matrix.md", "Evidence and its levels"), repo("docs/research/demo-narrative.md", "How the result is told")]],
      ["compute", "Which compute and models were used? What about NVIDIA BioNeMo or Brev?",
        ["Used and recorded: Nebius GPU jobs and its hosted structure service, Google Cloud machines and the Gemini API, and OpenResearch exemplars shown as a local recorder, not a cloud dispatcher. Allocation, measured use and scientific success are kept separate, and total spend is unknown.",
         "NVIDIA BioNeMo and Brev are not verified here. The hosted structure call is attributed to Nebius Scientific AI; the service gave no evidence it used BioNeMo, and no Brev execution is recorded. Any later use would be reported separately."],
        [repo("docs/bio-services.md", "Hosted model services"), { href: DF.href("/work", { tab: "built" }), label: "How it was built (System)" }, repo("docs/resource-utilization.md", "Resource use")]],
      ["organism", "Is there a realistic flying-fish organism?",
        ["No. The fish is a computational design candidate: geometry, equations, simulations and printable models. No organism was built, no genome was designed, and none of the simulations is a measurement of a living fish.",
         "Each model page states what it does not establish, and a bridge with no registered model is shown as an unresolved question."],
        [{ href: DF.href("/assemblies"), label: "Pinned assemblies and unresolved bridges" }, { href: DF.href("/simulations"), label: "Simulations and their limits" }, { href: DF.href("/demo"), label: "Watch the demo" }]],
    ];
    const link = (l) => (l ? html`<li><a href="${l.href}" ${l.ext ? html`target="_blank" rel="noopener noreferrer"` : ""}>${l.label}</a>${l.ext ? html` <span class="faint small">(repository)</span>` : ""}</li>` : "");
    return {
      html: html`<section class="pagehead"><p class="eyebrow">FAQ</p><h1>Questions people ask</h1><p class="lede">Plain answers about what this commons is, what it checks and what it does not claim. Each answer names the repository document that states it.</p></section>
        <nav class="panel faqindex" aria-label="Questions"><ol class="small">${Q.map(([id, q]) => html`<li><a href="#/faq?q=${id}" data-q="${id}">${q}</a></li>`)}</ol></nav>
        <section class="faq">${Q.map(([id, q, ans, links]) => html`<article class="panel faqitem" id="faq-${id}" aria-labelledby="faq-${id}-h"><h2 id="faq-${id}-h">${q}</h2>${ans.map((p) => html`<p>${p}</p>`)}<ul class="small faqlinks" aria-label="Sources for this answer">${links.map(link)}</ul></article>`)}</section>
        <p class="small faint">${U.pill("describes the project; adds no evidence", "ev")} Numbers appear only where the cited document gives them.</p>`,
      async after(root) {
        const open = (id) => { const t = root.querySelector("#faq-" + id); if (t) { t.scrollIntoView({ block: "start" }); const h = t.querySelector("h2"); h.setAttribute("tabindex", "-1"); h.focus({ preventScroll: true }); } };
        const q = (DF.parseHash ? DF.parseHash().params : {}).q || new URLSearchParams((location.hash.split("?")[1] || "")).get("q");
        if (q) open(q);
        root.querySelectorAll(".faqindex a").forEach((a) => a.addEventListener("click", (e) => { e.preventDefault(); history.replaceState(null, "", a.getAttribute("href")); open(a.dataset.q); }));
      },
    };
  };
})();
