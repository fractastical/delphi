#!/usr/bin/env python3
"""Test thompson1917-ch11-03: a constant ratio of outer to inner marginal growth
is an equiangular spiral, the same angle on both margins.

Pre-registered in result.json (commit before these files were opened).
Group S uses Spirula septal landmarks (figshare 10.6084/m9.figshare.12006366).
Group A uses ammonoid conch and umbilical radii (Zenodo 10.5281/zenodo.4937032).

The pole for Spirula is the algebraic circle through the first six external
landmarks, then held fixed, as registered. Theta for an ammonoid station labelled
"Whorl w" is the half-whorl index (2w) times pi, which is w revolutions.
"""
import hashlib, json, math, os, urllib.request
from datetime import datetime, timezone

import numpy as np
import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

UA = "delphi-claim-test/1.0 (thompson1917-ch11-03)"
FILES = {
    "ExternalSide.spiral": "https://ndownloader.figshare.com/files/22534694",
    "InternalSide.spiral": "https://ndownloader.figshare.com/files/22534697",
    "Ontogenetic_Conch_Parameter_Data.xlsx":
        "https://zenodo.org/api/records/4937032/files/Ontogenetic_Conch_Parameter_Data.xlsx/content",
}


def source_records():
    """Landing-record metadata. Licences come from the APIs, not from memory."""
    out = {}
    fig_url = "https://api.figshare.com/v2/articles/12006366"
    req = urllib.request.Request(fig_url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        fig = json.load(r)
    license_name = None
    if isinstance(fig.get("license"), dict):
        license_name = fig["license"].get("name") or fig["license"].get("url")
    out["figshare-12006366"] = {
        "api_url": fig_url,
        "title": fig.get("title"),
        "doi": fig.get("doi"),
        "license": license_name,
        "url": fig.get("url_public_html") or fig.get("figshare_url"),
    }
    zen_url = "https://zenodo.org/api/records/4937032"
    req = urllib.request.Request(zen_url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        zen = json.load(r)
    meta = zen.get("metadata") or {}
    out["zenodo-4937032"] = {
        "api_url": zen_url,
        "title": meta.get("title"),
        "doi": zen.get("doi"),
        "license": meta.get("license"),
        "related_identifiers": [
            {"relation": item.get("relation"), "identifier": item.get("identifier")}
            for item in (meta.get("related_identifiers") or [])
        ],
    }
    return out


def fetch(name, url):
    path = os.path.join(DATA, name)
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=180) as r:
            blob = r.read()
        with open(path, "wb") as f:
            f.write(blob)
    blob = open(path, "rb").read()
    return {
        "name": name,
        "download_url": url,
        "byte_size": len(blob),
        "sha256": hashlib.sha256(blob).hexdigest(),
        "retrieved_at": datetime.fromtimestamp(os.path.getmtime(path), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def parse_spiral(path):
    table = {}
    for line in open(path, encoding="utf-8", errors="replace"):
        if not line.strip():
            continue
        parts, cur, quoted = [], "", False
        for ch in line.rstrip("\r\n"):
            if ch == '"':
                quoted = not quoted
            elif ch == "," and not quoted:
                parts.append(cur)
                cur = ""
            else:
                cur += ch
        parts.append(cur)
        key = parts[0]
        vals = []
        for v in parts[1:]:
            v = v.strip()
            vals.append(np.nan if v in ("", "NA", "NaN") else float(v))
        table[key] = np.array(vals, float)
    return table


def circle_center(x, y):
    """Algebraic circle fit. Returns the centre, which is then held fixed."""
    A = np.column_stack([x, y, np.ones(len(x))])
    coef, *_ = np.linalg.lstsq(A, -(x * x + y * y), rcond=None)
    return float(-coef[0] / 2), float(-coef[1] / 2)


def unwrap(theta):
    out = np.array(theta, float)
    for i in range(1, len(out)):
        d = out[i] - out[i - 1]
        if d > math.pi:
            out[i:] -= 2 * math.pi
        elif d < -math.pi:
            out[i:] += 2 * math.pi
    return out


def polar(x, y, cx, cy):
    theta = unwrap(np.arctan2(y - cy, x - cx))
    if len(theta) > 2 and np.nanmedian(np.diff(theta)) < 0:
        theta = -theta
    theta = theta - theta[0]
    radius = np.hypot(x - cx, y - cy)
    return theta, radius


def fit_models(theta, radius):
    """Logarithmic r = a exp(k theta) and Archimedean r = a + b theta. RMSE on r."""
    mask = np.isfinite(theta) & np.isfinite(radius) & (radius > 0)
    th, r = theta[mask], radius[mask]
    if len(r) < 4 or np.std(th) < 1e-8:
        return None
    order = np.argsort(th)
    th, r = th[order], r[order]
    X = np.column_stack([np.ones(len(th)), th])
    coef_log, *_ = np.linalg.lstsq(X, np.log(r), rcond=None)
    pred_log = np.exp(X @ coef_log)
    coef_arch, *_ = np.linalg.lstsq(X, r, rcond=None)
    pred_arch = X @ coef_arch
    rmse_log = float(np.sqrt(np.mean((r - pred_log) ** 2)))
    rmse_arch = float(np.sqrt(np.mean((r - pred_arch) ** 2)))
    k = float(coef_log[1])
    if abs(k) < 0.02:
        alpha = 90.0
    else:
        alpha = float(np.degrees(np.arctan2(1.0, k)))
        if alpha < 0:
            alpha += 180.0
    return {
        "n": int(len(r)),
        "k": k,
        "alpha_deg": alpha,
        "rmse_log": rmse_log,
        "rmse_arch": rmse_arch,
        "log_adequate": bool(rmse_log <= 1.05 * rmse_arch),
    }


def ratio_cv(theta, r_outer, r_inner):
    """q = (mean outer radius) / (mean inner radius) on steps with Δθ > 0.05."""
    q = []
    for i in range(len(theta) - 1):
        dth = theta[i + 1] - theta[i]
        if not np.isfinite(dth) or dth <= 0.05:
            continue
        ro = (r_outer[i] + r_outer[i + 1]) / 2
        ri = (r_inner[i] + r_inner[i + 1]) / 2
        if np.isfinite(ro) and np.isfinite(ri) and ri > 0 and ro > 0:
            q.append(ro / ri)
    q = np.array(q, float)
    if len(q) < 4 or not np.isfinite(q).all() or np.mean(q) <= 0:
        return None, int(len(q))
    return float(np.std(q, ddof=1) / np.mean(q)), int(len(q))


def score_group(rows, min_n):
    """Apply the pre-registered group rule. rows are qualifying series only."""
    n = len(rows)
    if n < min_n:
        return {
            "n_qualifying": n,
            "group_verdict": "inconclusive",
            "reason": "underpowered",
            "detail": rows_summary(rows),
        }
    frac_outer = float(np.mean([r["log_outer"] for r in rows]))
    frac_inner = float(np.mean([r["log_inner"] for r in rows]))
    cv = np.array([r["cv_q"] for r in rows], float)
    dalpha = np.array([r["dalpha"] for r in rows], float)
    med_cv = float(np.median(cv))
    med_dalpha = float(np.median(dalpha))
    support = (
        frac_outer >= 0.80 and frac_inner >= 0.80 and med_cv <= 0.25 and med_dalpha <= 5.0
    )
    refute = frac_outer < 0.50 or frac_inner < 0.50 or med_cv >= 0.50 or med_dalpha >= 15.0
    if refute:
        verdict = "refutes"
    elif support:
        verdict = "supports"
    else:
        verdict = "mixed"
    return {
        "n_qualifying": n,
        "group_verdict": verdict,
        "fraction_log_adequate_outer": round(frac_outer, 4),
        "fraction_log_adequate_inner": round(frac_inner, 4),
        "median_cv_q": round(med_cv, 4),
        "median_abs_alpha_diff_deg": round(med_dalpha, 4),
        "median_alpha_outer_deg": round(float(np.median([r["alpha_outer"] for r in rows])), 3),
        "median_alpha_inner_deg": round(float(np.median([r["alpha_inner"] for r in rows])), 3),
        "detail_quantiles": {
            "cv_q": quantiles(cv),
            "abs_alpha_diff_deg": quantiles(dalpha),
        },
    }


def quantiles(a):
    qs = np.nanpercentile(a, [10, 25, 50, 75, 90])
    return [round(float(v), 4) for v in qs]


def descriptive_margins(rows):
    """Statistics the verdict does not use. Written so result.json can quote the script."""
    if not rows:
        return {}
    ko = np.array([r["k_outer"] for r in rows], float)
    ki = np.array([r["k_inner"] for r in rows], float)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(np.abs(ko) > 1e-8, ki / ko, np.nan)
    cv = np.array([r["cv_q"] for r in rows], float)
    dalpha = np.array([r["dalpha"] for r in rows], float)
    rlo = np.array([r["rmse_log_outer"] for r in rows], float)
    rao = np.array([r["rmse_arch_outer"] for r in rows], float)
    rli = np.array([r["rmse_log_inner"] for r in rows], float)
    rai = np.array([r["rmse_arch_inner"] for r in rows], float)
    inner_ratio = rli / rai

    def med(a, nd=6):
        return round(float(np.nanmedian(a)), nd)

    return {
        "median_k_outer": med(ko),
        "median_k_inner": med(ki),
        "median_k_inner_over_k_outer": med(ratio),
        "median_rmse_log_outer": med(rlo, 4),
        "median_rmse_arch_outer": med(rao, 4),
        "median_rmse_log_inner": med(rli, 4),
        "median_rmse_arch_inner": med(rai, 4),
        "fraction_cv_q_le_0.25": round(float(np.mean(cv <= 0.25)), 4),
        "fraction_cv_q_ge_0.50": round(float(np.mean(cv >= 0.50)), 4),
        "fraction_abs_alpha_diff_le_5": round(float(np.mean(dalpha <= 5.0)), 4),
        "fraction_abs_alpha_diff_ge_15": round(float(np.mean(dalpha >= 15.0)), 4),
        "fraction_inner_rmse_ratio_gt_1.05": round(float(np.mean(inner_ratio > 1.05)), 4),
        "fraction_inner_rmse_ratio_gt_2": round(float(np.mean(inner_ratio > 2.0)), 4),
    }


def rows_summary(rows):
    if not rows:
        return {}
    return {
        "n_computed": len(rows),
        "fraction_log_adequate_outer": round(float(np.mean([r["log_outer"] for r in rows])), 4),
        "fraction_log_adequate_inner": round(float(np.mean([r["log_inner"] for r in rows])), 4),
        "median_cv_q": round(float(np.median([r["cv_q"] for r in rows])), 4),
        "median_abs_alpha_diff_deg": round(float(np.median([r["dalpha"] for r in rows])), 4),
        "median_alpha_outer_deg": round(float(np.median([r["alpha_outer"] for r in rows])), 3),
        "median_alpha_inner_deg": round(float(np.median([r["alpha_inner"] for r in rows])), 3),
    }


def spirula_series():
    ext = parse_spiral(os.path.join(DATA, "ExternalSide.spiral"))
    inn = parse_spiral(os.path.join(DATA, "InternalSide.spiral"))
    ids = sorted({k.split(".", 1)[1] for k in ext if k.startswith("x.")})
    out = []
    for sid in ids:
        xo, yo = ext.get(f"x.{sid}"), ext.get(f"y.{sid}")
        xi, yi = inn.get(f"x.{sid}"), inn.get(f"y.{sid}")
        if xo is None or xi is None:
            continue
        n = min(len(xo), len(xi), len(yo), len(yi))
        xo, yo, xi, yi = xo[:n], yo[:n], xi[:n], yi[:n]
        m = np.isfinite(xo) & np.isfinite(yo) & np.isfinite(xi) & np.isfinite(yi)
        xo, yo, xi, yi = xo[m], yo[m], xi[m], yi[m]
        if len(xo) < 10:
            continue
        cx, cy = circle_center(xo[:6], yo[:6])
        th_o, r_o = polar(xo, yo, cx, cy)
        th_i, r_i = polar(xi, yi, cx, cy)
        # Shared station order is the septum order. Outer theta is the angular coordinate
        # of the outer landmark; the inner landmark keeps its own angle about the same pole.
        fit_o = fit_models(th_o, r_o)
        fit_i = fit_models(th_i, r_i)
        # q uses the outer angular step and the two radii at the same septum index.
        cv, n_q = ratio_cv(th_o, r_o, r_i)
        if fit_o is None or fit_i is None or cv is None:
            continue
        frac_outer = float(np.mean(r_o > r_i))
        if frac_outer < 0.8:
            continue
        out.append({
            "id": sid,
            "n": int(len(xo)),
            "fraction_outer_greater": round(frac_outer, 4),
            "log_outer": fit_o["log_adequate"],
            "log_inner": fit_i["log_adequate"],
            "alpha_outer": fit_o["alpha_deg"],
            "alpha_inner": fit_i["alpha_deg"],
            "dalpha": abs(fit_o["alpha_deg"] - fit_i["alpha_deg"]),
            "cv_q": cv,
            "k_outer": fit_o["k"],
            "k_inner": fit_i["k"],
            "rmse_log_outer": fit_o["rmse_log"],
            "rmse_arch_outer": fit_o["rmse_arch"],
            "rmse_log_inner": fit_i["rmse_log"],
            "rmse_arch_inner": fit_i["rmse_arch"],
            "pathological_label": sid.endswith("p"),
        })
    return out


def sheet_table(ws):
    rows = list(ws.iter_rows(values_only=True))
    header = [str(c) if c is not None else "" for c in rows[0]]
    return header, rows[1:]


def ammonoid_series():
    wb = openpyxl.load_workbook(
        os.path.join(DATA, "Ontogenetic_Conch_Parameter_Data.xlsx"),
        read_only=True, data_only=True)
    h_dm, dm_rows = sheet_table(wb["dm"])
    h_uw, uw_rows = sheet_table(wb["UWI"])
    wb.close()
    whorl_cols = []
    for i, name in enumerate(h_dm):
        if name.startswith("Whorl "):
            whorl_cols.append((float(name.split()[1]), i))
    whorl_cols.sort()
    uw_index = {row[0]: row for row in uw_rows}
    out = []
    for row in dm_rows:
        species = row[0]
        uw = uw_index.get(species)
        if uw is None:
            continue
        theta, r_o, r_i = [], [], []
        for whorl, col in whorl_cols:
            dm = row[col]
            uwi = uw[col]
            if not isinstance(dm, (int, float)) or not isinstance(uwi, (int, float)):
                continue
            if dm <= 0 or uwi <= 0 or uwi >= 1:
                continue
            # half-whorl index is 2*whorl (Whorl 0.5 is the first half-whorl); theta = index * pi
            theta.append(2.0 * whorl * math.pi)
            r_o.append(0.5 * float(dm))
            r_i.append(0.5 * float(uwi) * float(dm))
        theta, r_o, r_i = np.array(theta), np.array(r_o), np.array(r_i)
        if len(theta) < 6:
            continue
        if np.mean(r_o > r_i) < 1.0:
            continue
        fit_o = fit_models(theta, r_o)
        fit_i = fit_models(theta, r_i)
        cv, _ = ratio_cv(theta, r_o, r_i)
        if fit_o is None or fit_i is None or cv is None:
            continue
        out.append({
            "id": species,
            "n": int(len(theta)),
            "log_outer": fit_o["log_adequate"],
            "log_inner": fit_i["log_adequate"],
            "alpha_outer": fit_o["alpha_deg"],
            "alpha_inner": fit_i["alpha_deg"],
            "dalpha": abs(fit_o["alpha_deg"] - fit_i["alpha_deg"]),
            "cv_q": cv,
            "k_outer": fit_o["k"],
            "k_inner": fit_i["k"],
            "rmse_log_outer": fit_o["rmse_log"],
            "rmse_arch_outer": fit_o["rmse_arch"],
            "rmse_log_inner": fit_i["rmse_log"],
            "rmse_arch_inner": fit_i["rmse_arch"],
        })
    return out


def main():
    files = [fetch(name, url) for name, url in FILES.items()]
    spirula = spirula_series()
    ammonoids = ammonoid_series()
    group_s = score_group(spirula, 20)
    group_a = score_group(ammonoids, 20)
    group_s["descriptive"] = descriptive_margins(spirula)
    group_a["descriptive"] = descriptive_margins(ammonoids)
    group_s["n_series_with_any_radius_crossing"] = int(sum(
        1 for r in spirula if r.get("fraction_outer_greater", 1) < 1))
    ext = parse_spiral(os.path.join(DATA, "ExternalSide.spiral"))
    chunks = [v[np.isfinite(v)] for k, v in ext.items() if k.startswith(("x.", "y."))]
    median_abs = float(np.median(np.abs(np.concatenate(chunks))))
    group_s["median_abs_xy"] = round(median_abs, 3)
    group_s["pole_branch"] = "algebraic-circle" if median_abs >= 5 else "coordinate-origin"
    # Descriptive only: the landmark ids ending in "p" are the file's own pathological
    # specimens. Not used for the verdict (Spirula is under the pre-registered n).
    healthy = [r for r in spirula if not r["pathological_label"]]
    group_s["healthy_only_descriptive"] = rows_summary(healthy)
    group_s["healthy_only_descriptive"]["n"] = len(healthy)
    # Claim rule: refute if either scored group refutes; support only if both support;
    # one inconclusive group yields to the other; otherwise mixed.
    vs, va = group_s["group_verdict"], group_a["group_verdict"]
    if vs == "refutes" or va == "refutes":
        verdict = "refutes"
    elif vs == "supports" and va == "supports":
        verdict = "supports"
    elif vs == "inconclusive" and va != "inconclusive":
        verdict = va
    elif va == "inconclusive" and vs != "inconclusive":
        verdict = vs
    elif vs == "inconclusive" and va == "inconclusive":
        verdict = "inconclusive"
    else:
        verdict = "mixed"
    reason = None
    if verdict == "inconclusive":
        reason = group_a.get("reason") or group_s.get("reason") or "underpowered"
    measured = {
        "verdict": verdict,
        "reason": reason,
        "spirula": group_s,
        "ammonoids": group_a,
        "files": files,
        "source_records": source_records(),
    }
    # per-series tables
    def dump(path, rows):
        keys = ["id", "n", "log_outer", "log_inner", "alpha_outer", "alpha_inner",
                "dalpha", "cv_q", "k_outer", "k_inner",
                "rmse_log_outer", "rmse_arch_outer", "rmse_log_inner", "rmse_arch_inner"]
        with open(path, "w", encoding="utf-8") as f:
            f.write(",".join(keys) + "\n")
            for row in rows:
                f.write(",".join(str(row.get(k, "")) for k in keys) + "\n")
    dump(os.path.join(DERIVED, "spirula_series.csv"), spirula)
    dump(os.path.join(DERIVED, "ammonoid_series.csv"), ammonoids)
    with open(os.path.join(DERIVED, "measured.json"), "w", encoding="utf-8") as f:
        json.dump(measured, f, indent=2)
    print(json.dumps({
        "verdict": verdict,
        "reason": reason,
        "spirula_n": group_s["n_qualifying"],
        "spirula_verdict": vs,
        "spirula_detail": group_s.get("detail") or {k: group_s.get(k) for k in (
            "fraction_log_adequate_outer", "fraction_log_adequate_inner",
            "median_cv_q", "median_abs_alpha_diff_deg")},
        "ammonoid_n": group_a["n_qualifying"],
        "ammonoid_verdict": va,
        "ammonoid": {k: group_a.get(k) for k in (
            "fraction_log_adequate_outer", "fraction_log_adequate_inner",
            "median_cv_q", "median_abs_alpha_diff_deg",
            "median_alpha_outer_deg", "median_alpha_inner_deg")},
    }, indent=2))


if __name__ == "__main__":
    main()
