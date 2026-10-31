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
    """Tool names come from the Tools row of the table in docs/mcp.md, so the page cannot list a tool the document does not."""
    row = next((l for l in mcp_text.splitlines() if l.startswith("| Tools |")), "")
    cells = [c.strip() for c in row.strip().strip("|").split("|")]
    names = lambda c: re.findall(r"`(frontier_[a-z_]+)`", c)
    read = names(cells[1]) if len(cells) > 2 else []
    write = [n for n in names(cells[2]) if n not in read] if len(cells) > 2 else []
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
                files[f"results/{name}"] = b
                listing.append({"name": name, "path": f"{SIM_DIR}/{name}", "sha256": digest_bytes(b), "bytes": len(b), "href": f"data/results/{name}"})
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
    files["docs/" + Path(ATT_README).name] = text.encode()
    docs.append({"id": Path(ATT_README).stem, "title": next(l[2:].strip() for l in text.splitlines() if l.startswith("# ")), "status_line": None, "path": ATT_README,
                 "sha256": ins.seen[ATT_README]["sha256"], "href": "data/docs/" + Path(ATT_README).name})
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
        forms.append(entry)
    return {"label": man.get("label"), "display_scale": man.get("display_scale"), "display_scale_note": man.get("display_scale_note"), "run": {k: man["run"].get(k) for k in ("box_mm", "launch_speed_query_m_s", "libraries")} | {"solver_commit": (man["run"].get("solver") or {}).get("commit"), "solver_branch": (man["run"].get("solver") or {}).get("branch")}, "forms": forms}


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
            b = ins.read(f"{CTRL_DIR}/{name}"); out[f"docs/controlled_{name}"] = b
            files.append({"name": name, "path": f"{CTRL_DIR}/{name}", "sha256": digest_bytes(b), "bytes": len(b), "href": f"data/docs/controlled_{name}"})
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
            "couplings": [], "manifest": f"{d}/delta_notch_replay_manifest.json", "native": True})
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


def checklist(text: str) -> list[dict]:
    return [{"done": m.group(1) == "x", "text": m.group(2).strip()} for m in re.finditer(r"^- \[([ x])\] (.+)$", text, re.M)]


def system_block(ins: Inputs, files: dict, docs: list, board: list, lean, sim, attestation) -> dict:
    """Two levels, kept apart: what authors wrote (checkboxes, status text) and what a receipt in this tree measured."""
    goal = checklist(ins.text("GOAL.md")); spec5 = checklist(ins.text("specs/SPEC-005-agentic-engineering-demo.md"))
    specs = []
    for p in sorted((ROOT / "specs").glob("*.md")):
        rel = p.relative_to(ROOT).as_posix(); text = ins.text(rel); name = p.name
        if f"docs/{name}" not in files:
            files[f"docs/{name}"] = text.encode()
            docs.append({"id": p.stem, "title": next((l[2:].strip() for l in text.splitlines() if l.startswith("# ")), p.stem), "status_line": None, "path": rel, "sha256": ins.seen[rel]["sha256"], "href": f"data/docs/{name}"})
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
        meta["href"] = f"data/docs/{p.name}"
        docs.append(meta)
        files[f"docs/{p.name}"] = text.encode()
    for rel, ident, title in (("specs/SPEC-005-agentic-engineering-demo.md", "SPEC-005", "SPEC-005 Agentic engineering on a shared biological frontier"),
                              ("docs/mcp.md", "mcp", "Frontier MCP server")):
        name = Path(rel).name
        docs.append({"id": ident, "title": title, "status_line": None, "path": rel, "sha256": ins.seen[rel]["sha256"], "href": f"data/docs/{name}"})
        files[f"docs/{name}"] = ins.read(rel)

    # The label is a digest of the input hashes, not a git revision: a commit or merge cannot make --check stale.
    lean_receipt, simulation = recorded_results(ins, files)
    attestation = attestation_check(ins, files, docs)
    manifests = simulation_manifests(ins)
    belief_ex = belief_example(ins)
    extra: dict = {}
    prints = print_forms(ins, extra)
    controlled = controlled_results(ins, files)
    if simulation is not None:
        simulation["controlled"] = controlled
    manifests = manifests + native_video_cards(ins, extra)
    system = system_block(ins, files, docs, board, lean_receipt, simulation, attestation)
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
        "documents": docs,
        "capabilities": tools,
        "board": board,
        "lean_receipt": lean_receipt,
        "simulation": simulation,
        "attestation_check": attestation,
        "simulation_manifests": manifests,
        "system": system,
        "belief_example": belief_ex,
        "print_forms": prints,
        "spec_acceptance_open": len(re.findall(r"^- \[ \]", spec_text, re.M)),
    }
    catalog = {"schema": "frontier-site-catalog-0.1", "mode": "snapshot", "namespace": NAMESPACE, "snapshot": snapshot["label"], "records": build_catalog(snapshot)}
    out = {"snapshot.json": (json.dumps(snapshot, indent=1, ensure_ascii=False) + "\n").encode(),
           "catalog.json": (json.dumps(catalog, indent=1, ensure_ascii=False) + "\n").encode()}
    out.update(files); out.update(extra)
    return out


def write(out: dict[str, bytes]) -> None:
    for d in (DATA / "docs", DATA / "results", SITE / "artifacts" / "print"):
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
    pr = [("@artifacts/print/" + p.relative_to(SITE / "artifacts/print").as_posix()) for p in (SITE / "artifacts/print").rglob("*") if p.is_file()] if (SITE / "artifacts/print").exists() else []
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
