"""Build the fish control-knob dataset. Fetches the two sources, checks their pinned hashes, extracts Data S1A observations, fits and validates, and writes data/fish-controls/.

  PYTHONPATH=. python3 -m connectors.fish_controls.build
Not stored in the repo: the workbook (mmc2.xlsx) and the Fish 1990 PDF; only their hashes. Fish 1990 table values come from fish1990.py (read from page images).
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path

import numpy as np

from connectors.genomics import sources as S
from . import fish1990 as F

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "fish-controls"
S.ALLOWED_HOSTS = S.ALLOWED_HOSTS | {"ars.els-cdn.com", "health-sciences.wcupa.edu", "api.crossref.org"}
XLSX_URL = "https://ars.els-cdn.com/content/image/1-s2.0-S0960982221011908-mmc2.xlsx"
XLSX_SHA = "1ac98650f493036218837d235ed4451ff096d926fa50b797dcea4fc7fca52279"
FISH_URL = "https://health-sciences.wcupa.edu/sciences-mathematics/biology/fFish/documents/1990JZWing%20design.pdf"
FISH_SHA = "1efed334ed4aa48ec8e23801ff0b420d1d5c21430100a6d86d0b3e569421f8ea"
CROSSREF = "https://api.crossref.org/works/10.1016/j.cub.2021.08.054"
SEED, BOOT = 20261031, 2000
GROUPS = ["flying fish", "flying halfbeak", "halfbeak", "needlefish"]
fits_species: dict = {}
num = lambda x: float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def read_s1a(raw: bytes):
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    rows = list(wb["A - fin measurement"].iter_rows(values_only=True))
    assert list(rows[0][:9]) == ["fish #", "species", "group", "MCZ Catalog No", "SL (cm)", "pectoral (cm)", "pelvic (cm)", "pectoral/SL", "pelvic/SL"], rows[0]
    out = []
    for r in rows[1:]:
        if not r or r[0] is None:
            continue
        out.append({"fish_no": int(r[0]), "species": r[1], "group": r[2], "mcz_catalog_no": str(r[3]), "sl_cm": num(r[4]), "pectoral_cm": num(r[5]), "pelvic_cm": num(r[6]), "sheet_pectoral_over_sl": num(r[7]), "sheet_pelvic_over_sl": num(r[8]),
                    "cells_as_found": [None if c is None else str(c) for c in r[4:7]]})
    return out


def fit(x, y):
    """log10-log10 OLS with bootstrap CI and leave-one-out RMSE (all in log10 units). Returns (stats, per-point fitted and residuals)."""
    lx, ly = np.log10(x), np.log10(y)
    A = np.column_stack([np.ones_like(lx), lx])
    beta, *_ = np.linalg.lstsq(A, ly, rcond=None)
    fitted = A @ beta
    res = ly - fitted
    n = len(x)
    ss_res, ss_tot = float(res @ res), float(((ly - ly.mean()) ** 2).sum())
    H = A @ np.linalg.inv(A.T @ A) @ A.T
    loo = res / (1 - np.diag(H))
    rng = np.random.default_rng(SEED)
    bs = []
    for _ in range(BOOT):
        i = rng.integers(0, n, n)
        if len(set(lx[i])) < 2:
            continue
        bb, *_ = np.linalg.lstsq(np.column_stack([np.ones(n), lx[i]]), ly[i], rcond=None)
        bs.append(bb)
    bs = np.array(bs)
    ci = lambda v: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]
    stats = {"form": "log10(y) = log10(a) + b * log10(SL); y and SL in cm", "method": "ordinary least squares on log10 values", "n": n, "a": float(10 ** beta[0]), "b": float(beta[1]), "log10_a": float(beta[0]),
             "r2": 1 - ss_res / ss_tot if ss_tot > 0 else None, "residual_sd_log10": float(np.sqrt(ss_res / (n - 2))) if n > 2 else None, "loocv_rmse_log10": float(np.sqrt(np.mean(loo ** 2))),
             "bootstrap": {"seed": SEED, "resamples": int(len(bs)), "b_ci95": ci(bs[:, 1]), "a_ci95": [float(10 ** v) for v in ci(bs[:, 0])]}, "b_ci_excludes_1": not (ci(bs[:, 1])[0] <= 1 <= ci(bs[:, 1])[1])}
    return stats, fitted, res


def write_knobs(spec, fits, t1, t2, t3, src) -> int:
    """The control-knob dataset: {variable, unit, observations, fit/residuals, validity domain, taxon/context, source/locator}. Measured and published-fit-only knobs are never mixed."""
    s1a, f90 = src["sources"][0], src["sources"][1]
    knobs = []
    for key, f in fits.items():
        g, var = key.split("|")
        quality = "usable" if (f["r2"] is not None and f["r2"] >= 0.8 and f["n"] >= 15) else "weak: do not use as a control relation"
        knobs.append({
            "id": f"s1a-{var}-length-vs-sl-{g.replace(' ', '-')}", "kind": "observed_and_fitted_here", "variable": f"{var} fin length", "independent_variable": "standard length (SL)", "unit": "cm",
            "observations": {"path": "data/fish-controls/daane2021_s1a_observations.csv", "filter": {"group": g}, "column": f"{var}_cm", "n_nonmissing": f["n"], "n_missing": f["n_missing_in_group"], "missing_rule": "NA cells in the sheet stay empty; never replaced by a value"},
            "fit": {k: f[k] for k in ("form", "method", "n", "a", "b", "r2", "residual_sd_log10", "loocv_rmse_log10", "bootstrap", "b_ci_excludes_1", "ratio_to_sl")},
            "fit_quality": quality, "fit_quality_rule": "R^2 >= 0.8 and n >= 15", "residuals": {"path": "data/fish-controls/daane2021_s1a_residuals.csv", "filter": {"group": g, "variable": var}, "unit": "log10", "note": "observed minus fitted, per specimen"},
            "validity_domain": {"sl_cm": f["sl_cm_range"], "y_cm": f["y_cm_range"], "n": f["n"], "note": "inside the observed SL range of preserved museum specimens; no extrapolation"},
            "taxon_context": {"group": g, "species": fits_species[g], "material": "preserved specimens, Harvard Museum of Comparative Zoology", "pooling": "species and sizes pooled within the group; per-species relations may differ"},
            "source": {"id": "daane2021-data-s1", "locator": "Data S1A, sheet 'A - fin measurement'; Figure 1B", "sha256": s1a["sha256"]},
            "limits": ["fin length is the sheet's 'pectoral (cm)' / 'pelvic (cm)'; how it was measured is not stated in the sheet", "SL is not mass: do not combine with the mass-based Fish 1990 relations without a stated assumption (none is made here)",
                       "the sheet's own ratio columns are not used: ratios are recomputed from the lengths (one sheet cell is corrupt)"]})
    P = lambda t, name: {"id": "fish1990", "locator": t, "sha256": f90["sha256"]}
    for r in t1:
        knobs.append({"id": f"f90-t1-{r['dimension'].lower().replace(' ', '-')}-vs-mass-{r['genus'].lower()}", "kind": "published_fit_only", "variable": r["dimension"].lower(), "independent_variable": "body mass M", "unit": r["unit_inferred"] + " (unit inferred from magnitude, not printed)",
                      "observations": None, "raw_data_unavailable": "the paper measured 199 specimens and does not publish them", "observed_range": None,
                      "fit": {"form": "y = a * M^b (M in kg)", "method": "reduced major axis", "N": r["N"], "r": r["r"], "a": r["a"], "a_printed": r["a_printed"], "b": r["b"], "b_ci95": r["b_ci95"], "predicted_b_geometric": r["predicted_b"], "P_b_equals_predicted_printed": r["P_printed"]},
                      "residuals": None, "validity_domain": {"mass_kg": F.SPECIMENS["mass_range_kg"], "note": "the pooled range over all genera; the genus-specific mass range is not printed"},
                      "taxon_context": {"genus": r["genus"], "family": "Exocoetidae", "material": F.SPECIMENS["preserved"] + "; " + F.SPECIMENS["collections"]}, "source": P("Table I, journal p.394", ""), "limits": ["decimal point of `a` restored from the scan (a_printed is what is printed); checked by magnitude", "only one pectoral and one pelvic fin per specimen were measured"]})
    for r in t2:
        knobs.append({"id": f"f90-t2-wing-loading-vs-mass-{r['genus'].lower()}", "kind": "published_fit_only", "variable": "wing loading", "independent_variable": "body mass M", "unit": "N/m^2", "observations": None, "raw_data_unavailable": "per-specimen values not published",
                      "observed_range": {"wing_loading_N_per_m2": r["wing_loading_range_N_per_m2"], "kind": "min-max of the specimens, as printed"}, "fit": {"form": "wing loading = a * M^b (M in kg)", "method": "reduced major axis", "N": r["N"], "r": r["r"], "a": r["a"], "b": r["b"], "b_ci95": r["b_ci95"], "predicted_b_geometric": 0.33, "P_b_equals_predicted_printed": r["P_printed"]},
                      "residuals": None, "validity_domain": {"wing_loading_N_per_m2": r["wing_loading_range_N_per_m2"], "mass_kg": F.SPECIMENS["mass_range_kg"]}, "taxon_context": {"genus": r["genus"], "family": "Exocoetidae", "material": F.SPECIMENS["preserved"]}, "source": P("Table II, journal p.395", ""), "limits": ["wing loading excludes the ventral body area not continuous between the fins (text p.395)"]})
    for r in t3:
        knobs.append({"id": f"f90-t3-aspect-ratio-vs-mass-{r['genus'].lower()}", "kind": "published_fit_only", "variable": "aspect ratio (wing span squared over wing area)", "independent_variable": "body mass M", "unit": "dimensionless", "observations": None, "raw_data_unavailable": "per-specimen values not published",
                      "observed_range": {"aspect_ratio": r["aspect_ratio_range"], "kind": "min-max of the specimens, as printed"}, "fit": {"form": "AR = a * M^b (M in kg)", "method": "reduced major axis", "N": r["N"], "r": r["r"], "r_significant": r["r_significant"], "a": r["a"], "b": r["b"], "b_ci95": r["b_ci95"]},
                      "fit_quality": "usable" if r["r_significant"] else "weak: the paper marks r as not significant and computes no CI for b", "residuals": None, "validity_domain": {"aspect_ratio": r["aspect_ratio_range"], "mass_kg": F.SPECIMENS["mass_range_kg"]},
                      "taxon_context": {"genus": r["genus"], "family": "Exocoetidae"}, "source": P("Table III, journal p.396", ""), "limits": ["for genera with a non-significant r the printed b is not a usable scaling exponent"]})
    for g, (m, se) in F.PECTORAL_SHARE_PCT.items():
        knobs.append({"id": f"f90-text-pectoral-share-{g.lower()}", "kind": "published_summary_only", "variable": "share of wing area contributed by the pectoral fins", "unit": "percent", "observations": None, "raw_data_unavailable": "per-specimen values not published",
                      "fit": {"form": "mean +/- S.E. (arcsine-transformed ANOVA in the paper)", "mean": m, "se": se}, "residuals": None, "validity_domain": {"note": "genus mean over the specimens measured"}, "taxon_context": {"genus": g, "family": "Exocoetidae"},
                      "source": {"id": "fish1990", "locator": "text, journal pp.396-397 (Table IV not read)", "sha256": f90["sha256"]}, "limits": ["from the running text; Table IV was not read"]})
    knobs.append({"id": "f90-text-hypocaudal-share-pooled", "kind": "published_summary_only", "variable": "share of caudal fin area in the hypocaudal lobe", "unit": "percent", "observations": None, "raw_data_unavailable": "per-specimen values not published",
                  "fit": {"form": "mean +/- S.E., pooled over genera (no significant difference among genera)", "mean": F.HYPOCAUDAL_SHARE_POOLED_PCT[0], "se": F.HYPOCAUDAL_SHARE_POOLED_PCT[1]}, "residuals": None, "validity_domain": {"note": "pooled over the six genera"}, "taxon_context": {"family": "Exocoetidae"},
                  "source": {"id": "fish1990", "locator": "text, journal p.397", "sha256": f90["sha256"]}, "limits": []})
    doc = {"schema": "fish-controls-knobs-0.1 (connector-local; no root schema changed)", "status": "measured and published numbers only; nothing generated or imputed", "kinds": {"observed_and_fitted_here": "specimen observations in the repo plus a fit made here", "published_fit_only": "a fit printed in the paper; raw data unavailable", "published_summary_only": "a mean or range printed in the paper; raw data unavailable"},
           "no_cross_source_conversion": "S1A is length vs standard length; Fish 1990 is size vs body mass. No conversion between them is made.", "inconsistencies_in_fish1990": F.INCONSISTENCIES, "knobs": knobs}
    (OUT / "knobs.json").write_text(json.dumps(doc, indent=1, sort_keys=True))
    return len(knobs)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    xb, xr = S.fetch(XLSX_URL, 5_000_000)
    fb, fr = S.fetch(FISH_URL, 10_000_000)
    cb, cr = S.fetch(CROSSREF, 2_000_000)
    if xr.sha256 != XLSX_SHA or fr.sha256 != FISH_SHA:
        raise SystemExit(f"a source changed: xlsx {xr.sha256} fish {fr.sha256}")
    lic = [{"url": l.get("URL"), "content_version": l.get("content-version"), "start": (l.get("start") or {}).get("date-time")} for l in json.loads(cb)["message"].get("license", [])]
    spec = read_s1a(xb)
    # observations (specimen-level, as found; NA cells stay empty)
    cols = ["fish_no", "species", "group", "mcz_catalog_no", "sl_cm", "pectoral_cm", "pelvic_cm", "sheet_pectoral_over_sl", "sheet_pelvic_over_sl", "recomputed_pectoral_over_sl", "recomputed_pelvic_over_sl"]
    mism = []
    with open(OUT / "daane2021_s1a_observations.csv", "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(cols)
        for r in spec:
            rp = r["pectoral_cm"] / r["sl_cm"] if r["pectoral_cm"] is not None and r["sl_cm"] else None
            rv = r["pelvic_cm"] / r["sl_cm"] if r["pelvic_cm"] is not None and r["sl_cm"] else None
            for name, sheet, rec in (("pectoral/SL", r["sheet_pectoral_over_sl"], rp), ("pelvic/SL", r["sheet_pelvic_over_sl"], rv)):
                if sheet is not None and rec is not None and abs(sheet - rec) > 1e-6 * max(1, abs(rec)):
                    mism.append({"fish_no": r["fish_no"], "species": r["species"], "column": name, "sheet_value": sheet, "recomputed": rec})
            w.writerow([r["fish_no"], r["species"], r["group"], r["mcz_catalog_no"]] + ["" if v is None else repr(v) for v in (r["sl_cm"], r["pectoral_cm"], r["pelvic_cm"], r["sheet_pectoral_over_sl"], r["sheet_pelvic_over_sl"], rp, rv)])
    # fits and residuals
    fits, resid_rows = {}, []
    for g in GROUPS:
        for var, key in (("pectoral", "pectoral_cm"), ("pelvic", "pelvic_cm")):
            pts = [(r["fish_no"], r["sl_cm"], r[key]) for r in spec if r["group"] == g and r["sl_cm"] and r[key]]
            x, y = np.array([p[1] for p in pts]), np.array([p[2] for p in pts])
            st, fv, res = fit(x, y)
            ratios = y / x
            st.update({"sl_cm_range": [float(x.min()), float(x.max())], "y_cm_range": [float(y.min()), float(y.max())], "ratio_to_sl": {"median": float(np.median(ratios)), "min": float(ratios.min()), "max": float(ratios.max()), "n": len(ratios)},
                       "n_missing_in_group": sum(1 for r in spec if r["group"] == g and r[key] is None)})
            fits[f"{g}|{var}"] = st
            for (fn, sl, obs), f_, e in zip(pts, fv, res):
                resid_rows.append([fn, g, var, sl, obs, float(10 ** f_), float(e)])
    with open(OUT / "daane2021_s1a_residuals.csv", "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["fish_no", "group", "variable", "sl_cm", "observed_cm", "fitted_cm", "residual_log10"])
        w.writerows([[a, b, c, repr(d), repr(e), repr(f_), repr(g_)] for a, b, c, d, e, f_, g_ in resid_rows])
    species_by_group = {g: sorted({r["species"] for r in spec if r["group"] == g}) for g in GROUPS}
    (OUT / "daane2021_s1a_fits.json").write_text(json.dumps({"schema": "fish-controls-fits-0.1", "source_sheet": "Data S1A, sheet 'A - fin measurement'", "n_specimens": len(spec), "groups": species_by_group, "sheet_ratio_mismatches": mism, "fits": fits}, indent=1, sort_keys=True))
    # Fish 1990 published statistics, as data
    t1 = [{"genus": g, "dimension": d, "unit_inferred": F.UNIT_INFERRED[d], "N": v[0], "r": v[1], "a_printed": v[2], "a": float(v[2] if "." in v[2] else "0." + v[2][1:]), "b": v[3], "b_ci95": [v[4], v[5]], "predicted_b": F.PREDICTED[d], "P_printed": v[6]}
          for g, dims in F.TABLE_I.items() for d, v in dims.items()]
    t2 = [{"genus": g, "N": v[0], "wing_loading_range_N_per_m2": [v[1], v[2]], "r": v[3], "a": v[4], "b": v[5], "b_ci95": [v[6], v[7]], "predicted_b": 0.33, "P_printed": v[8]} for g, v in F.TABLE_II.items()]
    t3 = [{"genus": g, "N": v[0], "aspect_ratio_range": [v[1], v[2]], "r": v[3], "r_significant": v[4], "a": v[5], "b": v[6], "b_ci95": [v[7], v[8]] if v[7] is not None else None} for g, v in F.TABLE_III.items()]
    (OUT / "fish1990_tables.json").write_text(json.dumps({"schema": "fish-controls-fish1990-0.1", "read_from": "page images of the scanned PDF (PDF pp.4-7 = journal pp.394-397), not OCR text", "raw_data": "UNAVAILABLE: 199 specimens were measured; the paper publishes only the fits and ranges below",
                                                          "specimens": F.SPECIMENS, "form": "y = a * M^b, reduced major axis, M in kg", "table_I": t1, "table_II": t2, "table_III": t3,
                                                          "pectoral_share_of_wing_area_pct_mean_se_from_text": {g: list(v) for g, v in F.PECTORAL_SHARE_PCT.items()}, "hypocaudal_share_pooled_pct_mean_se": list(F.HYPOCAUDAL_SHARE_POOLED_PCT),
                                                          "table_IV_read": False, "inconsistencies_in_the_paper": F.INCONSISTENCIES}, indent=1, sort_keys=True))
    src = {"schema": "fish-controls-sources-0.1", "retrieved_utc": xr.retrieved_at, "sources": [
        {"id": "daane2021-data-s1", "citation": "Daane JM, Blum N, Lanni J, Boldt H, Iovine MK, Higdon CW, Johnson SL, Lovejoy NR, Harris MP. Modulation of bioelectric cues in the evolution of flying fishes. Curr Biol 31:5052-5061.e8 (2021). doi:10.1016/j.cub.2021.08.054",
         "locator": "Data S1 workbook (mmc2.xlsx), sheet 'A - fin measurement' (Data S1A); article Figure 1B", "url": XLSX_URL, "sha256": xr.sha256, "bytes": xr.bytes, "stored_in_repo": False, "sheets": ["A - fin measurement", "B - sample info", "C - cov. GO enrich.", "D - heterozygosity", "E - CNV", "F - gliders RER enrich.", "G - conv. aa subst.", "H - fin and limb genes", "I - Glider RER genes", "J - Exocoeidae phylop", "K - accel CNEs Exocoet.", "L - con CNEs Exocoet.", "M - accel CNEs halfbeak", "N - con CNEs halfbeak"],
         "license": {"supplement": "no licence stated in the workbook", "article_record": "Crossref lists the Elsevier open-access user licence (http://www.elsevier.com/open-access/userlicense/1.0/) for the version of record from 2022-11-22 and TDM licences from 2021-11-01; the terms were NOT read", "crossref_entries": lic},
         "redistribution": "the workbook is not stored; the per-specimen numbers (specimen measurements with MCZ catalog numbers) are kept in daane2021_s1a_observations.csv with attribution. Whether that is permitted under the Elsevier terms is unresolved: root decides", "read_level": "full workbook parsed (sheet A in full; other sheets listed)"},
        {"id": "fish1990", "citation": "Fish FE. Wing design and scaling of flying fish with regard to flight performance. J Zool 221:391-403 (1990)", "locator": "Tables I-III (journal pp.394-396), text pp.396-397; read from page images", "url": FISH_URL, "sha256": fr.sha256, "bytes": fr.bytes, "pages": 13, "stored_in_repo": False,
         "license": {"stated": None, "note": "author-hosted PDF of a 1990 journal article; no licence stated; the PDF is not stored; the published numbers are kept with locators"}, "read_level": "full text; tables read from page images; Table IV not read"}]}
    (OUT / "sources.json").write_text(json.dumps(src, indent=1, sort_keys=True))
    fits_species.update(species_by_group)
    nk = write_knobs(spec, fits, t1, t2, t3, src)
    files = sorted(f for f in OUT.iterdir() if f.is_file() and f.name != "manifest.json")
    (OUT / "manifest.json").write_text(json.dumps({"manifest_schema": "fish-controls-manifest-0.1 (connector-local)", "status": "proposed; single operator; unreviewed", "not_stored": ["Data S1 workbook (mmc2.xlsx)", "Fish 1990 PDF"],
                                                   "files": [{"path": f"data/fish-controls/{f.name}", "sha256": hashlib.sha256(f.read_bytes()).hexdigest(), "bytes": f.stat().st_size} for f in files]}, indent=1, sort_keys=True))
    print(nk, "knobs;", len(spec), "specimens;", len(fits), "fits;", len(mism), "sheet-ratio mismatches;", len(t1) + len(t2) + len(t3), "published rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
