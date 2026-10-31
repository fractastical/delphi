/* Flying-fish design workspace: browser arithmetic on published fits, a threshold check, and a
 * parametric projection of the entered dimensions.  This is calculation, not an SMT solver, not CFD,
 * and the geometry is a design visualisation, not an observed fish. */
(function () {
  const DF = window.DF; const { esc } = DF;
  const G = 9.81;
  const LIM = { WL_MAX: 208.9, AR_MIN: 3.0, AR_MAX: 16.9, AR_MAX_TABLE: 19.9, FIN_MAX: 0.79, SL_MAX: 0.5, SL_MIN: 0.05, V_ANCHOR: 16, WL_ANCHOR: 205.5, MASS_MIN: 0.003, MASS_MAX: 0.53 };
  const known = (x) => x !== null && x !== undefined && x !== "" && isFinite(x);
  const FIELDS = ["mass_kg", "standard_length_m", "span_m", "aspect_ratio", "pectoral_fin_m", "launch_speed", "four_winged", "cg_aft", "novel_appendage", "powered_flapping", "pect_share", "assume_pect_ar_wing", "assume_taxi_flight", "rho", "cl_max"];

  function blank() { const c = {}; FIELDS.forEach((f) => (c[f] = null)); c.pect_share = 0.8; return c; }

  function derive(c) {
    const area = known(c.span_m) && known(c.aspect_ratio) && c.aspect_ratio > 0 ? c.span_m * c.span_m / c.aspect_ratio : null;
    const wl = known(c.mass_kg) && area ? c.mass_kg * G / area : null;
    const vreq = wl !== null ? LIM.V_ANCHOR * Math.sqrt(wl / LIM.WL_ANCHOR) : null;
    return { area, wl, vreq, extrapolated: known(c.mass_kg) && (c.mass_kg > LIM.MASS_MAX || c.mass_kg < LIM.MASS_MIN) };
  }

  const R = (status, detail, extra = {}) => Object.assign({ status, detail }, extra);
  function checks(c, mission) {
    const d = derive(c); const out = {};
    const meta = Object.fromEntries(mission.constraints.map((k) => [k.id, k]));
    const ex = d.extrapolated ? "Mass lies outside the 0.003-0.53 kg range Fish (1990) measured, so this threshold is extrapolated." : null;
    out.C1 = d.wl === null ? R("unknown", "Needs mass, span and aspect ratio (wing area is span squared over aspect ratio).") :
      d.wl <= LIM.WL_MAX ? R("pass", `WL = ${DF.fmt(d.wl, 4)} N/m^2 is within the measured maximum of 208.9.`, { extrapolated: d.extrapolated, note: ex }) :
        R("fail", `WL = ${DF.fmt(d.wl, 4)} N/m^2 exceeds 208.9, the largest value measured on any specimen (${DF.fmt(d.wl / LIM.WL_MAX, 3)}x).`, { extrapolated: d.extrapolated, note: ex });
    if (d.wl === null) out.C2 = R("unknown", "Needs mass, span and aspect ratio.");
    else if (c.assume_taxi_flight !== true) out.C2 = R("unknown", `Not evaluated: the 16 m/s anchor is a Cypselurus taxiing launch speed (observed 16-20 m/s), not a flight-speed bound for every design. Opt in below to apply it as an assumption. Implied value if applied: ${DF.fmt(d.vreq, 3)} m/s.`);
    else if (!known(c.launch_speed)) out.C2 = R("unknown", `Assumption opted in. Implied requirement ${DF.fmt(d.vreq, 3)} m/s; no launch speed is declared and none is assumed.`, { extrapolated: d.extrapolated, note: ex, assumption: true });
    else out.C2 = c.launch_speed >= d.vreq ? R("pass", `ASSUMPTION (taxi anchor applied to flight): declared ${DF.fmt(c.launch_speed, 3)} m/s >= ${DF.fmt(d.vreq, 3)} m/s.`, { extrapolated: d.extrapolated, note: ex, assumption: true }) :
      R("fail", `ASSUMPTION (taxi anchor applied to flight): declared ${DF.fmt(c.launch_speed, 3)} m/s < ${DF.fmt(d.vreq, 3)} m/s.`, { extrapolated: d.extrapolated, note: ex, assumption: true });
    out.C3 = !known(c.pectoral_fin_m) || !known(c.standard_length_m) ? R("unknown", "Needs pectoral fin length and standard length.") :
      c.pectoral_fin_m <= LIM.FIN_MAX * c.standard_length_m ? R("pass", `Fin / SL = ${DF.fmt(c.pectoral_fin_m / c.standard_length_m, 3)} <= 0.79.`) :
        R("fail", `Fin / SL = ${DF.fmt(c.pectoral_fin_m / c.standard_length_m, 3)} > 0.79 (Davenport 1992: swimming impaired).`);
    if (c.cg_aft === null || c.cg_aft === undefined) out.C4 = R("unknown", "Centre-of-gravity position not declared.");
    else if (c.cg_aft === false) out.C4 = R("unknown", "Declared not aft. The source statement is qualitative and no numeric CG offset or threshold exists, so this cannot be a pass.");
    else if (c.four_winged === true) out.C4 = R("unknown", "Flag: CG declared aft; a pelvic tailplane is declared. Davenport describes pelvic fins as solving pitch stability, but no magnitude is checked and Davenport 2003 is unread.");
    else if (c.four_winged === false) out.C4 = R("fail", "Qualitative flag from Davenport (1992): CG aft of the pectorals without a pelvic tailplane is the Oxyporhamphus situation. No numeric check.");
    else out.C4 = R("unknown", "Flag: CG declared aft; whether a pelvic tailplane exists is not declared.");
    out.C5 = !known(c.aspect_ratio) ? R("unknown", "Needs aspect ratio.") : c.assume_pect_ar_wing !== true ? R("unknown", `Not evaluated: Fish's 3.0-16.9 is the aspect ratio of individual pectoral fins; this AR is whole-wing span^2/area. Opt in below to treat them as the same (an assumption). AR = ${DF.fmt(c.aspect_ratio, 3)}.`) :
      c.aspect_ratio < LIM.AR_MIN ? R("fail", `AR = ${DF.fmt(c.aspect_ratio, 3)} < 3.0.`) :
        c.aspect_ratio <= LIM.AR_MAX ? R("pass", `AR = ${DF.fmt(c.aspect_ratio, 3)} within 3.0-16.9.`) :
          c.aspect_ratio <= LIM.AR_MAX_TABLE ? R("disputed", `AR = ${DF.fmt(c.aspect_ratio, 3)} is above Fish's text maximum (16.9) but within his Table III maximum (19.9). The paper disagrees with itself.`) :
            R("fail", `AR = ${DF.fmt(c.aspect_ratio, 3)} > 19.9, above both stated maxima.`);
    const a = c.novel_appendage, b = c.powered_flapping;
    out.C6a = a === true || b === true ? R("fail", `Flag: ${a === true ? "a novel appendage" : "powered flapping"} is declared, which a beloniform-derived design is not assumed to have. Metadata flag only.`) :
      R("unknown", "No flag raised. That does NOT establish evolutionary reachability: the developmental and evolutionary bridge is unestablished.");
    out.C6b = !known(c.standard_length_m) ? R("unknown", "Needs standard length.") :
      c.standard_length_m <= LIM.SL_MAX ? R("pass", `SL = ${DF.fmt(c.standard_length_m, 3)} m is within the extant envelope (<= 0.50 m).`) :
        R("fail", `SL = ${DF.fmt(c.standard_length_m, 3)} m exceeds 0.50 m, the largest extant exocoetid. An observation about extant species, not a physical limit.`);
    out.C6c = !known(c.standard_length_m) ? R("unknown", "Needs standard length.") :
      c.standard_length_m >= LIM.SL_MIN ? R("pass", `SL = ${DF.fmt(c.standard_length_m, 3)} m >= 0.05 m.`) : R("fail", `SL = ${DF.fmt(c.standard_length_m, 3)} m < 0.05 m: juveniles this small do not glide.`);
    for (const id in out) out[id].meta = meta[id];
    return out;
  }
  function verdict(res) {
    const all = Object.values(res); const ev = all.filter((r) => r.status !== "unknown");
    const failed = all.filter((r) => r.status === "fail").map((r) => r.meta.id);
    const unknown = all.filter((r) => r.status === "unknown").map((r) => r.meta.id);
    const disputed = all.filter((r) => r.status === "disputed").map((r) => r.meta.id);
    const extrapolated = all.filter((r) => r.extrapolated).map((r) => r.meta.id);
    const label = failed.length ? "FLAG RAISED" : ev.length ? "NO FLAG RAISED" : "UNDETERMINED";
    return { label, evaluable: ev.length, total: all.length, failed, unknown, disputed, extrapolated };
  }

  function applyPreset(p, mission) {
    const c = blank(); const v = p.values;
    FIELDS.forEach((f) => { if (f in v) c[f] = v[f]; });
    if (v.span_from_wl && known(c.mass_kg) && known(c.aspect_ratio)) {
      const wl = v.span_from_wl * Math.pow(c.mass_kg, v.wl_exp);
      const area = c.mass_kg * G / wl; c.span_m = +Math.sqrt(c.aspect_ratio * area).toFixed(4);
    }
    return c;
  }

  function extrapolationRows(mission) {
    const cy = mission.genus_fits.find((g) => g.genus === "Cypselurus"), hi = mission.genus_fits.find((g) => g.genus === "Hirundichthys");
    return [0.53, 1, 2, 5, 10].map((m) => {
      const a = cy.a * Math.pow(m, cy.b), b = hi.a * Math.pow(m, hi.b);
      return { m, cy: a, hi: b, v: LIM.V_ANCHOR * Math.sqrt(a / LIM.WL_ANCHOR), measured: m <= LIM.MASS_MAX };
    });
  }

  /* ---------------- geometry ---------------- */
  function geometry(c) {
    const need = ["standard_length_m", "span_m", "aspect_ratio"].filter((k) => !known(c[k]));
    if (need.length) return { missing: need };
    const L = c.standard_length_m, b = c.span_m, S = b * b / c.aspect_ratio;
    const four = c.four_winged === true; const share = four ? Math.min(0.92, Math.max(0.76, c.pect_share || 0.8)) : 1;
    const tris = []; const add = (p, kind) => tris.push({ p, kind });
    const Dm = 0.16 * L, Wm = 0.12 * L, N = 26, M = 16;
    const prof = (t) => Math.max(0.1, Math.pow(Math.sin(Math.PI * Math.pow(t, 0.85)), 0.65));
    const ring = (t) => { const x = (t - 0.5) * L, f = prof(t); const pts = []; for (let j = 0; j < M; j++) { const a = (2 * Math.PI * j) / M; pts.push([x, Math.sin(a) * Dm * f / 2 - (Math.sin(a) < 0 ? 0.01 * L * f : 0), Math.cos(a) * Wm * f / 2]); } return pts; };
    let prev = ring(0);
    for (let i = 1; i <= N; i++) {
      const cur = ring(i / N);
      for (let j = 0; j < M; j++) { const k = (j + 1) % M; add([prev[j], prev[k], cur[j]], "body"); add([prev[k], cur[k], cur[j]], "body"); }
      prev = cur;
    }
    const tx = -L / 2, tb = 0.05 * L;
    add([[tx, 0, -0.001], [tx - 0.10 * L, 0.11 * L, 0], [tx, tb * 0.5, 0.001]], "tail-upper");
    add([[tx, 0, 0.001], [tx - 0.171 * L, -0.15 * L, 0], [tx, -tb * 0.5, -0.001]], "tail-lower");
    add([[tx, 0.04 * L, 0], [tx - 0.10 * L, 0.11 * L, 0], [tx, 0, 0]], "tail-upper"); add([[tx, -0.04 * L, 0], [tx - 0.171 * L, -0.15 * L, 0], [tx, 0, 0]], "tail-lower");
    const wing = (x0, y0, side, semi, area, sweep, kind) => {
      const taper = 0.4; const cr = (2 * area) / (semi * (1 + taper)); const ct = taper * cr;
      const zr = side * Wm * 0.5, zt = side * semi, xt = x0 - sweep * semi;
      const P = [[x0 + cr * 0.35, y0, zr], [xt + ct * 0.35, y0, zt], [xt - ct * 0.65, y0, zt], [x0 - cr * 0.65, y0, zr]];
      add([P[0], P[1], P[2]], kind); add([P[0], P[2], P[3]], kind);
    };
    const Ap = S * share / 2; const semiP = b / 2;
    [-1, 1].forEach((s) => wing(0.16 * L, 0.04 * L, s, semiP, Ap, 0.3, "pectoral"));
    if (four) {
      const Aq = S * (1 - share) / 2; const semiQ = 0.5 * Math.sqrt(c.aspect_ratio * S * (1 - share));
      [-1, 1].forEach((s) => wing(-0.04 * L, -0.045 * L, s, semiQ, Aq, 0.25, "pelvic"));
    }
    return { tris, L, b, S };
  }

  const COLORS = { body: [24, 58, 92], "tail-upper": [20, 48, 80], "tail-lower": [14, 100, 110], pectoral: [140, 190, 60], pelvic: [200, 160, 50] };
  const VIEWS = { side: [0, 0], top: [0, Math.PI / 2], front: [Math.PI / 2, 0], "3/4": [0.62, 0.38] };

  function rot(p, yaw, pitch) {
    let [x, y, z] = p; const cy = Math.cos(yaw), sy = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
    [x, z] = [x * cy + z * sy, -x * sy + z * cy];
    [y, z] = [y * cp - z * sp, y * sp + z * cp];
    return [x, y, z];
  }

  function paint(canvas, geo, cam, theme) {
    const dpr = Math.min(2, window.devicePixelRatio || 1); const w = canvas.clientWidth, h = canvas.clientHeight;
    if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) { canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr); }
    const ctx = canvas.getContext("2d"); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, w, h);
    const css = getComputedStyle(canvas); const ink = css.getPropertyValue("--ink").trim() || "#0f2238", faint = css.getPropertyValue("--faint").trim() || "#6b7a8c";
    if (!geo || geo.missing) {
      ctx.fillStyle = faint; ctx.font = "14px system-ui"; ctx.textAlign = "center";
      ctx.fillText("Enter standard length, span and aspect ratio to draw the design.", w / 2, h / 2 - 8);
      ctx.fillText("Nothing is drawn from defaults.", w / 2, h / 2 + 14); return null;
    }
    const proj = geo.tris.map((t) => { const q = t.p.map((p) => rot(p, cam.yaw, cam.pitch)); const n = cross(sub(q[1], q[0]), sub(q[2], q[0])); return { q, kind: t.kind, n, z: (q[0][2] + q[1][2] + q[2][2]) / 3 }; });
    let minx = Infinity, maxx = -Infinity, miny = Infinity, maxy = -Infinity;
    proj.forEach((t) => t.q.forEach((p) => { minx = Math.min(minx, p[0]); maxx = Math.max(maxx, p[0]); miny = Math.min(miny, p[1]); maxy = Math.max(maxy, p[1]); }));
    const pad = 46; const sc = Math.min((w - 2 * pad) / Math.max(1e-6, maxx - minx), (h - 2 * pad) / Math.max(1e-6, maxy - miny));
    const ox = w / 2 - ((minx + maxx) / 2) * sc, oy = h / 2 + ((miny + maxy) / 2) * sc;
    const X = (p) => ox + p[0] * sc, Y = (p) => oy - p[1] * sc;
    proj.sort((a, b) => a.z - b.z);
    const light = norm([-0.35, 0.8, 0.6]);
    proj.forEach((t) => {
      const nn = norm(t.n); const lam = Math.abs(dot(nn, light)); const base = COLORS[t.kind] || [120, 120, 120];
      const k = 0.55 + 0.55 * lam; const col = base.map((v) => Math.min(255, Math.round(v * k)));
      ctx.beginPath(); ctx.moveTo(X(t.q[0]), Y(t.q[0])); ctx.lineTo(X(t.q[1]), Y(t.q[1])); ctx.lineTo(X(t.q[2]), Y(t.q[2])); ctx.closePath();
      const wingKind = t.kind === "pectoral" || t.kind === "pelvic";
      ctx.fillStyle = `rgba(${col[0]},${col[1]},${col[2]},${wingKind ? 0.82 : 1})`; ctx.fill();
      ctx.strokeStyle = `rgba(${col[0]},${col[1]},${col[2]},${wingKind ? 0.9 : 1})`; ctx.lineWidth = 0.6; ctx.stroke();
    });
    // scale bar (metres, from the entered dimensions)
    const nice = [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1]; const target = (w * 0.2) / sc; const len = nice.reduce((a, b) => (Math.abs(b - target) < Math.abs(a - target) ? b : a));
    ctx.strokeStyle = ink; ctx.fillStyle = ink; ctx.lineWidth = 1.5; ctx.font = "12px ui-monospace, monospace"; ctx.textAlign = "left";
    ctx.beginPath(); ctx.moveTo(16, h - 18); ctx.lineTo(16 + len * sc, h - 18); ctx.moveTo(16, h - 23); ctx.lineTo(16, h - 13); ctx.moveTo(16 + len * sc, h - 23); ctx.lineTo(16 + len * sc, h - 13); ctx.stroke();
    ctx.fillText(len >= 1 ? `${len} m` : `${len * 100} cm`, 22 + len * sc, h - 14);
    return { sc };
  }
  const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
  const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  const norm = (a) => { const l = Math.hypot(a[0], a[1], a[2]) || 1; return [a[0] / l, a[1] / l, a[2] / l]; };

  /* ---------------- log-log wing loading chart ---------------- */
  function wlChart(host, mission, cand) {
    const W = 560, H = 300, m = { l: 52, r: 14, t: 14, b: 40 };
    const x = (mass) => m.l + ((Math.log10(mass) - Math.log10(0.001)) / (Math.log10(10) - Math.log10(0.001))) * (W - m.l - m.r);
    const y = (wl) => H - m.b - ((Math.log10(wl) - Math.log10(5)) / (Math.log10(2000) - Math.log10(5))) * (H - m.t - m.b);
    let s = `<svg viewBox="0 0 ${W} ${H}" class="chart" role="img" aria-label="Wing loading against body mass, per-genus fits from Fish 1990, measured mass range solid and extrapolation dashed, with the 208.9 N per square metre maximum and the candidate marked">`;
    [0.001, 0.01, 0.1, 1, 10].forEach((t) => { s += `<line x1="${x(t)}" x2="${x(t)}" y1="${m.t}" y2="${H - m.b}" class="grid"/><text x="${x(t)}" y="${H - m.b + 16}" class="tick" text-anchor="middle">${t}</text>`; });
    [10, 100, 1000].forEach((t) => { s += `<line y1="${y(t)}" y2="${y(t)}" x1="${m.l}" x2="${W - m.r}" class="grid"/><text x="${m.l - 6}" y="${y(t) + 4}" class="tick" text-anchor="end">${t}</text>`; });
    s += `<text x="${(W + m.l) / 2}" y="${H - 6}" class="axis" text-anchor="middle">body mass M (kg, log)</text><text transform="translate(12 ${H / 2}) rotate(-90)" class="axis" text-anchor="middle">wing loading WL (N/m², log)</text>`;
    s += `<rect x="${x(LIM.MASS_MIN)}" y="${m.t}" width="${x(LIM.MASS_MAX) - x(LIM.MASS_MIN)}" height="${H - m.t - m.b}" class="band"><title>Mass range measured by Fish 1990: 0.003-0.53 kg</title></rect>`;
    s += `<line x1="${m.l}" x2="${W - m.r}" y1="${y(LIM.WL_MAX)}" y2="${y(LIM.WL_MAX)}" class="limit"/><text x="${W - m.r - 4}" y="${y(LIM.WL_MAX) - 5}" class="tick" text-anchor="end">208.9 largest measured WL</text>`;
    const cols = ["#0e7c86", "#a6c936", "#d97b29", "#7a5ea8", "#c0392b", "#3a7bd5"];
    mission.genus_fits.forEach((g, i) => {
      const pts = (lo, hi) => { let d = ""; for (let k = 0; k <= 24; k++) { const mass = lo * Math.pow(hi / lo, k / 24); d += (k ? "L" : "M") + x(mass).toFixed(1) + "," + y(g.a * Math.pow(mass, g.b)).toFixed(1); } return d; };
      s += `<path d="${pts(LIM.MASS_MIN, LIM.MASS_MAX)}" class="curve" stroke="${cols[i]}"><title>${esc(g.genus)}: WL = ${g.a} M^${g.b} (n = ${g.n})</title></path>`;
      s += `<path d="${pts(LIM.MASS_MAX, 10)}" class="curve dashed" stroke="${cols[i]}"/>`;
    });
    const d = derive(cand);
    if (d.wl !== null && cand.mass_kg >= 0.001 && cand.mass_kg <= 10) s += `<g class="cand"><circle cx="${x(cand.mass_kg)}" cy="${y(Math.min(2000, Math.max(5, d.wl)))}" r="6"/><text x="${x(cand.mass_kg) + 9}" y="${y(Math.min(2000, Math.max(5, d.wl))) - 8}">candidate WL ${DF.fmt(d.wl, 3)}</text></g>`;
    s += "</svg>";
    host.innerHTML = s + `<ul class="legend inline">${mission.genus_fits.map((g, i) => `<li><i class="sw" style="background:${cols[i]}"></i>${esc(g.genus)} <span class="faint">b = ${g.b}</span></li>`).join("")}</ul>`;
  }

  DF.fish = { LIM, FIELDS, blank, derive, checks, verdict, applyPreset, extrapolationRows, geometry, paint, VIEWS, wlChart, known };
})();
