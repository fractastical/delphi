/* Bounded simulation previews (POST /api/simulations/run, contract frontier.simulation.preview/1). The page sends exactly {model, parameters}, refuses
 * out-of-range values instead of clamping them, and plots only numbers the node returned. A preview is not stored, not calibrated, and not a fish. */
(function () {
  const DF = window.DF; const { html, esc, fmt, raw } = DF; const U = DF.ui;
  const BIO = [["sodium_scale", "Sodium conductance scale", "0.35", null, "model's own validation"], ["gap_mS_cm2", "Gap-junction conductance (mS/cm²)", "0.5", null, "model's own validation"], ["duration_ms", "Duration (ms)", "30", [10, 30], "10 to 30"], ["dt_ms", "Time step (ms)", "0.025", [0.0125, 0.025], "0.0125 to 0.025"]];
  const MECH = [["viscosity_pN_s_nm", "Viscosity (pN·s/nm)", "1.0", null, "model's own validation"], ["duration_s", "Duration (s)", "5", [1, 10], "1 to 10"], ["dt_s", "Time step (s)", "0.01", [0.005, 0.02], "0.005 to 0.02"], ["frame_count", "Frames", "101", [2, 101], "2 to 101 (whole number)"]];

  function lineChart(xs, series, o) {
    const W = 640, H = 260, m = { l: 56, r: 12, t: 24, b: 40 }; const allY = series.flatMap((s) => s.ys).filter((v) => Number.isFinite(v));
    if (!xs.length || !allY.length) return "<p class='empty'>No numeric series to plot.</p>";
    const x0 = Math.min(...xs), x1 = Math.max(...xs); let y0 = Math.min(...allY), y1 = Math.max(...allY); if (y0 === y1) { y0 -= 1; y1 += 1; }
    const X = (v) => m.l + ((v - x0) / (x1 - x0 || 1)) * (W - m.l - m.r), Y = (v) => H - m.b - ((v - y0) / (y1 - y0)) * (H - m.t - m.b); const cols = ["#0e7c86", "#d97b29", "#7a5ea8", "#c0392b", "#3a7bd5", "#5b7a0f"];
    let g = `<svg viewBox="0 0 ${W} ${H}" class="chart" role="img" aria-label="${esc(o.title)}"><text x="${m.l}" y="14" class="axis">${esc(o.title)}</text>`;
    for (let i = 0; i <= 4; i++) { const yv = y0 + ((y1 - y0) * i) / 4, xv = x0 + ((x1 - x0) * i) / 4; g += `<line x1="${m.l}" x2="${W - m.r}" y1="${Y(yv)}" y2="${Y(yv)}" class="grid"/><text x="${m.l - 6}" y="${Y(yv) + 4}" class="tick" text-anchor="end">${fmt(yv, 3)}</text><text x="${X(xv)}" y="${H - m.b + 16}" class="tick" text-anchor="middle">${fmt(xv, 3)}</text>`; }
    g += `<text x="${(W + m.l) / 2}" y="${H - 6}" class="axis" text-anchor="middle">${esc(o.xlabel)}</text><text transform="translate(12 ${H / 2}) rotate(-90)" class="axis" text-anchor="middle">${esc(o.ylabel)}</text>`;
    const step = Math.max(1, Math.ceil(xs.length / 400));
    series.forEach((s, k) => { let d = ""; xs.forEach((x, i) => { if (i % step && i !== xs.length - 1) return; d += (d ? "L" : "M") + X(x).toFixed(1) + "," + Y(s.ys[i]).toFixed(1); }); g += `<path d="${d}" class="curve" stroke="${cols[k % 6]}"><title>${esc(s.name)}</title></path>`; });
    return g + "</svg>" + `<ul class="legend inline">${series.map((s, k) => `<li><i class="sw" style="background:${cols[k % 6]}"></i>${esc(s.name)}</li>`).join("")}</ul>`;
  }

  /* A digest field may be one hash or a map of file to hash. */
  const shaField = (v) => (v && typeof v === "object" ? html`${Object.entries(v).map(([k, h]) => html`<span class="small">${k}: ${h && typeof h === "object" ? shaField(h) : U.sha(h)}</span> `)}` : U.sha(v));

  function render(model, r) {
    const res = r.result || {};
    const meta = html`<p class="small faint">${r.schema} · ${r.status} · evidence kind ${r.evidence_kind} · persisted: <b>${String(r.persisted)}</b> · calibrated: <b>${String(r.calibrated)}</b> · computed ${r.computed_at}<br>request sha256 ${U.sha(r.request_sha256)} · effective request ${U.sha(r.effective_request_sha256)} · code ${shaField(r.code_sha256)}</p>${r.scope ? html`<p class="note small"><b>Scope.</b> ${r.scope}</p>` : ""}${r.preview_limits ? html`<details><summary class="small">Preview limits</summary><pre class="json">${JSON.stringify(r.preview_limits, null, 1)}</pre></details>` : ""}`;
    if (r.status !== "completed") return html`<div class="rescard"><div class="resrow"><span class="vlabel">${r.status}</span></div><p>${r.reason ? String(r.reason).replace(/_/g, " ") : "The node did not complete the run."} No result or frames were returned, and none are shown.</p>${meta}</div>`.toString();
    let chart = "", note = "";
    if (model === "bioelectric" && Array.isArray(res.time_ms) && Array.isArray(res.voltage_mV)) {
      const nc = (res.voltage_mV[0] || []).length; const series = Array.from({ length: nc }, (_, c) => ({ name: `cell ${c + 1}`, ys: res.voltage_mV.map((row) => row[c]) }));
      chart = lineChart(res.time_ms, series, { title: "Membrane voltage per cell", xlabel: "time (ms)", ylabel: "voltage (mV)" }); note = `${res.time_ms.length} time points, ${nc} cells, as returned.`;
    } else if (model === "mechanobio" && Array.isArray(res.frames)) {
      const ts = res.frames.map((f) => f.t_s);
      chart = lineChart(ts, [{ name: "traction (pN)", ys: res.frames.map((f) => f.traction_pN) }], { title: "Traction", xlabel: "time (s)", ylabel: "traction (pN)" }) + lineChart(ts, [{ name: "substrate (nm)", ys: res.frames.map((f) => f.substrate_nm) }, { name: "actin (nm)", ys: res.frames.map((f) => f.actin_nm) }], { title: "Substrate and actin displacement", xlabel: "time (s)", ylabel: "nm" });
      note = `${res.frames.length} frames, as returned; clutch states are in the raw result.`;
    } else chart = "<p class='empty'>The result has no series this page knows how to plot; the raw result is below.</p>";
    return html`<div class="rescard"><div class="resrow"><span class="vlabel">completed</span> ${U.pill("simulated", "ev")} ${U.pill("not stored", "st-unk")} ${U.pill("not calibrated", "warn")}</div><p class="small">${note} Plotted exactly from the returned numbers; nothing is smoothed, extrapolated or animated by this page.</p>${DF.raw(chart)}${meta}<details><summary class="small">Raw result</summary><pre class="json">${JSON.stringify(res, null, 1).slice(0, 60000)}</pre></details></div>`.toString();
  }

  DF.mountSimWidget = function (host) {
    const live = DF.api.isLive();
    const fld = (defs) => defs.map(([n, l, v, rng, hint]) => html`<div class="field"><label for="sw-${n}">${l}</label><input id="sw-${n}" name="${n}" type="number" step="any" value="${v}" aria-describedby="swh-${n}"><small id="swh-${n}">${hint}</small></div>`);
    host.innerHTML = html`<form class="simform" aria-label="Preview parameters" novalidate><label for="sw-model" class="small"><b>Model</b></label> <select id="sw-model"><option value="bioelectric">Bioelectric (cell voltage)</option><option value="mechanobio">Mechanobiology (adhesion clutch)</option></select>
      <div id="sw-fields" class="simfields"></div><p><button class="btn" type="submit" ${live ? "" : raw("disabled")}>Run a preview</button> <span class="small faint">${live ? "Sends one bounded request; nothing is stored." : "Needs a live node: none answered, so this cannot run. Nothing is simulated here."}</span></p><p class="small" id="sw-err" role="alert"></p></form><div id="sw-out" role="status"></div>`.toString();
    const sel = host.querySelector("#sw-model"); const fields = host.querySelector("#sw-fields");
    const draw = () => { fields.innerHTML = fld(sel.value === "bioelectric" ? BIO : MECH).map(String).join(""); }; sel.addEventListener("change", draw); draw();
    host.querySelector("form").addEventListener("submit", async (e) => {
      e.preventDefault(); const err = host.querySelector("#sw-err"), out = host.querySelector("#sw-out"); err.textContent = ""; const model = sel.value; const defs = model === "bioelectric" ? BIO : MECH; const v = {};
      for (const [n, l, , rng] of defs) { const raw0 = host.querySelector("#sw-" + n).value.trim(); if (raw0 === "") continue; const x = Number(raw0);
        if (!Number.isFinite(x)) { err.textContent = `${l}: not a finite number.`; return; } if (rng && (x < rng[0] || x > rng[1])) { err.textContent = `${l}: ${x} is outside ${rng[0]} to ${rng[1]}. It is not clamped; change it.`; return; } if (n === "frame_count" && !Number.isInteger(x)) { err.textContent = "Frames must be a whole number."; return; } v[n] = x; }
      const body = model === "bioelectric" ? { model, parameters: v } : { model, parameters: { parameters: { viscosity_pN_s_nm: v.viscosity_pN_s_nm }, duration_s: v.duration_s, dt_s: v.dt_s, frame_count: v.frame_count } };
      if (model === "mechanobio") Object.keys(body.parameters).forEach((k) => body.parameters[k] === undefined && delete body.parameters[k]); if (model === "mechanobio" && body.parameters.parameters.viscosity_pN_s_nm === undefined) delete body.parameters.parameters;
      out.innerHTML = '<p class="small">Running… (the node allows up to 8 s)</p>';
      try { out.innerHTML = render(model, await DF.api.simulate(body)); } catch (ex) { out.innerHTML = html`<p class="adapter-out unavailable">${ex.message}</p>`.toString(); }
    });
  };
})();
