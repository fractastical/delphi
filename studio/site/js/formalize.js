/* Proposal checker: a proposed formalization of a passage is shown in separate parts (source passage, proposed constraints, units and assumptions,
 * solver result, unresolved translation, Lean text) and checked by the node's POST /api/formalize/propose. The check covers the constraints as written,
 * not whether they match the source; Lean is generated text and is never run here. */
(function () {
  const DF = window.DF; const { html, raw, esc } = DF; const U = DF.ui;
  const OPS = { "==": "=", "<=": "≤", ">=": "≥", "<": "<", ">": ">", "*": "·", "/": "/", "+": "+", "-": "−" };
  const exprText = (e) => {
    if (typeof e === "string") return e;
    if (!e || typeof e !== "object") return String(e);
    if (e.op === "pow") return `${exprText(e.base)}^${exprText(e.exp)}`;
    if (e.lhs !== undefined && e.rhs !== undefined) return `${exprText(e.lhs)} ${OPS[e.op] || e.op} ${exprText(e.rhs)}`;
    if (Array.isArray(e.args)) return e.args.map((a) => (a && typeof a === "object" && a.args ? "(" + exprText(a) + ")" : exprText(a))).join(` ${OPS[e.op] || e.op} `);
    return JSON.stringify(e);
  };
  const dom = (d) => (d ? `${d.lo_open ? "(" : "["}${d.lo ?? "−∞"}, ${d.hi ?? "∞"}${d.hi_open ? ")" : "]"}` : "not given");
  const tone = { checked: "ok", unsat: "warn", invalid: "no", unknown: "st-unk", unsupported_expression: "no" };

  const section = (title, body, id) => html`<section class="panel fzsec" aria-labelledby="${id}"><h2 id="${id}">${title}</h2>${body}</section>`;

  function proposalParts(ex) {
    const r = ex.request, P = r.proposal;
    return html`${section("1. Source passage", html`<p class="small">${r.claim.text}</p>${ex.passage ? html`<details><summary class="small">Passage text given to the proposer (sha256 ${ex.passage_sha256 ? ex.passage_sha256.slice(0, 12) + "…" : "none"})</summary><pre class="json">${ex.passage}</pre></details>` : html`<p class="small faint">No external passage: a design target stated by the proposer.</p>`}<p class="small faint">Source reference: ${r.claim.source.ref} (${r.claim.source.locator})</p>`, "fz-src")}
      ${section("2. Proposed constraints", html`<ul class="fzcons">${P.constraints.map((c) => html`<li><b>${c.id}</b> ${U.pill(c.kind, "grp")} <code>${exprText(c.expr)}</code>${c.source_ref ? html` <span class="small faint">from ${c.source_ref}</span>` : ""}</li>`)}</ul>
        <h3>Source mapping, as the proposer states it</h3><ul class="small">${(P.source_mapping || []).map((m) => html`<li><b>${m.element}</b>: “${m.quote}” <span class="faint">(${m.locator})</span></li>`)}</ul>`, "fz-prop")}
      ${section("3. Symbols, units and assumptions", html`<div class="tablewrap"><table><caption class="sr">Declared symbols</caption><thead><tr><th scope="col">Symbol</th><th scope="col">Unit</th><th scope="col">Domain</th><th scope="col">Status</th><th scope="col">Where the value comes from</th></tr></thead><tbody>${P.symbols.map((s) => html`<tr><th scope="row"><code>${s.name}</code></th><td>${s.unit}</td><td class="small">${dom(s.domain)}</td><td>${U.pill(s.status, s.status === "given" ? "ok" : s.status === "unknown" ? "st-unk" : "warn")}</td><td class="small">${s.source_ref}</td></tr>`)}</tbody></table></div>
        <h3>Assumptions</h3><ul class="small">${P.assumptions.map((a) => html`<li><b>${a.id}</b> ${U.pill(a.kind, "grp")} ${a.text}</li>`)}</ul>`, "fz-sym")}`;
  }

  function resultParts(res) {
    const chk = (res.checks || [])[0] || {};
    return html`${section("4. Solver result", html`<p>${U.pill(res.status, tone[res.status] || "st-unk")} ${res.evidence_kind ? U.pill("evidence kind: " + res.evidence_kind, "ev") : ""} ${U.pill("calibrated: " + String(res.calibrated), "st-unk")}</p>
        ${(res.checks || []).map((c) => html`<dl class="kv wide"><div><dt>Constraint set</dt><dd>${c.constraint || "ALL"}</dd></div><div><dt>Result</dt><dd>${c.result}</dd></div><div><dt>Method</dt><dd>${c.method || "not stated"}</dd></div><div><dt>Independent check</dt><dd>${c.independent_check || "not stated"}</dd></div>${c.witness ? html`<div><dt>Witness (exact values)</dt><dd><code>${Object.entries(c.witness).map(([k, v]) => k + " = " + v).join(", ")}</code></dd></div>` : ""}</dl>`)}
        ${(res.dimension_report || []).length ? html`<h3>Units check</h3><ul class="small">${res.dimension_report.map((d) => html`<li><b>${d.constraint}</b>: ${d.dims || ""} ${U.pill(d.ok ? "dimensions consistent" : "dimension fault", d.ok ? "ok" : "no")}</li>`)}</ul>` : ""}
        ${(res.refusals || []).length ? html`<h3>Refusals</h3><ul class="small">${res.refusals.map((x) => html`<li>${typeof x === "string" ? x : x.code + (x.detail ? ": " + x.detail : "")}</li>`)}</ul>` : ""}
        ${res.controls_summary ? html`<p class="small"><b>Negative controls run by the checker:</b> ${res.controls_summary.as_expected} of ${res.controls_summary.n} behaved as pre-declared (${res.controls_summary.probes} probes have no expectation).</p>` : ""}
        <p class="note small"><b>Scope.</b> ${res.assumed_scope || ""}</p><p class="small faint">Request ${U.sha(res.request_sha256)} · proposal ${U.sha(res.proposal_sha256)}</p>`, "fz-res")}
      ${section("5. Unresolved translation", html`<p class="note warn small">What the checker cannot decide: whether the constraints say what the source says.</p><ul>${(res.unresolved_translation || []).map((u) => html`<li><b>${u.id}</b> ${u.question}</li>`)}</ul>${(res.not_established || []).length ? html`<p class="small"><b>Not established:</b> ${res.not_established.join("; ")}.</p>` : ""}`, "fz-unres")}
      ${section("6. Lean statement (generated text, not compiled)", html`<p>${U.pill("lean: " + (res.lean || "not_run"), "warn")} ${res.lean_statement ? U.pill(res.lean_statement.status, "st-unk") : ""}</p>${res.lean_statement ? html`<p class="small">${res.lean_statement.meaning}</p><details><summary class="small">Show the text (sha256 ${res.lean_statement.sha256.slice(0, 12)}…)</summary><pre class="json">${res.lean_statement.text}</pre></details>` : html`<p class="small faint">No Lean text was returned.</p>`}<p class="small faint">Nothing is compiled or run by this page or by this request.</p>`, "fz-lean")}`;
  }

  DF.views.formalize = function (snap, route) {
    const F = snap.formalize;
    if (!F) return { html: html`<section class="pagehead"><h1>Proposal checker</h1><p class="empty">No fixtures are present in this snapshot.</p></section>` };
    const cur = F.examples.find((e) => e.id === route.params.ex) || F.examples[0];
    return {
      html: html`<section class="pagehead"><h1>Proposal checker</h1><p class="lede">A proposed formalization of a passage, shown in separate parts and checked by the node. The check covers the constraints as written: units, exact-value consistency, and negative controls. It does not say the constraints match the source, and no Lean is run.</p></section>
        <section class="panel"><form class="filters" data-form="fz" aria-label="Choose a proposal"><label>Proposal <select name="ex">${F.examples.map((e) => html`<option value="${e.id}" ${e.id === cur.id ? raw("selected") : ""}>${e.title}</option>`)}</select></label><button class="btn" type="submit">Show</button></form>
          <p class="small">${U.pill(cur.kind, cur.kind.startsWith("recorded") ? "warn" : "grp")} ${cur.note}</p>
          ${cur.receipt ? html`<dl class="kv wide"><div><dt>Model</dt><dd>${cur.receipt.provider} ${cur.receipt.model}</dd></div><div><dt>Finish reason</dt><dd>${cur.receipt.finish_reason}</dd></div><div><dt>Recorded checker outcome</dt><dd>${cur.receipt.outcome_status || cur.receipt.parent_checker_status || "not recorded"}</dd></div><div><dt>Tokens (reported)</dt><dd>${Object.entries(cur.receipt.tokens).filter(([, v]) => v !== null && v !== undefined).map(([k, v]) => k.replace("Count", "") + " " + v).join(", ") || "not reported"}</dd></div><div><dt>Receipt</dt><dd><code class="small">${cur.receipt.path}</code></dd></div></dl>` : ""}</section>
        ${cur.request ? proposalParts(cur) : ""}
        ${cur.request ? html`<section class="panel"><h2>Check this proposal</h2><p class="small">${DF.api.isLive() ? "Sends the request to this node's checker. It stores nothing, calls no model and runs no Lean." : "No node is connected, so nothing can be checked and no result is shown."}</p>
          <button type="button" class="btn" id="fzgo" ${DF.api.isLive() ? "" : raw("disabled")}>Check this proposal</button> <span id="fzerr" class="small" role="alert"></span></section>
          <div id="fzout" aria-live="polite"></div>` : ""}`,
      async after(root) {
        DF.bindForm(root, "fz", (v) => DF.href("/formalize", v));
        const go = root.querySelector("#fzgo"); if (!go) return;
        go.addEventListener("click", async () => {
          const out = root.querySelector("#fzout"), err = root.querySelector("#fzerr"); err.textContent = ""; go.disabled = true; out.textContent = "";
          const body = JSON.stringify(cur.request);
          if (body.length > F.limits.max_bytes) { err.textContent = "The request is larger than the node's " + F.limits.max_bytes + "-byte limit; nothing was sent."; go.disabled = false; return; }
          try { const res = await DF.api.formalize(cur.request); out.innerHTML = resultParts(res).toString(); DF.renderMath(out); }
          catch (e) { err.textContent = e.message + " No result is shown."; }
          finally { go.disabled = false; }
        });
      },
    };
  };
})();
