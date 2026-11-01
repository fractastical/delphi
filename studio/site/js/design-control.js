/* Design-control map (frontier.design-control/1): per scale, the parameters a human can set, whether each bound is measured, sourced,
 * assumed or unknown, what sensitivity and identifiability evidence exists, the causal bridges that are missing, and work packages with
 * their real input dependencies. Every number comes from the artifact; nothing here is computed, scored or given a probability. */
(function () {
  const DF = window.DF; const { html, esc } = DF;
  const v = (x) => { const r = x && typeof x === "object" && !Array.isArray(x) && "value" in x ? x.value : x;
    return r === null || r === undefined ? "unknown" : typeof r === "object" ? JSON.stringify(r) : String(r); };
  const chip = (st) => html`<span class="chip dc-${esc(st)}" data-bound="${esc(st)}">${st}</span>`;
  const pre = (id) => `dc-${id}`;

  const sens = (s) => { if (!s) return "";
    const el = s.elasticity ? html` elasticity <b>${Number(s.elasticity.value).toPrecision(3)}</b> (dimensional expectation ${v(s.expected_from_dimensions)})` : "";
    const tab = s.table ? html`<table class="small"><caption>Responses at the fixed 0.6 s endpoint (of 16 fish over 2 seeds)</caption><thead><tr><th>setting</th><th>mode</th><th>responses</th></tr></thead><tbody>
      ${s.table.map((r) => html`<tr><td>${r.setting}</td><td>${r.mode}</td><td>${r.responses_at_0_6s}/${r.fish}</td></tr>`)}</tbody></table>` : "";
    return html`<div class="small">${s.kind}${el}${s.result ? html`<br>${s.result}` : ""}${tab}</div>`; };

  const param = (p) => { const b = p.bound; const extra = Object.entries(b).filter(([k]) => !["status", "basis"].includes(k));
    const ir = p.identifiability_ref ? Object.entries(p.identifiability_ref).map(([k, x]) => `${k.replace(/_/g, " ")} ${v(x)}`).join("; ") : "";
    return html`<tr><th scope="row">${p.label}<div class="faint small">${p.controllable ? "human-settable" : "uncontrolled context"}${p.unit ? " · " + p.unit : ""}</div></th>
      <td>${v(p.value)}${p.alternative ? html` <span class="faint">vs ${v(p.alternative)}</span>` : ""}</td>
      <td>${chip(b.status)}<div class="small">${b.basis}</div>${extra.length ? html`<div class="small faint">${extra.map(([k, x]) => `${k.replace(/_/g, " ")}: ${v(x)}`).join(" · ")}</div>` : ""}</td>
      <td>${sens(p.sensitivity)}</td><td class="small">${p.identifiability}${ir ? html`<div class="faint">${ir}</div>` : ""}</td></tr>`; };

  const layer = (l) => html`<details class="dc-layer" id="${pre(l.id)}" open><summary><b>${l.label}</b> <span class="faint">${l.scale}${l.region_ids.length ? " · regions: " + l.region_ids.join(", ") : ""}</span></summary>
    <p class="small">${l.what_exists}</p>
    ${l.parameters.length ? html`<table class="small dc-params"><thead><tr><th>Parameter</th><th>Value</th><th>Bound</th><th>Sensitivity</th><th>Identifiability</th></tr></thead><tbody>${l.parameters.map(param)}</tbody></table>`
      : html`<p class="note warn">${l.controls_note}</p>`}
    ${l.results.length ? html`<ul class="small">${l.results.map((r) => html`<li>${r.text}${r.fraction ? html`: <b>${r.numerator.value}/${r.denominator.value}</b> = ${Number(r.fraction.value).toFixed(4)} <span class="faint">(${r.interval_kind}: ${v(r.interval)}). ${r.meaning}</span>` : r.count !== undefined && r.ref ? html`: ${r.count}` : r.count !== undefined ? html`: ${r.count}` : r.status ? html`: ${v(r.status)}, ${v(r.computed)}/${v(r.scenarios)} computed. <span class="faint">${v(r.scope)}</span>` : r.ref ? html`: ${v(r.ref)}` : ""}</li>`)}</ul>` : ""}
    <h4 class="eh">Missing causal bridges</h4><ul class="small">${l.bridges.map((b) => html`<li><b>${b.from}</b> → <b>${b.to}</b>: ${chip(b.status)}${b.need ? html` ${v(b.need)}` : ""}</li>`)}</ul></details>`;

  const wp = (w, byId) => html`<li id="${pre(w.id)}"><b>${w.title}</b> <span class="faint">${w.kind} · ${w.status.replace(/-/g, " ")}</span><br><span class="small">${v(w.why)}${w.inputs.length ? html` <b>Depends on:</b> ${w.inputs.map((i) => byId[i].title).join("; ")}.` : " Independent: no declared input from another package."}</span></li>`;

  DF.designControlPanel = function (M) {
    if (!M) return html`<section class="panel" aria-labelledby="dc-h"><h2 id="dc-h">Design control map</h2><p class="empty">No design-control map is present in this tree (looked for <code>artifacts/design-control/map.json</code>).</p></section>`;
    if (M.error || M.schema !== "frontier.design-control/1") return html`<section class="panel" aria-labelledby="dc-h"><h2 id="dc-h">Design control map</h2><p class="empty">${M.error || "Unexpected schema " + M.schema}. Nothing is shown rather than a guess.</p></section>`;
    const byId = Object.fromEntries(M.workpackages.map((w) => [w.id, w])); const n = M.next_experiment;
    return html`<section class="panel dc" aria-labelledby="dc-h"><h2 id="dc-h">${M.concept.line}</h2><p>${M.concept.text}</p>
      <p class="note warn">${M.separation} Biological success probability: <b>${v(M.biological_success_probability)}</b>. No confidence figure or score exists in this map.</p>
      ${M.layers.map(layer)}
      <h3 class="eh">Work packages and their real dependencies</h3><p class="small">${M.execution_note}</p><ul>${M.workpackages.map((w) => wp(w, byId))}</ul>
      <h3 class="eh">Best next bounded experiment</h3><p><b>${byId[n.id].title}</b></p><ul class="small">${n.why_this_one.map((t) => html`<li>${t}</li>`)}</ul><p class="small faint">${n.not_claimed}</p>
      <h3 class="eh">Not claimed</h3><ul class="small">${M.non_claims.map((t) => html`<li>${t}</li>`)}</ul>
      <details><summary>Sources: ${M.sources.length} pinned blobs</summary><table class="small"><tbody>${M.sources.map((s) => html`<tr><td>${s.id}</td><td><code>${s.path}</code> @ ${s.commit.slice(0, 10)}</td><td class="mono">${s.sha256.slice(0, 16)}…</td></tr>`)}</tbody></table></details></section>`;
  };
})();
