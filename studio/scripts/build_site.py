"""Build the Delphi Frontier site snapshot from tracked repository files.

Inputs are read only from this checkout (seeds/, results/, specs/, tasks/, docs/, site/content/);
nothing is read from /home, /data or the network. Every input is recorded with its sha256 so a reader
can check the snapshot against the bytes it was made from. A statistic with no receipt is not emitted:
there is deliberately no test count, no job count and no "records in a store" figure, because none of
those is derivable from a file here.

    python3 scripts/build_site.py            # writes site/data/{snapshot,catalog}.json and site/data/docs/
    python3 scripts/build_site.py --check    # exit 1 if the committed output differs from a fresh build
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
DATA = SITE / "data"
SCHEMA = "frontier-site-snapshot-0.1"
NAMESPACE = "snapshot"



def mcp_tools(mcp_text: str) -> list[dict]:
    """Read named tools from the documentation's capability tables."""
    row = next((l for l in mcp_text.splitlines() if l.startswith("| Tools |")), "")
    cells = [c.strip() for c in row.strip().strip("|").split("|")]
    names = lambda c: re.findall(r"`(frontier_[a-z_]+)`", c)
    read = names(cells[1]) if len(cells) > 2 else []
    write = [n for n in names(cells[2]) if n not in read] if len(cells) > 2 else []
    section = ""
    for line in mcp_text.splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
        if section == "Expanded read and calculation tools":
            match = re.match(r"\| `(frontier_[a-z_]+)` \|", line)
            if match and match[1] not in read:
                read.append(match[1])
    return [{"name": n, "mode": "read", "documented_in_docs_mcp": True} for n in read] + [{"name": n, "mode": "write (opt-in)", "documented_in_docs_mcp": True} for n in write]


def digest_bytes(b: bytes) -> str:
    return sha256(b).hexdigest()


def canonical(v) -> str:
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class Inputs:
    """Reads files relative to ROOT and remembers each one's hash."""

    def __init__(self):
        self.seen: dict[str, dict] = {}

    def read(self, rel: str) -> bytes:
        b = (ROOT / rel).read_bytes()
        self.seen[rel] = {"path": rel, "sha256": digest_bytes(b), "bytes": len(b)}
        return b

    def text(self, rel: str) -> str:
        return self.read(rel).decode("utf-8")

    def json(self, rel: str):
        return json.loads(self.read(rel))


def doc_meta(rel: str, text: str) -> dict:
    title = next((l[2:].strip() for l in text.splitlines() if l.startswith("# ")), Path(rel).stem)
    status = None
    m = re.search(r"\*\*(?:Final status|Verdict):[^\n]*", text)
    if m:
        status = re.sub(r"\*\*", "", m.group(0)).strip()
    return {"id": Path(rel).stem, "title": title, "status_line": status, "path": rel}


