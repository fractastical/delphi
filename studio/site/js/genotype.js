/* Genotype to design: the compiler's dependency graph, the sequence-evidence ledger and the cross-scale design screen, shown as the repository holds them.
 * The compiler checks and proposes; it does not create DNA, and no interface is a calibrated transfer, so nothing is endorsed. Counts are computed by the
 * adapter from the current ledger. A formal dependence is kept apart from the biological premises it would need, and no aggregate confidence is shown.
 * All text is inserted by the renderer's escaping, never as HTML. A stale input is withheld with its reason, never shown as current. */
(function () {
  const DF = window.DF; const { html } = DF; const U = DF.ui;
  const STATE = { unknown: ["unknown", "warn"], proposed: ["proposed", "warn"], measured_context: ["measured in one context", "warn"], calibrated_transfer: ["calibrated transfer", "ok"] };
  const BRIDGE = { context_supported: ["supported in one source context", "warn"], contradicted: ["contradicted by the source", "no"], unresolved: ["unresolved", "warn"] };
  const KIND = { natural_reference: "natural reference", existing_model_output: "existing model output" };
  const word = (s) => String(s === null || s === undefined ? "not stated" : s).replace(/_/g, " ");
  const kv = (o) => Object.entries(o || {}).map(([k, v]) => html`<li><b>${word(k)}</b>: ${v}</li>`);
  const short = (h) => (h ? U.sha(h) : html`<span class="faint">not stated</span>`);

  function counts(g) {
    const c = g.ledger ? g.ledger.counts : null;
    const cell = (n, label, note) => html`<div class="gcount"><b>${n === null || n === undefined ? "withheld" : n}</b><span>${label}</span>${note ? html`<small>${note}</small>` : ""}</div>`;
    return html`<div class="gcounts" role="list" aria-label="Counts computed from the current ledger and compiler">
      ${cell(g.nodes.length || null, "nodes")}${cell(g.interfaces.length || null, "interfaces", g.uncalibrated_interfaces.length + " not calibrated")}
      ${cell(c && c.sequence_artifacts, "sequence artifacts", c ? Object.entries(c.sequence_kinds).map(([k, n]) => n + " " + (KIND[k] || word(k))).join(", ") : "")}
      ${cell(c && c.entries, "contextual entries", c ? Object.entries(c.entries_by_direction).map(([k, n]) => n + " " + word(k)).join(", ") : "")}
      ${cell(g.endorsed_candidates, "endorsed candidates", "no calibrated path")}${cell(c && c.retained_unscreened_proposals, "retained unscreened proposals", "kept, not endorsed")}</div>`;
  }

  function iface(i, nodeText) {
    const st = STATE[i.state] || [word(i.state), "warn"]; const v = i.validation;
    return html`<details class="gif" id="gif-${i.id}"><summary><b>${i.id}</b> ${nodeText(i.from)} <span aria-hidden="true">→</span> ${nodeText(i.to)} ${U.pill(st[0], st[1])}</summary>
      <p class="small">${i.text}.</p><p class="small"><b>A calibrated transfer here needs:</b> ${i.required_measurement}.</p>
      ${i.bridges.length ? html`<p class="small"><b>Recorded bridges:</b> ${i.bridges.map((b) => html`<code>${b.id}</code> `)}</p>` : ""}
      ${v ? html`<div class="gslice"><h3>Validation slice</h3><ul class="small"><li><b>Input:</b> ${v.input}</li><li><b>Observation:</b> ${v.observation}</li><li><b>Decision rule:</b> ${v.decision_rule}</li></ul>
        <p class="small"><b>Controls:</b> ${(v.controls || []).join("; ") || "none stated"}</p>
        <p class="small"><b>Instrument slots:</b> ${v.instrument_slots.map((s) => s.id ? html`<span class="gslot">${s.kind}: <code>${s.id}</code> ${U.pill("uncalibrated", "warn")}</span> ` : html`<span class="gslot">${s.kind}: <span class="faint">${s.gap}</span></span> `)}</p>
        <p class="small faint">${v.invalidated_by_dna_change ? "A changed DNA sequence invalidates this boundary's evidence. " : ""}${v.invalidated_by_context_change ? "A changed context invalidates it too." : ""}</p>
        ${v.ledger_readouts.length ? html`<p class="small"><b>Readouts the ledger names:</b></p><ul class="small">${v.ledger_readouts.map((r) => html`<li><code>${r.entry}</code> ${r.falsifiable_validation_readout}</li>`)}</ul>` : ""}</div>` : html`<p class="note small warn">Validation slice withheld: its inputs changed since it was generated.</p>`}</details>`;
  }

  function chain(g) {
    const text = Object.fromEntries(g.nodes.map((n) => [n.id, n.text]));
    const nodeText = (id) => html`<span class="gnode">${word(id)}</span>`;
    return html`<section class="panel" aria-labelledby="g-chain"><h2 id="g-chain">Six nodes, five interfaces</h2>
      <ol class="gnodes">${g.nodes.map((n, k) => html`<li><span class="gnode" title="${n.text}">${word(n.id)}</span>${k < g.nodes.length - 1 ? html`<span class="garrow" aria-hidden="true">→</span>` : ""}</li>`)}</ol>
      <p class="small faint">${g.interfaces.length ? "Open an interface for what it would need, how it would be checked and what invalidates it." : "The graph is withheld."}</p>
      ${g.interfaces.map((i) => iface(i, nodeText))}
      <p class="small"><b>If the DNA changes:</b> ${g.after_dna_change ? g.after_dna_change.meaning : "not available (validation slices withheld)"}${g.after_dna_change ? html` Retained calibrations: ${g.after_dna_change.retained_calibrations.length}.` : ""}</p></section>`;
  }

  function formal(g) {
    return html`<section class="panel" aria-labelledby="g-formal"><h2 id="g-formal">What follows by structure, and what rests on biology</h2>
      <div class="gtwo"><article class="card"><h3>Formal dependence</h3><p class="small">${g.formal.text}</p>
        <ul class="small">${g.cutsets.map((c) => html`<li><b>${c.claim}</b> crosses ${c.interfaces.join(", ") || "no interface"}; not calibrated: ${c.not_calibrated.join(", ") || "none"}</li>`)}</ul></article>
      <article class="card"><h3>Biological premises, as recorded</h3><ul class="small">${g.premises.map((b) => { const s = BRIDGE[b.status] || [word(b.status), "warn"]; return html`<li id="bridge-${b.id}"><b>${b.id}</b> ${U.pill(s[0], s[1])}<br>${b.conditions} <span class="faint">(from <code>${b.from_entry}</code> to ${word(b.to_layer)})</span></li>`; })}</ul>
        <p class="small faint">Each premise stands alone. They are not combined into a score.</p></article></div></section>`;
  }

  function sequences(g) {
    const L = g.ledger; if (!L) return html`<section class="panel"><h2>Sequences and entries</h2><p class="note warn small">The ledger is withheld, so no sequence or entry is shown.</p></section>`;
    const natural = L.sequences.filter((s) => s.kind === "natural_reference");
    return html`<section class="panel" aria-labelledby="g-seq"><h2 id="g-seq">Natural references and model outputs</h2>
      <p class="small">${natural.length} sequences are natural reference sequences (NCBI annotation); their identity as the experimental allele or construct is <b>unknown</b>. ${L.sequences.length - natural.length} are existing model outputs: generated text, function unknown, never an experimental sequence.</p>
      <details><summary><b>All ${L.sequences.length} sequence artifacts</b></summary><div class="tablewrap"><table class="qtable"><caption class="sr">Sequence artifacts in the ledger</caption><thead><tr><th scope="col">Id</th><th scope="col">Kind</th><th scope="col">Length</th><th scope="col">Identity</th><th scope="col">Sequence sha256</th><th scope="col">Source</th></tr></thead><tbody>
        ${L.sequences.map((s) => html`<tr><td data-label="Id"><code>${s.id}</code></td><td data-label="Kind">${KIND[s.kind] || word(s.kind)}</td><td data-label="Length">${s.length_nt} nt</td><td data-label="Identity">${s.identity ? "experimental identity " + s.identity : "generated, no experimental identity"}</td><td data-label="Sequence sha256">${short(s.sequence_sha256)}</td><td data-label="Source">${s.download ? html`<a href="${s.download}" download>download FASTA</a>` : html`<span class="faint">pinned in ${s.artifact.path.split("/").pop()}</span>`}</td></tr>`)}</tbody></table></div></details>
      <details><summary><b>All ${L.entries.length} contextual entries</b> <span class="small faint">what each source did and in which context</span></summary><div class="tablewrap"><table class="qtable"><caption class="sr">Contextual entries in the ledger</caption><thead><tr><th scope="col">Entry</th><th scope="col">Evidence</th><th scope="col">Direction</th><th scope="col">Function</th><th scope="col">Context</th><th scope="col">Missing bridge</th></tr></thead><tbody>
        ${L.entries.map((e) => html`<tr><td data-label="Entry"><code>${e.id}</code></td><td data-label="Evidence">${word(e.evidence_class)}</td><td data-label="Direction">${word(e.direction)}</td><td data-label="Function">${U.pill(word(e.functional_validation), e.functional_validation === "unknown" ? "warn" : "ev")}</td><td data-label="Context">${Object.keys(e.context).length ? html`<ul class="small gctx">${kv(Object.fromEntries(Object.entries(e.context).map(([k, v]) => [k, typeof v === "object" ? (v && v.accession) || "see ledger" : v])))}</ul>` : html`<span class="faint">not stated</span>`}</td><td data-label="Missing bridge">${e.missing_causal_bridge || html`<span class="faint">not stated</span>`}</td></tr>`)}</tbody></table></div></details>
      <p class="small"><b>Sources:</b> ${L.sources.length} papers or records; ${L.sources.filter((x) => !x.full_text_in_public_tree).length} are cited by response digest and locator only, with no article text republished. ${g.manifests.sequence_evidence ? html`<a href="${g.manifests.sequence_evidence.href}" download>sequence-evidence manifest</a>` : html`<span class="faint">sequence-evidence manifest withheld</span>`}</p></section>`;
  }

  function instruments(g) {
    const C = g.instrument_contracts, S = g.design_screen;
    return html`<section class="panel" aria-labelledby="g-inst"><h2 id="g-inst">Instruments and the design screen</h2>
      ${C ? html`<p class="small">${C.rows.length} instrument contracts are proposed or computed; <b>none is calibrated</b> to any biological system. A contract names what would be measured; it is not a measurement.</p>
      <div class="tablewrap"><table class="qtable"><caption class="sr">Instrument contracts</caption><thead><tr><th scope="col">Instrument</th><th scope="col">Kind</th><th scope="col">Interface</th><th scope="col">Blocked on</th></tr></thead><tbody>
      ${C.rows.map((r) => html`<tr><td data-label="Instrument"><code>${r.id}</code></td><td data-label="Kind">${word(r.kind)} ${U.pill("uncalibrated", "warn")}</td><td data-label="Interface">${r.interface}</td><td data-label="Blocked on">${r.blocked_on || html`<span class="faint">computed from saved fields</span>`}</td></tr>`)}</tbody></table></div>` : html`<p class="note warn small">The instrument contracts are withheld: their file changed since the design manifest was written.</p>`}
      ${S ? html`<p class="small"><b>Design screen:</b> ${S.candidates} candidates were screened down to ${S.survivors} by ${S.stages.length} stages (${S.evidence_kind}). It ranks designs for the next measurement; it is not a biological result and gives no success probability.</p>
      <ul class="small">${S.stages.map((s) => html`<li><b>${word(s.id)}</b>: flagged ${s.flags_any}, rejected on the first listed rule ${s.rejects_first_listed}</li>`)}</ul>` : ""}</section>`;
  }

  DF.genotype = {
    panel(snap) {
      const g = snap.genotype; if (!g) return "";
      const files = g.files || [];
      return html`<div class="genotype" id="genotype"><section class="panel" aria-labelledby="g-head"><p class="eyebrow">Genotype to design</p><h2 id="g-head">What a sequence-to-function checker can and cannot say</h2>
        <p>${U.pill(g.status === "current" ? "inputs match their manifests" : "partial: some inputs withheld", g.status === "current" ? "ok" : "warn")} ${U.pill("proposals, not DNA", "warn")} ${U.pill("0 endorsed", "warn")}</p>
        <ul class="small">${g.scope.map((s) => html`<li>${s}</li>`)}</ul>
        ${g.withheld.length ? html`<div class="note warn small"><b>Withheld.</b><ul>${g.withheld.map((w) => html`<li><code>${w.path}</code>: ${w.reason}</li>`)}</ul></div>` : ""}
        ${counts(g)}</section>
        ${chain(g)}${formal(g)}${sequences(g)}${instruments(g)}
        <section class="panel" aria-labelledby="g-files"><h2 id="g-files">Source files</h2><ul class="small prooffiles">${files.map((f) => html`<li><a href="${f.path}" download>${f.name}</a> <span class="faint">${f.role}</span> ${short(f.sha256)} <span class="faint">${f.bytes} bytes</span></li>`)}</ul></section></div>`;
    },
  };
})();
