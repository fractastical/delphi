/* Views: Engineering, Evidence, Work, Belief and the shared catalog/search list. */
(function () {
  const DF = window.DF; const { html, raw, esc, fmt } = DF; const U = DF.ui; const F = DF.fish;

  /* ---------------- shared candidate state (this browser only; never submitted) ---------------- */
  DF.cand = null; // initialised in app after the snapshot loads
  DF.candLabel = "";
  DF.initCandidate = (snap) => {
    if (DF.cand) return;
    const p = snap.mission.presets.find((x) => x.id === "cyps01");
    DF.cand = F.applyPreset(p, snap.mission); DF.candLabel = p.name;
  };

  /* A canvas with view buttons, drag/touch/keyboard rotation. Returns {redraw}. */
  DF.mountFishCanvas = function (host, { readonly = false, getCand }) {
    host.innerHTML = "";
    const cam = { yaw: F.VIEWS["3/4"][0], pitch: F.VIEWS["3/4"][1] };
    const wrap = document.createElement("div"); wrap.className = "fishwrap";
    const canvas = document.createElement("canvas"); canvas.className = "fishcanvas"; canvas.tabIndex = 0;
    canvas.setAttribute("role", "img");
    const bar = document.createElement("div"); bar.className = "viewbar"; bar.setAttribute("role", "group"); bar.setAttribute("aria-label", "Camera view");
    Object.keys(F.VIEWS).forEach((k) => { const b = document.createElement("button"); b.type = "button"; b.className = "btn small"; b.textContent = k === "3/4" ? "3/4 view" : k[0].toUpperCase() + k.slice(1); b.addEventListener("click", () => { [cam.yaw, cam.pitch] = F.VIEWS[k]; redraw(); }); bar.appendChild(b); });
    wrap.appendChild(canvas); host.appendChild(wrap); host.appendChild(bar);
    const hint = document.createElement("p"); hint.className = "small faint"; hint.textContent = "Drag to rotate, or focus the drawing and use the arrow keys. Stylised body proportions are fixed; only the entered dimensions and fin share change the shape. A design visualisation, not an observed fish and not CFD."; host.appendChild(hint);
    function redraw() {
      const c = getCand(); const geo = F.geometry(c);
      const d = F.derive(c);
      canvas.setAttribute("aria-label", geo.missing ? "Design drawing: dimensions missing" : `Parametric design drawing: standard length ${fmt(c.standard_length_m, 3)} m, span ${fmt(c.span_m, 3)} m, wing area ${fmt(d.area, 3)} square metres. Visualisation only.`);
      F.paint(canvas, geo, cam);
    }
    let drag = null;
    canvas.addEventListener("pointerdown", (e) => { drag = { x: e.clientX, y: e.clientY, yaw: cam.yaw, pitch: cam.pitch }; canvas.setPointerCapture(e.pointerId); });
    canvas.addEventListener("pointermove", (e) => { if (!drag) return; cam.yaw = drag.yaw + (e.clientX - drag.x) * 0.01; cam.pitch = Math.max(-1.5, Math.min(1.5, drag.pitch + (e.clientY - drag.y) * 0.01)); redraw(); });
    const end = () => (drag = null); canvas.addEventListener("pointerup", end); canvas.addEventListener("pointercancel", end);
    canvas.addEventListener("keydown", (e) => { const s = 0.12; const k = { ArrowLeft: [-s, 0], ArrowRight: [s, 0], ArrowUp: [0, -s], ArrowDown: [0, s] }[e.key]; if (k) { e.preventDefault(); cam.yaw += k[0]; cam.pitch = Math.max(-1.5, Math.min(1.5, cam.pitch + k[1])); redraw(); } });
    if (window.ResizeObserver) { const ro = new ResizeObserver(() => redraw()); ro.observe(canvas); DF.onLeave(() => ro.disconnect()); }
    redraw();
    return { redraw };
  };

  DF.mountFishMini = function (host) {
    host.innerHTML = '<div class="mini-canvas"></div>';
    DF.mountFishCanvas(host.querySelector(".mini-canvas"), { getCand: () => DF.cand });
    const cap = document.createElement("p"); cap.className = "caption";
    cap.innerHTML = `Candidate: <b>${esc(DF.candLabel || "custom")}</b>. Dimensions are arithmetic or illustration, not a measured fish. <a href="${DF.href("/engineering")}">Change it in Engineering</a>.`;
    host.appendChild(cap);
  };

  /* ---------------- ENGINEERING ---------------- */
  const STATUS = { pass: ["pass", "ok", "within the check"], fail: ["fail", "no", "outside the check"], unknown: ["cannot evaluate", "unk", "input missing"], disputed: ["disputed", "warn", "sources disagree"] };
  const statusPill = (s) => html`<span class="pill st-${STATUS[s][1]}"><span class="dot" aria-hidden="true"></span>${STATUS[s][0]}</span>`;

  const FIELD_DEFS = [
    ["mass_kg", "Body mass", "kg", "0.1", "Measured range 0.003–0.53 kg"],
    ["standard_length_m", "Standard length", "m", "0.21", "Extant exocoetids reach 0.50 m"],
    ["span_m", "Wing span (tip to tip)", "m", "0.29", "Pectoral span; the area uses span² / AR"],
    ["aspect_ratio", "Aspect ratio", "", "10", "Measured 3.0–16.9 (Table III up to 19.9)"],
    ["pectoral_fin_m", "Pectoral fin length", "m", "0.14", "Check C3: ≤ 0.79 × SL"],
    ["launch_speed", "Declared launch speed", "m/s", "18", "Observed Cypselurus taxi speeds are 16–20 m/s; never assumed"],
    ["rho", "Air density (optional)", "kg/m³", "1.225", "Blank = unknown. Used only by the solver, never defaulted"],
    ["cl_max", "Maximum lift coefficient (optional)", "", "1.0", "Blank = unknown. Used only by the solver, never defaulted"],
    ["mass_min", "Solver requirement: minimum mass", "kg", "0.2", "Sent only to the solver as a design requirement"],
    ["wing_loading_min", "Solver requirement: minimum wing loading", "N/m²", "100", "Sent only to the solver as a design requirement"],
    ["speed_max", "Solver requirement: maximum speed", "m/s", "20", "Sent only to the solver as a design requirement"],
  ];
  const TRI = [["four_winged", "Pelvic fins as a second pair of wings (four-winged)"], ["cg_aft", "Centre of gravity aft of the pectoral fins (qualitative flag)"], ["novel_appendage", "Declare: needs a novel appendage (metadata flag)"], ["powered_flapping", "Declare: needs powered flapping (metadata flag)"], ["assume_pect_ar_wing", "ASSUMPTION: whole-wing aspect ratio can be compared with Fish's fin-level range (off unless yes)"], ["assume_taxi_flight", "ASSUMPTION: the Cypselurus taxi speed anchor applies as a flight bound (off unless yes)"]];

  DF.views.engineering = function (snap, route) {
    const m = snap.mission; const scaleKey = route.params.scale || "organism"; const scale = m.scales.find((s) => s.key === scaleKey) || m.scales.find((s) => s.key === "organism");
    const tabOf = scale.tab;
    const tabScales = (t) => m.scales.filter((s) => s.tab === t);
    const num = (name, label, unit, ph, hint) => html`<div class="field"><label for="f-${name}">${label}${unit ? html` <span class="unit">${unit}</span>` : ""}</label>
        <input id="f-${name}" name="${name}" type="number" step="any" inputmode="decimal" placeholder="unknown" aria-describedby="h-${name}"><small id="h-${name}">${hint}</small><small class="err" id="e-${name}" role="alert"></small></div>`;
    const tri = (name, label) => html`<div class="field"><label for="f-${name}">${label}</label><select id="f-${name}" name="${name}"><option value="">unknown</option><option value="yes">yes</option><option value="no">no</option></select></div>`;
    const shareDef = html`<div class="field"><label for="f-pect_share">Pectoral share of wing area <span class="unit">fraction</span></label><input id="f-pect_share" name="pect_share" type="number" step="0.01" min="0.76" max="0.92" value="0.8" aria-describedby="h-pect_share"><small id="h-pect_share">Visual split only, used when four-winged. Fish 1990: pectorals supply 76–92% of wing area.</small></div>`;

    const scaleTabs = html`<nav class="subnav tabs7" aria-label="Scale groups"><ul>${m.tabs.map((t) => html`<li><a href="${DF.href("/engineering", { scale: tabScales(t)[0].key })}" aria-current="${t === tabOf ? "page" : "false"}">${t}</a></li>`)}</ul></nav>`;
    const chips = html`<ol class="scales compact">${m.scales.map((s, i) => html`<li><a class="scale ${s.have.length ? "has" : "none"} ${s.key === scale.key ? "on" : ""}" href="${DF.href("/engineering", { scale: s.key })}" aria-current="${s.key === scale.key ? "true" : "false"}"><span class="n">${i + 1}</span><b>${s.label}</b></a></li>`)}</ol>`;
    const haveSrc = scale.have.map((id) => snap.mission.sources.find((s) => s.id === id)).filter(Boolean);
    const outC = m.couplings.filter((c) => c.from === scale.key); const inC = m.couplings.filter((c) => c.to === scale.key);
    const cstat = { absent: ["no executable coupling", "no"], empirical: ["empirical fit only", "warn"], qualitative: ["qualitative premise only", "warn"] };
    const cRow = (c, dir) => html`<li>${U.pill(cstat[c.status][0], "cs-" + cstat[c.status][1])} <b>${dir === "out" ? scale.label + " → " + (m.scales.find((s) => s.key === c.to) || {}).label : (m.scales.find((s) => s.key === c.from) || {}).label + " → " + scale.label}</b>: ${c.text}</li>`;

    const reqRows = m.constraints.map((k) => html`<tr data-c="${k.id}"><td><b>${k.id}</b></td><td>${k.name}<br><code class="rule">${k.rule}</code></td><td class="cstat"></td><td class="cdetail"></td><td>${U.src("src:" + k.source, DF.sourceTitle(snap, k.source))}<br><small class="faint">${k.confidence}</small></td></tr>`);

    return {
      html: html`<section class="pagehead"><h1>Engineering</h1>
        <p class="lede">From a requirement to a constrained design: requirements and constraints, candidate checks, and what simulation would be needed. Mission: <b>engineer toward a flying fish</b>.</p></section>

        <nav class="flow" aria-label="Engineering flow"><ol>${[["wb-g", "1 Goal"], ["rq-h", "2 Constraints"], ["ws-h", "3 Candidate"], ["rq-h", "4 Results"], ["oq-h", "5 Open questions"]].map(([id, t]) => html`<li><button type="button" class="btn small ghost" data-scroll="${id}">${t}</button></li>`)}</ol></nav>
        <section class="panel" id="wb-g" aria-labelledby="wb-gh"><h2 id="wb-gh">Goal</h2><p>${m.whiteboard.goal.text}</p><p class="small"><a href="${DF.href("/frontier/G1")}">See it on the whiteboard</a></p></section>
        <section class="panel" aria-labelledby="sc-h"><h2 id="sc-h">Scales</h2>
          <p class="note small">All eleven MorphoSwarm scales are shown. A scale without an executable coupling to its neighbours is an <b>open question</b>, not a gap to ignore.</p>
          ${scaleTabs}${chips}
          <article class="scalecard"><h3>${scale.label} scale</h3>
            <h4>What is indexed</h4>${haveSrc.length ? html`<ul>${haveSrc.map((s) => html`<li>${U.src("src:" + s.id, s.cite.split("). ")[0] + ")")} ${U.pill(s.read_level, "rl")}</li>`)}</ul>` : html`<p class="faint">No source indexed at this scale in this snapshot.</p>`}
            <h4>Open question</h4><p>${scale.open}</p>
            <h4>Couplings</h4><ul class="couplings">${[...inC.map((c) => cRow(c, "in")), ...outC.map((c) => cRow(c, "out"))]}${!inC.length && !outC.length ? html`<li class="faint">No coupling recorded.</li>` : ""}</ul>
            <p class="small faint">${scale.coupling_out}</p></article></section>

        <section class="panel workspace" aria-labelledby="ws-h"><h2 id="ws-h">Design workspace: flying-fish candidate</h2>
          <p class="note warn"><b>Preliminary.</b> This arithmetic reimplements an earlier checker table. Where the corrected solver differs (opt-in assumptions, qualitative flags that cannot pass, genus context), the solver is authoritative. With a live runtime, use the solver request below; this page does not override it.</p>
          <p class="note"><b>Calculation, not a solver.</b> The numbers below are browser arithmetic on published fits (Fish 1990) and thresholds from the checker handoff. They are not an SMT solver, not a simulation, and not validated for any organism. Blank means unknown, and unknown stays unknown.</p>
          <div class="ws-grid">
            <div class="ws-left">
              <div id="fishbig" class="fishbig"></div>
              <div id="wlchart" class="chartwrap"></div>
            </div>
            <form id="candform" class="ws-form" aria-label="Candidate design inputs" novalidate>
              <div class="presets" role="group" aria-label="Load a labelled example">${m.presets.map((p) => html`<button class="btn small ghost" type="button" data-preset="${p.id}" title="${p.note}">${p.name}</button>`)}</div>
              <p id="presetnote" class="small faint" role="status"></p>
              <fieldset><legend>Dimensions</legend>${FIELD_DEFS.map((f) => num(...f))}</fieldset>
              <fieldset><legend>Design premises</legend>${TRI.map(([n, l]) => tri(n, l))}${shareDef}</fieldset>
              <div class="row-actions"><button class="btn ghost small" type="button" id="resetc">Clear all (unknown)</button><button class="btn small" type="button" id="dlc">Download candidate JSON</button></div>
              <p class="small faint">The download is a local file on your machine. Nothing is submitted anywhere.</p>
            </form>
          </div>
          <div id="derived" class="derived" aria-live="polite"></div>
        </section>

        <section class="panel" aria-labelledby="rq-h"><h2 id="rq-h">Requirements and constraints, checked against this candidate</h2>
          <div id="verdict" class="verdictbox" role="status"></div>
          <div class="tablewrap"><table class="ctable"><thead><tr><th>Id</th><th>Constraint</th><th>Status</th><th>Detail</th><th>Source and confidence</th></tr></thead><tbody>${reqRows}</tbody></table></div>
          <p class="small faint">A satisfied check means “not refuted by this threshold”. A threshold measured on one population does not transfer outside it, and the extrapolation flag says when it is being used that way. “Cannot evaluate” is never counted as a pass.</p></section>

        <section class="panel" aria-labelledby="ex-h"><h2 id="ex-h">What the measured fits say beyond the measured range</h2>
          <p class="note small">${m.extrapolation_table_note}</p>
          <div class="tablewrap"><table><thead><tr><th>Mass (kg)</th><th><i>Cypselurus</i> WL (N/m²)</th><th><i>Hirundichthys</i> WL (N/m²)</th><th>Required speed, anchored at 16 m/s (<i>Cypselurus</i>)</th><th>Status</th></tr></thead><tbody>
            ${F.extrapolationRows(m).map((r) => html`<tr><td>${r.m}</td><td>${fmt(r.cy, 3)}</td><td>${fmt(r.hi, 3)}</td><td>${fmt(r.v, 3)} m/s</td><td>${r.measured ? U.pill("edge of measured range", "ok") : U.pill("extrapolated", "warn")}</td></tr>`)}</tbody></table></div></section>

        <section class="panel" aria-labelledby="oq-h"><h2 id="oq-h">Open questions that limit this design</h2>
          <p class="note small">For each constraint, the unresolved questions that stop it from being strengthened or trusted further. They update with the candidate's results; each opens on the whiteboard.</p>
          <div id="oqlist"></div></section>

        <section class="panel" aria-labelledby="rr-h"><h2 id="rr-h">Recorded results: Lean receipt and simulation</h2>${recordedResults(snap)}</section>

        <section class="panel" aria-labelledby="sv-h"><h2 id="sv-h">Solver candidates and simulation</h2>
          <div class="two">
            <article><h3>Solver candidates</h3><p>None attached to this snapshot. A solver returns satisfiable, unsatisfiable, unknown or timeout; the page will show whichever it returns, never a default.</p>
              <button class="btn small" type="button" data-adapter="solve">Request a solver run</button><p class="small faint">Sends this candidate's entered numbers as decimal strings; blank air density and lift coefficient stay unknown. No online Lean status is produced; any Lean receipt is separate and offline.</p><div class="adapter-out" data-out="solve" role="status"></div></article>
            <article><h3>Simulation</h3><p>No recorded glide simulation is attached to this snapshot. Only a recorded run, with its receipt, will appear here; the arithmetic above is not a simulation.</p>
              <button class="btn small" type="button" data-adapter="simulate">Request a simulation run</button><div class="adapter-out" data-out="simulate" role="status"></div></article>
          </div></section>`,
      after(root) { wireEngineering(root, snap); },
    };
  };

  function recordedResults(snap) {
    const L = snap.lean_receipt, S = snap.simulation; const fx = (x, d = 4) => (x === null || x === undefined ? "n/a" : fmt(x, d));
    const lean = L ? html`<article class="card"><h3>Lean check (offline receipt)</h3>
        <p>${U.pill(L.all_ok ? "all checks as recorded" : "recorded failure", L.all_ok ? "ok" : "no")} ${U.pill("not run by this page", "warn")}</p>
        <p class="small">${L.lean_version}. Mathlib ${String(L.mathlib_rev).slice(0, 12)}, toolchain ${L.toolchain}. Receipt <code>${L.path}</code> sha256 ${U.sha(L.sha256)}.</p>
        <ul><li>Positive file: exit <b>${L.positive.exit}</b> in ${L.positive.seconds} s; axioms used ${(L.positive.axioms_used || []).join(", ")}${L.positive.only_standard_axioms ? " (standard only)" : " (NON-standard axiom present)"}.</li>
        <li>Negative controls (altered law or corrupted certificate): exit ${L.negative.exit}; each block rejected: ${Object.entries(L.negative.each_block_rejected || {}).map(([k, v]) => `${k}: ${v ? "rejected" : "ACCEPTED"}`).join(", ")}.</li></ul>
        <p class="note small"><b>What this does and does not show.</b> It checks that a specific conflict certificate for three encoded constraints (level-lift proxy, minimum wing loading, maximum speed) is valid, and that mutated laws fail. It is a statement about the encoding of those constraints, not about any fish. The solver's other verdicts are z3 verdicts with no Lean check, and the solve endpoint reports Lean as not run.</p></article>`
      : html`<article class="card"><h3>Lean check</h3><p class="empty">No Lean receipt is present in this tree. Nothing is shown in its place.</p></article>`;
    if (!S) return html`<div class="cards">${lean}<article class="card"><h3>Simulation</h3><p class="empty">No recorded simulation results are present in this tree (looked for <code>engineering/simulation/results/summary.json</code>). There is also no mesh or print geometry. Nothing is drawn in their place.</p></article></div>`;
    const m = S.summary; const c = S.controls || {}; const f = S.findings || {};
    const ctl = Object.entries(c).filter(([k, v]) => typeof v === "object" && v !== null).map(([k, v]) => html`<tr><td>${k.replace(/_/g, " ")}</td><td>${v.rel_err !== undefined ? fx(v.rel_err, 3) : v.max_rel_drift !== undefined ? fx(v.max_rel_drift, 3) : v.rel_diff !== undefined ? fx(v.rel_diff, 3) : ""}</td><td>${v.tol !== undefined ? v.tol : ""}</td></tr>`);
    const sim = html`<article class="card"><h3>Glide simulation (${m.model_version}) ${U.pill("simulated", "ev")}</h3>
        <p class="small">${m.n_designs} designs, ${m.n_pareto} on the Pareto set, ${m.n_unconverged} unconverged; largest step-halving range difference ${fx(m.max_dt_half_rel_diff, 3)}. Monte Carlo n = ${m.mc_n}, seed ${m.mc_seed}.
          Nominal assumptions: ${Object.entries(m.nominal_assumptions || {}).map(([k, v]) => k + " = " + v).join(", ")}. These coefficients are model assumptions, not measurements.</p>
        <div class="tablewrap"><table><thead><tr><th>Numerical control</th><th>Error or drift</th><th>Tolerance</th></tr></thead><tbody>${ctl}</tbody></table></div>
        <p class="small">All controls pass: <b>${String(c.all_pass)}</b>.</p>
        ${f.interpretation ? html`<p class="note warn small"><b>The authors' own caveat.</b> ${f.interpretation}</p>` : ""}</article>`;
    const fig = (S.files || []).find((x) => x.name === "figure.png");
    const par = S.pareto_selected || [];
    return html`<div class="cards">${lean}${sim}</div>
      ${fig ? html`<figure class="simfig"><img src="${fig.href}" alt="Recorded simulation figure from the glide sweep" loading="lazy"><figcaption class="small faint">Figure as recorded (<code>${fig.path}</code>, sha256 ${U.sha(fig.sha256)}). Simulated point-mass glides, not a fish and not CFD.</figcaption></figure>` : ""}
      ${par.length ? html`<details class="pareto"><summary><b>${par.length} selected Pareto designs (simulated)</b>: open the table</summary><p class="small faint">Objectives: ${(m.pareto_objectives || []).join("; ")}. Range quantiles come from the Monte Carlo over the priors above. Use one as the candidate to compare it against the constraint flags; the standard length stays unknown.</p>
        <div class="tablewrap"><table><thead><tr><th>m (kg)</th><th>S (m²)</th><th>b (m)</th><th>AR</th><th>WL (N/m²)</th><th>range q10 / q50 / q90 (m)</th><th>sink (m/s)</th><th>L/D</th><th></th></tr></thead><tbody>${par.map((d, i) => html`<tr><td>${fx(d.m, 3)}</td><td>${fx(d.S, 3)}</td><td>${fx(d.b, 3)}</td><td>${fx(d.AR, 3)}</td><td>${fx(d.WL, 3)}</td><td>${fx(d.range_q10, 3)} / ${fx(d.range_q50, 3)} / ${fx(d.range_q90, 3)}</td><td>${fx(d.sink_eq_ms, 3)}</td><td>${fx(d.LoD_eq, 3)}</td><td><button class="btn small ghost" type="button" data-pareto="${i}">Use as candidate</button></td></tr>`)}</tbody></table></div></details>` : ""}
      <p class="small">Files: ${(S.files || []).map((x) => html`<a href="${x.href}">${x.name}</a> (${x.bytes} bytes, ${U.sha(x.sha256)}) `)}</p>
      <p class="small faint">There is no mesh or print-geometry artifact in this tree; the drawing above is a parametric visualisation, not a validated model.</p>`;
  }

  function readForm(form) {
    const c = F.blank(); const errors = {};
    ["mass_kg", "standard_length_m", "span_m", "aspect_ratio", "pectoral_fin_m", "launch_speed", "rho", "cl_max", "mass_min", "wing_loading_min", "speed_max"].forEach((n) => {
      const raw = form.elements[n].value.trim(); if (raw === "") { c[n] = null; return; }
      const v = Number(raw); if (!isFinite(v) || v <= 0) { c[n] = null; errors[n] = "Enter a positive number, or leave blank for unknown."; } else c[n] = v;
    });
    ["four_winged", "cg_aft", "novel_appendage", "powered_flapping", "assume_pect_ar_wing", "assume_taxi_flight"].forEach((n) => { const v = form.elements[n].value; c[n] = v === "yes" ? true : v === "no" ? false : null; });
    const s = Number(form.elements.pect_share.value); c.pect_share = isFinite(s) && s >= 0.76 && s <= 0.92 ? s : 0.8;
    if (form.elements.pect_share.value !== "" && !(s >= 0.76 && s <= 0.92)) errors.pect_share = "Use 0.76–0.92.";
    return { c, errors };
  }
  function writeForm(form, c) {
    Object.keys(c).forEach((n) => { const el = form.elements[n]; if (!el) return; el.value = typeof c[n] === "boolean" ? (c[n] ? "yes" : "no") : c[n] === null ? "" : c[n]; });
  }

  function wireEngineering(root, snap) {
    const m = snap.mission; const form = root.querySelector("#candform");
    const fish = DF.mountFishCanvas(root.querySelector("#fishbig"), { getCand: () => DF.cand });
    writeForm(form, DF.cand);
    function update(fromForm) {
      if (fromForm) { const { c, errors } = readForm(form); DF.cand = c; DF.candLabel = "custom"; ["mass_kg", "standard_length_m", "span_m", "aspect_ratio", "pectoral_fin_m", "launch_speed", "rho", "cl_max", "mass_min", "wing_loading_min", "speed_max", "pect_share"].forEach((n) => { const e = root.querySelector("#e-" + n); if (e) { e.textContent = errors[n] || ""; form.elements[n].setAttribute("aria-invalid", errors[n] ? "true" : "false"); } }); }
      const c = DF.cand; const d = F.derive(c); const res = F.checks(c, m); const v = F.verdict(res);
      root.querySelector("#derived").innerHTML = html`<h3>Derived (arithmetic)</h3><dl class="kv">
        <div><dt>Wing area S = span² / AR</dt><dd>${d.area === null ? "unknown" : fmt(d.area, 4) + " m²"}</dd></div>
        <div><dt>Wing loading WL = M g / S</dt><dd>${d.wl === null ? "unknown" : fmt(d.wl, 4) + " N/m²"}</dd></div>
        <div><dt>Required launch speed 16 √(WL / 205.5)</dt><dd>${d.vreq === null ? "unknown" : fmt(d.vreq, 3) + " m/s"}</dd></div>
        <div><dt>Mass inside measured range?</dt><dd>${!F.known(c.mass_kg) ? "unknown" : d.extrapolated ? "No: extrapolated" : "Yes"}</dd></div></dl>
        ${F.known(c.pectoral_fin_m) && F.known(c.span_m) && (2 * c.pectoral_fin_m < 0.8 * c.span_m || 2 * c.pectoral_fin_m > 1.2 * c.span_m) ? html`<p class="note small">Pectoral fin length and span are not consistent (two fins plus the body should roughly equal the span). The drawing uses the span; check C3 uses the fin length.</p>` : ""}`.toString();
      root.querySelector("#verdict").innerHTML = html`<div class="vlabel v-${v.label.replace(/ /g, "-").toLowerCase()}">${v.label}</div>
        <p>${v.evaluable} of ${v.total} checks could be evaluated. ${v.failed.length ? html`Failed: <b>${v.failed.join(", ")}</b>. ` : ""}${v.unknown.length ? html`Cannot evaluate: ${v.unknown.join(", ")}. ` : ""}${v.disputed.length ? html`Disputed: ${v.disputed.join(", ")}. ` : ""}${v.extrapolated.length ? html`<b>Extrapolated</b>: ${v.extrapolated.join(", ")}.` : ""}</p>
        <p class="small faint">Scope: browser arithmetic against published thresholds. “No flag raised” means no evaluable threshold failed. It does not mean feasible, evolvable or flightworthy, and says nothing about reachability. “Flag raised” names thresholds or declared premises, not an impossibility.</p>`.toString();
      m.constraints.forEach((k) => { const r = res[k.id]; const tr = root.querySelector(`tr[data-c="${k.id}"]`);
        tr.querySelector(".cstat").innerHTML = statusPill(r.status).toString() + (r.extrapolated ? ' <span class="pill st-warn">extrapolated</span>' : "");
        tr.querySelector(".cdetail").innerHTML = esc(r.detail) + (r.note ? ` <small class="faint">${esc(r.note)}</small>` : "") + `<br><small class="faint">${esc(k.note)}</small>`; });
      fish.redraw(); F.wlChart(root.querySelector("#wlchart"), m, c);
      const qs = DF.questions(snap);
      root.querySelector("#oqlist").innerHTML = m.constraints.map((k) => { const lim = qs.filter((q) => (m.whiteboard.annotations[q.id] || {}).limits && m.whiteboard.annotations[q.id].limits.includes(k.id));
        return `<div class="oqrow"><b>${esc(k.id)} ${esc(k.name)}</b> ${statusPill(res[k.id].status)} ${lim.length ? lim.map((q) => `<a href="${esc(DF.href("/frontier/" + q.id))}">${esc(q.id)}: ${esc(q.title)}</a>`).join(" · ") : '<span class="faint">no unresolved question recorded</span>'}</div>`; }).join("");
    }
    form.addEventListener("input", () => update(true)); form.addEventListener("submit", (e) => e.preventDefault());
    root.querySelectorAll("[data-preset]").forEach((b) => b.addEventListener("click", () => {
      const p = m.presets.find((x) => x.id === b.dataset.preset); DF.cand = F.applyPreset(p, m); DF.candLabel = p.name; writeForm(form, DF.cand);
      root.querySelector("#presetnote").textContent = p.name + ": " + p.note; update(false);
    }));
    root.querySelectorAll("[data-pareto]").forEach((b) => b.addEventListener("click", () => {
      const d = snap.simulation.pareto_selected[+b.dataset.pareto]; const c = F.blank();
      c.mass_kg = +d.m.toPrecision(6); c.span_m = +d.b.toPrecision(6); c.aspect_ratio = +d.AR.toPrecision(6);
      DF.cand = c; DF.candLabel = `Pareto design ${+b.dataset.pareto + 1} (simulated, glide-pointmass)`; writeForm(form, c);
      root.querySelector("#presetnote").textContent = DF.candLabel + ": mass, span and aspect ratio from a simulated sweep. Standard length is unknown."; update(false);
      form.scrollIntoView({ block: "start" });
    }));
    root.querySelector("#resetc").addEventListener("click", () => { DF.cand = F.blank(); DF.candLabel = "nothing declared"; writeForm(form, DF.cand); root.querySelector("#presetnote").textContent = "Cleared. Every check is now unknown."; update(false); });
    root.querySelector("#dlc").addEventListener("click", () => {
      const c = DF.cand; const doc = { schema: "frontier-site-candidate-0.1", note: "Local browser arithmetic. Not a solver result, not a simulation, not submitted.", snapshot: snap.label, label: DF.candLabel, candidate: c, derived: F.derive(c), checks: Object.fromEntries(Object.entries(F.checks(c, m)).map(([k, r]) => [k, { status: r.status, detail: r.detail, extrapolated: !!r.extrapolated }])), verdict: F.verdict(F.checks(c, m)) };
      const url = URL.createObjectURL(new Blob([JSON.stringify(doc, null, 2)], { type: "application/json" }));
      const a = document.createElement("a"); a.href = url; a.download = "frontier-candidate.json"; document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 2000);
    });
    root.querySelectorAll("[data-adapter]").forEach((b) => b.addEventListener("click", async () => {
      const out = root.querySelector(`[data-out="${b.dataset.adapter}"]`); out.textContent = "Requesting…";
      try { const r = await DF.api[b.dataset.adapter](DF.cand); out.className = "adapter-out"; out.innerHTML = solveResult(r); }
      catch (e) { out.className = "adapter-out unavailable"; out.textContent = e.name === "Unavailable" ? `Not connected: ${e.adapter}. ${e.detail}` : "Request failed: " + e.message; }
    }));
    root.querySelectorAll("[data-scroll]").forEach((b) => b.addEventListener("click", () => { const t = root.querySelector("#" + b.dataset.scroll); if (t) { t.scrollIntoView({ block: "start" }); t.setAttribute("tabindex", "-1"); t.focus({ preventScroll: true }); } }));
    update(false);
  }

  function solveResult(r) {
    const res = r.result || {}; const man = r.ui_manifest || r.manifest || null; const fu = Array.isArray(r.followup_questions) ? r.followup_questions : [];
    const cb = r.checked_by && typeof r.checked_by === "object" ? r.checked_by : null; const prov = res.provenance && typeof res.provenance === "object" ? res.provenance : null;
    const list = (a) => (a && a.length ? html`<ul>${a.map((x) => html`<li>${typeof x === "string" ? x : JSON.stringify(x)}</li>`)}</ul>` : "");
    const wit = res.witness && typeof res.witness === "object" ? res.witness : null; const conf = res.conflict;
    const kv = (o) => html`<dl class="kv">${Object.entries(o).map(([k, v]) => html`<div><dt>${k}</dt><dd>${typeof v === "object" && v !== null ? JSON.stringify(v) : DF.exact(v)}</dd></div>`)}</dl>`;
    const params = r.parameters && typeof r.parameters === "object" ? r.parameters : {};
    return html`<div class="verdictbox"><div class="vlabel">${(man && man.badge) || res.status || "no status returned"}</div>
      ${man && man.headline ? html`<p><b>${man.headline}</b></p>` : ""}${res.reason ? html`<p>${res.reason}</p>` : ""}
      <p class="small">${r.schema || ""} · evidence kind <b>${r.evidence_kind || "not reported"}</b> · computed ${r.computed_at || "not reported"} · request sha256 <code>${r.request_sha256 || "not reported"}</code></p>
      ${r.scope || res.scope ? html`<p class="note small"><b>Scope.</b> ${r.scope || res.scope}</p>` : ""}
      ${man && man.must_display && man.must_display.length ? html`<h4>The solver requires this to be shown</h4>${list(man.must_display)}` : ""}
      ${man && man.must_not_say && man.must_not_say.length ? html`<h4>Must not be said</h4>${list(man.must_not_say)}` : ""}
      ${wit ? html`<h4>Witness: an exact point in the encoded model, not a validated design</h4>${kv(wit)}` : ""}
      ${res.partial_witness && typeof res.partial_witness === "object" ? html`<h4>Partial point (NOT a design)</h4>${kv(res.partial_witness)}` : ""}
      ${Array.isArray(res.missing_parameters) && res.missing_parameters.length ? html`<p><b>Unset parameters, so some constraints were not evaluated:</b> ${res.missing_parameters.join(", ")}</p>` : ""}
      ${conf ? html`<h4>Conflict</h4><pre class="json">${JSON.stringify(conf, null, 1)}</pre>` : ""}
      ${Array.isArray(res.extrapolates_envelope) && res.extrapolates_envelope.length ? html`<p class="note warn small"><b>Extrapolates a source envelope:</b> ${res.extrapolates_envelope.join(", ")}</p>` : ""}
      ${prov ? html`<h4>Constraints used and where they come from</h4><div class="tablewrap"><table><thead><tr><th>Constraint</th><th>Kind</th><th>Source</th><th>Correspondence</th></tr></thead><tbody>${Object.entries(prov).map(([k, x]) => html`<tr><td><code>${k}</code></td><td>${x.kind}</td><td>${x.source}</td><td>${x.correspondence || ""}</td></tr>`)}</tbody></table></div>` : ""}
      ${man && Array.isArray(man.rows) ? html`<h4>Constraint rows</h4><div class="tablewrap"><table><thead><tr><th>Constraint</th><th>Kind</th><th>In force</th><th>In conflict</th><th>Source</th><th>Correspondence</th></tr></thead><tbody>${man.rows.map((x) => html`<tr><td>${x.name || x.id || ""}</td><td>${x.kind}</td><td>${String(x.in_force)}</td><td>${String(x.in_conflict)}</td><td>${x.source || ""}</td><td>${x.correspondence || ""}${x.opt_in_assumption ? " (opt-in assumption)" : ""}${x.parameters_missing && x.parameters_missing.length ? " Missing: " + x.parameters_missing.join(", ") : ""}</td></tr>`)}</tbody></table></div>` : ""}
      <h4>Checks</h4>${cb ? html`<ul><li>Solver: ${res.solver ? JSON.stringify(res.solver) : cb.solver ? JSON.stringify(cb.solver) : "not reported"}</li><li>Independent witness check: ${cb.independent_witness ? html`<b>${cb.independent_witness.ok === true ? "passed" : "not passed"}</b> ${cb.independent_witness.problems && cb.independent_witness.problems.length ? JSON.stringify(cb.independent_witness.problems) : ""}` : "not applicable (no witness)"}</li><li>Lean: <b>${cb.lean === "not_run" ? "not run online" : String(cb.lean)}</b>. Any Lean receipt is offline and separate.</li></ul>` : html`<p>${typeof r.checked_by === "string" ? r.checked_by : "not reported"}</p>`}
      ${man && man.lean ? html`<p class="small">Lean covers: ${JSON.stringify(man.lean.covers || "")}. Does not cover: ${JSON.stringify(man.lean.does_not_cover || "")}.</p>` : ""}
      ${r._submitted ? html`<h4>Exactly what was submitted</h4><p class="small faint">Decimal strings rounded to 12 places; the area is derived as span² / aspect ratio in this browser. A null is an unknown, never a default.</p><pre class="json">${JSON.stringify(r._submitted, null, 1)}</pre>` : ""}
      <h4>Parameters (caller-supplied, with their basis)</h4><div class="tablewrap"><table><thead><tr><th>Name</th><th>Value</th><th>Unit</th><th>Basis</th></tr></thead><tbody>${Object.entries(params).map(([k, p]) => html`<tr><td>${k}</td><td>${p && typeof p === "object" ? (p.value === null ? "unknown" : p.value) : String(p)}</td><td>${p && p.unit || ""}</td><td>${p && p.basis || ""}</td></tr>`)}</tbody></table></div>
      ${fu.length ? html`<h4>Follow-up questions (${r.questions_persisted === false ? "not stored; shown for this result only" : "as returned"})</h4><ul>${fu.map((q) => html`<li>${typeof q === "string" ? q : html`${U.pill(q.approach || "question", "ap-" + (q.approach || "unknown"))} ${q.question} <span class="faint small">${(q.scales || []).join(", ")}</span>`}</li>`)}</ul>` : ""}</div>`.toString();
  }

  /* ---------------- EVIDENCE ---------------- */
  const readClass = (rl) => (/^full-text/.test(rl) ? "full-text" : /^abstract/.test(rl) ? "abstract" : /parsed/.test(rl) ? "parsed data" : "summary / listing / unread");
  DF.views.evidence = function (snap, route) {
    const m = snap.mission; const f = { rl: route.params.rl || "" };
    const srcs = m.sources.filter((s) => !f.rl || readClass(s.read_level) === f.rl);
    const classes = [...new Set(m.sources.map((s) => readClass(s.read_level)))];
    const docs = snap.documents.filter((d) => d.href.includes("results") || /RESULT|STOPPED/.test(d.href));
    const neg = [
      ...m.sources.filter((s) => /listing|search-summary/.test(s.read_level) || /NOT READ/i.test(s.note)).map((s) => ({ t: s.cite.split(". ")[0] + "…", w: `Read level: ${s.read_level}. ${s.note}`, id: "src:" + s.id })),
      ...m.data_inventory.filter((d) => /not found/.test(d.state)).map((d) => ({ t: d.what, w: d.detail, id: null })),
    ];
    return {
      html: html`<section class="pagehead"><h1>Evidence</h1><p class="lede">Sources with the grade at which each was actually read, disagreements kept visible, and replayable results, including the one that stopped. Open any source to see what the page rests on.</p></section>

      <section class="panel" aria-labelledby="ev-s"><h2 id="ev-s">Sources</h2>
        <form class="filters" data-form="evidence" aria-label="Filter sources"><label>Read level <select name="rl"><option value="">all</option>${classes.map((c) => html`<option ${c === f.rl ? raw("selected") : ""}>${c}</option>`)}</select></label><button class="btn" type="submit">Apply</button>${f.rl ? html`<a class="btn ghost" href="${DF.href("/evidence")}">Clear</a>` : ""}</form>
        <p class="count" role="status">${srcs.length} of ${m.sources.length} sources shown</p>
        <div class="tablewrap"><table><thead><tr><th>Source</th><th>Read level</th><th>Evidence kind</th><th>What it supports</th></tr></thead><tbody>
          ${srcs.map((s) => html`<tr><td>${U.src("src:" + s.id, s.cite)}</td><td>${U.pill(s.read_level, "rl")}</td><td>${U.pill(s.kind, "ev")}</td><td>${s.note}</td></tr>`)}</tbody></table></div>
        <p class="small faint">Read levels are the research report's own. “As returned by a fetch tool” means a separate small model summarised the page; that is weaker than text parsed directly.</p></section>

      <section class="panel" aria-labelledby="ev-d"><h2 id="ev-d">Disagreement</h2><div class="cards">
        ${m.disagreements.map((d) => html`<article class="card"><h3>${d.title}</h3><ul class="positions">${d.positions.map((p) => html`<li><b>${p.who}:</b> ${p.says}</li>`)}</ul><p><b>How the page handles it.</b> ${d.handling}</p><p class="small">${U.src("src:" + d.source, "Open the source")}</p></article>`)}</div></section>

      <section class="panel" aria-labelledby="ev-r"><h2 id="ev-r">Replayable results</h2>
        <p class="note small">These two records were produced by earlier work and are shown with their own caveats. The cavefish result is a reproduction on public data, not a discovery; its biological interpretation is labelled separately in the document. The KCNE1 protocol stopped at its preregistered floor: a failed input gate is evidence about the proposed action.</p>
        <div class="cards">${docs.filter((d) => /results/.test(d.path)).map((d) => html`<article class="card"><h3>${d.title}</h3><p>${d.status_line ? d.status_line : ""}</p><p class="small">${U.src("doc:" + d.id, "Open the full document")} · sha256 ${U.sha(d.sha256)} · <a href="${d.href}">raw file</a></p></article>`)}</div></section>

      <section class="panel" aria-labelledby="ev-a"><h2 id="ev-a">Artifacts index</h2>
        <p class="note small">Data, proofs, simulations, geometry, code and documents, each with its exact source, the context it was made in, the check it passed or failed, any dispute, and the next action. A digest in a record is a declaration, not a byte verification. <b>No simulation or geometry artifact is indexed in this snapshot.</b></p>
        <form class="filters" data-form="evidence" aria-label="Filter artifacts"><label>Type <select name="at"><option value="">all</option>${["data", "proof", "simulation", "geometry", "protocol", "code", "document"].map((t) => html`<option ${t === (route.params.at || "") ? raw("selected") : ""}>${t}</option>`)}</select></label><input type="hidden" name="rl" value="${f.rl}"><button class="btn" type="submit">Apply</button></form>
        <div id="artifacts" role="status">Loading…</div></section>

      <section class="panel" aria-labelledby="ev-n"><h2 id="ev-n">What could not be obtained</h2>
        <p class="note small">Unread sources and unfound data are first-class: they bound what any constraint here can claim.</p>
        <ul class="neg">${neg.map((n) => html`<li><b>${n.t}</b> ${n.w} ${n.id ? U.src(n.id, "Open") : ""}</li>`)}</ul>
        <h3>Data inventory (exocoetid)</h3><div class="tablewrap"><table><thead><tr><th>Dataset</th><th>State</th><th>Detail</th></tr></thead><tbody>${m.data_inventory.map((d) => html`<tr><td>${d.what}</td><td>${U.pill(d.state, /not found/.test(d.state) ? "no" : "ok")}</td><td>${d.detail}</td></tr>`)}</tbody></table></div>
        <p class="small faint">States separate discovered, retrieved, replayed and validated. Here, nothing has been replayed or validated.</p></section>`,
      async after(root) {
        DF.bindForm(root, "evidence", (v) => DF.href("/evidence", v));
        const host = root.querySelector("#artifacts"); const want = route.params.at || "";
        const rows = DF.artifactIndex(snap);
        try { const r = await DF.api.artifacts({ limit: 50 }); rows.push(...DF.liveArtifacts(r.items)); } catch (e) { rows.push({ title: "Runtime artifacts could not be read", type: "document", source: e.message, context: "", check: "", dispute: "", next: "", error: true }); }
        const shown = rows.filter((r) => !want || r.type === want);
        host.innerHTML = shown.length ? html`<div class="tablewrap"><table class="arttable"><thead><tr><th>Artifact</th><th>Type</th><th>Exact source</th><th>Context</th><th>Check</th><th>Dispute</th><th>Next action</th></tr></thead><tbody>${shown.map((r) => html`<tr><td>${r.doc ? U.src("doc:" + r.doc, r.title) : r.title}</td><td>${U.pill(r.type, "ev")}</td><td>${r.url ? U.ext(r.url, r.source) : r.source}</td><td>${r.context}</td><td>${r.check}</td><td>${r.dispute || ""}</td><td>${r.next}${r.download ? html` <a class="btn small ghost" href="${r.download}" target="_blank" rel="noopener noreferrer" download>Download file</a>` : r.doc ? "" : html` <span class="faint small">no downloadable file is declared</span>`}</td></tr>`)}</tbody></table></div>`.toString() : `<p class="empty">No ${esc(want || "")} artifact is indexed. Nothing is shown in its place.</p>`;
      },
    };
  };
  const ROLE_TYPE = { input: "data", output: "data", code: "code", environment: "code", protocol: "protocol", log: "document", certificate: "proof", geometry: "geometry" };
  DF.artifactIndex = (snap) => {
    const rows = snap.mission.artifacts.map((a) => ({ ...a }));
    if (snap.simulation) snap.simulation.files.forEach((f) => rows.push({ title: "Glide sweep: " + f.name, type: /png|csv/.test(f.name) ? (f.name.endsWith("csv") ? "data" : "simulation") : "simulation", source: `${f.path} · sha256 ${f.sha256.slice(0, 12)}… · ${f.bytes} bytes`, url: null, download: f.href, context: `${snap.simulation.summary.model_version}; ${snap.simulation.summary.evidence_kind}; assumptions are the model's, not measurements`, check: `step-halving and analytic controls: all pass = ${snap.simulation.controls && snap.simulation.controls.all_pass}`, dispute: "The authors flag release-speed convention and mass dropping out as model artefacts.", next: "Replace constant coefficients with sourced values before reading any trend biologically." }));
    if (snap.lean_receipt) rows.push({ title: "Lean receipt for the constraint certificate", type: "proof", source: `${snap.lean_receipt.path} · sha256 ${snap.lean_receipt.sha256.slice(0, 12)}…`, url: null, context: `Lean ${snap.lean_receipt.lean_version.split(",")[0]}; offline run`, check: `positive exit ${snap.lean_receipt.positive.exit}, standard axioms only = ${snap.lean_receipt.positive.only_standard_axioms}; all mutants rejected = ${Object.values(snap.lean_receipt.negative.each_block_rejected || {}).every(Boolean)}`, dispute: "Covers three encoded constraints only; not biology.", next: "Extend to further constraints only with their own mutants." });
    snap.claims.forEach((c) => c.evidence.filter((e) => /compilation|formal/.test(e.kind)).forEach((e) => rows.push({ title: e.label, type: "proof", source: e.url, url: e.url, context: c.label + ". " + c.context.slice(0, 200) + (c.context.length > 200 ? "…" : ""), check: e.kind + " (upstream receipt; not re-run here)", dispute: DF.CATEGORY[c.category].text + ". " + (c.category === "unchecked" ? "" : c.finding.slice(0, 160)), next: c.next_action })));
    return rows;
  };
  DF.liveArtifacts = (items) => items.map((it) => { const a = it.artifact || {}; return { title: a.title || "(untitled)", type: ROLE_TYPE[a.role] || "document", source: `${a.uri} · sha256 ${String(a.sha256).slice(0, 12)}… · ${a.byte_size} bytes · ${a.availability}${it.is_head === false ? " · superseded version" : ""}`, url: /^https:/.test(a.uri || "") ? a.uri : null,
    context: (it.context || "") + (it.relation ? ` (relation: ${it.relation}; target ${it.target ? it.target.kind + " " + it.target.id : "?"}${it.produced_by ? "; produced by " + it.produced_by.id : ""})` : ""), check: `${it.evidence_kind || "evidence"}; local status ${String(it.local_status || "not reported").replace(/_/g, " ")}; digest declared, bytes ${it.artifact_bytes_verified ? "verified" : "not verified"}`,
    dispute: it.relation === "refutes" ? "This evidence refutes its target." : "", download: a.availability === "downloadable" && /^https:/.test(a.uri || "") ? a.uri : null, next: (it.limitations || []).join("; ") }; });

  /* ---------------- WORK ---------------- */
  DF.views.work = function (snap) {
    const live = DF.api.state.mode === "live";
    return {
      html: html`<section class="pagehead"><h1>Work</h1><p class="lede">Agents, capabilities, leases, resources and contributions. This page shows only what a connected runtime reports, plus what the repository declares. It does not draw activity that is not there.</p></section>
      <section class="panel" aria-labelledby="w-r"><h2 id="w-r">Runtime</h2>
        <p>${U.pill(live ? "live runtime" : "snapshot only", live ? "ok" : "warn")} ${DF.api.state.reason}.</p>
        ${live ? html`<p>Namespace: <code>${DF.api.state.health.namespace || "not reported"}</code>.</p>` : html`<p class="note small">No runtime is connected, so there are no agents, leases, resources or contributions to show. Nothing below is simulated.</p>`}</section>
      <section class="panel" aria-labelledby="w-e"><h2 id="w-e">Events, leases and contributions</h2><div id="events" role="status">Loading…</div></section>
      <section class="panel" aria-labelledby="w-c"><h2 id="w-c">Declared capabilities (MCP tools)</h2>
        <p class="note small">Declared in the repository's MCP server, tested only with the official SDK client. A declared tool is not demonstrated competence; availability and observed success are separate facts, and no success receipts are attached here.</p>
        <div class="tablewrap"><table><thead><tr><th>Tool</th><th>Mode</th><th>Documented in docs/mcp.md</th></tr></thead><tbody>${snap.capabilities.map((t) => html`<tr><td><code>${t.name}</code></td><td>${t.mode}</td><td>${t.documented_in_docs_mcp ? "yes" : "no"}</td></tr>`)}</tbody></table></div>
        <p class="small">Writes need the <code>--allow-write</code> flag and an operator credential kept outside prompts. Contributions stay <i>proposed</i>; the executor cannot certify its own work. ${U.src("doc:mcp", "Read the MCP document")}</p></section>
      <section class="panel" aria-labelledby="w-p"><h2 id="w-p">Planned assignments (as written in the repository)</h2>
        <p class="note small">From <code>tasks/BUILD.md</code> at ${snap.label}. This is a plan with owners and acceptance text, <b>not live status</b>: nothing here says that any item is running, finished or healthy.</p>
        <div class="tablewrap"><table><thead><tr><th>Priority</th><th>Deliverable</th><th>Owner</th><th>Status text at snapshot</th></tr></thead><tbody>${snap.board.map((r) => html`<tr><td>${r.priority}</td><td>${r.deliverable}</td><td>${r.owner}</td><td>${r.status_text}</td></tr>`)}</tbody></table></div></section>
      <section class="panel" aria-labelledby="w-h"><h2 id="w-h">How work is counted</h2>
        <p>Results, reuse and compute counts will appear only when derived from run receipts and recorded edges. Counts of test definitions, generated records or submitted jobs are not successful executions, and this page shows none of them.</p></section>`,
      async after(root) {
        const host = root.querySelector("#events");
        try { const r = await DF.api.events(); host.innerHTML = r.events.length ? html`<p class="small faint">Events are records emitted by the store, in sequence order; they say what was recorded, not that it is correct.</p><div class="tablewrap"><table><thead><tr><th>#</th><th>Kind</th><th>Id</th><th>Issuer</th><th>Created</th></tr></thead><tbody>${r.events.map((e) => html`<tr><td>${e.sequence}</td><td>${e.kind}</td><td><code>${e.id}</code></td><td>${e.issuer || ""}</td><td>${e.created_at || ""}</td></tr>`)}</tbody></table></div>${r.next_cursor ? html`<p class="small faint">More events exist than shown.</p>` : ""}`.toString() : `<p class="empty">${esc(r.note || "The runtime reports no events.")} No agents, leases or contributions are displayed.</p>`; }
        catch (e) { host.innerHTML = `<p class="empty">Could not read events: ${esc(e.message)}. Nothing is displayed in their place.</p>`; }
      },
    };
  };

  /* ---------------- BELIEF ---------------- */
  DF.views.belief = function (snap) {
    return {
      html: html`<section class="pagehead"><h1>Belief and decision</h1><p class="lede">Explicit structure for forecasts and priorities. <b>This is kept apart from truth status.</b> A probability here is somebody's estimate of an event; it does not make a claim true, and no one has entered any.</p></section>
      <section class="panel" aria-labelledby="b-sep"><h2 id="b-sep">Four things that must not be merged</h2>
        <div class="four">
          <article><h3>Truth status</h3><p>What evidence and independent review establish about a claim, with scope. Shown on Knowledge and Evidence.</p></article>
          <article><h3>Forecast</h3><p>A resolvable event with a horizon, a probability or interval, a method, and a resolution source. Unresolved events are never scored as false.</p><p class="faint small">No forecasts are recorded in this snapshot.</p></article>
          <article><h3>Priority</h3><p>A named policy with reasons and prerequisites for what to do next. Unknown utilities stay unknown.</p><p class="faint small">No priority policy is recorded; the question order on Frontier is source order.</p></article>
          <article><h3>Decision</h3><p>The bounded action chosen, who took it, and what it consumed.</p><p class="faint small">None recorded.</p></article>
        </div></section>
      <section class="panel" aria-labelledby="b-fg"><h2 id="b-fg">Factor graph: what the flying-fish check depends on (structure only)</h2>
        <p class="note small">Variables are yes/no conditions from the Engineering checks. Squares are factors. The factor shown is the page's own rule (no flag raised when no evaluable check fails), not a probabilistic model. No probabilities are attached.</p>
        <div id="fg" class="fgwrap graphhost"></div>
        <p class="small faint">The same structure as text: V1 (C1, wing loading), V2 (C2, launch speed), V3 (C4, stability), V4 (C6a, reachability) all feed factor F1, which defines V5, “no flag raised by these checks”. V5 says nothing about reachability.</p></section>
      <section class="panel" aria-labelledby="b-sc"><h2 id="b-sc">Scratch arithmetic (yours, local, not a forecast)</h2>
        <p class="note small">Enter your own probabilities that each condition holds. The product assumes the four are independent, which they are not (mass enters C1 and C2 together). It is a way to see the shape of a bet, nothing more. It is not saved, not submitted, and is not scored.</p>
        <form id="scratch" class="scratch" novalidate>${[["v1", "V1 wing loading within envelope"], ["v2", "V2 launch speed reachable"], ["v3", "V3 no stability flag"], ["v4", "V4 no novel-appendage flag"]].map(([k, l]) => html`<div class="field"><label for="p-${k}">${l} <span class="unit">probability 0–1</span></label><input id="p-${k}" name="${k}" type="number" step="0.01" min="0" max="1" placeholder="not entered"></div>`)}</form>
        <p id="scratchout" class="verdictbox" role="status">Enter all four to see the product under independence.</p></section>
      <section class="panel" aria-labelledby="b-a"><h2 id="b-a">Belief and forecast interface</h2>
        <p>The belief/forecast service is not connected, so no stored belief appears here.</p>
        <button class="btn small" type="button" id="beliefreq">Request beliefs for this mission</button><div class="adapter-out" id="beliefout" role="status"></div></section>`,
      after(root) {
        const nodes = [{ id: "V1", label: "V1 C1: wing loading ≤ 208.9", col: 0, row: 0, cls: "cur" }, { id: "V2", label: "V2 C2: launch speed reachable", col: 0, row: 1, cls: "cur" }, { id: "V3", label: "V3 C4: stability flag", col: 0, row: 2, cls: "cur" }, { id: "V4", label: "V4 C6a: novel-appendage flag", col: 0, row: 3, cls: "cur" },
          { id: "F1", label: "F1 rule: no flag raised", col: 1, row: 1, cls: "gen", sub: "factor" }, { id: "V5", label: "V5 no flag raised by these checks", col: 2, row: 1, cls: "cur" }];
        const edges = [["V1", "F1"], ["V2", "F1"], ["V3", "F1"], ["V4", "F1"], ["F1", "V5"]].map(([a, b], i) => ({ id: "e" + i, from: a, to: b, kind: b === "V5" ? "defines" : "input", label: a + " → " + b }));
        let sel = null;
        const draw = () => DF.graph.draw(root.querySelector("#fg"), { columns: [{ title: "Variables" }, { title: "Factor" }, { title: "Variable" }], nodes, edges, selected: sel, ariaLabel: "Factor graph of the flying-fish check", legend: [{ cls: "cur", text: "variable" }, { cls: "gen", text: "factor" }], onSelect(t, id) { sel = { type: t, id }; draw(); } });
        draw();
        const form = root.querySelector("#scratch"); const out = root.querySelector("#scratchout");
        form.addEventListener("input", () => {
          const vals = ["v1", "v2", "v3", "v4"].map((k) => form.elements[k].value.trim());
          if (vals.some((v) => v === "")) { out.textContent = "Enter all four to see the product under independence."; return; }
          const nums = vals.map(Number);
          if (nums.some((n) => !isFinite(n) || n < 0 || n > 1)) { out.textContent = "Each probability must be between 0 and 1."; return; }
          out.textContent = `Product under independence: ${(nums.reduce((a, b) => a * b, 1)).toFixed(3)}. Your own arithmetic; not a forecast, not saved, not truth status.`;
        });
        root.querySelector("#beliefreq").addEventListener("click", async () => {
          const o = root.querySelector("#beliefout"); try { await DF.api.belief(); } catch (e) { o.className = "adapter-out unavailable"; o.textContent = e.name === "Unavailable" ? `Not connected: ${e.adapter}. ${e.detail}` : "Request failed: " + e.message; }
        });
      },
    };
  };

  /* ---------------- CATALOG / SEARCH ---------------- */
  DF.catalogView = function (snap, route, head, base) {
    const f = { q: route.params.q || "", kind: route.params.kind || "", status: route.params.status || "" };
    const kinds = ["Claim", "Problem", "Evidence"];
    return {
      html: html`${head}<section><p class="note small">Records are shown as full envelopes with a <b>separate local status</b>. Upstream labels never become local acceptance. The catalog is read through the adapter: <b>${DF.api.state.mode}</b> mode (${DF.api.state.reason}).</p>
        <form class="filters" role="search" data-form="catalog" aria-label="Search the catalog"><input type="hidden" name="tab" value="catalog">
          <label>Query <input type="search" name="q" value="${f.q}" placeholder="words in a record"></label>
          <label>Kind <select name="kind"><option value="">all</option>${kinds.map((k) => html`<option ${k === f.kind ? raw("selected") : ""}>${k}</option>`)}</select></label>
          <label>Local status <select name="status"><option value="">any</option>${(DF.api.state.mode === "live" && DF.api.state.authenticated ? ["proposed", "imported_unreviewed", "accepted", "disputed", "rejected"] : ["snapshot_unreviewed"]).map((s) => html`<option value="${s}" ${s === f.status ? raw("selected") : ""}>${s.replace(/_/g, " ")}</option>`)}</select></label>
          <button class="btn" type="submit">Search</button>${f.q || f.kind || f.status ? html`<a class="btn ghost" href="${DF.href(base, { tab: "catalog" })}">Clear</a>` : ""}</form>
        <p class="count" id="ccount" role="status">Loading…</p><ul class="catalog" id="clist"></ul><div id="cmore"></div></section>`,
      async after(root) {
        DF.bindForm(root, "catalog", (v) => DF.href(base, v));
        const list = root.querySelector("#clist"), count = root.querySelector("#ccount"), more = root.querySelector("#cmore"); let shown = 0;
        const load = async (after) => {
          try {
            const r = await DF.api.catalog({ query: f.q, kind: f.kind, status: f.status, limit: 20, after });
            list.insertAdjacentHTML("beforeend", r.records.map((rec) => recordRow(rec)).join("")); shown += r.records.length;
            count.textContent = `${shown} record${shown === 1 ? "" : "s"} shown${r.total_matching !== undefined ? ` of ${r.total_matching} matching` : ""} · mode ${r.mode}${r.namespace ? " · namespace " + r.namespace : ""}${r.search_mode ? " · search " + String(r.search_mode).replace(/_/g, " ") : ""}`;
            if (!shown) count.textContent = `No record matches (${DF.api.state.mode === "live" ? "the live node returned none" : "the snapshot has none"}). Try fewer words or clear the filters. · mode ${r.mode}${r.namespace ? " · namespace " + r.namespace : ""}`;
            more.innerHTML = r.next_cursor ? `<button class="btn" type="button">Load more</button>` : "";
            const b = more.querySelector("button"); if (b) b.addEventListener("click", () => { b.disabled = true; load(r.next_cursor); });
          } catch (e) { count.textContent = "The catalog could not be read: " + e.message + ". Nothing is shown in its place."; }
        };
        load("");
      },
    };
  };
  DF.recRefs = DF.recRefs || {};
  function recordRow(rec) {
    const r = rec.ref || {}; const p = rec.payload || {}; const title = rec.title || p.title || r.id || "(untitled record)";
    const key = `rec:${r.kind}:${r.id}`; DF.recRefs[key] = r;
    const upstream = rec.upstream_label ? Object.entries(rec.upstream_label).map(([k, v]) => `${k}: ${v}`).join("; ") : "";
    const why = Array.isArray(rec.why_matched) ? rec.why_matched : null; const cur = rec.curation || null; const dis = rec.disputes || null;
    const disN = dis ? (dis.disputing_reviews || []).length + (dis.cited_evidence || []).length + (dis.diverging_versions || []).length : 0;
    return html`<li class="catrow"><div><span class="pill k-${r.kind}">${r.kind || "record"}</span> <a class="srclink" href="${DF.hrefWith({ src: key })}" data-src="${key}"><b>${title}</b></a>${rec.is_head === false ? html` ${U.pill("not the current version", "warn")}` : ""}</div>
      <div class="small"><span class="pill st-unk">local status: ${String(rec.local_status || "not reported").replace(/_/g, " ")}</span> ${upstream ? html`<span class="faint">upstream assertion → ${upstream}</span>` : ""}</div>
      ${rec.snippet ? html`<div class="small">${rec.snippet}</div>` : ""}
      ${why ? html`<div class="small faint">Matched on: ${why.length ? why.join("; ") : "no reason reported"}. This is lexical matching, not relevance, quality or truth.</div>` : ""}
      ${cur ? html`<div class="small faint">Source fidelity: <b>${String(cur.source_fidelity || "not reported").replace(/_/g, " ")}</b>${cur.source_fidelity === "locator_present" ? " (a locator exists; that does not mean the source supports the text)" : ""}${(cur.labels || []).length ? " · labels: " + cur.labels.join(", ") : ""}</div>` : ""}
      ${dis && disN ? html`<div class="small"><span class="pill warn">disputed or diverging: ${disN}</span>${dis.truncated ? " more exist than shown" : ""}</div>` : ""}
      ${rec.references_complete === false ? html`<div class="small faint">More references exist than are shown. An empty list means none visible found, not none.</div>` : ""}
      <div class="small faint"><code>${r.namespace}/${r.kind}/${r.id}</code> · version ${U.sha(r.version)}</div></li>`.toString();
  }

  DF.views.search = function (snap, route) {
    const head = html`<section class="pagehead"><h1>Search</h1><p class="lede">Search every record the node can read. Results come from the live catalog when a runtime is connected, otherwise from the committed snapshot, and the mode is stated above the list.</p></section>`;
    return DF.catalogView(snap, route, head, "/search");
  };
})();