def parse_board(text: str) -> list[dict]:
    """The owner table in tasks/BUILD.md. It is a plan as written at the snapshot, not live activity."""
    rows = []
    for line in text.splitlines():
        if not line.startswith("| P"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 4:
            rows.append({"priority": cells[0], "deliverable": cells[1], "owner": cells[2], "status_text": cells[3]})
    return rows


def build_catalog(snapshot: dict) -> list[dict]:
    """Envelope-shaped records for the snapshot adapter. Local status is always separate from any upstream label."""
    records = []

    def add(kind, rid, title, payload, upstream=None):
        body = {"kind": kind, "id": rid, "title": title, "payload": payload}
        version = digest_bytes(canonical(body).encode())
        records.append({
            "ref": {"namespace": NAMESPACE, "kind": kind, "id": rid, "version": version},
            "title": title,
            "payload": payload,
            "upstream_label": upstream,
            "local_status": "snapshot_unreviewed",
        })

    for c in snapshot["claims"]:
        add("Claim", c["id"], c["label"], c, {"category": c["category"], "review_title": c["review_title"], "note": "Upstream assertion from the seed, not accepted by this site."})
    for p in snapshot["problems"]:
        add("Problem", p["id"], p["title"], p, {"state": p["state"]})
    for s in snapshot["mission"]["sources"]:
        add("Evidence", "src-" + s["id"], s["cite"], s, {"read_level": s["read_level"]})
    for d in snapshot["documents"]:
        add("Evidence", "doc-" + d["id"], d["title"], d, {"status_line": d["status_line"]})
    records.sort(key=lambda r: (r["ref"]["kind"], r["ref"]["id"]))
    return records


SIM_DIR = "engineering/simulation/results"
SIM_FILES = ("summary.json", "controls.json", "pareto.json", "model_structure_findings.json", "designs.csv", "figure.png")
LEAN_RECEIPT = "engineering/formal/RECEIPT.json"


def recorded_results(ins: Inputs, files: dict) -> tuple[dict | None, dict | None]:
    """Recorded runs that exist in this tree. A missing file is reported as absent, never filled in."""
    lean = sim = None
    if (ROOT / LEAN_RECEIPT).exists():
        lc = json.loads(ins.read(LEAN_RECEIPT))["lean_checks"]
        lean = {"path": LEAN_RECEIPT, "sha256": ins.seen[LEAN_RECEIPT]["sha256"], "run": lc.get("lean"), "lean_version": lc.get("lean_version"),
                "mathlib_rev": lc["provenance"].get("mathlib_rev"), "toolchain": lc["provenance"].get("lean_toolchain_file"),
                "theory_sha256": lc.get("theory_sha256"), "all_ok": lc.get("all_ok"),
                "positive": {k: lc["positive"].get(k) for k in ("exit", "seconds", "axioms_used", "only_standard_axioms")},
                "negative": {"exit": lc["negative"].get("exit"), "seconds": lc["negative"].get("seconds"), "each_block_rejected": lc["negative"].get("each_block_rejected"),
                             "first_error_message": lc["negative"].get("first_error_message")},
                "file_hashes": lc["provenance"].get("files")}
    if (ROOT / SIM_DIR / "summary.json").exists():
        listing = []
        for name in SIM_FILES:
            if (ROOT / SIM_DIR / name).exists():
                b = ins.read(f"{SIM_DIR}/{name}")
                csv = name.endswith(".csv")                      # the runtime serves .csv only under site/artifacts/
                out_files_key = f"@artifacts/results/{name}" if csv else f"results/{name}"
                files[out_files_key] = b
                listing.append({"name": name, "path": f"{SIM_DIR}/{name}", "sha256": digest_bytes(b), "bytes": len(b), "href": (f"artifacts/results/{name}" if csv else f"data/results/{name}")})
        load = lambda n: json.loads((ROOT / SIM_DIR / n).read_text()) if (ROOT / SIM_DIR / n).exists() else None
        summ, ctrl, find = load("summary.json"), load("controls.json"), load("model_structure_findings.json")
        sim = {"summary": {k: v for k, v in summ.items() if k != "pareto_designs_selected_dimensions"}, "pareto_selected": summ.get("pareto_designs_selected_dimensions", []),
               "controls": ctrl, "findings": find, "files": listing}
    return lean, sim


ATT = "findings/attestation-check-15.json"
ATT_REVIEW = "findings/attestation-facet-review-15.json"
ATT_README = "findings/README-attestation-check-15.md"
SIM_MANIFESTS = "site/artifacts/simulations"


def attestation_check(ins: Inputs, files: dict, docs: list) -> dict | None:
    if not all((ROOT / f).exists() for f in (ATT, ATT_REVIEW, ATT_README)):
        return None
    mech, rev = json.loads(ins.read(ATT)), json.loads(ins.read(ATT_REVIEW))
    text = ins.text(ATT_README)
    files["docs/" + Path(ATT_README).name + ".txt"] = text.encode()
    docs.append({"id": Path(ATT_README).stem, "title": next(l[2:].strip() for l in text.splitlines() if l.startswith("# ")), "status_line": None, "path": ATT_README,
                 "sha256": ins.seen[ATT_README]["sha256"], "href": "data/docs/" + Path(ATT_README).name + ".txt"})
    by = {r["slug"] + str(r["index"]): r for r in mech["results"]}
    items = []
    for it in rev["items"]:
        m = by.get(it["slug"] + str(it["index"]), {})
        items.append({"slug": it["slug"], "stance": it["stance"], "stratum": it["stratum"], "source": m.get("source"), "article_title": m.get("article_title"), "article_year": m.get("article_year"),
                      "locator": m.get("locator"), "mechanical_status": m.get("status"), "match": m.get("match"), "supports": it["quote_supports_stance"], "fit": it["fit_to_question"],
                      "flags": it["flags"], "note": it["note"]})
    return {"readme": Path(ATT_README).stem, "n": mech["n"], "status_counts": mech["status_counts"], "tally": rev.get("tally"), "reviewer": rev.get("reviewer"), "items": items,
            "scope": "A fixed 15-item sample chosen by a hashed rule, not a random or representative sample. The counts are not a population rate and verify nothing about the other attestations or the 250 problems."}


def simulation_manifests(ins: Inputs) -> list[dict]:
    """Optional manifests dropped next to their artifacts. A video is playable only if the file exists and matches its declared sha256."""
    out = []
    base = ROOT / SIM_MANIFESTS
    for mf in sorted(base.glob("*/manifest.json")) if base.exists() else []:
        rel = mf.relative_to(ROOT).as_posix()
        try:
            m = json.loads(ins.read(rel))
        except ValueError:
            out.append({"id": mf.parent.name, "title": mf.parent.name, "error": "manifest is not valid JSON", "manifest": rel})
            continue
        v = m.get("video"); state, href = "none", None
        if v:
            f = mf.parent / str(v.get("file", ""))
            if not f.is_file() or ".." in str(v.get("file", "")):
                state = "declared_but_missing"
            else:
                b = f.read_bytes(); ins.seen[f.relative_to(ROOT).as_posix()] = {"path": f.relative_to(ROOT).as_posix(), "sha256": digest_bytes(b), "bytes": len(b)}
                state = "present_verified" if v.get("sha256") == digest_bytes(b) else "digest_mismatch"
                href = f.relative_to(ROOT / "site").as_posix() if state == "present_verified" else None
        pf = mf.parent / str(m.get("poster", "")) if m.get("poster") else None
        m["poster_href"] = pf.relative_to(ROOT / "site").as_posix() if pf and pf.is_file() and ".." not in str(m["poster"]) else None
        m.setdefault("id", mf.parent.name); m["video_state"], m["video_href"], m["manifest"] = state, href, rel
        out.append(m)
    return out


PRINT_DIR = "artifacts/print"
PRINT_OUT = "@artifacts/print"          # site-relative output root (the runtime serves .stl only under site/artifacts/)


def print_media(ins: Inputs, out: dict, fid: str) -> dict | None:
    """Turntable render of a form (optional): files are offered only when their bytes equal the render manifest's declared hashes."""
    rj = ROOT / PRINT_DIR / "media" / fid / "render.json"
    if not rj.exists():
        return None
    r = json.loads(ins.read(f"{PRINT_DIR}/media/{fid}/render.json")); res = {"evidence_kind": r.get("evidence_kind"), "caveats": r.get("caveats"), "checks": r.get("checks"), "render_sha256": ins.seen[f"{PRINT_DIR}/media/{fid}/render.json"]["sha256"], "video_href": None, "gif_href": None, "poster_href": None, "state": {}}
    for key, fname, declared in (("video", r["video"]["file"], r["video"].get("sha256")), ("gif", (r.get("gif") or {}).get("file"), (r.get("gif") or {}).get("sha256")), ("poster", r.get("poster"), r.get("poster_sha256"))):
        if not fname:
            res["state"][key] = "not declared"; continue
        f = ROOT / PRINT_DIR / "media" / fid / fname
        if not f.is_file():
            res["state"][key] = "declared_but_missing"; continue
        b = ins.read(f"{PRINT_DIR}/media/{fid}/{fname}")
        if declared and digest_bytes(b) != declared:
            res["state"][key] = "digest_mismatch"; continue
        out[f"{PRINT_OUT}/media/{fid}/{fname}"] = b; res[key + "_href"] = f"artifacts/print/media/{fid}/{fname}"; res["state"][key] = "present_verified"
    res["video"] = {k: r["video"].get(k) for k in ("duration_s", "fps", "n_frames", "loop", "width", "height")}
    return res


def print_forms(ins: Inputs, out: dict) -> dict | None:
    """Printable form studies, when present: the manifest's own words and receipts, plus the real STL and image files."""
    mf = ROOT / PRINT_DIR / "manifest.json"
    if not mf.exists():
        return None
    man = json.loads(ins.read(f"{PRINT_DIR}/manifest.json"))
    forms = []
    def copy(rel):
        b = ins.read(f"{PRINT_DIR}/{rel}"); out[f"{PRINT_OUT}/{rel}"] = b
        return {"href": f"artifacts/print/{rel}", "sha256": digest_bytes(b), "bytes": len(b), "declared_sha256": man["files"].get(rel)}
    for fid, f in man["forms"].items():
        d = json.loads(ins.read(f"{PRINT_DIR}/{f['design']}"))
        es = d.get("engineering_status") or {}
        entry = {"id": fid, "title": d.get("title"), "role": d.get("role"), "status_note": d.get("status_note"), "bounds_mm": f.get("bounds_mm"), "volume_mm3": f.get("volume_mm3"),
                 "valid": f.get("valid"), "converged": f.get("converged"), "stand_valid": f.get("stand_valid"), "solver": f.get("solver"), "glide": f.get("glide"),
                 "meaning": es.get("meaning"), "may_not_say": es.get("may_not_say"), "solver_conflict": es.get("solver_conflict"), "not_checked": d.get("not_checked"),
                 "validation": {k: (d.get("validation") or {}).get(k) for k in ("closed_two_manifold", "consistently_oriented", "degenerate_triangles", "euler_characteristic", "face_connected_components", "fits_box", "fits_box_mm", "edges_not_shared_by_exactly_two_faces")},
                 "roundtrip": {k: (d.get("stl_roundtrip") or {}).get(k) for k in ("ok", "triangles", "signed_volume_mm3")}, "convergence": {k: (d.get("convergence") or {}).get(k) for k in ("converged", "default_vs_fine_rel_extent", "default_vs_fine_rel_volume")},
                 "design_sha256": man["files"].get(f["design"]), "files": {}}
        for key, rel in (("stl", f"stl/{fid}.stl"), ("stand_stl", f"stl/{fid}-stand.stl"), ("image", f"img/{fid}.png"), ("image_on_stand", f"img/{fid}-on-stand.png")):
            if (ROOT / PRINT_DIR / rel).exists():
                entry["files"][key] = copy(rel)
        entry["files"]["design"] = {"sha256": entry["design_sha256"]}
        entry["display_scale"] = f.get("display_scale"); entry["set"] = f.get("set"); entry["simulation_comparison"] = f.get("simulation_comparison")
        entry["media"] = print_media(ins, out, fid)
        forms.append(entry)
    sets = {k: {"display_scale": v.get("display_scale"), "forms": v.get("forms", [])} for k, v in (man.get("sets") or {}).items()}
    return {"label": man.get("label"), "sets": sets, "display_scale_note": man.get("display_scale_note"), "printer_resin": man.get("printer_resin"), "run": {k: man["run"].get(k) for k in ("box_mm", "launch_speed_query_m_s", "libraries")} | {"solver_commit": (man["run"].get("solver") or {}).get("commit"), "solver_branch": (man["run"].get("solver") or {}).get("branch")}, "forms": forms}


SIM_OUT = "@artifacts/simulations"
CTRL_DIR = "engineering/simulation/results_controlled"


def controlled_results(ins: Inputs, out: dict) -> dict | None:
    """The corrected common-launch comparison, when present; it supersedes the exploratory Pareto set as the thing to read."""
    if not (ROOT / CTRL_DIR / "summary.json").exists():
        return None
    s = json.loads(ins.read(f"{CTRL_DIR}/summary.json"))
    w = json.loads(ins.read(f"{CTRL_DIR}/witness_check.json")) if (ROOT / CTRL_DIR / "witness_check.json").exists() else None
    designs = s.get("designs", [])
    files = []
    for name in ("summary.json", "comparison.csv", "witness_check.json"):
        if (ROOT / CTRL_DIR / name).exists():
            b = ins.read(f"{CTRL_DIR}/{name}"); csv = name.endswith(".csv"); out[f"@artifacts/results/controlled_{name}" if csv else f"docs/controlled_{name}"] = b
            files.append({"name": name, "path": f"{CTRL_DIR}/{name}", "sha256": digest_bytes(b), "bytes": len(b), "href": (f"artifacts/results/controlled_{name}" if csv else f"data/docs/controlled_{name}")})
    return {"model_version": s.get("model_version"), "evidence_kind": s.get("evidence_kind"), "protocol": s.get("protocol"), "n_rows": s.get("n_rows"), "n_unconverged": s.get("n_unconverged"),
            "baselines": s.get("baselines", []), "baselines_excluded": s.get("baselines_excluded_wl_outside_genus_range", []),
            "n_baseline_infeasible_scenarios": len(s.get("baseline_infeasible_scenarios", [])), "n_designs": len(designs),
            "n_robust_win": sum(1 for d in designs if d.get("robust_win")), "n_flips": sum(1 for d in designs if d.get("flips")),
            "witness": ({"solver_status": w.get("solver_status"), "witness": w.get("witness"), "wing_loading": w.get("witness_wing_loading_N_m2"), "query": w.get("query"),
                         "verified": (w.get("independent_verify_certificate") or {}).get("ok"), "not_established": (w.get("receipt") or {}).get("not_established")} if w else None), "files": files}


def _vid(ins, out, vid, src_dir, fname, declared, bytes_declared=None):
    """Copy a declared video/poster into the site and compare its bytes with the declared sha256."""
    f = ROOT / src_dir / fname
    if not f.is_file():
        return "declared_but_missing", None
    b = ins.read(f"{src_dir}/{fname}"); h = digest_bytes(b)
    if declared and declared != h:
        return "digest_mismatch", None
    out[f"{SIM_OUT}/{vid}/{fname}"] = b
    return "present_verified", f"artifacts/simulations/{vid}/{fname}"


def home_biology(ins: Inputs) -> dict | None:
    """Sourced anatomy and parameter provenance for the Home page: per-component parameter statuses from the fish3d candidate, the
    fitted relations with their context, and the evidence categories kept separate. Nothing is combined into one count of laws."""
    f3 = "artifacts/fish3d/fish3d-N1-cypselurus-baseline"; fc = "data/fish-controls"
    if not ((ROOT / f3 / "components.json").exists() and (ROOT / fc / "knobs.json").exists()):
        return None
    comps = json.loads(ins.read(f"{f3}/components.json"))["components"]; cand = json.loads(ins.read(f"{f3}/candidate.json")); K = json.loads(ins.read(f"{fc}/knobs.json")); SRC = json.loads(ins.read(f"{fc}/sources.json"))["sources"]; F90 = json.loads(ins.read(f"{fc}/fish1990_tables.json"))
    group = lambda n: n.split("_")[0]
    regions = {}
    for n, v in comps.items():
        r = regions.setdefault(group(n), {"id": group(n), "params": {}, "notes": []})
        for k, pv in v.get("params", {}).items():
            if isinstance(pv, dict) and "status" in pv:
                r["params"].setdefault(k, pv["status"])
                if pv.get("note") and pv["note"] not in r["notes"]:
                    r["notes"].append(pv["note"])
    for n, v in comps.items():
        for k, pv in v.get("params", {}).items():
            if k == "note" and isinstance(pv, str) and pv not in regions[group(n)]["notes"]:
                regions[group(n)]["notes"].append(pv)
    fitted = [{"id": x["id"], "variable": x["variable"], "group": x["taxon_context"]["group"], "species": x["taxon_context"]["species"], "material": x["taxon_context"]["material"], "n": x["fit"]["n"], "r2": x["fit"]["r2"], "b": x["fit"]["b"], "b_ci95": x["fit"]["bootstrap"]["b_ci95"], "quality": x["fit_quality"], "unit": x["unit"], "limits": x["limits"][:2]}
              for x in K["knobs"] if x["kind"] == "observed_and_fitted_here"]
    counts = {k: sum(1 for x in K["knobs"] if x["kind"] == k) for k in K["kinds"]}
    bio = cand["biology"]
    return {"candidate": {"label": cand["label"], "id": cand["id"], "mass_kg": cand["mass_kg"], "standard_length_mm": bio["standard_length_m"]["value"] * 1000, "wing_span_mm": bio["wing_span_m"]["value"] * 1000, "wing_area_mm2": bio["wing_area_m2"]["value"] * 1e6, "fin_thickness": cand["fidelity"]["fin_thickness_mm"]},
        "regions": sorted(regions.values(), key=lambda r: r["id"]), "fitted": fitted, "evidence_counts": counts, "kinds": K["kinds"], "no_cross_source_conversion": K["no_cross_source_conversion"], "knobs_status": K["status"],
        "fish1990": {"specimens": F90["specimens"], "raw_data": F90["raw_data"], "pectoral_share_pct_mean_se": F90["pectoral_share_of_wing_area_pct_mean_se_from_text"], "hypocaudal_share_pct_mean_se": F90["hypocaudal_share_pooled_pct_mean_se"], "inconsistencies": F90["inconsistencies_in_the_paper"]},
        "sources": [{"id": x["id"], "citation": x["citation"], "read_level": x.get("read_level"), "licence": (x["license"].get("note") or x["license"].get("article_record") or "not stated") if isinstance(x.get("license"), dict) else str(x.get("license"))} for x in SRC],
        "manifest": f"{fc}/manifest.json"}


def lifecycle_block(ins: Inputs) -> dict | None:
    """Zebrafish life-cycle source layer (data/fish-lifecycle) projected for the Studio developmental panel. Statuses and quotes are copied, not summarised."""
    d = "data/fish-lifecycle"
    if not (ROOT / d / "assurance.json").exists():
        return None
    A = json.loads(ins.read(f"{d}/assurance.json")); S = json.loads(ins.read(f"{d}/stages.json")); E = json.loads(ins.read(f"{d}/equations.json")); N = json.loads(ins.read(f"{d}/nutrient_diffusion_check.json"))
    M = json.loads(ins.read(f"{d}/manifest.json"))
    st = lambda v: v.get("status") if isinstance(v, dict) else v
    return {"organism": A["organism"], "status": M["status"], "stage_order": A["stages"], "statuses": A["statuses"], "claims_not_made": A["claims_not_made"], "gaps_first": A["gaps_first"], "temperature_c": S["temperature_reference_c"], "stage_note": S["note"],
        "stages": [{"id": x["id"], "name": x["name"], "time": x.get("time"), "definition": (x.get("definition") or {}).get("quote"), "axes": {k: st(x.get(k)) for k in ("size", "growth", "metabolism", "locomotion", "fins_and_scales")}} for x in S["stages"]],
        "processes": {k: {sg: {"status": v[sg]["status"], "note": v[sg].get("note", ""), "sources": v[sg].get("sources", "")} for sg in A["stages"] if sg in v} for k, v in A["processes"].items()},
        "equations": [{"id": q["id"], "name": q["name"], "form": q["form"], "context": q.get("context", ""), "not_established_here": q.get("not_established_here", ""), "claimed_by_source": q.get("claimed_by_source", "")} for q in E["equations"]],
        "diffusion": {"status": N["status"], "derived": N["derived"], "inputs": N["inputs"], "assumptions": N["geometry_assumptions"], "not_known": N["not_known"], "reading": N["comparison_with_fish_body_height"]["reading"], "rows": N["comparison_with_fish_body_height"]["rows"]},
        "manifest": f"{d}/manifest.json", "doc": "docs/fish-lifecycle.md"}


def engineering_cards(ins: Inputs, out: dict) -> list[dict]:
    """Wind-tunnel, behavior controller and scale-growth manifests as gallery cards, with equations, sources and limitations.
    Every number is copied from the worker's own receipt; verdicts and misses are carried, never softened."""
    cards = []
    d = "artifacts/windtunnel"
    if (ROOT / d / "render-manifest.json").exists() and (ROOT / d / "summary.json").exists():
        rm = json.loads(ins.read(f"{d}/render-manifest.json")); sm = json.loads(ins.read(f"{d}/summary.json")); o = rm["outputs"]
        st, href = _vid(ins, out, "windtunnel-2d", d, "windtunnel.mp4", o["windtunnel.mp4"]["sha256"]); _, ph = _vid(ins, out, "windtunnel-2d", d, "poster.png", o["poster.png"]["sha256"])
        cs = sm["cases"]
        cards.append({"id": "windtunnel-2d", "title": "2D low-Reynolds flow past the N1 silhouette (lattice-Boltzmann), verdict " + sm["label"], "scales": ["organism", "organ"], "evidence_kind": sm["evidence_kind"] + " (video: " + rm["evidence_kind"] + ")",
            "model": {"name": "D2Q9 BGK lattice-Boltzmann, Guo forcing, bounce-back on a staircase mask of the N1 print silhouette", "context": sm["scope"] + ". Status is PARTIAL: no grid-refinement verdict and not validated flight."},
            "time": {"units": "lattice steps, shown as convective times; see the case request", "note": f"{rm['n_frames']} frames at {rm['fps']} fps from case {rm['case']}"},
            "video": {"file": "windtunnel.mp4", "sha256": o["windtunnel.mp4"]["sha256"], "note": f"{o['windtunnel.mp4']['byte_size']} bytes"}, "video_state": st, "video_href": href, "poster_href": ph,
            "numerical_checks": [{"name": k.replace("_", " "), "result": "not computed (null)" if v is None else ("passed" if v else "FAILED")} for k, v in sm["checks"].items()]
                + [{"name": f"case {k}", "result": f"{c['status']}; Re {c['Re']:.0f}; mean Cd {c['mean_Cd_last20pct']:.3f}, Cl {c['mean_Cl_last20pct']:.3f} (last 20%)" + (f"; {c['failure']}" if c.get("failure") else "")} for k, c in cs.items()]
                + [{"name": "time refinement", "result": f"relative drag difference {sm['time_relative_drag_difference']:.4f}"}],
            "parameter_unknowns": ["Re about 80 at 8 mm/s on a 0.15 m body; a flying fish glides at orders of magnitude higher Re.", "Geometry is a print-modified candidate silhouette extruded infinitely in 2D; span is ignored."],
            "open_questions": ["Does the grid-48 case finish within budget to give a grid-refinement verdict?", "What 3D, high-Re, free-surface simulation or measurement would test lift and drag?"] + [x if isinstance(x, str) else json.dumps(x) for x in rm.get("not_established", [])][:6],
            "equations": [{"label": "Lattice-Boltzmann update (BGK)", "tex": "f_i(\\mathbf{x}+\\mathbf{c}_i,t+1)-f_i(\\mathbf{x},t)=-\\tfrac{1}{\\tau}\\left[f_i-f_i^{eq}\\right]+F_i", "source": "engineering/windtunnel/lbm.py"}, {"label": "Viscosity and Reynolds number", "tex": "\\nu=\\tfrac{\\tau-1/2}{3},\\qquad \\mathrm{Re}=\\tfrac{U L}{\\nu}", "source": "engineering/windtunnel/lbm.py"}],
            "sources": [{"label": "Solver, protocol and controls", "locator": f"{d}/protocol sha256 {sm['protocol_sha256'][:12]}…, analytic-controls.json (Poiseuille, Taylor-Green)"}, {"label": "Geometry", "locator": f"{rm['mesh']['path']} sha256 {rm['mesh']['sha256'][:12]}…"}],
            "limitations": [rm["mesh"]["geometry_warning"], sm["scope"], "biological_success_probability: null (not computed)."],
            "couplings": [], "manifest": f"{d}/render-manifest.json", "native": True})
    d = "artifacts/fish3d/fish3d-N1-cypselurus-baseline/render"
    if (ROOT / d / "render.json").exists():
        r = json.loads(ins.read(f"{d}/render.json")); v = r["video"]
        st, href = _vid(ins, out, "fish3d-render", d, "turntable.mp4", v["sha256"]); _, ph = _vid(ins, out, "fish3d-render", d, "poster.png", r["poster_sha256"])
        cards.append({"id": "fish3d-render", "title": "Candidate N1 as a 3D model: path-traced turntable", "scales": ["organism"], "evidence_kind": r["evidence_kind"],
            "model": {"name": r["schema"], "context": " ".join(r["caption"])},
            "time": {"units": "none: a camera orbit around a static model", "note": f"{v['n_frames']} frames at {v['fps']} fps, looping; {v['width']}x{v['height']}"},
            "video": {"file": "turntable.mp4", "sha256": v["sha256"], "note": f"{v['bytes']} bytes"}, "video_state": st, "video_href": href, "poster_href": ph,
            "numerical_checks": [{"name": k.replace("_", " "), "result": "passed" if val else "FAILED"} for k, val in r["checks"].items()],
            "parameter_unknowns": ["Fin thickness, eyes and gill covers are assumed.", "Scales are an assumed lattice (50 along the body), not a grown or measured pattern."],
            "open_questions": ["What measured fin camber, ray structure and thickness would replace the assumed ones?"],
            "limitations": ["Not claimed: " + x for x in r["not_claimed"]] + [f"The mesh itself (fish.glb, sha256 {r['glb_sha256'][:12]}…) is in artifacts/fish3d and is not served by this site."],
            "couplings": [], "manifest": f"{d}/render.json", "native": True})
    d = "artifacts/behavior"
    if (ROOT / d / "manifest.json").exists() and (ROOT / d / "controls.json").exists():
        m = json.loads(ins.read(f"{d}/manifest.json")); ct = json.loads(ins.read(f"{d}/controls.json")); fl = m["files"]
        st, href = _vid(ins, out, "behavior-cpg", d, "behavior.mp4", fl["behavior.mp4"]["sha256"]); _, ph = _vid(ins, out, "behavior-cpg", d, "poster.png", fl["poster.png"]["sha256"])
        probs = json.loads(ins.read(f"{d}/problems.json"))["problems"]
        cards.append({"id": "behavior-cpg", "title": "Rhythm-generator controller driving a designed joint servo (eight segments)", "scales": ["neural", "organ", "organism"], "evidence_kind": m["evidence_kind"],
            "model": {"name": m["schema"] if "schema" in m else "frontier.behavior", "context": "Source-form phase and amplitude oscillators plus a designed joint servo. Eight coarse segments, not somites; independent plant joints; no hydrodynamics. Biological accuracy: " + m["biological_accuracy"] + "."},
            "time": {"units": "seconds (2 s run, 0.2 ms step)", "note": m["control_scope"]},
            "video": {"file": "behavior.mp4", "sha256": fl["behavior.mp4"]["sha256"], "note": f"{fl['behavior.mp4']['byte_size']} bytes"}, "video_state": st, "video_href": href, "poster_href": ph,
            "numerical_checks": [{"name": c["name"].replace("_", " "), "result": "passed" if c["passed"] else "FAILED"} for c in ct["checks"]],
            "parameter_unknowns": ["Joint inertia, damping, stiffness and feedback gains are engineering values, not measured fish values.", "No target-species circuit or kinematic recording constrains frequency, phase lag or amplitude."],
            "open_questions": [f"{p['question']} (blocks: {p['blocks']})" for p in probs],
            "equations": [{"label": "Phase oscillator with phase-biased coupling (source form)", "tex": "\\dot\\theta_i=2\\pi\\nu_i+\\sum_j w_{ij}\\sin(\\theta_j-\\theta_i-\\varphi_{ij})", "source": "Ijspeert et al. 2007, doi 10.1126/science.1138353 (salamander model)"}, {"label": "Amplitude relaxation, closed form checked", "tex": "r(t)=1-\\left(1+\\tfrac{a t}{2}\\right)e^{-a t/2}", "source": "controls.json amplitude_closed_form, max error 4e-11"}],
            "sources": [{"label": "Oscillator form", "locator": "Ijspeert 2007, p1416 equations; salamander and robot, not zebrafish"}, {"label": "Protocol", "locator": f"{d}/protocol.json sha256 {m['protocol_sha256'][:12]}…"}],
            "limitations": [m["control_scope"], "Controls test frozen numerical predicates only; no biological or fluid-force success is tested.", "The wind tunnel is static; the moving-fluid bridge does not exist."],
            "couplings": [], "manifest": f"{d}/manifest.json", "native": True})
    d = "artifacts/scales/erk-wave"
    if (ROOT / d / "receipt.json").exists():
        r = json.loads(ins.read(f"{d}/receipt.json")); fl = r["files"]; gc = r["growth_coupling"]; mc = r["measured_comparison"]; ctl = r["controls"]
        st, href = _vid(ins, out, "scale-erk-wave", d, "erk_growth.mp4", fl["erk_growth.mp4"]["sha256"]); _, ph = _vid(ins, out, "scale-erk-wave", d, "poster.png", fl["poster.png"]["sha256"])
        cards.append({"id": "scale-erk-wave", "title": "Erk trigger waves and wave-gated growth on one regenerating zebrafish scale", "scales": ["tissue", "developmental"], "evidence_kind": r["evidence_kind"],
            "model": {"name": r["model"], "context": "Zebrafish regenerating scale, Hayden 2021 Table 1 parameters (fitted in the source). Transfer to flying-fish scales is unknown."},
            "time": {"units": "hours; 120 h run, 1 h per video frame", "note": "Rendering of model state in reference coordinates, not a microscope image."},
            "video": {"file": "erk_growth.mp4", "sha256": fl["erk_growth.mp4"]["sha256"], "note": f"{fl['erk_growth.mp4']['bytes']} bytes"}, "video_state": st, "video_href": href, "poster_href": ph,
            "numerical_checks": [{"name": "control " + k.replace("_", " "), "result": "not gated; reported" if v.get("pass") is None else ("passed" if v["pass"] else "FAILED")} for k, v in ctl.items()]
                + [{"name": "vs measured: " + k.replace("_", " "), "result": f"simulated {v['simulated']} vs band {v['band'][0]} to {v['band'][1]}: {'in band' if v['in_band'] else 'MISS'} ({v['measured_source']})"} for k, v in mc.items()],
            "parameter_unknowns": [f"Growth coupling is ASSUMED: {gc['assumed']['form']}. Measured is a LINEAR slope {gc['measured']['value_per_h']} per h (68% CI {gc['measured']['ci68_per_h']}, {gc['measured']['n']}).", f"Per 24 h window: exponential {gc['assumed']['per_window_factor_exponential']:.3f} vs linear {gc['assumed']['per_window_factor_if_linear']:.3f}; not tuned."],
            "open_questions": [f"Misses retained: {', '.join(r['measured_comparison_misses'])} (simulated {mc['rise_10_90_h']['simulated']} h vs measured about 3 h).", "Synchronous activation does not reproduce the measured impairment of scale growth (area ratio " + f"{ctl['synchronous']['area_ratio']:.2f} vs standard {ctl['synchronous']['standard_area_ratio']:.2f}); the growth law cannot tell a wave from a synchronous pulse."],
            "equations": [{"label": "Erk activity", "tex": "\\dot E=\\alpha_1\\tfrac{A^2}{\\beta^2+A^2}(1-E)-E(\\gamma_1 I+\\gamma_e)", "source": "Hayden 2021, doi 10.1016/j.bpj.2021.05.004"}, {"label": "Activator with diffusion", "tex": "\\dot A=\\alpha_2[\\text{source}]+\\alpha_3E-\\gamma_2A+D\\nabla^2A", "source": "Hayden 2021"}, {"label": "Inhibitor", "tex": "\\dot I=\\gamma_3(\\alpha_4E-I)", "source": "Hayden 2021"}, {"label": "Growth coupling (ASSUMED exponential form)", "tex": "\\frac{d\\ln a}{dt}=0.006\\ \\mathrm{h^{-1}}\\ \\text{for}\\ t-t_{\\text{peak}}\\le 24\\ \\mathrm{h}", "source": "assumption; measured form is linear, De Simone 2021 Ext. Data Fig. 7b"}],
            "sources": [{"label": s_["citation"], "locator": f"doi {s_['doi']}; read level {s_['read_level']}; {s_.get('used_for', '')}"} for s_ in r["sources"] if not s_.get("used_for", "").startswith("NOT YET")],
            "limitations": r["not_claimed"], "couplings": [], "manifest": f"{d}/receipt.json", "native": True})
    return cards


def native_video_cards(ins: Inputs, out: dict) -> list[dict]:
    """Map each worker's own manifest to the gallery card shape. Nothing is invented: absent fields stay absent."""
    cards = []
    d = "connectors/biomodels/video"; mf = ROOT / d / "delta_notch_replay_manifest.json"
    if mf.exists():
        m = json.loads(ins.read(f"{d}/delta_notch_replay_manifest.json")); v = m["video"]
        st, href = _vid(ins, out, "biomodels-delta-notch", d, v["file"], v.get("sha256"))
        _, ph = _vid(ins, out, "biomodels-delta-notch", d, m["poster"]["file"], m["poster"].get("sha256"))
        cards.append({"id": "biomodels-delta-notch", "title": "Two-cell Delta-Notch replay (BioModels BIOMD0000001047)", "scales": ["cellular"], "evidence_kind": m["evidence_kind"],
            "model": {"name": "BIOMD0000001047, Collier et al. 1996, replayed from the published SBML", "context": m["claims"]["shows"] + ". " + m["claims"]["captions"]["footer"]},
            "time": {"units": "non-dimensional model time, 0 to 60", "note": m["time_mapping"]["rule"] + ". " + m["time_mapping"]["note"]},
            "video": {"file": v["file"], "sha256": v.get("sha256"), "note": f"{v['width']}x{v['height']}, {v['duration_s']} s, {v['codec']}"}, "video_state": st, "video_href": href, "poster_href": ph,
            "numerical_checks": [{"name": "replay inputs", "result": f"three scenario CSVs hashed ({len(m['inputs']['csv'])}); model and replay-code hashes recorded"}],
            "parameter_unknowns": ["Model time and concentrations are non-dimensional; no physical units."], "open_questions": ["It does not show: " + "; ".join(m["claims"]["does_not_show"]) + "."],
            "caption": m["claims"]["captions"]["header"] + " | " + m["claims"]["captions"]["footer"], "couplings": [], "manifest": f"{d}/delta_notch_replay_manifest.json", "native": True})
    d = "engineering/fin_mechanics/artifacts"; mf = ROOT / d / "manifest.json"
    if mf.exists():
        m = json.loads(ins.read(f"{d}/manifest.json")); o = m["outputs"]; v = m["video"]
        st, href = _vid(ins, out, "fin-mechanics", d, "fin_mechanics.mp4", o["fin_mechanics.mp4"]["sha256"])
        _, ph = _vid(ins, out, "fin-mechanics", d, "poster.png", o["poster.png"]["sha256"])
        cards.append({"id": "fin-mechanics", "title": "Elastic fin-ray surrogate (Euler-Bernoulli cantilever)", "scales": ["organ"], "evidence_kind": m["evidence_kind"],
            "model": {"name": m["schema"], "context": "Frames from " + v["frames_from"] + ". A scoped elastic surrogate, not a fin."},
            "time": {"units": "not a physical time axis; see the manifest", "note": m["note"]},
            "video": {"file": "fin_mechanics.mp4", "sha256": o["fin_mechanics.mp4"]["sha256"], "note": f"{v['duration_s']} s at {v['fps']} fps, {v['n_frames']} frames"}, "video_state": st, "video_href": href, "poster_href": ph,
            "numerical_checks": [{"name": "frames flagged invalid by the beam checker", "result": f"{v['n_frames_invalid']} of {v['n_frames']}"}, {"name": "reproducible quantity", "result": "frames_data_sha256 " + v["frames_data_sha256"][:16] + "…"}],
            "parameter_unknowns": ["Material and geometry come from the request file, not from a measured fin."], "open_questions": ["Which loads on a real fin ray would the load bridge need from the glide model, and with what uncertainty?"],
            "couplings": [], "manifest": f"{d}/manifest.json", "native": True})
    d = "artifacts/bioelectric"; mf = ROOT / d / "manifest.json"
    if mf.exists():
        m = json.loads(ins.read(f"{d}/manifest.json")); fl = m.get("files", {}); rr = json.loads(ins.read(f"{d}/render_receipt.json")) if (ROOT / d / "render_receipt.json").exists() else {}
        vsha = (fl.get("bioelectric.mp4") or {}).get("sha256"); psha = (fl.get("poster.png") or {}).get("sha256")
        st, href = _vid(ins, out, "bioelectric-cells", d, "bioelectric.mp4", vsha) if vsha else ("none", None)
        _, ph = _vid(ins, out, "bioelectric-cells", d, "poster.png", psha) if psha else (None, None)
        ctrl = json.loads(ins.read(f"{d}/controls_baseline.json")) if (ROOT / d / "controls_baseline.json").exists() else {}
        cards.append({"id": "bioelectric-cells", "title": "Bioelectric cell-voltage model: baseline, sodium-reduced and disconnected gap junctions", "scales": ["cellular"], "evidence_kind": m.get("evidence_kind", "SimulationResult"),
            "model": {"name": m.get("schema"), "context": "Saved states of an electrophysiology model rendered as frames. " + str(m.get("numerical_scope", ""))},
            "time": {"units": f"model time in milliseconds; {rr.get('model_horizon_ms')} ms horizon shown over {rr.get('wall_playback_seconds')} s of video", "note": str(rr.get("temporal_interpolation", ""))},
            "video": {"file": "bioelectric.mp4", "sha256": vsha, "note": f"{rr.get('n_frames')} frames at {rr.get('fps')} fps"}, "video_state": st, "video_href": href, "poster_href": ph,
            "numerical_checks": [{"name": c.get("name", "control").replace("_", " "), "result": "passed" if c.get("passed") else "FAILED", "tolerance": c.get("tolerance") or c.get("tolerance_mV")} for c in (ctrl.get("checks") or [])][:6] + [{"name": "mutation control", "result": "recorded in mutation_receipt.json"}],
            "parameter_unknowns": ["Bounds: " + ", ".join(m.get("bounds", {}) if isinstance(m.get("bounds"), dict) else m.get("bounds", []))], "open_questions": ["Biological validation: " + str(m.get("biological_validation", "not stated"))],
            "couplings": [], "manifest": f"{d}/manifest.json", "native": True})
    d = "artifacts/mechanobio"; mf = ROOT / d / "render-manifest.json"
    if mf.exists():
        m = json.loads(ins.read(f"{d}/render-manifest.json")); by = {a["title"]: a for a in m.get("artifacts", [])}
        v = by.get("mechanobio.mp4"); po = by.get("poster.png")
        st, href = _vid(ins, out, "mechanobio-clutch", d, "mechanobio.mp4", v["sha256"]) if v else ("none", None)
        _, ph = _vid(ins, out, "mechanobio-clutch", d, "poster.png", po["sha256"]) if po else (None, None)
        cards.append({"id": "mechanobio-clutch", "title": "Adhesion clutch mechanics (render of a simulation)", "scales": ["cellular"], "evidence_kind": m.get("evidence_kind", "render_of_simulation"),
            "model": {"name": m.get("schema"), "context": "Frames chosen from a saved molecular-clutch trajectory and its response sweep; not a cell and not a fin."},
            "time": {"units": "model time in seconds (see the trajectory file)", "note": f"{m.get('frames')} frames at {m.get('fps')} fps, frame indices hashed ({str(m.get('frame_indices_sha256'))[:12]}…)"},
            "video": {"file": "mechanobio.mp4", "sha256": v["sha256"] if v else None, "note": f"{v['byte_size']} bytes" if v else ""}, "video_state": st, "video_href": href, "poster_href": ph,
            "numerical_checks": [{"name": "controls", "result": "recorded in controls.json and protocol.json"}], "parameter_unknowns": ["Environment and parameter provenance are in environment.json and protocol.json; transfer to a fin is not attempted."],
            "open_questions": ["What measured traction or substrate stiffness would calibrate this against a real tissue?"], "couplings": [], "manifest": f"{d}/render-manifest.json", "native": True})
    d = "engineering/simulation/video"
    for mname, vid, title, scale in (("manifest.json", "glide-fixed-launch", "Glide trajectories at a fixed launch (point mass)", "organism"), ("manifest_rd.json", "rd-fields", "Reaction-diffusion field time series", "tissue")):
        if not (ROOT / d / mname).exists():
            continue
        m = json.loads(ins.read(f"{d}/{mname}"))
        st, href = _vid(ins, out, vid, d, m["video"], m.get("video_sha256")); _, ph = _vid(ins, out, vid, d, m["poster"], m.get("poster_sha256"))
        tu = m.get("time_units", {})
        extra = ([{"name": "release", "result": f"V0 {m['release']['V0_ms']} m/s, h0 {m['release']['h0_m']} m"}, {"name": "polar", "result": (m.get("polar_status") or "")}] if m.get("release") else [{"name": "reproduction of frozen rows", "result": ", ".join(f"cell {c['cell_id']}: {c['reproduces_frozen_row']}" for c in m.get("cells", []))}])
        cards.append({"id": vid, "title": title, "scales": [scale], "evidence_kind": m["evidence_kind"], "model": {"name": m.get("kind"), "context": "; ".join(c.get("label", "") for c in m.get("cells", []))[:600] or "Constant-coefficient point-mass glide; the coefficients are design assumptions."},
            "time": {"units": tu.get("axis", "not stated"), "note": tu.get("separate_from", "")}, "video": {"file": m["video"], "sha256": m.get("video_sha256"), "note": f"{m['resolution'][0]}x{m['resolution'][1]}, {m['duration_video_s']} s, {m['fps']} fps"},
            "video_state": st, "video_href": href, "poster_href": ph, "numerical_checks": extra,
            "parameter_unknowns": [f"{k}: sampled over {v[0]} to {v[1]}" for k, v in (m.get("mc") or {}).get("priors", {}).items()] or ["See the manifest."],
            "open_questions": ["The glide clock and the reaction-diffusion clock are unrelated and not coupled." if "separate_from" in tu else "Coefficients are assumptions, not measurements."], "couplings": [], "manifest": f"{d}/{mname}", "native": True})
    return cards


COUPLING = "engineering/COUPLING_MANIFEST.json"


def coupling_manifest(ins: Inputs, files: dict, docs: list) -> dict | None:
    """The guilds coupling manifest: typed interface verdicts between models. A verdict is about interfaces, not biology."""
    if not (ROOT / COUPLING).exists():
        return None
    m = json.loads(ins.read(COUPLING))
    for name in ("model-coupling", "fish-lifecycle"):
        if (ROOT / f"docs/{name}.md").exists():
            t = ins.text(f"docs/{name}.md"); files[f"docs/{name}.md.txt"] = t.encode()
            docs.append({"id": name, "title": next((l[2:].strip() for l in t.splitlines() if l.startswith("# ")), name), "status_line": None, "path": f"docs/{name}.md", "sha256": ins.seen[f"docs/{name}.md"]["sha256"], "href": f"data/docs/{name}.md.txt"})
    rows = []
    for c in m["couplings"]:
        cp, v = c["coupling"], c["verdict"]
        rows.append({"id": cp["id"], "from": cp["from"], "to": cp["to"], "mapping_kind": cp.get("mapping_kind"), "time_relation": cp.get("time_relation"), "uncertainty_kind": cp.get("uncertainty_kind"), "note": cp.get("note"),
                     "status": v["status"], "label": v["label"], "reasons": v.get("reasons", []), "checks": v.get("checks", {}), "missing_calibrations": v.get("missing_calibrations", []), "assumption_ids": v.get("assumption_ids", [])})
    return {"schema": m["schema"], "manifest_sha256": m.get("manifest_sha256"), "file_sha256": ins.seen[COUPLING]["sha256"], "scope": m["scope"], "counts": m["counts"], "must_display": m["must_display"], "must_not_say": m["must_not_say"],
            "assumptions": m["assumptions"], "calibrations_registered": m["calibrations_registered"], "timescale_separation": m.get("timescale_separation"), "couplings": rows,
            "models": [{"id": x["model_id"], "name": x["name"], "status": x.get("status"), "engine": x.get("engine"), "scope": x.get("scope"), "not_established": x.get("not_established", []), "ports": len(x.get("ports", []))} for x in m["models"]],
            "proposals": [{"id": x["id"], "title": x["title"], "status": x["status"], "coupling": x.get("source_coupling"), "success": x.get("success"), "falsifier": x.get("falsifier"), "not_a_claim": x.get("not_a_claim")} for x in m.get("problem_proposals", [])]}


GEN = "data/genomics"


def _walk_receipts(d, key, out):
    """Flatten receipts.json: any dict holding a receipt with a url and sha256 is one retrieval. Query strings are dropped (they can carry signatures)."""
    if isinstance(d, dict):
        r = d.get("receipt")
        if isinstance(r, dict) and r.get("url") and r.get("sha256"):
            out.append({"key": key, "url": str(r["url"]).split("?")[0], "retrieved_at": r.get("retrieved_at"), "http_status": r.get("http_status"), "bytes": r.get("bytes"), "sha256": r["sha256"], "license": (d.get("license") or {}).get("name") if isinstance(d.get("license"), dict) else None, "kept_rows": d.get("kept_rows")})
        for k, v in d.items():
            if k != "receipt" and isinstance(v, dict):
                _walk_receipts(v, f"{key}/{k}" if key else k, out)


def genomics(ins: Inputs) -> dict | None:
    """The retrieved genomic and cell/tissue data slice, when present: gene identifiers and retrieval receipts. Data, not a model."""
    if not (ROOT / GEN / "receipts.json").exists():
        return None
    rec = json.loads(ins.read(f"{GEN}/receipts.json")); receipts = []
    _walk_receipts(rec, "", receipts)
    genes = {}
    def tsv(name):
        f = ROOT / GEN / "artifacts" / name
        return [l.split("\t") for l in ins.read(f"{GEN}/artifacts/{name}").decode().splitlines() if l.strip()] if f.exists() else []
    for r in tsv("zfin_gene_selected.tsv"):
        genes[r[2]] = {"symbol": r[2], "zfin": r[0], "ncbi_gene": r[3] if len(r) > 3 else None}
    for r in tsv("zfin_ensembl_1_to_1_selected.tsv"):
        genes.setdefault(r[2], {"symbol": r[2], "zfin": r[0]})["ensembl"] = r[3]
    nf = ROOT / GEN / "artifacts" / "ncbi_gene_summaries.json"
    if nf.exists():
        res = json.loads(ins.read(f"{GEN}/artifacts/ncbi_gene_summaries.json")).get("result", {})
        by = {v.get("nomenclaturesymbol"): v for k, v in res.items() if isinstance(v, dict) and "uid" in v}
        for sym, g in genes.items():
            v = by.get(sym)
            if v:
                g["description"] = v.get("description"); g["chromosome"] = v.get("chromosome")
    ff = None
    if (ROOT / GEN / "flyingfish_receipts.json").exists():
        f = json.loads(ins.read(f"{GEN}/flyingfish_receipts.json")); _walk_receipts(f.get("files", {}), "flyingfish", receipts)
        art = f.get("article") or {}
        ff = {"doi": art.get("doi"), "license": (art.get("license") or {}).get("name"), "published": art.get("published"), "annotation_totals": f.get("annotation_totals"), "selected_genes": len(f.get("selected_genes", [])),
              "length_consistent": f.get("length_consistent_selected_genes"), "absent_symbols": {k: v.get("queries_with_any_hit") for k, v in (f.get("absent_symbols_any_hit") or {}).items()},
              "mapping_note": "gene models in the annotation subset are inferred by protein alignment; a symbol with no hit is not evidence that the gene is absent"}
    return {"genes": sorted(genes.values(), key=lambda g: g["symbol"]), "receipts": receipts, "flyingfish": ff, "receipts_sha256": ins.seen[f"{GEN}/receipts.json"]["sha256"]}


def project_drafts(ins: Inputs) -> dict:
    """Validated, unsubmitted Project drafts (guilds' schema), keyed by file stem. Shown as drafts: a draft is not a store record."""
    out = {}
    base = ROOT / "projects"
    for f in sorted(base.glob("*.draft.json")) if base.exists() else []:
        rel = f.relative_to(ROOT).as_posix(); d = json.loads(ins.read(rel)); p = d.get("draft", {}).get("payload") or {}
        if not p:
            continue
        out[f.name[: -len(".draft.json")]] = {"path": rel, "sha256": ins.seen[rel]["sha256"], "title": p.get("title"), "mission": p.get("mission"), "limitations": p.get("limitations", []),
            "scale_coverage": p.get("scale_coverage", []), "requirements": p.get("requirements", []),
            "open_questions": [{"text": q.get("text"), "problem": (q.get("problem") or {}).get("id"), "blocks": q.get("blocks", [])} for q in p.get("open_questions", [])],
            "members": [{"subsystem": m.get("subsystem"), "role": m.get("role"), "relationship": m.get("relationship"), "causal_bridge": m.get("causal_bridge"), "applicability": m.get("applicability"), "ref": {k: (m.get("ref") or {}).get(k) for k in ("kind", "id", "namespace")}} for m in p.get("members", [])]}
    return out


ASSURANCE = "artifacts/assurance/map.json"


def assurance_map(ins: Inputs) -> dict | None:
    """The regional design-assurance map (frontier.design-assurance/1), when present. Shown as written: no aggregation, no probability is computed here."""
    if not (ROOT / ASSURANCE).exists():
        return None
    m = json.loads(ins.read(ASSURANCE))
    if m.get("schema") != "frontier.design-assurance/1":
        return {"error": f"unexpected schema {m.get('schema')!r}; not shown", "file_sha256": ins.seen[ASSURANCE]["sha256"]}
    m["file_sha256"] = ins.seen[ASSURANCE]["sha256"]
    return m


RESOURCES = "results/resources/resource-inventory.json"


def mcp_check(ins: Inputs) -> dict | None:
    """The recorded public MCP check (official SDK). Shown with its own scope; no product-client claim is derived from it."""
    f = "deploy/receipts/mcp-public-check.json"
    if not (ROOT / f).exists():
        return None
    d = json.loads(ins.read(f)); cs = d.get("checks", [])
    return {"checked_at": d.get("checked_at"), "endpoint": d.get("endpoint"), "transport": d.get("transport"), "total": len(cs), "passed": sum(1 for c in cs if c.get("passed")), "failed": [c.get("name") for c in cs if not c.get("passed")],
            "scientific_records_written": d.get("scientific_records_written"), "scope": d.get("scope"), "file_sha256": ins.seen[f]["sha256"]}


def resource_inventory(ins: Inputs) -> dict | None:
    """The recorded resource inventory (observed at a stated time): requested capacity and outcomes, never utilisation or spend that was not measured."""
    if not (ROOT / RESOURCES).exists():
        return None
    d = json.loads(ins.read(RESOURCES)); d["file_sha256"] = ins.seen[RESOURCES]["sha256"]
    return d


def checklist(text: str) -> list[dict]:
    return [{"done": m.group(1) == "x", "text": m.group(2).strip()} for m in re.finditer(r"^- \[([ x])\] (.+)$", text, re.M)]


def system_block(ins: Inputs, files: dict, docs: list, board: list, lean, sim, attestation) -> dict:
    """Two levels, kept apart: what authors wrote (checkboxes, status text) and what a receipt in this tree measured."""
    goal = checklist(ins.text("GOAL.md")); spec5 = checklist(ins.text("specs/SPEC-005-agentic-engineering-demo.md"))
    specs = []
    for p in sorted((ROOT / "specs").glob("*.md")):
        rel = p.relative_to(ROOT).as_posix(); text = ins.text(rel); name = p.name
        if f"docs/{name}.txt" not in files:
            files[f"docs/{name}.txt"] = text.encode()
            docs.append({"id": p.stem, "title": next((l[2:].strip() for l in text.splitlines() if l.startswith("# ")), p.stem), "status_line": None, "path": rel, "sha256": ins.seen[rel]["sha256"], "href": f"data/docs/{name}.txt"})
        did = next((d["id"] for d in docs if d["path"] == rel), p.stem)
        specs.append({"id": did, "title": next((l[2:].strip() for l in text.splitlines() if l.startswith("# ")), p.stem), "path": rel, "sha256": ins.seen[rel]["sha256"]})
    measured = []
    if lean:
        measured.append({"what": "Lean check of the constraint certificate (offline run)", "result": "all recorded checks passed" if lean["all_ok"] else "recorded failure", "receipt": lean["path"], "sha256": lean["sha256"], "covers": "three encoded constraints and four mutants; not biology"})
    if sim:
        c = (sim.get("controls") or {}).get("all_pass")
        measured.append({"what": "Glide simulation numerical controls", "result": "all pass" if c else f"all_pass = {c}", "receipt": SIM_DIR + "/controls.json", "sha256": next((f["sha256"] for f in sim["files"] if f["name"] == "controls.json"), None), "covers": "analytic and step-halving controls of a point-mass model; not a fish"})
    if attestation:
        measured.append({"what": "Attestation quote check (15 items)", "result": f"{attestation['status_counts'].get('verified', 0)} of {attestation['n']} quotes found; judgment {attestation['tally'].get('clean_yes_and_direct_no_flags')} of {attestation['n']} clean", "receipt": ATT, "sha256": ins.seen[ATT]["sha256"], "covers": "a hand-picked sample; not a population rate"})
    return {"goal_checklist": goal, "spec005_acceptance": spec5, "specs": specs, "board": board, "measured": measured,
            "levels": {"author_report": "What the repository's own documents say: checkboxes, status text, owners, plans. Written by the people or agents doing the work.",
                       "measured": "What a receipt in this tree records: a run with its hash and result. A receipt covers only what it says it covers."},
            "unknown": ["CPU and GPU job counts, utilisation and cost: no receipt in this tree; provider-billed spend is stated by the board as not yet known", "Which commit is deployed: not derivable from files"]}


def belief_example(ins: Inputs) -> dict | None:
    """The declared illustration shipped with frontier/beliefs.py (stdlib only), used as the default scenario on the Belief page."""
    if not (ROOT / "frontier/beliefs.py").exists():
        return None
    ins.read("frontier/beliefs.py")
    sys.path.insert(0, str(ROOT))
    try:
        from frontier.beliefs import EXAMPLE_SCENARIO
    finally:
        sys.path.remove(str(ROOT))
    return json.loads(json.dumps(EXAMPLE_SCENARIO))


def build() -> dict[str, bytes]:
    ins = Inputs()
    seeds = ins.json("seeds/frontier-data.json")
    problems = ins.json("seeds/frontier-problems.json")
    mission = ins.json("site/content/mission.json")
    projects = ins.json("site/content/projects.json")
    board = parse_board(ins.text("tasks/BUILD.md"))
    spec_text = ins.text("specs/SPEC-005-agentic-engineering-demo.md")
    mcp_text = ins.text("docs/mcp.md")
    tools = mcp_tools(mcp_text)

    docs, files = [], {}
    for p in sorted((ROOT / "results").glob("*.md")):
        rel = p.relative_to(ROOT).as_posix()
        text = ins.text(rel)
        meta = doc_meta(rel, text)
        meta["sha256"] = ins.seen[rel]["sha256"]
        meta["href"] = f"data/docs/{p.name}.txt"
        docs.append(meta)
        files[f"docs/{p.name}.txt"] = text.encode()
    for rel, ident, title in (("specs/SPEC-005-agentic-engineering-demo.md", "SPEC-005", "SPEC-005 Agentic engineering on a shared biological frontier"),
                              ("docs/mcp.md", "mcp", "Frontier MCP server")):
        name = Path(rel).name
        docs.append({"id": ident, "title": title, "status_line": None, "path": rel, "sha256": ins.seen[rel]["sha256"], "href": f"data/docs/{name}.txt"})
        files[f"docs/{name}.txt"] = ins.read(rel)

    # The label is a digest of the input hashes, not a git revision: a commit or merge cannot make --check stale.
    lean_receipt, simulation = recorded_results(ins, files)
    attestation = attestation_check(ins, files, docs)
    manifests = simulation_manifests(ins)
    belief_ex = belief_example(ins)
    genomics_slice = genomics(ins)
    project_recs = project_drafts(ins)
    assurance = assurance_map(ins)
    resources = resource_inventory(ins)
    mcp_chk = mcp_check(ins)
    extra: dict = {}
    prints = print_forms(ins, extra)
    controlled = controlled_results(ins, files)
    if simulation is not None:
        simulation["controlled"] = controlled
    manifests = manifests + native_video_cards(ins, extra) + engineering_cards(ins, extra)
    couplings_m = coupling_manifest(ins, files, docs)
    system = system_block(ins, files, docs, board, lean_receipt, simulation, attestation)
    design_review = ins.json("site/content/design-review.json")
    lifecycle = lifecycle_block(ins)
    home_biology_block = home_biology(ins)
    fingerprint = digest_bytes(canonical(sorted((i["path"], i["sha256"]) for i in ins.seen.values())).encode())
    snapshot = {
        "schema": SCHEMA,
        "label": f"snapshot of inputs {fingerprint[:12]}",
        "input_fingerprint": fingerprint,
        "inputs": sorted(ins.seen.values(), key=lambda i: i["path"]),
        "scope": {"claims": seeds["scope"], "problems": problems["scope"], "ranking": problems["ranking"], "seed_source_revision": seeds["source_revision"]},
        "claims": seeds["nodes"],
        "bridges": seeds["bridges"],
        "problems": problems["problems"],
        "mission": mission,
        "projects": projects,
        "documents": docs,
        "capabilities": tools,
        "board": board,
        "lean_receipt": lean_receipt,
        "simulation": simulation,
        "attestation_check": attestation,
        "simulation_manifests": manifests,
        "system": system,
        "coupling_manifest": couplings_m,
        "belief_example": belief_ex,
        "print_forms": prints,
        "genomics": genomics_slice,
        "project_drafts": project_recs,
        "assurance": assurance,
        "design_review": design_review,
        "lifecycle": lifecycle,
        "home_biology": home_biology_block,
        "resource_inventory": resources,
        "mcp_check": mcp_chk,
        "spec_acceptance_open": len(re.findall(r"^- \[ \]", spec_text, re.M)),
    }
    catalog = {"schema": "frontier-site-catalog-0.1", "mode": "snapshot", "namespace": NAMESPACE, "snapshot": snapshot["label"], "records": build_catalog(snapshot)}
    out = {"snapshot.json": (json.dumps(snapshot, indent=1, ensure_ascii=False) + "\n").encode(),
           "catalog.json": (json.dumps(catalog, indent=1, ensure_ascii=False) + "\n").encode()}
    out.update(files); out.update(extra)
    return out


def write(out: dict[str, bytes]) -> None:
    for d in (DATA / "docs", DATA / "results", SITE / "artifacts" / "print", SITE / "artifacts" / "results"):
        if d.exists():
            shutil.rmtree(d)
    for name, b in out.items():
        dest = SITE / name[1:] if name.startswith("@") else DATA / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b)


def check(out: dict[str, bytes]) -> list[str]:
    at = lambda n: SITE / n[1:] if n.startswith("@") else DATA / n
    stale = [n for n, b in out.items() if not at(n).exists() or at(n).read_bytes() != b]
    extra = [p.relative_to(DATA).as_posix() for sub in ("docs", "results") if (DATA / sub).exists() for p in (DATA / sub).glob("*")]
    pr = [("@artifacts/" + sub + "/" + p.relative_to(SITE / "artifacts" / sub).as_posix()) for sub in ("print", "results") for p in (SITE / "artifacts" / sub).rglob("*") if p.is_file()] if (SITE / "artifacts").exists() else []
    return stale + [f"unexpected {e}" for e in extra if e not in out] + [f"unexpected {e}" for e in pr if e not in out]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    out = build()
    if args.check:
        bad = check(out)
        print(json.dumps({"stale": bad}))
        return 1 if bad else 0
    write(out)
    snap = json.loads(out["snapshot.json"])
    print(json.dumps({"label": snap["label"], "inputs": len(snap["inputs"]),
                      "claims": len(snap["claims"]), "problems": len(snap["problems"]), "documents": len(snap["documents"])}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
