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
import collections
import copy
import datetime
import importlib.util
import json
import re
import shutil
import sys
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo

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


EVENT_START_UTC = "2026-10-30T07:00:00"   # 2026-10-30 00:00 PDT; the event window the System page may report on
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


def _vid(ins, out, vid, src_dir, fname, declared, bytes_declared=None, allow_unpinned=False):
    """Copy a declared video/poster into the site and compare its bytes with the declared sha256."""
    f = ROOT / src_dir / fname
    if not f.is_file():
        return "declared_but_missing", None
    b = ins.read(f"{src_dir}/{fname}"); h = digest_bytes(b)
    if declared and declared != h:
        return "digest_mismatch", None
    out[f"{SIM_OUT}/{vid}/{fname}"] = b
    return ("present_verified" if declared or not allow_unpinned else "present_unpinned"), f"artifacts/simulations/{vid}/{fname}"


def build_timeline(ins: Inputs) -> dict | None:
    """Evidence-linked record of how the work ran: dated live checks, model-usage windows, GPU telemetry windows, provider launch outcomes
    and preregistered result verdicts. Every row names the file and its sha256; undated rows are listed apart, spend stays unknown."""
    ri = "results/resources/resource-inventory.json"
    if not (ROOT / ri).exists():
        return None
    uf = "results/resources/hackathon-usage.json"; U = json.loads(ins.read(uf)) if (ROOT / uf).exists() else None
    R = json.loads(ins.read(ri)); rows = []; sha = lambda path: ins.seen[path]["sha256"] if path in ins.seen else None
    add = lambda t, kind, title, outcome, path, ok=None, scope="", digest=None: rows.append({"time": t, "kind": kind, "title": title, "outcome": outcome, "ok": ok, "path": path, "sha256": digest or sha(path), "scope": scope})
    dated_only = []
    for f in sorted((ROOT / "deploy/receipts").glob("*.json")):
        path = f"deploy/receipts/{f.name}"; d = json.loads(ins.read(path)); ch = d.get("checks", []); note = ch if isinstance(ch, str) else None   # a receipt may state its checks as prose
        ch = [c for c in ch if isinstance(c, dict)] if isinstance(ch, list) else []
        npass = sum(1 for c in ch if c.get("passed")); target = d.get("base") or d.get("endpoint") or "public node"
        if "checked_at" not in d:                         # a receipt with no time of day is listed apart, never given a made-up time
            dated_only.append({"title": f.stem.replace("-", " ") + (" (release " + str(d["sha"])[:12] + ")" if d.get("sha") else ""), "outcome": "; ".join(f"{c.get('name', 'check')}: {c.get('result') or ('passed' if c.get('passed') is True else 'not passed')} (exit {c.get('exit', 'not recorded')})" for c in ch) or "no checks listed", "ok": all(c.get("exit", 1) == 0 for c in ch) if ch else None, "path": path, "sha256": sha(path), "date": "no time recorded"}); continue
        add(d["checked_at"], "live check", f.stem.replace("-", " ") + " (" + target + ")", (note if note and not ch else f"{npass} of {len(ch)} checks passed"), path, (None if note and not ch else npass == len(ch)), d.get("scope", ""))
    for k, u in (U or R)["model_usage"].items():
        if isinstance(u, dict) and u.get("window_utc"):
            out = ", ".join(f"{n.replace('_', ' ')} {u[n]}" for n in ("documents_embedded", "embedding_requests", "failed_requests", "calls", "input_tokens", "output_tokens_including_thinking") if n in u)
            add(u["window_utc"][0], "model usage", f"{u.get('provider', 'provider')} {u.get('model', k.replace('_', ' '))}", out + f"; window {u['window_utc'][0]} to {u['window_utc'][1]}", u["receipt"], u.get("failed_requests", 0) == 0 if "failed_requests" in u else None, u["usage_scope"], u.get("sha256"))
    for t in (U or R)["historical_gpu_telemetry"]:
        mem = f"; memory max {t['gpu_memory_used_mib_max']} of {t['gpu_memory_total_mib']} MiB" if t.get("gpu_memory_used_mib_max") is not None and t.get("gpu_memory_total_mib") else ""
        add(t["window_utc"][0], "GPU telemetry", t["task_label"], f"{t['samples']} samples at {t.get('sample_period_ms', 1000)} ms; GPU utilisation mean {t['gpu_utilization_pct_mean']}%, max {t['gpu_utilization_pct_max']}%" + (f", {t['samples_ge_90']} samples at or above 90%" if t.get("samples_ge_90") is not None else "") + mem, t["source"], None, "A sampled historical window, not current utilisation.", t.get("sha256"))
    for f in sorted((ROOT / "results").glob("20*.md")):
        path = f"results/{f.name}"; t = ins.text(path); date = f.name[:10]
        head = next((l for l in t.splitlines() if l.startswith("**")), ""); title = next((l[2:].strip() for l in t.splitlines() if l.startswith("# ")), f.name)
        dated_only.append({"title": title, "outcome": re.sub(r"\*+", "", head).strip()[:260], "ok": None, "path": path, "sha256": sha(path), "date": date})
    rows = [r for r in rows if r["time"] >= EVENT_START_UTC]       # only dated use inside the event window; no earlier preparation is narrated
    rows.sort(key=lambda r: r["time"])
    po = json.loads(ins.read("results/resources/provider-outcome.json")); n = po["nebius"]; g = po["google_compute"]
    undated = dated_only + [{"title": "Nebius CPU worker request (" + po["task"] + ")", "outcome": f"{n['result']} on quota {n['quota']}: limit {n['limit']}, aggregate requested {n['aggregate_requested']}; no job created", "ok": False, "path": "results/resources/provider-outcome.json", "sha256": sha("results/resources/provider-outcome.json")},
        {"title": "Google compute enable (an earlier attempt; the later readiness receipt in the Cost row supersedes its state)", "outcome": f"{g['error']} ({g['reason']}); no VM created", "ok": False, "path": "results/resources/provider-outcome.json", "sha256": sha("results/resources/provider-outcome.json")}]
    N = R["compute"]["nebius"]
    mu = R["model_usage"]; emb = mu.get("gemini_embedding_index", {}); bio = mu.get("bioservices_gemini_calls", {}); wi = R["worker_inventory"]; na = wi["native_agents"]
    tel_s = sum(t["samples"] * t["sample_period_ms"] / 1000 for t in R["historical_gpu_telemetry"])
    live_states = ", ".join(f"{n} {k.lower().replace('_', ' ')}" for k, n in N["job_states"].items() if n)
    counters = [
        {"quantity": "Agents", "value": f"{na['root_coordinator']} root coordinator and {na['child_agents']} child agents reported by the orchestration API; {wi['selected_frontier_tmux_panes']['count']} tmux panes of unknown activity", "status": "partial", "note": "Roles beyond these counts are not recorded in a receipt here. Total distinct agents: unknown.", "source": ri},
        {"quantity": "Model calls and tokens", "value": f"Embedding index: {emb.get('embedding_requests')} requests, {emb.get('documents_embedded')} documents, {emb.get('failed_requests')} failed. Bioservices ledger: {bio.get('calls')} calls, {bio.get('input_tokens')} input and {bio.get('output_tokens_including_thinking')} output tokens (thinking included)", "status": "partial", "note": "These two receipts only. Total model usage across all workers: unknown.", "source": ri},
        {"quantity": "GPU jobs", "value": f"{N['own_job_count']} jobs by this project on Nebius: {live_states}", "status": "actual", "note": "Job allocation state at " + N["observed_at_utc"] + "; allocation is requested capacity, not utilisation.", "source": ri},
        {"quantity": "GPU seconds", "value": f"{tel_s:.0f} s inside {len(R['historical_gpu_telemetry'])} sampled telemetry windows", "status": "partial", "note": "Sampled windows only, a lower bound on measured time. Total GPU seconds across all jobs: unknown.", "source": ri},
        {"quantity": "CPU jobs and usage", "value": "No CPU counter is recorded", "status": "unknown", "note": "One Nebius CPU worker request was refused (ResourceExhausted); local CPU runs are not metered here.", "source": "results/resources/provider-outcome.json"},
        {"quantity": "Cost", "value": "Unknown", "status": "unknown", "note": R["cost"]["interpretation"], "source": ri}]
    def pdt(iso):
        return datetime.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    usage = None
    if U:
        def job_kind(job):
            platform = job.get("platform", "")
            return "gpu" if platform.startswith("gpu-") else "cpu" if platform.startswith("cpu-") else "unknown"
        # Derive processor counts from the preserved individual records. Producers
        # have published both flat and processor-nested state summaries.
        sc = {kind: collections.Counter(j["state"] for j in U["own_jobs"] if job_kind(j) == kind) for kind in ("gpu", "cpu", "unknown")}
        ag = U["agents"]; mu = U["model_usage"]; emb = mu["gemini_embedding_index"]; bio = mu["bioservices_gemini_calls"]; of = (U.get("hosted_biomodels") or [{}])[0]
        attribution = U.get("team_attribution") or {}
        owners = attribution.get("ownership_breakdown") or {"current_frontier": attribution.get("current_frontier_jobs", "unknown"), "historical_team": attribution.get("historical_team_jobs", "unknown"), "unattributed": attribution.get("unattributed_jobs", "unknown")}
        attribution_note = f" Separate attribution snapshot ({attribution.get('observed_at_seattle', 'time not recorded')}): {owners['current_frontier']} current Frontier jobs, {owners['historical_team']} historical team jobs, {owners['unattributed']} unattributed (not asserted to be other teams)." if attribution else ""
        st = lambda d: ", ".join(f"{n} {k.lower()}" for k, n in d.items() if n)
        gp = "results/resources/gcp/readiness.json"
        runtime_path = "results/resources/gcp/runtime-status.json"
        if (ROOT / runtime_path).is_file():
            g = json.loads(ins.read(runtime_path))
            gpu_count = sum(a.get("acceleratorCount", 0) for instance in g.get("instances", []) if instance.get("status") == "RUNNING" for a in instance.get("guestAccelerators", []))
            gcp_note = f" Google Cloud allocation snapshot ({g['observed_at_utc']}): {g.get('active_allocated_vcpus', 'unknown')} allocated vCPUs and {gpu_count} attached GPU(s) on RUNNING instances. Reservations are not measured utilization; spend remains unknown."
        elif (ROOT / gp).exists():                       # a dated receipt replaces the earlier terms-of-service note
            g = json.loads(ins.read(gp)); gcp_note = f" Google Cloud, from the dated readiness receipt ({g['observed_at_utc']}): {g['state']}; observed instances {g['observed_instances']}; GPU quota granted {g['gpu_quota_granted']}, requested {g['gpu_quota_requested']}. No VM usage and no spend are inferred from this."
        else:
            gcp_note = " Google Cloud: no dated readiness receipt is in this tree; an earlier terms-of-service block is superseded and is not repeated. No VM usage is inferred."
        counters = [
            {"quantity": "Agents", "value": f"{ag['native_running_snapshot']} native agents with orchestrator status running; {ag['known_contributors_in_audited_slice']} identified contributors in the audited {ag['contributor_window_seattle']} slice", "status": "partial", "note": ag["definition"] + " Total distinct agents and currently active agents: unknown. No collective speedup is measured.", "source": uf},
            {"quantity": "GPU jobs (own H100)", "value": f"{sum(sc['gpu'].values())}: {st(sc['gpu'])}", "status": "actual", "note": f"Own job records from {pdt(U['provider_window_utc'][0])} to {pdt(U['provider_window_utc'][1])}. Provider COMPLETED is not a scientific pass. Shared H100 capacity is not our use." + attribution_note, "source": uf},
            {"quantity": "CPU jobs (own)", "value": f"{sum(sc['cpu'].values())}: {st(sc['cpu'])}", "status": "actual", "note": "CPU seconds are not recorded: unknown.", "source": uf},
            {"quantity": "GPU container work seconds", "value": (f"{U['measured_completed_container_work']['gpu']['seconds']} s across {U['measured_completed_container_work']['gpu']['jobs']} completed GPU jobs and {U['measured_completed_container_work']['cpu']['seconds']} s across {U['measured_completed_container_work']['cpu']['jobs']} completed CPU jobs, from controller receipts" if U.get("measured_completed_container_work") else f"{U['five_completed_h100_container_work_seconds']} s across five completed H100 jobs"), "status": "partial", "note": (U["measured_completed_container_work"]["scope"] + " " if U.get("measured_completed_container_work") else "") + U["time_definition"] + " GPU kernel seconds and billed GPU seconds: unknown.", "source": uf},
            {"quantity": "GPU utilisation", "value": f"{len(U['historical_gpu_telemetry'])} sampled windows, listed below; current utilisation unknown", "status": "partial", "note": "Windows include low and zero values; no project-wide average is inferred.", "source": uf},
            {"quantity": "Model calls and tokens", "value": f"Embedding index: {emb['embedding_requests']} requests, {emb['documents_embedded']} documents, {emb['failed_requests']} failed. Bioservices ledger: {bio['calls']} calls, {bio['input_tokens']} input and {bio['output_tokens_including_thinking']} output tokens (thinking included). Hosted OpenFold2: {of.get('count', 0)} operation, {of.get('final_status', '')}", "status": "partial", "note": "Named ledgers only; embedding and generation units are not merged. Total tokens: unknown. BioNeMo-specific execution: not established.", "source": uf},
            {"quantity": "Cost", "value": "Unknown (not $0)", "status": "unknown", "note": U["cost"]["interpretation"] + gcp_note, "source": uf}]
        if sc["unknown"]:
            counters.append({"quantity": "Jobs with unknown processor kind", "value": f"{sum(sc['unknown'].values())}: {st(sc['unknown'])}", "status": "unknown", "note": "Not assigned to CPU or GPU totals.", "source": uf})
        usage = {"observed_at_seattle": U["observed_at_seattle"], "jobs": [{"name": j["name"], "kind": job_kind(j).upper(), "state": j["state"], "created": pdt(j["created_at"]), "capacity": j["requested_capacity"]} for j in sorted(U["own_jobs"], key=lambda j: j["created_at"])],
            "controller": [{"task": e["task"], "status": e["controller_status"], "wall_s": e["container_wall_s"], "rc": e["result_rc"], "path": e["source"], "sha256": e["sha256"]} for e in U["recent_controller_events"]],
            "roles": ag["roles"], "credit": U["external_tools_credit"], "limitations": U["limitations"], "sha256": sha(uf)}
    audits = {}
    for key, path in (("contributors", "results/resources/agent-contributors.json"),
                      ("models", "results/resources/bio-model-usage.json")):
        if (ROOT / path).is_file():
            audits[key] = {"data": ins.json(path), "path": path, "sha256": sha(path)}
    activity_path = "results/resources/repository-activity-20261101-0523.json"
    if (ROOT / activity_path).is_file():
        document = ins.json(activity_path)
        module_path = "scripts/repository_activity.py"
        ins.read(module_path)
        spec = importlib.util.spec_from_file_location("frontier_repository_activity", ROOT / module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        checked = module.combine(document["repositories"], document["since_utc"], document["until_utc"])
        if checked["deduplicated_counts"] != document["deduplicated_counts"]:
            raise ValueError("Repository activity counts do not match the commit records")
        summary = {k: document[k] for k in ("since_utc", "until_utc", "scope", "deduplicated_counts")}
        summary["repositories"] = [{k: v for k, v in r.items() if k != "commits"} for r in document["repositories"]]
        for repo in document["repositories"]:
            if repo["counts"] != module.counts(repo["commits"]):
                raise ValueError("Per-repository count does not match commit records")
        audits["repositories"] = {"data": summary, "path": activity_path, "sha256": sha(activity_path)}
        c = document["deduplicated_counts"]
        counters.append({"quantity": "Repository commits", "value": f"{c['commit_objects']:,} across four repositories", "status": "actual", "note": f"{c['non_merge_commits']:,} non-merge and {c['merge_commits']:,} merge commit objects; full SHAs deduplicated. Default branches pinned separately, {pdt(document['since_utc'])} to {pdt(document['until_utc'])}. Code activity, not agent or scientific-result counts.", "source": activity_path})
    if "contributors" in audits:
        a = audits["contributors"]; c = a["data"]["counts"]
        observed = datetime.datetime.fromisoformat(a["data"]["window"]["observed_utc"].replace("Z", "+00:00")).astimezone(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
        counters = [c for c in counters if c["quantity"] != "Agents"]
        counters[:0] = [
            {"quantity": "Contributing harnesses", "value": f"At least {c['distinct_contributing_harness_ids_supported_minimum']} distinct harness identities", "status": "partial", "note": f"Authored handoffs or reviewed identity mappings with checked artifacts, observed {observed}. A supported minimum, not a census or concurrent-worker count.", "source": a["path"]},
            {"quantity": "Native collaborators", "value": str(c['native_contributors_supported_minimum']), "status": "partial", "note": "Separate native collaboration identities; work artifacts checked and attribution attested by the coordinator. Root is not counted again. No collective speedup is inferred.", "source": a["path"]},
            {"quantity": "Live harness processes", "value": str(c['live_harness_processes_now']), "status": "partial", "note": f"Process snapshot at {observed}. Includes idle and authentication-blocked sessions; this is not a count of agents working.", "source": a["path"]}]
        participation = a["data"].get("participation")
        if participation:
            source = "results/resources/agent-participation.json"
            raw = ins.read(source)
            if digest_bytes(raw) != participation["source_sha256"]:
                raise ValueError("Participant receipt changed; refuse stale counts")
            native = participation["recorded_native_children"]
            nested = participation["recorded_nested_claude_children"]
            floor = participation["supported_harnesses"] + native + nested
            if floor != participation["recorded_participant_floor"]:
                raise ValueError("Participant classes do not reproduce the recorded floor")
            cutoff = pdt(participation["window"]["observed_utc"])
            live = participation["live_native_api"]
            for counter in counters:
                if counter["quantity"] == "Native collaborators":
                    counter.update(value=str(native), note=f"Historical native children, including retired sessions; transcript evidence through {cutoff}. Artifact-backed identities below are a subset. Not a count of running workers.", source=source)
            counters[:0] = [
                {"quantity": "Recorded participants", "value": f"At least {floor}", "status": "partial", "note": f"{participation['supported_harnesses']} harnesses + {native} native children + {nested} nested Claude children. Historical supported floor through {cutoff}; root counted once. Not completed scientific tasks.", "source": source},
                {"quantity": "Recorded subagents", "value": str(native + nested), "status": "partial", "note": f"{native} native + {nested} nested Claude child identities; shared with the participant total, not additional participants. Global current activity is unknown.", "source": source},
                {"quantity": "Native running snapshot", "value": str(live['running_roots'] + live['running_children']), "status": "actual", "note": f"{live['running_roots']} coordinator + {live['running_children']} children at {pdt(live['observed_utc'])}. API running state, not CPU or model utilization; other harnesses not covered.", "source": source}]

    return {"observed_at": R["observed_at"], "usage": usage, "audits": audits, "counters": counters, "event_window_start_utc": EVENT_START_UTC, "rows": rows, "undated": undated, "nebius": {"own_job_count": N["own_job_count"], "job_states": N["job_states"], "observed_at_utc": N["observed_at_utc"]},
        "unknown": [R["cost"]["interpretation"], "Total provider LLM usage: " + str(R["model_usage"].get("total_provider_llm_usage", "unknown")), "Utilisation of currently allocated GPUs is unknown until sampled."],
        "limitations": R["scope"]["limitations"], "inventory": ri, "inventory_sha256": sha(ri)}


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


def fish3d_files(ins: Inputs, out: dict) -> dict | None:
    """Copy the actual fish3d candidates for the viewer: the baseline (fish.glb + render files) and the v3 variants (adult-fao GLB, appearance record,
    preview, components). Each file is copied only if its bytes equal the declared sha256; refusals are listed."""
    cid = "fish3d-N1-cypselurus-baseline"; d = f"artifacts/fish3d/{cid}"
    if not (ROOT / d / "render/render.json").exists():
        return None
    state = {"copied": [], "refused": []}
    def put(cdir, rel, declared=None):
        b = ins.read(f"artifacts/fish3d/{cdir}/{rel}") if (ROOT / "artifacts/fish3d" / cdir / rel).exists() else None
        if b is None or (declared and digest_bytes(b) != declared):
            state["refused"].append(f"{cdir}/{rel}"); return False
        out[f"@artifacts/fish3d/{cdir}/{rel}"] = b; state["copied"].append(f"{cdir}/{rel}"); return True
    r = json.loads(ins.read(f"{d}/render/render.json")); comps = json.loads(ins.read(f"{d}/components.json"))["components"]
    put(cid, "fish.glb", r["glb_sha256"]); put(cid, "components.json"); put(cid, "render/render.json"); put(cid, "render/poster.png", r["poster_sha256"]); put(cid, "render/turntable.mp4", r["video"]["sha256"])
    for v in comps.values():
        if v.get("stl"):
            put(cid, v["stl"], v.get("stl_sha256"))
    candidates = [{"id": cid, "label": "N1 baseline (flat fin plates)", "base": f"artifacts/fish3d/{cid}/", "variants": [], "knobs": None, "status_counts": dict(collections.Counter(p["status"] for c in comps.values() for p in c.get("params", {}).values() if isinstance(p, dict) and "status" in p)), "rays": None, "candidate_sha256": json.loads(ins.read(f"{d}/candidate.json")).get("candidate_sha256")}]
    ix = "artifacts/fish3d/v3-index.json"
    if (ROOT / ix).exists():
        V = json.loads(ins.read(ix))
        for vid, meta in V["candidates"].items():
            vd = f"artifacts/fish3d/{vid}"
            if not (ROOT / vd / "appearance-adult-fao.json").exists():
                continue
            ap = json.loads(ins.read(f"{vd}/appearance-adult-fao.json")); vc = json.loads(ins.read(f"{vd}/components.json"))["components"]
            ok = put(vid, "fish-adult-fao.glb", ap["glb_sha256"]) and put(vid, "appearance-adult-fao.json") and put(vid, "preview-adult-fao.png") and put(vid, "components.json") and put(vid, "build.json") and put(vid, "candidate.json")
            for c in vc.values():
                if c.get("stl"):
                    put(vid, c["stl"], c.get("stl_sha256"))
            if ok:
                candidates.append({"id": vid, "label": vid.replace("fish3d-", ""), "base": f"artifacts/fish3d/{vid}/", "knobs": meta["knobs"], "candidate_sha256": meta["candidate_sha256"],
                                   "variants": [{"id": "adult-fao", "glb": "fish-adult-fao.glb", "appearance": "appearance-adult-fao.json", "poster": "preview-adult-fao.png", "video": None}],
                                   "status_counts": dict(collections.Counter(p["status"] for c in vc.values() for p in c.get("params", {}).values() if isinstance(p, dict) and "status" in p)),
                                   "rays": {k: f["n_rays"] for k, f in json.loads(ins.read(f"{vd}/rays.json"))["fins"].items()} if (ROOT / vd / "rays.json").exists() else None})
        shared = V.get("shared")
    else:
        shared = None
    return {"base": f"artifacts/fish3d/{cid}/", "glb_sha256": r["glb_sha256"], "candidates": candidates, "shared": shared, **state}


ECO = "artifacts/ecology"


def ecology_block(ins: Inputs, out: dict) -> dict | None:
    """Ecology saved-state scenarios for the trajectory viewer. Files are published only when their bytes equal the hash declared by the run receipt,
    render receipt or v3a build record; refusals are listed. Nothing here is a measurement or a validated flying fish."""
    ix = ROOT / ECO / "index.json"
    if not ix.exists():
        return None
    index = json.loads(ins.read(f"{ECO}/index.json")); run = index["canonical_run"]
    rec = json.loads(ins.read(f"{run}/receipt.json")); declared = {f["path"]: f["sha256"] for f in rec["files"]}
    summary = json.loads(ins.read(f"{run}/summary.json")); iface = json.loads(ins.read(f"{ECO}/interface.json")); geo = json.loads(ins.read(f"{ECO}/geometry-manifest.json"))
    state = {"copied": [], "refused": []}
    def put(rel, want, root_rel=None):
        f = ROOT / rel
        b = ins.read(rel) if f.is_file() else None
        if b is None or not want or digest_bytes(b) != want:
            state["refused"].append(rel); return None
        dest = (root_rel or rel)
        out["@" + dest] = b; state["copied"].append(rel); return dest
    cases = []
    for c in iface["canonical_cases"]:
        t = c["trajectory"]; ok = put(t, declared.get(t))
        cases.append({"id": c["id"], "trajectory": ok, "trajectory_sha256": declared.get(t), "half_step_trajectory": None, "summary": summary.get(c["id"])})
        half = t.replace(c["id"] + "/", c["id"] + "-dt-half/")
        cases[-1]["half_step_declared"] = half in declared
    receipts = {k: put(f"{run}/{k}.json", declared.get(f"{run}/{k}.json")) for k in ("controls", "summary")}
    receipts["receipt"] = f"{run}/receipt.json"; out["@" + receipts["receipt"]] = ins.read(receipts["receipt"]); state["copied"].append(receipts["receipt"])
    media = []
    for m in index["media"]:
        prov = json.loads(ins.read(m["video"].replace(".mp4", ".provenance.json")))
        files = {}
        for key in ("video", "poster"):
            rel = m[key]; want = prov.get(key + "_sha256")
            files[key] = put(rel, want)
        out["@" + m["video"].replace(".mp4", ".provenance.json")] = ins.read(m["video"].replace(".mp4", ".provenance.json"))
        media.append({"id": m["id"], "frames": prov.get("video_frames"), "frame_method": prov.get("frame_method"), "geometry": prov.get("geometry"), **files, "provenance": m["video"].replace(".mp4", ".provenance.json")})
    v3 = "artifacts/fish3d/fish3d-v3a-fan"; bj = json.loads(ins.read(f"{v3}/build.json"))
    pins = {p["path"]: p["sha256"] for p in geo["candidate_and_panel_pins"]}
    mesh = put(f"{v3}/fish.glb", (bj.get("files") or bj.get("sha256") or bj).get("fish.glb") if isinstance(bj, dict) else None)
    panels = put(f"{v3}/panels.json", pins.get(f"{v3}/panels.json"))
    for rel in (f"{ECO}/geometry-manifest.json", f"{ECO}/interface.json", f"{ECO}/index.json", f"{ECO}/RESULTS.md"):
        out["@" + rel] = ins.read(rel)
    unc = ecology_uncertainty(ins, put)
    return {"index": index, "uncertainty": unc, "cases": cases, "receipts": receipts, "media": media, "mesh": mesh, "panels": panels, "status": iface["status"], "engine": iface["engine"],
            "limits": iface.get("limits"), "biological_success_probability": iface.get("biological_success_probability"), "empirical_validation": index.get("empirical_validation"),
            "history": index.get("history"), "geometry": {k: geo.get(k) for k in ("source", "source_component_units", "mesh_to_body", "cg_from_nose_m")}, **state}


BIO = "artifacts/biodesign-compiler"


def biodesign_block(ins: Inputs, out: dict) -> dict | None:
    """Biodesign assembly compiler output: the pinned assemblies, six separate axes, diffs and unresolved bridges, copied as the compiler wrote them.
    Files are published only when equal to the hash the compiler's own manifest declares. No single badge is computed here."""
    mp = ROOT / BIO / "manifest.json"
    if not mp.exists() or not (ROOT / BIO / "report.json").exists():
        return None
    man = json.loads(ins.read(f"{BIO}/manifest.json")); want = {f["path"]: f["sha256"] for f in man["files"]}
    state = {"copied": [], "refused": []}
    def put(rel):
        f = ROOT / rel
        b = ins.read(rel) if f.is_file() else None
        if b is None or digest_bytes(b) != want.get(rel):
            state["refused"].append(rel); return None
        out["@" + rel] = b; state["copied"].append(rel); return rel
    report_path = put(f"{BIO}/report.json")
    assemblies = {}
    for rel in sorted(want):
        if rel.startswith(f"{BIO}/assemblies/"):
            path = put(rel)
            if path:
                a = json.loads(ins.read(rel))
                assemblies[a["id"]] = {"path": path, "sha256": want[rel], "components": a["components"], "shared_pins": a.get("shared_pins"), "shared_pins_note": a.get("shared_pins_note"),
                                       "siblings": a.get("siblings"), "scope": a.get("scope"), "unresolved_interfaces": a.get("unresolved_interfaces"), "parent": a.get("parent")}
    out["@" + f"{BIO}/manifest.json"] = ins.read(f"{BIO}/manifest.json")
    if (ROOT / BIO / "README.md").exists():
        out["@" + f"{BIO}/README.md"] = ins.read(f"{BIO}/README.md")
    report = json.loads(ins.read(f"{BIO}/report.json")) if report_path else None
    return {"report": report, "report_path": report_path, "report_sha256": want.get(f"{BIO}/report.json"), "manifest": f"{BIO}/manifest.json", "readme": f"{BIO}/README.md" if (ROOT / BIO / "README.md").exists() else None,
            "assemblies": assemblies, **state}


def ecology_uncertainty(ins: Inputs, put) -> dict | None:
    """Assumed-parameter sensitivity of the neighbour cue (28 scenarios). Figures and files are published only when equal to the hash the native
    uncertainty manifest declares; the table is copied from the aggregate summary. Shared-model scenarios, not biological confidence."""
    mp = f"{ECO}/uncertainty-manifest.json"
    if not (ROOT / mp).exists() or not (ROOT / ECO / "uncertainty-aggregate/summary.json").exists():
        return None
    man = json.loads(ins.read(mp)); want = {f["path"]: f["sha256"] for f in man["files"]}
    agg = json.loads(ins.read(f"{ECO}/uncertainty-aggregate/summary.json"))
    files = {}
    for key, rel in (("aggregate_figure", "uncertainty-aggregate/paired-sensitivity.png"), ("aggregate_provenance", "uncertainty-aggregate/paired-sensitivity.provenance.json"),
                     ("aggregate_summary", "uncertainty-aggregate/summary.json"), ("initial_figure", "uncertainty-initial/paired-sensitivity.png"),
                     ("initial_provenance", "uncertainty-initial/paired-sensitivity.provenance.json"), ("initial_summary", "uncertainty-initial/summary.json")):
        files[key] = put(f"{ECO}/{rel}", want.get(f"{ECO}/{rel}"))
    proto = json.loads(ins.read(f"{ECO}/uncertainty-protocol.json")); out_manifest = put(mp, digest_bytes(ins.read(mp)))
    res = agg["results"]
    return {"status": agg["status"], "scenario_count": agg["scenario_count"], "computed_count": agg["computed_count"],
            "numeric_gate_passed": sum(1 for r in res if r["numeric_gate_passed"]), "initial_native_status": agg["initial_native_status_unchanged"],
            "continuation_native_status": agg["continuation_native_status"], "scope": agg["scope"], "question": proto["scientific_question"],
            "settings": [{"id": x["id"], "overrides": x["overrides"]} for x in proto["settings"]], "seeds": proto["seeds"], "design": proto["design"],
            "termination_reasons": dict(collections.Counter(r["main_summary"]["termination_reason"] for r in res)),
            "paired": agg["paired_comparisons"], "files": files, "manifest": out_manifest, "source_and_transfer_limits": proto.get("source_and_transfer_limits")}


def formalize_examples(ins: Inputs) -> dict | None:
    """Fixtures from engineering/formalize/cases.py and the recorded Gemini extraction runs, for the proposal checker page. Nothing is run here:
    the site only offers these requests to the node's POST /api/formalize/propose."""
    fdir = ROOT / "engineering/formalize"
    if not (fdir / "cases.py").exists():
        return None
    import importlib, sys as _sys
    _sys.path.insert(0, str(ROOT))
    try:
        cases = importlib.import_module("engineering.formalize.cases")
    finally:
        _sys.path.pop(0)
    for rel in ("cases.py", "sources/MANIFEST.json", "sources/cantilever_passage.txt", "sources/oca2_passage.txt"):
        if (fdir / rel).exists():
            ins.read(f"engineering/formalize/{rel}")
    passages = {"cantilever": ins.text("engineering/formalize/sources/cantilever_passage.txt"), "oca2": ins.text("engineering/formalize/sources/oca2_passage.txt"), "gc": ""}
    ex = []
    add = lambda eid, title, kind, req, case, note="", receipt=None: ex.append({"id": eid, "title": title, "kind": kind, "request": req, "passage": passages[case], "passage_sha256": digest_bytes(passages[case].encode()) if passages[case] else None, "note": note, "receipt": receipt})
    add("cantilever", "Cantilever tip deflection (human-written proposal)", "human fixture", cases.cantilever_request(), "cantilever", "The expected result is a checked proposal with a witness; translation fidelity is still unresolved.")
    for k, why in (("L2", "L cubed written as L squared: a dimension fault the checker should reject"), ("wrong_unit", "second moment of area declared in m squared: a unit fault"), ("drop_guard", "the small-deflection guard removed. The checker still reports checked: it tests consistency, and cannot see that the proposal no longer matches the source. That gap is what the unresolved-translation part is for."), ("flip_guard", "the guard inequality reversed. The checker still reports checked for the same reason: it cannot see a mismatch with the source.")):
        add("cantilever-" + k, "Cantilever with a deliberate fault: " + k.replace("_", " "), "negative control", cases.corrupt_cantilever(k), "cantilever", why)
    add("gc-feasible", "Oligonucleotide GC window (human-written, feasible)", "human fixture", cases.gc_design_request(), "gc", "A counting property only; says nothing about function.")
    if hasattr(cases, "gc_infeasible_request"):
        add("gc-infeasible", "Oligonucleotide GC window (human-written, infeasible)", "negative control", cases.gc_infeasible_request(), "gc", "The constraints cannot all hold; the checker should say unsat.")
    base = {"cantilever": cases.cantilever_request(), "oca2": cases.oca2_request()}
    for rd in sorted((fdir / "runs").glob("*")):
        rr = f"engineering/formalize/runs/{rd.name}"
        if not (rd / "receipt.json").exists():
            continue
        rc = json.loads(ins.read(f"{rr}/receipt.json")); raw = ins.text(f"{rr}/response.raw.txt") if (rd / "response.raw.txt").exists() else ""
        case = rc.get("case")
        try:
            prop = json.loads(raw)
        except Exception:
            prop = None
        receipt = {"model": rc.get("model_version_reported"), "provider": rc.get("provider"), "finish_reason": rc.get("finish_reason"), "outcome_status": (rc.get("outcome") or {}).get("status"), "parent_checker_status": rc.get("parent_checker_status"), "repair_of": rc.get("repair_of"),
                   "wall_s": rc.get("wall_s"), "tokens": {k: (rc.get("usage_reported_by_provider") or {}).get(k) for k in ("promptTokenCount", "candidatesTokenCount", "thoughtsTokenCount")}, "response_sha256": rc.get("response_sha256"), "path": rr}
        if prop is None or case not in base:
            ex.append({"id": "run-" + rd.name, "title": f"Recorded Gemini extraction {rd.name}", "kind": "recorded model proposal (not usable)", "request": None, "passage": passages.get(case, ""), "passage_sha256": rc.get("passage_sha256"), "note": "The model output is not valid JSON (finish reason " + str(rc.get("finish_reason")) + "), so there is nothing to check.", "receipt": receipt}); continue
        req = copy.deepcopy(base[case]); req["claim"]["id"] = f"{case}-recorded-{rd.name}"; req["proposal"] = prop
        ex.append({"id": "run-" + rd.name, "title": f"Recorded Gemini proposal {rd.name}", "kind": "recorded model proposal", "request": req, "passage": passages[case], "passage_sha256": rc.get("passage_sha256"), "note": "A model's proposal recorded earlier, shown unedited; the checker decides, the model does not. Its recorded checker outcome is in the receipt.", "receipt": receipt})
    return {"examples": ex, "schema": "frontier.formalize.request/1", "limits": {"max_bytes": 16384}}


def print_families(min_version: int = 1) -> list[Path]:
    """Discover numbered print editions without changing frozen earlier artifacts."""
    families = []
    for path in (ROOT / "artifacts").glob("print*"):
        match = re.fullmatch(r"print(?:-v([1-9][0-9]*))?", path.name)
        if path.is_dir() and match:
            version = int(match[1] or 1)
            if version >= min_version:
                families.append((version, path))
    return [path for _, path in sorted(families, key=lambda row: (row[0], row[1].name), reverse=True)]


def print_v3_block(ins: Inputs, out: dict) -> dict | None:
    """Publish the v3 prop contract and later editions; retain the existing wire key."""
    forms, refused, limitations, printer_resin = [], [], [], None
    ids = set()
    for directory in print_families(3):
        d = directory.relative_to(ROOT).as_posix()
        if not (directory / "downloads.json").is_file():
            continue
        data = json.loads(ins.read(f"{d}/downloads.json"))
        if data.get("schema") != "frontier.print.downloads/1":
            raise ValueError("Unsupported print downloads schema: " + d)
        printer_resin = printer_resin or data["printer_resin"]
        limitations.extend(x for x in data["limitations"] if x not in limitations)
        for form in data["forms"]:
            if form["id"] in ids:
                raise ValueError("Duplicate printable form: " + form["id"])
            ids.add(form["id"])
            files = []
            for item in form["files"]:
                if item["kind"] in ("glb_prop", "design_json"):
                    continue  # Full mesh downloads are also available in model_downloads.
                member = Path(item["path"])
                if member.is_absolute() or ".." in member.parts:
                    refused.append(f"{d}/{item['path']}")
                    continue
                href = f"{d}/{item['path']}"
                raw = ins.read(href) if (ROOT / href).is_file() else None
                if raw is None or digest_bytes(raw) != item["sha256"] or len(raw) != item["bytes"]:
                    refused.append(href)
                    continue
                out["@" + href] = raw
                files.append({"kind": item["kind"], "href": href, "bytes": item["bytes"], "sha256": item["sha256"], "units": item.get("units")})
            forms.append({"id": form["id"], "title": form.get("title") or form["id"], "short": form.get("short"), "display_scale": form["display_scale"], "prop_size_mm": form.get("prop_size_mm"), "source_candidate": form.get("source_candidate"), "source_candidate_sha256": form.get("source_candidate_sha256"), "family": directory.name, "files": files,
                          "why": form.get("why"), "wall_rule_mm": form.get("wall_rule_mm"),
                          "mass_conditional_g": form.get("mass_conditional_g"),
                          "mass_density_kg_m3": form.get("mass_density_kg_m3")})
    return {"forms": forms, "limitations": limitations, "printer_resin": printer_resin, "refused": refused} if forms else None


def model_downloads(ins: Inputs, out: dict) -> dict:
    """Publish print revisions from manifest-pinned bytes, including earlier editions."""
    manifests = [directory / "manifest.json" for directory in print_families()]
    manifests += sorted((ROOT / "artifacts/glider").glob("*/manifest.json"))
    defects_path = "artifacts/glider/KNOWN_DEFECTS.json"
    defects = json.loads(ins.read(defects_path)) if (ROOT / defects_path).is_file() else {}
    handedness = defects.get("right_hand_print_files_are_left_parts", {})
    groups, refused = [], []
    for path in manifests:
        if not path.is_file():
            continue
        directory = path.parent.relative_to(ROOT).as_posix()
        raw_manifest = ins.read(path.relative_to(ROOT).as_posix())
        manifest = json.loads(raw_manifest)
        withdrawn_right = manifest.get("revision") in handedness.get("revisions", [])
        files = []
        for rel, declared in manifest.get("files", {}).items():
            member = Path(rel)
            if member.is_absolute() or ".." in member.parts:
                refused.append(f"{directory}/{rel}")
                continue
            if member.suffix.lower() not in {".stl", ".glb", ".zip"}:
                continue
            source = path.parent / member
            data = ins.read(f"{directory}/{rel}") if source.is_file() else None
            if data is None or digest_bytes(data) != declared:
                refused.append(f"{directory}/{rel}")
                continue
            href = f"{directory}/{rel}"
            out["@" + href] = data
            withdrawn = withdrawn_right and "_R" in member.name and member.suffix == ".stl"
            files.append({"name": member.name, "href": href, "sha256": declared, "bytes": len(data), "format": member.suffix[1:].upper(),
                          "withdrawn": "Duplicates the left fin; use the corrected revision." if withdrawn else None})
        sidecar = path.parent / "download.json"
        if sidecar.is_file():
            bundle = json.loads(ins.read(sidecar.relative_to(ROOT).as_posix()))
            member = Path(bundle["path"])
            if member.is_relative_to(Path(directory)):
                member = member.relative_to(Path(directory))
            if member.is_absolute() or ".." in member.parts or member.suffix != ".zip":
                refused.append(f"{directory}/{member}")
            else:
                source = path.parent / member
                data = ins.read(f"{directory}/{member}") if source.is_file() else None
                if (data is None or len(data) != bundle["bytes"] or digest_bytes(data) != bundle["sha256"]
                        or bundle.get("manifest_sha256") != digest_bytes(raw_manifest)):
                    refused.append(f"{directory}/{member}")
                else:
                    href = f"{directory}/{member}"
                    out["@" + href] = data
                    files.insert(0, {"name": "Complete six-part test-print bundle", "href": href, "sha256": bundle["sha256"],
                                     "bytes": len(data), "format": "ZIP", "withdrawn": None})
        href = f"{directory}/manifest.json"
        out["@" + href] = raw_manifest
        groups.append({"id": directory, "title": manifest.get("revision") or path.parent.name,
                       "scope": "Untested launch prototype; inspect its failed constraints before printing." if "/glider/" in directory else "Display models; not flight-tested designs. STL units: mm.",
                       "warning": "Archived revision: right-fin print files are withdrawn because they duplicate left fins. Use r4-daane-printfix." if withdrawn_right else None,
                       "manifest_href": href, "files": files})
    return {"groups": groups, "refused": refused}


def print_laws(ins: Inputs, out: dict, downloads: dict) -> dict | None:
    """Only show grounding when its exact file pins match the published catalog."""
    path = "artifacts/print-law-index.json"
    if not (ROOT / path).is_file():
        return None
    raw = ins.read(path)
    index = json.loads(raw)
    catalog = {f["href"]: f for g in downloads["groups"] for f in g["files"]}
    rows = index.get("files", [])
    refused = [r.get("path", "missing path") for r in rows
               if r.get("path") not in catalog or r.get("sha256") != catalog[r["path"]]["sha256"]]
    indexed = {r.get("path") for r in rows}
    refused.extend(p for p, f in catalog.items() if f["format"] == "STL" and p not in indexed)
    if index.get("schema") != "frontier.print-law-index/1" or not rows or len(indexed) != len(rows):
        refused.append("index schema or cardinality")
    if refused:
        return {"data": None, "refused": sorted(set(refused))}
    out["@" + path] = raw
    return {"data": index, "href": path, "sha256": digest_bytes(raw), "refused": []}


def lean_proofs(ins: Inputs, out: dict) -> dict:
    module_path = "scripts/lean_gallery.py"
    ins.read(module_path)
    spec = importlib.util.spec_from_file_location("frontier_lean_gallery", ROOT / module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build(ins, out, root=ROOT)


def demo_videos(ins: Inputs, out: dict) -> dict | None:
    """Preserve earlier cuts while admitting an additive, completely pinned edit."""
    result = {"cuts": [], "refused": [], "limits": []}
    present = False
    for directory, expected in (("artifacts/demo-video", {"frontier-60s": 60, "frontier-120s": 120}),
                                ("artifacts/demo-video-90", {"frontier-90s": 90}),
                                ("artifacts/demo-video-science", {"frontier-science-60s": 60, "frontier-science-120s": 120}),
                                ("artifacts/demo-video-delphi", {"frontier-delphi-60s": 60, "frontier-delphi-120s": 120})):
        manifest = _demo_manifest(ins, out, directory, expected)
        if manifest is None:
            continue
        present = True
        result["cuts"].extend(manifest["cuts"])
        result["refused"].extend(manifest["refused"])
        result["limits"].extend(x for x in manifest["limits"] if x not in result["limits"])
    return result if present else None


def _demo_manifest(ins: Inputs, out: dict, directory: str, expected_cuts: dict) -> dict | None:
    """Publish complete edits only when every required media file matches its pin."""
    manifest_path = f"{directory}/manifest.json"
    if not (ROOT / manifest_path).is_file():
        return None
    manifest = ins.json(manifest_path)
    result = {"cuts": [], "refused": [], "limits": manifest.get("limits", [])}
    if manifest.get("status") != "complete":
        return result
    required = {"video": {".mp4"}, "poster": {".png", ".jpg"}, "captions": {".vtt"}, "transcript": {".txt"}}
    for cut in manifest.get("cuts", []):
        expected = expected_cuts.get(cut.get("id"))
        if expected is None or not isinstance(cut.get("duration_s"), (int, float)) or abs(cut["duration_s"] - expected) > 0.25:
            result["refused"].append({"id": cut.get("id"), "reason": "unexpected cut or duration"})
            continue
        pending, hrefs = {}, {}
        for role, extensions in required.items():
            pin = cut.get("files", {}).get(role, {})
            path = Path(pin.get("path", ""))
            rel = f"{directory}/{path.as_posix()}"
            limit = 64_000_000 if role == "video" else 16_000_000
            if path.is_absolute() or ".." in path.parts or path.suffix not in extensions or not (ROOT / rel).is_file():
                break
            if not (ROOT / rel).resolve().is_relative_to((ROOT / directory).resolve()):
                break
            size = (ROOT / rel).stat().st_size
            if not 0 < size <= limit or size != pin.get("bytes"):
                break
            data = ins.read(rel)
            if digest_bytes(data) != pin.get("sha256") or (role == "captions" and not data.startswith(b"WEBVTT")):
                break
            pending["@" + rel], hrefs[role] = data, rel
        else:
            out.update(pending)
            result["cuts"].append({"id": cut["id"], "title": cut["title"], "duration_s": cut["duration_s"],
                                   "href": hrefs["video"], "poster_href": hrefs["poster"],
                                   "subtitles_href": hrefs["captions"], "transcript_href": hrefs["transcript"],
                                   "manifest_href": manifest_path})
            continue
        result["refused"].append({"id": cut.get("id"), "reason": "required media missing, outside scope, oversized, or changed"})
    if result["cuts"]:
        out["@" + manifest_path] = ins.read(manifest_path)
    return result


def diffusion_pilot(ins: Inputs, out: dict) -> dict | None:
    """Recorded denoising frames and evaluation receipts, with failed checks preserved."""
    directory = "artifacts/rd-diffusion/visuals"
    manifest_path = f"{directory}/manifest.json"
    if not (ROOT / manifest_path).is_file():
        return None
    manifest = json.loads(ins.read(manifest_path))
    files, refused = [], []
    for name, pin in manifest["files"].items():
        rel = f"{directory}/{name}"
        data = ins.read(rel) if (ROOT / rel).is_file() else None
        if data is None or len(data) != pin["bytes"] or digest_bytes(data) != pin["sha256"]:
            refused.append(name)
            continue
        out["@" + rel] = data
        files.append({"name": name, "href": rel, **pin})
    receipts = {}
    sources = {
        "recovery": "results/infra/diffusion-recovery/results/infra25-rd-ddpm-evaluation-recovery/recovery-result.json",
        "secondary_audit": "results/infra/diffusion-secondary/collection-audit.json",
    }
    for kind, path in sources.items():
        if (ROOT / path).is_file():
            data = ins.read(path)
            href = f"artifacts/rd-diffusion/{kind}.json"
            out["@" + href] = data
            receipts[kind] = {"href": href, "sha256": digest_bytes(data), "data": json.loads(data)}
    out["@" + manifest_path] = ins.read(manifest_path)
    return {"manifest": manifest, "manifest_href": manifest_path, "files": files, "refused": refused, "receipts": receipts}


def runtime_inputs(ins: Inputs, out: dict, stem: str) -> dict | None:
    """Publish a fixed runtime archive only when its sidecar digest and size match."""
    d = "artifacts/rd-diffusion"; sc = f"{d}/{stem}.json"; ar = f"{d}/{stem}.tar.xz"
    if not ((ROOT / sc).exists() and (ROOT / ar).exists()):
        return None
    m = json.loads(ins.read(sc)); b = ins.read(ar)
    ok = len(b) == m["bytes"] and digest_bytes(b) == m["archive_sha256"]
    if ok:
        out["@" + ar] = b; out["@" + sc] = ins.read(sc)
    return {**m, "published": ok, "href": ar if ok else None, "sha256": m["archive_sha256"], "sidecar": sc}


def recovery_inputs(ins: Inputs, out: dict) -> dict | None:
    """Original failed primary inputs retain their status separately from recovery."""
    m = runtime_inputs(ins, out, "primary-runtime-inputs")
    if m is None:
        return None
    return {"published": m["published"], "href": m["href"], "bytes": m["bytes"], "sha256": m["archive_sha256"], "status": m["status"], "training_steps": m["training_steps"], "checkpoint_sha256": m["checkpoint_sha256"],
            "primary_full_run_status": m["primary_full_run_status"], "original_primary_job_id": m["original_primary_job_id"], "next_admission": m["next_admission"], "members": m["files"], "sidecar": m["sidecar"]}


def fish_history(ins: Inputs) -> dict | None:
    """Design lineage read from the manifests that state it: print v1 sets (siblings), print v2 `supersedes` (chronological revisions), the 3D baseline's
    from_print_form, v3 candidates' baseline_candidate/variant (siblings differing only in knobs) and each display prop's source_candidate. Nothing is inferred.
    Dates are the author date of the first commit that added each manifest in this repository: a repository fact, not a design date."""
    import subprocess
    def first_commit(path):
        try:
            r = subprocess.run(["git", "-C", str(ROOT), "log", "--diff-filter=A", "--format=%aI", "--", path], capture_output=True, text=True, timeout=20)
            lines = [x for x in r.stdout.split() if x]
            return lines[-1] if lines else None                    # the oldest add of that path
        except Exception:
            return None
    need = ["artifacts/print/manifest.json", "artifacts/print-v2/manifest.json", "artifacts/fish3d/v3-index.json", "artifacts/print-v3/downloads.json"]
    if not all((ROOT / n).exists() for n in need):
        return None
    P1 = json.loads(ins.read(need[0])); P2 = json.loads(ins.read(need[1])); V3 = json.loads(ins.read(need[2]))
    nodes, edges, sib = [], [], []
    mk = lambda i, kind, title, man, extra=None: nodes.append({"id": i, "kind": kind, "title": title, "manifest": man, "manifest_sha256": ins.seen[man]["sha256"] if man in ins.seen else None, "first_commit_date": first_commit(man), **(extra or {})})
    sets1 = P1.get("sets", {}); sets2 = P2.get("sets", {})
    for sname, S in sets1.items():
        for fid in S["forms"]:
            mk(fid, "print form v1 (display scale)", fid, "artifacts/print/manifest.json", {"set": sname, "display_scale": S.get("display_scale")})
        sib.append({"group": sname, "members": S["forms"], "basis": "listed together in one set of artifacts/print/manifest.json; they differ in the parameters that manifest names", "manifest": "artifacts/print/manifest.json"})
    for sname, S in sets2.items():
        for fid in S["forms"]:
            mk(fid, "print form v2 (display scale)", fid, "artifacts/print-v2/manifest.json", {"set": sname, "display_scale": S.get("display_scale")})
        sib.append({"group": sname, "members": S["forms"], "basis": "listed together in one set of artifacts/print-v2/manifest.json", "manifest": "artifacts/print-v2/manifest.json"})
    for new, old in (P2.get("edition") or {}).get("supersedes", {}).items():
        edges.append({"from": new, "to": old, "relation": "revision", "label": "v2 supersedes v1 (the v1 files stay as published)", "source": "artifacts/print-v2/manifest.json: edition.supersedes", "chronological": True})
    base = V3["baseline"]; bc = json.loads(ins.read(f"artifacts/fish3d/{base}/candidate.json"))
    mk(base, "3D candidate (1:1)", "N1 baseline, flat fin plates", f"artifacts/fish3d/{base}/candidate.json", {"set": None})
    if bc.get("from_print_form"):
        edges.append({"from": base, "to": bc["from_print_form"], "relation": "built from", "label": "sized from the v1 print form's parameters", "source": f"artifacts/fish3d/{base}/candidate.json: from_print_form", "chronological": False})
    group = []
    for vid, meta in V3["candidates"].items():
        cj = f"artifacts/fish3d/{vid}/candidate.json"
        if not (ROOT / cj).exists():
            continue
        c = json.loads(ins.read(cj)); mk(vid, "3D candidate (1:1)", c.get("title") or vid, cj, {"candidate_sha256": meta["candidate_sha256"], "knobs": meta["knobs"]}); group.append(vid)
        edges.append({"from": vid, "to": c.get("baseline_candidate", base), "relation": "variant of", "label": "v3 rebuild of the baseline; siblings differ only in knobs", "source": f"{cj}: baseline_candidate", "chronological": False})
    sib.append({"group": "v3 variants", "members": group, "basis": V3["shared"], "manifest": need[2]})
    for directory in print_families(3):
        path = (directory / "downloads.json").relative_to(ROOT).as_posix()
        if not (ROOT / path).is_file():
            continue
        for f in json.loads(ins.read(path))["forms"]:
            mk(f["id"], "display prop (print, not a launch prototype)", f.get("title") or f["id"], path, {"display_scale": f["display_scale"], "set": f.get("set")})
            edges.append({"from": f["id"], "to": f["source_candidate"], "relation": "printed from", "label": "display prop made from this 3D candidate", "source": f"{path}: forms[].source_candidate", "chronological": False})
    # Launch glider print sets: lineage comes only from each manifest's parent_revision and source_candidate pins; chronology is never inferred from the names.
    gd = ROOT / "artifacts/glider"; gl = []
    defects = json.loads(ins.read("artifacts/glider/KNOWN_DEFECTS.json")) if (gd / "KNOWN_DEFECTS.json").exists() else {}
    bad_revs = {r: k for k, v in defects.items() if isinstance(v, dict) for r in v.get("revisions", [])}
    for mp in (sorted(gd.glob("*/manifest.json")) if gd.exists() else []):
        mrel = mp.relative_to(ROOT).as_posix(); m = json.loads(ins.read(mrel)); rid = m["revision"]; sc = m.get("source_candidate", {})
        ok_pin = sc.get("id") in V3["candidates"] and V3["candidates"][sc["id"]]["candidate_sha256"] == sc.get("sha256")
        bad = defects.get(bad_revs.get(rid), {}) if rid in bad_revs else {}
        mk("glider-" + rid, "launch glider print set (a launch prototype, untested)", m.get("title") or rid, mrel, {"revision": rid, "parent_revision": m.get("parent_revision"), "pin_matches_v3_index": ok_pin,
           "known_defect": bad.get("what"), "fixed_in": bad.get("fixed_in"), "label": m.get("label", "")[:300], "source_candidate": sc.get("id")})
        gl.append(rid)
        if m.get("parent_revision"):
            edges.append({"from": "glider-" + rid, "to": "glider-" + m["parent_revision"], "relation": "revision", "label": "named as parent_revision in the manifest (not inferred from the names)", "source": mrel + ": parent_revision", "chronological": True})
        if sc.get("id") and ok_pin:
            edges.append({"from": "glider-" + rid, "to": sc["id"], "relation": "built from", "label": "source_candidate, pinned by sha256 and matching the v3 index", "source": mrel + ": source_candidate", "chronological": False})
    lp = {"exists": bool(gl), "revisions": gl, "note": ("Launch glider print sets exist as manifests (" + ", ".join(gl) + "). Every one is labelled a launch prototype, untested: not printed, weighed, glided or thrown here." if gl else "No launch-prototype artifact is in the tree: source owners are still preparing it. Nothing is shown in its place.")}
    return {"nodes": nodes, "edges": edges, "siblings": sib, "launch_prototype": lp,
            "date_basis": "Author date of the first commit that added the node's manifest in this repository (a repository fact, not the date the design was made); null when git history is unavailable."}


def regulatory_map(ins: Inputs) -> dict | None:
    """Fish cell-regulatory applicability map (source-only): the seven cell programs, four datasets, four coupling ports (all unknown), proposed next actions and the source list.
    Local response paths are dropped; nothing is added or inferred here."""
    d = "artifacts/fish-regulatory-map"
    if not (ROOT / d / "map.json").exists():
        return None
    M = json.loads(ins.read(f"{d}/map.json")); S = json.loads(ins.read(f"{d}/sources.json")); man = json.loads(ins.read(f"{d}/manifest.json"))
    return {"status": M["status"], "organism": M["organism"], "target_organism_transfer": M["target_organism_transfer"], "rows": M["rows"], "datasets": M["datasets"], "coupling_ports": M["coupling_ports"], "next_actions": M["proposed_next_actions"],
            "flags": {k: M[k] for k in ("blocked_generation_replayed", "new_model_inference_performed", "whole_organism_genome_design_available", "biological_success_probability")},
            "sources": [{k: x.get(k) for k in ("id", "primary_url", "response_sha256", "response_bytes", "read_scope", "evidence_status")} for x in S["sources"]], "not_performed": S.get("not_performed", []),
            "excluded": {"reason": S["excluded_response"]["reason"], "sha256": S["excluded_response"]["sha256"]} if S.get("excluded_response") else None,
            "files": man["files"], "manifest": f"{d}/manifest.json"}


def claim_reuse_block(ins: Inputs) -> dict | None:
    """A worked example of exact Claim reuse and an independent dispute: two distinct Actions consumed the same exact Claim version before their solver ran; an independent
    reviewer recorded both Evidence as disputed. Everything is copied from the producer audit, the review readback and the author response; no benefit is computed."""
    d = "artifacts/claim-reuse"; rv = "docs/reviews/fin-reuse-review-run/readback"
    if not ((ROOT / d / "audit.json").exists() and (ROOT / rv / "assessment-above.json").exists()):
        return None
    A = json.loads(ins.read(f"{d}/audit.json")); E = json.loads(ins.read(f"{d}/reuse-verification.json")); reviews = []
    for n in ("below", "above"):
        r = json.loads(ins.read(f"{rv}/assessment-{n}.json")); pl = r["record"]["payload"]
        reviews.append({"case": n, "reviewer": r["record"]["issuer"], "policy": r["policy_version"], "decision": pl["decision"], "assessment_id": r["record"]["id"], "created_at": r["record"]["created_at"],
                        "dimensions": {k: {"status": v.get("status"), "rationale": v.get("rationale", "")} for k, v in pl["dimensions"].items()}})
    return {"claim_ref": A["claim_ref"], "distinct_actions": A["distinct_current_action_ids_with_recorded_input_use"], "causal_order_checked": A["causal_read_and_input_binding_before_each_solver"],
            "cases": [{k: c.get(k) for k in ("case", "action_ref", "evidence_ref", "parsed_EIcrit_Nm2_exact", "solver_EI_Nm2_exact", "tip_over_L", "tip_over_L_limit", "max_slope_rad", "model_domain_valid", "numerical_checks_passed", "result_sha256", "action_state_at_readback", "evidence_status_at_submission", "wall_seconds")} for c in A["cases"]],
            "edges": E["edges"], "edges_truncated": E["truncated"], "reviews": reviews,
            "not_established": {"time_or_cost_saved": A["time_or_cost_saved"], "collective_benefit": A["collective_benefit"], "biological_success_probability": A["biological_success_probability"], "empirical_validation": A["empirical_validation"]},
            "scope": A["scope"], "original_proposals": A["original_proposals"], "readme": ins.text(f"{d}/README.md"), "author_response": ins.text(f"{d}/author-response.md"),
            "audit": f"{d}/audit.json", "audit_sha256": ins.seen[f"{d}/audit.json"]["sha256"], "review_readback": rv}


def genetic_blueprints(ins: Inputs) -> dict | None:
    """Genetic implementation blueprints (SPEC-012): source-backed PROPOSED designs in zebrafish, copied as written. No sequence, effector or coefficient is added; unknowns stay as the package states them."""
    d = "artifacts/genetic-blueprints"
    if not (ROOT / d / "blueprints.json").exists():
        return None
    B = json.loads(ins.read(f"{d}/blueprints.json")); S = json.loads(ins.read(f"{d}/sources.json")) if (ROOT / d / "sources.json").exists() else {}
    return {"status": B["status"], "species_scope": B["species_scope"], "date": B["date"], "designs": B["designs"], "comparison": B["comparison"], "global_causal_gaps": B["global_causal_gaps"], "not_done": B["not_done"],
            "inputs": B["inputs"], "citations": B["citation_table"], "revision": B.get("revision"), "revision_log": B.get("revision_log", []), "parent": B.get("parent"), "cell_programs": B.get("cell_program_blueprints", []), "actors": B.get("regulatory_actors"), "claim_ledger": B.get("claim_use_ledger"), "source_status": S.get("status"), "source_index": {x["id"]: {k: x.get(k) for k in ("citation", "primary_url", "read_level")} for x in S.get("sources", []) if x.get("id")}, "files": {"blueprints.json": ins.seen[f"{d}/blueprints.json"]["sha256"], "sources.json": ins.seen.get(f"{d}/sources.json", {}).get("sha256")}}


def openresearch_exemplars(ins: Inputs) -> dict | None:
    """Two real local OpenResearch (orx) runs recorded as provenance exemplars. OpenResearch is a local recorder of which code was run, not a cloud dispatcher; fields are copied from the run records."""
    a = "connectors/biomodels/orx/orx_facts.json"; b = "frontier_adapters/examples/orx_run_turing"
    if not ((ROOT / a).exists() and (ROOT / b / "run.json").exists()):
        return None
    iso = lambda ms: datetime.datetime.fromtimestamp(ms / 1000, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    F = json.loads(ins.read(a)); R = json.loads(ins.read(f"{b}/run.json"))["run"]; H = json.loads(ins.read(f"{b}/health.json")); ec = ins.text(f"{b}/exit_code").strip()
    log = ins.text(f"{b}/log"); first = log.splitlines()[0] if log else ""
    ex = [{"title": F["experiment_title"], "command": F["command"], "backend": F["backend_kind"], "commit": F["commit_sha"], "started_utc": iso(F["created_ms"]), "duration_s": round((F["ended_ms"] - F["created_ms"]) / 1000, 2), "exit_code_file": F["exit_code_file"], "db_exit_code": F["db_exit_code"], "status": F["status"],
           "source_tar_sha256": F["source_tar_sha256"], "outputs": [{"path": o["path"], "sha256": o["sha256"], "bytes": o["bytes"]} for o in F["outputs"]], "replay_checks": F["replay_comparison"], "orx_version": F["orx_version"], "note": F["orx_version_note"], "record": a},
          {"title": "Neumann-mode Turing scan (exact rationals)", "command": R["command"], "backend": R["backend"]["kind"], "commit": R["commitSha"], "started_utc": iso(R["createdAt"]), "duration_s": round((R["endedAt"] - R["createdAt"]) / 1000, 2), "exit_code_file": int(ec) if ec.isdigit() else ec, "db_exit_code": None, "status": R["status"],
           "source_tar_sha256": R["backend"]["sourceDigest"], "outputs": [{"path": "results.json", "sha256": first.split("sha256 ")[-1] if "sha256 " in first else None, "bytes": None}], "replay_checks": None, "orx_version": "orx " + H["version"], "note": "outputs are not registered by orx; the digest is the producer's own printed line", "record": b + "/run.json"}]
    return {"exemplars": ex, "scope": "OpenResearch is a local recorder of which code was run. It is not a cloud dispatcher and none of these runs used a remote backend. A completed run is evidence that this code at this commit exited 0 and printed this, not that the science is right.", "report": "OpenResearch integration note (corpus session, single reader, not independently reviewed)"}


def planner_plan(ins: Inputs, base: Path, d: str) -> dict | None:
    """Structured projection of the planner's result.json: values copied, hashes checked against the planner's own manifest. Prospective calculation only."""
    rp, mp = base / "result.json", base / "manifest.json"
    if not rp.is_file():
        return None
    r = json.loads(ins.read(f"{d}/result.json")); declared = {}
    if mp.is_file():
        declared = (json.loads(ins.read(f"{d}/manifest.json")).get("files") or {}).get("result.json", {}).get("sha256")
    got = ins.seen[f"{d}/result.json"]["sha256"]; aa = r.get("action_artifact") or {}; ap = aa.get("action_proposal") or {}
    designs = []
    for x in r.get("designs", []):
        i = x.get("identifiability") or {}
        designs.append({"id": x["id"], "intervention": x.get("intervention"), "cost": x.get("cost"), "cost_unit": x.get("cost_unit"), "cost_basis": x.get("cost_basis"),
                        "rank": i.get("rank"), "parameter_count": i.get("parameter_count"), "full_rank": i.get("full_rank"), "nullspace_basis": i.get("nullspace_basis"),
                        "singular_values": i.get("singular_values"), "target_prior_variance": x.get("target_prior_variance"),
                        "target_posterior_variance": x.get("expected_target_posterior_variance"), "variance_reduction": x.get("expected_target_variance_reduction"),
                        "reduction_per_cost": x.get("expected_target_variance_reduction_per_cost"), "posterior_covariance": x.get("expected_posterior_covariance"),
                        "observations": x.get("observations"), "measurement_rows": len(x.get("measurement_rows") or [])})
    designs.sort(key=lambda z: -(z["reduction_per_cost"] or 0))
    for n, z in enumerate(designs, 1):
        z["objective_order"] = n
    return {"result_path": f"{d}/result.json", "result_sha256": got, "declared_sha256": declared or None, "hash_matches_manifest": bool(declared) and declared == got,
            "schema": r.get("schema"), "status": r.get("status"), "design_version": r.get("design_version"), "protocol_sha256": r.get("protocol_sha256"),
            "selected_design_id": r.get("selected_design_id"), "objective": r.get("selection_objective"), "target": r.get("target"), "equation": r.get("equation"),
            "parameters": r.get("parameters"), "designs": designs, "measurement_rows": len(r.get("measurement_rows") or []), "controls": r.get("controls"),
            "assumptions": ap.get("assumptions"), "limitations": ap.get("limitations"), "link_blockers": aa.get("link_blockers"), "state": aa.get("state"),
            "links": aa.get("links"), "context": r.get("context"), "model_discrepancy": r.get("model_discrepancy"), "held_out_validation": r.get("held_out_validation"),
            "replicate_unit": r.get("replicate_unit"), "batch_effects": r.get("batch_effects"), "stop_rules": r.get("stop_rules"), "observed_result": aa.get("observed_result")}


def experimentation_block(ins: Inputs) -> dict | None:
    """SPEC-013's bridge table (parsed from the spec, not retyped) and the planner's artifacts when they exist. Measurement categories are not experiments run; no observation is invented."""
    sp = "specs/SPEC-013-adaptive-experimentation.md"
    if not (ROOT / sp).exists():
        return None
    t = ins.text(sp); rows = []; grab = False
    for line in t.splitlines():
        if line.startswith("| Bridge |"):
            grab = True; continue
        if grab:
            if not line.startswith("|"):
                break
            if set(line.replace("|", "").strip()) <= set("- "):
                continue
            c = [x.strip() for x in line.strip().strip("|").split("|")]
            if len(c) >= 2:
                rows.append({"bridge": c[0], "measure": c[1]})
    states = re.search(r"Protocol hash, ([^\n]+?) states and lineage", t)
    out = {"spec": sp, "bridges": rows, "states_text": states.group(1) if states else None, "planner": None}
    for d in ("artifacts/experimental-design", "engineering/experimental_design/artifacts/experimental-design"):
        base = ROOT / d
        if base.is_dir():
            files = sorted(f for f in base.rglob("*") if f.is_file() and f.suffix in (".json", ".md"))
            listing = []
            for f in files[:40]:
                rel = f.relative_to(ROOT).as_posix(); b = ins.read(rel)
                schema = None
                if f.suffix == ".json":
                    try:
                        schema = json.loads(b).get("schema")
                    except Exception:
                        schema = None
                listing.append({"path": rel, "sha256": digest_bytes(b), "bytes": len(b), "schema": schema})
            out["planner"] = {"dir": d, "files": listing, "plan": planner_plan(ins, base, d)}
            break
    return out


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


def observed_update_cards(ins: Inputs, out: dict) -> list[dict]:
    """Expose the pinned observed-data update through the common evidence gallery."""
    module_path = "engineering/observed_update/site.py"
    ins.read(module_path)
    spec = importlib.util.spec_from_file_location("frontier_observed_update", ROOT / module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    card = module.build(ins, out)
    f = card["facts"]
    card.update({
        "time": {"units": "cross-sectional specimen measurements; no trajectory", "note": "No new wet-lab measurements."},
        "numerical_checks": [
            {"name": "Held-out-species log10 RMSE", "result": f"WORSENED: {f['heldout_RMSE_log10']['heldout_before']:.6f} → {f['heldout_RMSE_log10']['heldout_after']:.6f}"},
            {"name": "Prediction at standard length 8.35 cm", "result": f"{f['prediction_before_cm']:.5f} → {f['prediction_after_cm']:.5f} cm after adding 19 specimen rows"},
            {"name": "Exact-version cache", "result": "Stale result rejected and recomputed"},
            {"name": "Import read-back", "result": "6 typed records read back; imported_unreviewed, Action proposed"}],
        "parameter_unknowns": ["Transfer to zebrafish, growth dynamics and causal genetic effects are uncalibrated.", "Only three flying-fish species; working uncertainty bands are not calibrated population confidence."],
        "open_questions": ["Which additional species or growth-stage observations would improve held-out transfer?"],
        "couplings": [], "manifest_href": card["manifest"],
        "sources": card["sources"] + [
            {"label": "Measurements and fitted predictions", "href": card["report"], "locator": "Source observations remain separate from model predictions."},
            {"label": "Corrected record bundle", "href": card["current_bundle_href"], "locator": "Exact Claim, Evidence, Problem and proposed Action versions."},
            {"label": "Live import receipt", "href": card["import_receipt_href"], "locator": card["record_status"]},
            {"label": "Grouping correction and preserved history", "href": card["correction_report"], "locator": "Original and corrected scientific outputs match on this dataset."}],
        "files": [{"name": "Source observations CSV", **next(x for x in card["downloads"] if x["path"].endswith("/source-observations.csv"))}],
    })
    return [card]


def engineering_cards(ins: Inputs, out: dict) -> list[dict]:
    """Wind-tunnel, behavior controller and scale-growth manifests as gallery cards, with equations, sources and limitations.
    Every number is copied from the worker's own receipt; verdicts and misses are carried, never softened."""
    cards = []
    if (ROOT / "artifacts/fin-ray/artifact-manifest.json").is_file():
        module_path = "engineering/fin_ray/site.py"
        ins.read(module_path)
        spec = importlib.util.spec_from_file_location("frontier_fin_ray_card", ROOT / module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cards.append(module.build_card(ins.read, lambda name, sha: _vid(
            ins, out, "fin-ray-bilaminar", "artifacts/fin-ray", name, sha)))
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
    d = "artifacts/bioelectric-tissue"
    if (ROOT / d / "summary.json").exists():
        sm = json.loads(ins.read(f"{d}/summary.json")); ef = sm["effects"]; ku, gb, kg = ef["k_up"], ef["gj_block"], ef.get("k_up_gj_block", {})
        st, href = _vid(ins, out, "betse-tissue", d, "bioelectric_tissue.mp4", None, allow_unpinned=True); _, ph = _vid(ins, out, "betse-tissue", d, "poster.png", None, allow_unpinned=True)
        cards.append({"id": "betse-tissue", "title": "BETSE bioelectric tissue patch: potassium permeability and gap-junction block", "scales": ["tissue", "cellular"], "evidence_kind": "SimulationResult (" + sm["label"] + ")",
            "model": {"name": sm["betse"] + ", official seed/init/sim", "context": f"{sm['n_cells']} cells, {sm['n_membranes']} membranes on a hexagonal patch; electrodiffusion with gap junctions and an electrogenic pump; {sm['samples']} samples over {sm['time_s'][1]:.1f} s; intervention window {sm['intervention_window_s'][0]} to {sm['intervention_window_s'][1]} s on {ku['n_targeted_cells']} targeted cells. The potassium change is a generic membrane-permeability scale, not a named channel."},
            "time": {"units": "seconds of model time", "note": "Five scenarios from one seeded world: baseline, K+ permeability up, gap junctions blocked, both, baseline at half time step."},
            "video": {"file": "bioelectric_tissue.mp4", "sha256": None, "note": "No digest is declared for this movie in the worker's summary; the build copied the file but could not check it against a declaration."}, "video_state": st, "video_href": href, "poster_href": ph,
            "numerical_checks": [{"name": k.replace("_", " "), "result": "passed" if v.get("ok") else "FAILED"} for k, v in sm["checks"].items()]
                + [{"name": "K+ up: peak change in targeted cells", "result": f"{ku['targeted_peak_dVm_mV']:.2f} mV; {ku['other_peak_dVm_mV']:.2f} mV in the {ku['n_other_cells']} untargeted cells (spread through gap junctions)"}, {"name": "gap junctions blocked alone", "result": f"{gb['targeted_peak_dVm_mV']:.3f} mV targeted, {gb['other_peak_dVm_mV']:.3f} mV untargeted"}]
                + ([{"name": "K+ up with junctions blocked", "result": f"{kg['targeted_peak_dVm_mV']:.2f} mV targeted; {kg['other_peak_dVm_mV']:.2f} mV untargeted"}] if kg else []),
            "parameter_unknowns": ["Not calibrated to any fish cell, fin or channel (Kir2.1 is not modelled).", "Concentrations and permeabilities are BETSE defaults and the worker's scale factors."],
            "open_questions": ["Which measured cell-type voltage and permeability data would calibrate this patch?", "How would tissue voltage map to a fin growth law? No such bridge exists."],
            "limitations": ["Simulated numerical output, not observed, not calibrated, not a fish fin.", "Single-reader work: not independently reviewed."], "couplings": [], "manifest": f"{d}/summary.json", "native": True})
    sensitivity = "artifacts/bioelectric-tissue/sensitivity-v1/index.json"
    if (ROOT / sensitivity).is_file():
        module_path = "engineering/bioelectric_tissue/sensitivity_site.py"
        ins.read(module_path)
        spec = importlib.util.spec_from_file_location("frontier_betse_sensitivity_card", ROOT / module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cards.append(module.build_card(ins.read, lambda name, sha: _vid(
            ins, out, "betse-k-sensitivity-v1", "artifacts/bioelectric-tissue/sensitivity-v1", name, sha)))
    d = "artifacts/multicell"
    if (ROOT / d / "summary.json").exists():
        sm = json.loads(ins.read(f"{d}/summary.json")); arms = sm["arms"]; shas = {l.split()[1].split("/")[-1]: l.split()[0] for l in ins.text(f"{d}/mp4.sha256").splitlines() if l.strip()}
        fh = json.loads(ins.read(f"{d}/full/full_summary.json")) if (ROOT / d / "full/full_summary.json").exists() else None
        st, href = _vid(ins, out, "morpheus-multicell", d, "baseline.mp4", shas.get("baseline.mp4"))
        cards.append({"id": "morpheus-multicell", "title": "Morpheus multicellular growth: cell cycle, division, cytokine feedback (baseline arm)", "scales": ["tissue", "cellular"], "evidence_kind": "SimulationResult (generic example model)",
            "model": {"name": "Morpheus v2.3.9 official multiscale example (cell-cycle ODE, cellular Potts division, cytokine PDE, feedback)", "context": f"The first three arms ran headless and each hit the 600 s cap at model time {sm['common_horizon_t']} of a 2.0 horizon; a later full-horizon rerun reached t = 2.0 (see the limitations). Generic and not calibrated; not fish growth."},
            "time": {"units": "model time units (example model)", "note": "All arms are compared at the common horizon; none reached the planned end."},
            "video": {"file": "baseline.mp4", "sha256": shas.get("baseline.mp4"), "note": "22 frames"}, "video_state": st, "video_href": href, "poster_href": None,
            "numerical_checks": [{"name": f"arm {a}", "result": f"{v['cells_at_common_horizon']} cells at t={v['reached_t']}; divisions at {v['division_event_times_to_horizon']}; max cdk1 {v['max_cdk1']:.3f}"} for a, v in arms.items()],
            "parameter_unknowns": ["Not calibrated to any organism.", "The early-window arms stopped at the 600 s cap. Only one seed repeat exists; there is no refinement study."],
            "open_questions": ["Is the feedback effect on cell count robust across more seeds and a finer time step? One repeat and one step size exist."],
            "limitations": ["Generic example, not fish growth.", "Seed repeat is one repeat, not an uncertainty estimate.", "Two further arm movies (feedback-off, seed repeat) exist in artifacts/multicell and are not shown here."] + ([f"Full horizon (t = 2.0, exit 0): baseline {fh['baseline']['final_cells']} cells, feedback-off {fh['nofeedback']['final_cells']}, seed repeat {fh['seed2']['final_cells']}; the movie above is the early window only." ] if fh else []), "couplings": [], "manifest": f"{d}/summary.json", "native": True})
    d = "artifacts/molecular"
    if (ROOT / d / "cuda-render/render.json").exists() and (ROOT / d / "cuda-analysis/ensemble.json").exists():
        rr = json.loads(ins.read(f"{d}/cuda-render/render.json")); en = json.loads(ins.read(f"{d}/cuda-analysis/ensemble.json")); o = rr["outputs"]; runs = en["runs"]; ds = en["descriptive_endpoint_CA_RMSD_nm"]
        st, href = _vid(ins, out, "molecular-md-cuda", f"{d}/cuda-render", "trajectory.mp4", o["trajectory.mp4"]); _, ph = _vid(ins, out, "molecular-md-cuda", f"{d}/cuda-render", "poster.png", o["poster.png"])
        cards.append({"id": "molecular-md-cuda", "title": "Collagen-mimetic trimer: three 100 ps molecular dynamics runs on an H100 (OpenMM, CUDA)", "scales": ["molecular"], "evidence_kind": rr["kind"] + "; computed ensemble of declared seeds",
            "model": {"name": "OpenMM classical atomistic MD, CUDA backend, ff14SB with TIP3P water", "context": f"{len(runs)} runs (seeds {', '.join(str(r['seed']) for r in runs)}), each {runs[0]['production_ps']:.0f} ps production after {runs[0]['preliminary_thermalization_ps']:.0f} ps thermalization, {runs[0]['frames']} saved states per run. The movie shows seed {rr['seed']}. One structure, one solvent system, one force field and one assumed 300 K condition are shared by all runs."},
            "time": {"units": "picoseconds of simulated time", "note": f"{rr['frames']} frames at {rr['display_fps']} fps; rigid alignment for display only. Duration is not a relaxation time."},
            "video": {"file": "trajectory.mp4", "sha256": o["trajectory.mp4"], "note": ""}, "video_state": st, "video_href": href, "poster_href": ph,
            "numerical_checks": [{"name": f"seed {r['seed']}", "result": f"CA RMSD from production start {r['final_CA_RMSD_from_production_start_nm']:.3f} nm; kinetic temperature {r['kinetic_temperature_range_K'][0]:.0f} to {r['kinetic_temperature_range_K'][1]:.0f} K; last 20% mean {r['last_20_percent_sampled_temperature_mean_K']:.1f} ± {r['last_20_percent_sampled_temperature_SD_K']:.1f} K"} for r in runs]
                + [{"name": "endpoint CA RMSD across seeds", "result": f"mean {ds['mean']:.3f} nm, sample SD {ds['sample_SD']:.3f} nm, range {ds['minimum']:.3f} to {ds['maximum']:.3f} nm (n = {ds['n_runs']})"}],
            "parameter_unknowns": ["Empirical accuracy: " + str(en["empirical_accuracy"]) + ".", "Equilibrated ensemble: " + str(en["equilibrated_ensemble"]) + ".", "Tissue material modulus: not computed (null)."],
            "open_questions": ["Do longer runs from different starting structures change any observable? Warm-start parents for a next job are recorded in warmstart-v3.json."],
            "limitations": [en["scope"], "Biological success probability: null (not computed).", "Synthetic collagen-mimetic peptide, not a fish protein.", "The earlier 0.2 ps CPU setup run is a separate card and is not part of this ensemble."], "couplings": [], "manifest": f"{d}/cuda-render/render.json", "native": True})
    d = "artifacts/molecular"
    if (ROOT / d / "continuation-render/render.json").exists() and (ROOT / d / "continuation-analysis/summary.json").exists():
        rr = json.loads(ins.read(f"{d}/continuation-render/render.json")); an = json.loads(ins.read(f"{d}/continuation-analysis/summary.json")); o = rr["outputs"]
        st, href = _vid(ins, out, "molecular-md-continuation", f"{d}/continuation-render", "trajectory.mp4", o["trajectory.mp4"]); _, ph = _vid(ins, out, "molecular-md-continuation", f"{d}/continuation-render", "poster.png", o["poster.png"])
        br = an["branches"]; drift = [b["predeclared_diagnostic"]["small_window_drift"] for b in br]
        cards.append({"id": "molecular-md-continuation", "title": "Collagen-mimetic trimer: three 900 ps continuations from the 100 ps states (OpenMM, CUDA)", "scales": ["molecular"], "evidence_kind": rr["kind"] + "; conditional branches, not independent samples",
            "model": {"name": "OpenMM classical MD continued from each parent's final saved state with a new thermostat seed", "context": f"{an['n_parent_branches']} branches reach global production time {br[0]['global_production_end_ps']:.0f} ps. The movie shows seed {rr['seed']} ({rr['frames']} saved states over {rr['simulation_duration_ps']:.0f} ps, global {rr['global_production_time_ps'][0]:.0f} to {rr['global_production_time_ps'][1]:.0f} ps). Each branch starts from one shared parent state, so the branches are conditional, not independent."},
            "time": {"units": "picoseconds of simulated time", "note": f"{rr['frames']} frames at {rr['display_fps']} fps; rigid alignment for display only. RMSD reference: {rr['RMSD_reference']}."},
            "video": {"file": "trajectory.mp4", "sha256": o["trajectory.mp4"], "note": ""}, "video_state": st, "video_href": href, "poster_href": ph,
            "numerical_checks": [{"name": f"branch from seed {b['parent_seed']} (thermostat seed {b['new_thermostat_seed']})", "result": f"final CA RMSD from the original reference {b['final_original_reference_CA_RMSD_nm']:.3f} nm; CA radius of gyration {b['final_CA_geometric_Rg_nm']:.3f} nm; predeclared small-window drift: {'TRUE' if b['predeclared_diagnostic']['small_window_drift'] else 'false'} (RMSD window means differ by {b['predeclared_diagnostic']['RMSD_window_mean_change_nm']:.4f} nm)"} for b in br]
                + [{"name": "predeclared drift diagnostic", "result": f"true for {an['small_window_drift_diagnostic_count']} of {an['diagnostic_denominator']} branches; false outcomes are kept"}, {"name": "new independent biological samples", "result": str(an["n_new_independent_biological_samples"])}],
            "parameter_unknowns": ["Empirical accuracy: " + str(an["empirical_accuracy"]) + ".", "Biological success probability: null (not computed).", "Equilibrium and material modulus are not established."],
            "open_questions": ["Do longer runs from different starting structures change any observable? These branches share one parent and one Hamiltonian."],
            "limitations": [an["scope"], "A true diagnostic does not establish equilibrium; a false one is not hidden.", "Synthetic collagen-mimetic peptide, not a fish protein."], "couplings": [], "manifest": f"{d}/continuation-analysis/summary.json", "native": True})
    d = "artifacts/metabolism"
    if (ROOT / d / "manifest.json").exists() and (ROOT / d / "basic-nutrients-v3/metabolism_results.json").exists():
        mf = json.loads(ins.read(f"{d}/manifest.json")); R = json.loads(ins.read(f"{d}/basic-nutrients-v3/metabolism_results.json")); png = next((f for f in mf["files"] if f["path"].endswith("o2_atp_biomass.png")), None)
        _, ph = _vid(ins, out, "metabolism-gem", f"{d}/basic-nutrients-v3", "o2_atp_biomass.png", png["sha256"]) if png else (None, None)
        sw = R["o2_sweep"]; C = R["controls"]; m = R["model"]
        cards.append({"id": "metabolism-gem", "title": "Generic zebrafish metabolic model: a steady-state flux balance with an assumed medium", "scales": ["subcellular", "cellular"], "evidence_kind": "computed (flux balance analysis); figure is a plot of stored numbers",
            "model": {"name": f"Zebrafish-GEM (Wang 2021 PNAS, {mf['model']['license']}), commit {mf['model']['commit'][:9]}, cobra {mf['software']['cobra']} with {mf['software']['solver']}", "context": f"A generic Danio rerio network of {m['reactions']:,} reactions, {m['metabolites']:,} metabolites and {m['genes']:,} genes (counts measured from the file). It defines no growth medium, so the medium is ASSUMED: " + R["assumed_medium"]["basis"] + ". A steady-state linear programme, not a time course; not specific to fin, tissue or life stage."},
            "time": {"units": "none: steady state", "note": R["units"]},
            "video": {"file": None, "sha256": None, "note": ""}, "video_state": "none", "poster_href": ph, "poster_is_figure": True,
            "numerical_checks": [{"name": k.replace("_", " "), "result": (f"{v['status']}; objective {v['objective']:.4g}; max |S v| {v['max_abs_Sv']:.1e}" if isinstance(v, dict) and "objective" in v else json.dumps(v)[:160])} for k, v in C.items()]
                + [{"name": "oxygen sweep", "result": f"biomass {sw[0]['biomass']:.3f} at zero oxygen uptake, {sw[-1]['biomass']:.3f} at uptake limit {sw[-1]['o2_uptake_limit']}: growth barely depends on the oxygen limit"}],
            "parameter_unknowns": ["The medium is assumed, not published or measured.", "Flux units are not declared in the SBML; mmol/gDW/h is assumed.", "Uptake is uncapped except glucose."],
            "open_questions": ["Which measured medium and uptake bounds would replace the assumed ones? The sweep does not show oxygen dependence because the model can make its own oxygen through a reaction next to uncapped vitamin uptake; the owner's diagnostic is in the branch, not in this tree."],
            "limitations": ["Not a measurement of fish oxygen use or oxygen dependence.", "Growth values are model objective fluxes, not physiological growth.", "Not fin- or tissue-specific and says nothing about flying fish.", "The ATP-maintenance slope is not calibrated."], "couplings": [], "manifest": f"{d}/manifest.json", "native": True})
    d = "artifacts/molecular"; ws = f"{d}/warmstart-v3.tar.xz"          # d was reassigned by the cards above; set it explicitly
    if (ROOT / ws).exists() and (ROOT / d / "warmstart-v3.json").exists():
        wm = json.loads(ins.read(f"{d}/warmstart-v3.json")); b = ins.read(ws)
        if digest_bytes(b) == wm["sha256"] and len(b) == wm["bytes"]:
            out["@artifacts/molecular/warmstart-v3.tar.xz"] = b
    d = "artifacts/molecular"
    if (ROOT / d / "cpu-render/render.json").exists():
        rr = json.loads(ins.read(f"{d}/cpu-render/render.json")); an = json.loads(ins.read(f"{d}/analysis.json")); o = rr["outputs"]
        st, href = _vid(ins, out, "molecular-md", f"{d}/cpu-render", "trajectory.mp4", o["trajectory.mp4"]); _, ph = _vid(ins, out, "molecular-md", f"{d}/cpu-render", "poster.png", o["poster.png"])
        lo, hi = an["kinetic_temperature_observed_range_K"]
        cards.append({"id": "molecular-md", "title": "Collagen-mimetic trimer: 0.2 ps CPU setup run (OpenMM), the earlier short run", "scales": ["molecular"], "evidence_kind": rr["kind"] + "; " + an["kind"],
            "model": {"name": "OpenMM 8.4 classical atomistic MD of a synthetic collagen-mimetic (Pro-Pro-Gly) trimer", "context": f"{an['frames']} saved states, {an['production_ps']} ps production after {an['preliminary_thermalization_ps']} ps preliminary thermalization, seed {an['seed']}. Rigid alignment for display only; no deformation invented."},
            "time": {"units": "picoseconds of simulated time", "note": f"{rr['frames']} frames at {rr['display_fps']} fps; trajectory duration is not a relaxation time."},
            "video": {"file": "trajectory.mp4", "sha256": o["trajectory.mp4"], "note": ""}, "video_state": st, "video_href": href, "poster_href": ph,
            "numerical_checks": [{"name": "kinetic temperature", "result": f"observed {lo:.0f} to {hi:.0f} K; 300 K is the target, not the observation"}, {"name": "kinetic equilibration", "result": an["kinetic_equilibration"]}, {"name": "conformational equilibration", "result": an["conformational_equilibration"]}, {"name": "CA RMSD from production start", "result": f"{an['final_CA_RMSD_from_production_start_nm']:.3f} nm"}],
            "parameter_unknowns": ["Empirical accuracy: " + str(an["empirical_accuracy"]) + ".", "Material stiffness: not computed (null).", "No conversion from chain length to fin stiffness is made; the cross-scale gate refuses it."],
            "open_questions": ["Does a longer, equilibrated run change any observable? A GPU run is pending and is not claimed here."],
            "limitations": ["Not equilibrated: a deliberately short CPU setup run.", "Biological success probability: null (not computed).", "Synthetic collagen-mimetic peptide, not a fish protein."], "couplings": [], "manifest": f"{d}/cpu-render/render.json", "native": True})
    d = "artifacts/bio-services/kcnj13_openfold2"
    if (ROOT / d / "metrics.json").exists():
        mt = json.loads(ins.read(f"{d}/metrics.json")); op = json.loads(ins.read(f"{d}/operation_receipt.json")); pl = mt["provider_metrics"]; cc = mt["coordinate_check"]
        cards.append({"id": "openfold2-kcnj13", "title": "Predicted structure of zebrafish Kcnj13 (OpenFold2): a computed model, not an observation", "scales": ["molecular"], "evidence_kind": mt["epistemic_status"],
            "model": {"name": f"OpenFold2 via {mt['provider']}, parameter set {mt['model_parameter_set']}, monomer, unrelaxed", "context": f"{mt['input_length_aa']} residues (NCBI BAF03613.1, matched to UniProt Q0KIZ7). Operation {mt['operation_id']} finished {op['completed_utc']} with status {op['final_status']}."},
            "time": {"units": "none: a single static prediction", "note": f"Reported inference time {pl['reported_inference_seconds']:.1f} s; hardware allocation was not returned."},
            "video": {"file": None, "sha256": None, "note": ""}, "video_state": "none", "poster_href": None,
            "numerical_checks": [{"name": "returned sequence matches the input", "result": "yes" if cc["sequence_exact_match"] else "NO"}, {"name": "C-alpha residues parsed", "result": str(cc["ca_residue_count"])},
                {"name": "pLDDT", "result": f"mean {pl['plddt']['mean']:.1f}; {pl['plddt']['fraction_at_least_70'] * 100:.0f}% of residues at or above 70; {pl['plddt']['fraction_below_50'] * 100:.0f}% below 50"}, {"name": "predicted aligned error", "result": f"mean {pl['predicted_aligned_error']['mean_A']:.1f} Å, max {pl['predicted_aligned_error']['max_A']:.1f} Å"}, {"name": "pTM", "result": f"{pl['ptm_score']:.2f}"}],
            "parameter_unknowns": ["Confidence and PAE are model-internal metrics, not a calibrated probability that the structure is correct."],
            "open_questions": ["Does a tetrameric, membrane-embedded model with a real MSA change the confidence? None was run."],
            "limitations": mt["limits"], "couplings": [], "manifest": f"{d}/metrics.json", "native": True})
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
    d = "artifacts/cfd3d/gpu-v1"
    if (ROOT / d / "status.json").exists() and (ROOT / d / "receipt.json").exists():
        stt = json.loads(ins.read(f"{d}/status.json")); rc = json.loads(ins.read(f"{d}/receipt.json")); gate = stt["reference_gate"]
        for tag, cid in (("L128_Re1000", "cfd3d-gpu-L128-Re1000"), ("L192_Re1000", "cfd3d-gpu-L192-Re1000")):
            rd = f"{d}/gpu_fish_{tag}/render"
            if not (ROOT / rd / "render.json").exists():
                continue
            r = json.loads(ins.read(f"{rd}/render.json")); cs = json.loads(ins.read(f"{d}/gpu_fish_{tag}/case.json"))["case"]
            st, href = _vid(ins, out, cid, rd, "flow.mp4", r["video"]["sha256"]); _, ph = _vid(ins, out, cid, rd, r["poster"], r["poster_sha256"])
            cards.append({"id": cid, "title": f"3D flow past the fish3d candidate, Re = {cs['Re']}, {cs['L_cells']} cells along the body (WaterLily, H100)", "scales": ["organism"], "evidence_kind": "simulated (numerical demo; video is a render of solver slices)",
                "model": {"name": "WaterLily 1.10.0 three-dimensional Navier-Stokes, fixed rigid body, candidate 4a3b912eb346", "context": r["what"] + ". " + " ".join(r["caption"].splitlines()[1:2])},
                "time": {"units": "convective time units", "note": f"{r['frames']} frames at {r['fps']} fps; case runs to t = {cs['t_end']}, averaging over the last {cs['t_avg']}. Container wall {rc['container_wall_s']} s on {rc['device']} for the whole packet (all four cases), not for this case alone."},
                "video": {"file": "flow.mp4", "sha256": r["video"]["sha256"], "note": ""}, "video_state": st, "video_href": href, "poster_href": ph,
                "numerical_checks": [{"name": "C1 sphere reference (Re 100)", "result": f"FAILED: |Cd| {gate['evidence'].split('|Cd| ')[1].split(' vs')[0]} against correlation 1.092, band [0.95, 1.35]; no physical-validation claim"}, {"name": "platform gates", "result": "reproduce model behaviour only (" + gate["consequence"] + ")"}],
                "parameter_unknowns": ["Fins are " + r["caption"].splitlines()[2 - 1].split("Fins are ")[1].split(": fin flow")[0] + ". Fin flow is not resolved.", "A flying fish glides at Reynolds numbers orders of magnitude above this."],
                "open_questions": ["Can the C1 reference be brought into its band? Until then no case here supports a quantitative force claim."],
                "limitations": r["caption"].splitlines()[2:] + ["Low-Re numerical demo: not swimming-, taxiing- or flight-validated."], "couplings": [], "manifest": f"{rd}/render.json", "native": True})
    d = "artifacts/multicell/full"
    if (ROOT / d / "full_horizon_chart.mp4").exists() and (ROOT / d / "full_summary.json").exists():
        fh = json.loads(ins.read(f"{d}/full_summary.json"))
        receipt_path = f"{d}/full_horizon_chart.receipt.json"
        receipt = json.loads(ins.read(receipt_path))
        video = receipt["output"]["video"]
        poster = receipt["output"]["poster"]
        st, href = _vid(ins, out, "morpheus-full-horizon-chart", d, "full_horizon_chart.mp4", video["sha256"])
        _, ph = _vid(ins, out, "morpheus-full-horizon-chart", d, "full_horizon_chart_poster.png", poster["sha256"])
        cards.append({"id": "morpheus-full-horizon-chart", "title": "Morpheus full-horizon logger chart (t to 2.0): a chart of logged counts, not a spatial tissue movie", "scales": ["tissue", "cellular"], "evidence_kind": "chart rendered from the run's logged data (not a spatial simulation render)",
            "model": {"name": "Morpheus v2.3.9 official multiscale example, three full-horizon arms", "context": "The chart plots, as t advances to 2.0, the logged cell count (log scale), mean CDK1 per cell and mean g_l per cell for the three arms, from the returned logger file only. It draws no cell shapes or fields: the full-horizon runs saved no spatial frames. The earlier spatial movies cover t up to 0.46 only."},
            "time": {"units": "model time units (example model)", "note": "100 frames at 12 fps; each frame advances t. Generic example, not calibrated."},
            "video": {"file": "full_horizon_chart.mp4", "sha256": video["sha256"], "note": "Video and poster checked against the render receipt; input logs and producer code are separately pinned there."}, "video_state": st, "video_href": href, "poster_href": ph,
            "numerical_checks": [{"name": f"arm {a}", "result": f"reached t = {v['reached_t']}; {v['final_cells']} cells at the end; {v['n_division_event_times']} division events; max cdk1 {v['max_cdk1']:.3f}; max g_l {v['max_g_l']:.3f}"} for a, v in fh.items()],
            "parameter_unknowns": ["Not calibrated to any organism or tissue; units are the example's own.", "'Cells' are model cells, not a growth measurement."],
            "open_questions": ["Why the feedback-on CDK1 oscillation damps after about t = 1.5 as the count levels off near 256 was not investigated."],
            "limitations": ["A chart of logged values, not a spatial movie: the remote run saved no spatial frames.", "Generic example, not fish growth; one seed repeat only."], "couplings": [], "manifest": receipt_path, "native": True})
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


def aeroelastic_cards(ins: Inputs, out: dict) -> list[dict]:
    """Static aeroelastic coupling card from the native model card and its production audit. Wording follows the independent review (B1, B2): a
    bending-only, torsion-rigid scaffold; a fixed-alpha assumed-release descent proxy; ledger gates are bookkeeping; the absolute mesh gate does not
    resolve small paired effects; small differences are not validated improvements. The 36-arm production arms are used, not the earlier coarse slice."""
    d = "artifacts/aeroelastic"
    if not (ROOT / d / "index.json").exists():
        return []
    ix = json.loads(ins.read(f"{d}/index.json")); art = ix["artifacts"]; P = ix.get("production")
    if not P:
        return []
    sub = lambda k: art[k]["path"].split(d + "/", 1)[1]
    st, href = _vid(ins, out, "aeroelastic-coupling", d, sub("video"), art["video"]["sha256"])
    _, ph = _vid(ins, out, "aeroelastic-coupling", d, sub("poster"), art["poster"]["sha256"])
    _, prov = _vid(ins, out, "aeroelastic-coupling", d, sub("render_provenance"), art["render_provenance"]["sha256"])
    au = json.loads(ins.read(f"{d}/production-audit.json")); dg = json.loads(ins.read(f"{d}/production-diagnostics.json"))
    gates = dg["native_lattice_gates"]; npass = sum(1 for g in gates if g.get("lattice_gate_passed"))
    nom = next(e for e in dg["paired_effects"] if e["compliance"] == 0.2 and e["speed_m_s"] == 20.0 and e["comparison"] == "two_way_minus_one_way")["meshes"]["fine"]
    rv = dg.get("review", {})
    (r_cl, o_cl, t_cl), (r_rg, o_rg, t_rg) = P["nominal_fine"]["CL"], P["nominal_fine"]["descent_range_m"]
    return [{"id": "aeroelastic-coupling", "title": f"Static aeroelastic coupling of the fins: {P['arms']} arms, bending-only torsion-rigid scaffold", "scales": ["organ", "organism"], "evidence_kind": ix["evidence_kind"] + " (video: render of saved states)",
        "model": {"name": "equivalent constant-EI bending scaffold + steady thin-surface VLM", "context": ix["question"] + " " + ix["status"] + "."},
        "time": {"units": "static iterations, not physical seconds", "note": "The video holds terminal states explicitly; deflection is unscaled. The descent paths are a separate rigidized-shape point-mass proxy."},
        "video": {"file": "coupled-states.mp4", "sha256": art["video"]["sha256"], "note": f"{art['video']['bytes']} bytes"}, "video_state": st, "video_href": href, "poster_href": ph, "provenance_href": prov,
        "numerical_checks": [
            {"name": "production run", "result": f"{P['native_execution_status']}: {P['arms']} arms over {P['contexts']} compliance and speed contexts, two lattices; empirical accuracy {P['empirical_accuracy']}"},
            {"name": "nominal (compliance 0.2, 20 m/s, fine lattice)", "result": f"CL rigid {r_cl:.6f}, one-way {o_cl:.6f}, two-way {t_cl:.6f}; assumed-release descent range {r_rg:.3f}, {o_rg:.3f}, {t_rg:.3f} m"},
            {"name": "two-way minus one-way", "result": f"dCL {t_cl - o_cl:.2e}, range {1000 * (t_rg - o_rg):+.2f} mm; about {nom['abs_delta_CL_over_fixed_point_tolerance']:.1f} times the frozen fixed-point tolerance. A small effect, not a demonstrated useful flight improvement"},
            {"name": "independent audit of the returned files", "result": f"{au['collection_files_checked']} files, {au['actual_static_frames_checked']} static frames and {au['actual_glide_states_checked']} descent states reproduced exactly; same-model integrity, not validation"},
            {"name": "mesh gate", "result": f"the absolute 3% CL gate between the two lattices passed for {npass} of {len(gates)} comparisons; it cannot resolve smaller paired effects or establish a convergence rate"},
            {"name": "ledger gates", "result": "the force, moment and virtual-work residuals hold by construction and only detect an overridden normal vector; they are bookkeeping, not an independent transfer validation"}],
        "parameter_unknowns": [ix["inputs"]["material"] + ".", "Mass, drag coefficients, release height and fixed alpha in the descent proxy are assumed engineering values.", "Paired differences and their mesh ratios are descriptive posthoc diagnostics; no acceptance criterion was changed or added."],
        "open_questions": ix["open_questions"],
        "equations": [], "sources": [{"label": "Static aeroelastic method (aircraft model, not a fish)", "locator": "Ting, Nguyen, Trinh 2014, NASA NTRS 20140008648, Eq 63-66, 74-75 and Section VIII"}, {"label": "Beam deflection reference", "locator": "MIT 1.050 beam deflection notes"}, {"label": "Independent review (claude-07), kept byte-exact, with the author's response", "locator": f"{d}/independent-review-claude07.md sha256 {rv.get('sha256', '')[:12]}…"}, {"label": "Protocol", "locator": f"{d}/protocol.json sha256 {art['protocol']['sha256'][:12]}…"}],
        "limitations": ["Bending-only, torsion-rigid scaffold; the descent is a fixed-alpha, assumed-release proxy; neither is validated fin or glide performance.", "Independent review B1: the ledger identities cannot catch a wrong station, frame or scaling, so they are not independent transfer validation.", "Independent review B2: the 3% absolute mesh gate cannot establish paired effects smaller than itself; the deltas, mesh ratios and tolerance multiples shown are descriptive and added after the fact, with no new gate.", "Torsion, axial, hinge stiffness, trimmed flight, unsteady fluid and structure, viscosity and separation are not modelled.", "Computed engineering result; empirical validation: " + str(ix["empirical_validation"]) + ". No biological calibration of the equivalent stiffness exists."],
        "couplings": [], "manifest": f"{d}/index.json", "native": True}]


def nca_cards(ins: Inputs, out: dict) -> list[dict]:
    """Keep original/seed results and the fresh matched-curriculum comparison separate.
    All fit one design raster; none implements measured tissue or DNA."""
    cards = []
    kinds = {}
    sp = ROOT / "artifacts/nca-seed-placement/index.json"
    if sp.exists():
        kinds = {b["kind"]: b for b in json.loads(ins.read("artifacts/nca-seed-placement/index.json")).get("by_kind", [])}
    for cid, d in (("nca-pattern", "artifacts/nca-pattern"), ("nca-seed-placement", "artifacts/nca-seed-placement")):
        if not (ROOT / d / "index.json").exists() or not (ROOT / d / "returned-analysis").is_dir():
            continue
        ix = json.loads(ins.read(f"{d}/index.json")); art = ix["artifacts"]; rel = lambda k: art[k]["path"].split(d + "/", 1)[1]
        st, href = _vid(ins, out, cid, d, rel("video"), art["video"]["sha256"]); _, ph = _vid(ins, out, cid, d, rel("poster"), art["poster"]["sha256"])
        _, plot = _vid(ins, out, cid, d, rel("training_plot"), art["training_plot"]["sha256"]); _, prov = _vid(ins, out, cid, d, rel("render_provenance"), art["render_provenance"]["sha256"])
        c = ix["counts"]; seed = cid == "nca-seed-placement"; nfr = len(json.loads(ins.read(art["render_provenance"]["path"]))["frames"])
        checks = [{"name": "declared design predicates", "result": f"{c['design_passed']} of {c['design_executed']} passed; negative controls {c['negative_passed']} of {c['negative_executed']}"}]
        if seed:
            checks += [{"name": b["kind"].replace("-", " "), "result": f"original {b['parent']['passed']} of {b['parent']['executed']} to corrected seed {b['variant']['passed']} of {b['variant']['executed']}"} for b in kinds.values()]
            checks += [{"name": "regime " + r["regime"], "result": f"{r['passed']} of {r['tested']}"} for r in ix["regime_counts"]]
        cards.append({"id": cid, "title": ("Neural cellular automaton fin pattern, corrected seed placement: 32 of 48 predicates, left-half recovery 0 of 12" if seed else "Neural cellular automaton fin pattern, original run: 0 of 48 predicates"),
            "scales": ["tissue", "developmental"], "evidence_kind": "computed (trained model on a 64x64 design raster; video renders saved states, not tissue)",
            "model": {"name": "neural cellular automaton, 8336 shared local-rule weights", "context": ("One factor changed from the original run: the seed cell " + str(ix["parent_seed_xy"]) + " -> " + str(ix["seed_xy"]) + ". Target, source, training budgets and evaluation cases are unchanged. " + ix["evaluation_status"] + "." if seed else "The original run, kept unchanged: " + ix["inverse_objective_status"] + ". Four models, two initialisations, a fin/ray design raster; not observed tissue.")},
            "time": {"units": f"cellular-automaton update steps; {nfr} frames shown", "note": "Frames are saved model states drawn as a raster, not a microscope image."},
            "video": {"file": rel("video"), "sha256": art["video"]["sha256"], "note": f"{art['video']['bytes']} bytes"}, "video_state": st, "video_href": href, "poster_href": ph, "plot_href": plot, "provenance_href": prov,
            "numerical_checks": checks,
            "parameter_unknowns": ["The 12 hidden channels are computational state, not measured biochemical signals.", ("Evaluation cases are reused from the original run: not fresh held-out cases and not a new target." if seed else "Seeds and pools are declared inputs; repeated probes are not independent biological replicates.")],
            "open_questions": ["Large left-half damage failed all 12 cases even with the corrected seed." if seed else "Would a different seed placement change the outcome? One factor was tested separately (see the corrected-seed card).", "No DNA, cell program, neural control or tissue regeneration is implemented or implied."],
            "equations": [], "sources": [{"label": "Protocol", "locator": art["protocol"]["path"] + " sha256 " + art["protocol"]["sha256"][:12] + "…"}, {"label": "Audit", "locator": art["audit"]["path"] + " sha256 " + art["audit"]["sha256"][:12] + "…"}],
            "limitations": list(ix.get("limits", [])) + ["Computed result; empirical validation: " + str(ix["empirical_validation"]) + ". Not generalisation and not a biological regeneration result."],
            "couplings": [], "manifest": f"{d}/index.json", "native": True})
    d, cid = "artifacts/nca-curriculum", "nca-curriculum"
    if (ROOT / d / "index.json").exists():
        ix = json.loads(ins.read(f"{d}/index.json"))
        art = ix["artifacts"]
        def checked(name, relative):
            ref = art[name]
            if ref["path"] != f"{d}/{relative}":
                raise ValueError("Curriculum card artifact path changed")
            raw = ins.read(ref["path"])
            if digest_bytes(raw) != ref["sha256"] or len(raw) != ref["bytes"]:
                raise ValueError("Curriculum card artifact digest/size mismatch")
            return json.loads(raw)
        audit = checked("audit", "returned-analysis/audit.json")
        provenance = checked("render_provenance", "returned-analysis/render-provenance.json")
        checked("checkpoint_barrier", "run/checkpoint-before-holdout.json")
        if ix["counts"] != audit["counts"] or ix["paired_effects"] != audit["per_pair_effects"]:
            raise ValueError("Curriculum card differs from audited counts/pairs")
        hrefs, states = {}, {}
        for key in ("video", "poster", "training_plot", "render_provenance", "protocol", "audit", "checkpoint_barrier", "question_outcome"):
            path = art[key]["path"]
            if not path.startswith(d + "/") or ".." in Path(path).parts:
                raise ValueError("Curriculum media path escapes artifact directory")
            states[key], hrefs[key] = _vid(ins, out, cid, d, path[len(d) + 1:], art[key]["sha256"])
            if states[key] != "present_verified":
                raise ValueError("Curriculum result lacks a matching source/media artifact: " + key)
        _, manifest_href = _vid(ins, out, cid, d, "index.json", ins.seen[f"{d}/index.json"]["sha256"])
        c = ix["counts"]
        regimes = {x["regime"]: x for x in ix["regime_counts"]}
        baseline, curriculum = regimes["damage-pool"], regimes["curriculum-pool"]
        persistence = next(x["regimes"] for x in ix["by_kind"] if x["kind"] == "persistence")
        checks = [{"name": "declared design probes (erased controls separate)", "result": f"{c['design_passed']}/{c['design_declared']}; baseline {baseline['passed']}/{baseline['declared']}, curriculum {curriculum['passed']}/{curriculum['declared']}. No aggregate benefit in these probes."}]
        checks += [{"name": x["kind"].replace("-", " "), "result": "baseline {passed}/{executed}; curriculum ".format(**x["regimes"]["damage-pool"]) + "{passed}/{executed}".format(**x["regimes"]["curriculum-pool"])} for x in ix["by_kind"]]
        checks += [{"name": f"paired initialization {x['initialization_seed']}", "result": "baseline {passed}/{declared}; curriculum ".format(**x["regimes"]["damage-pool"]) + "{passed}/{declared}".format(**x["regimes"]["curriculum-pool"]) + "; shared-weight probes are dependent"} for x in ix["paired_effects"] if x["group"] == "all_design"]
        checks += [{"name": "erased-state negative controls", "result": f"{c['negative_passed']}/{c['negative_declared']}; excluded from 192"}, {"name": "metric reproduction", "result": f"bit-for-bit {audit['exact_metric_reproduction']}; separate fixed-roundoff {audit['fixed_roundoff_metric_reproduction']}; max difference {audit['max_metric_absolute_difference']:.3g}"}]
        cards.append({"id": cid, "title": f"NCA curriculum repair/persistence tradeoff: {c['design_passed']}/{c['design_declared']} design predicates",
            "scales": ["tissue", "developmental"], "evidence_kind": "computed trained local rule on a design raster, not tissue",
            "model": {"name": "Neural cellular automaton, 8336 shared local-rule weights per model", "context": f"Eight final 2000-step models, four matched initialization pairs. One of three circular training erasures is replaced by a staged prefix erasure. Fresh independently committed damage masks/update seeds. Prefix30/34 repair improves while persistence falls {persistence['damage-pool']['passed']}/12 to {persistence['curriculum-pool']['passed']}/12; aggregate {baseline['passed']}/96 to {curriculum['passed']}/96. No general benefit established."},
            "time": {"units": f"Computational update steps; {len(provenance['frames'])} actual saved frames", "note": "Movie: all eight preselected prefix-34 recovery histories through 768 updates. Separate 2048-update persistence endpoints are in the table, not this movie."},
            "video": {"file": art["video"]["path"][len(d) + 1:], "sha256": art["video"]["sha256"], "note": f"{art['video']['bytes']} bytes"},
            "video_state": states["video"], "video_href": hrefs["video"], "poster_href": hrefs["poster"], "plot_href": hrefs["training_plot"], "provenance_href": hrefs["render_provenance"],
            "numerical_checks": checks, "parameter_unknowns": ["Four paired training initializations are replicate units; mask/update probes share learned weights and are dependent.", "One previously fitted design target. Fresh cases do not establish new-target generalization.", "Twelve hidden channels, pixels and update counts have no measured biochemical/cell-size/time calibration."],
            "open_questions": ["Can a separately frozen comparison retain targeted repair gains without losing persistence? No new large job before review.", "No tissue regeneration, DNA/cell program or nervous-system implementation is established."],
            "equations": [], "sources": [{"label": key.replace("_", " "), "href": hrefs[key], "locator": art[key]["path"] + " sha256 " + art[key]["sha256"]} for key in ("protocol", "audit", "checkpoint_barrier", "question_outcome")],
            "limitations": list(ix["limits"]), "biological_success_probability": None, "empirical_validation": "unknown",
            "couplings": [], "manifest": f"{d}/index.json", "manifest_href": manifest_href, "native": True})
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


DESIGN_CONTROL = "artifacts/design-control/map.json"


def design_control_map(ins: Inputs) -> dict | None:
    """The design-control map (frontier.design-control/1), when present. Shown as written; the pinned-source check is engineering.design_control.build --check."""
    if not (ROOT / DESIGN_CONTROL).exists():
        return None
    m = json.loads(ins.read(DESIGN_CONTROL))
    if m.get("schema") != "frontier.design-control/1":
        return {"error": f"unexpected schema {m.get('schema')!r}; not shown", "file_sha256": ins.seen[DESIGN_CONTROL]["sha256"]}
    m["file_sha256"] = ins.seen[DESIGN_CONTROL]["sha256"]
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
    design_control = design_control_map(ins)
    resources = resource_inventory(ins)
    mcp_chk = mcp_check(ins)
    extra: dict = {}
    proofs = lean_proofs(ins, extra)
    prints = print_forms(ins, extra)
    controlled = controlled_results(ins, files)
    if simulation is not None:
        simulation["controlled"] = controlled
    manifests = manifests + native_video_cards(ins, extra) + engineering_cards(ins, extra) + aeroelastic_cards(ins, extra) + nca_cards(ins, extra) + observed_update_cards(ins, extra)
    couplings_m = coupling_manifest(ins, files, docs)
    system = system_block(ins, files, docs, board, lean_receipt, simulation, attestation)
    design_review = ins.json("site/content/design-review.json")
    pr_path = "imports/2026-10-31-curated-v2/project-receipt.json"
    if (ROOT / pr_path).exists():
        pr = json.loads(ins.read(pr_path))
        design_review["history"] = [{"ref": pr["predecessor_ref"], "label": "Earlier version of this Project", "note": f"The current version ({pr['project_ref']['version'][:12]}…) has {pr['members']} declared members, {pr['preserved_members']} preserved from this one. {pr['old_version_annotations']} challenges stay anchored here on their original exact version; they were not moved. {pr['scope']}"}]
        design_review["current_project"] = {"ref": pr["project_ref"], "members": pr["members"], "preserved_members": pr["preserved_members"], "receipt": pr_path, "receipt_sha256": ins.seen[pr_path]["sha256"], "local_status": pr["local_status"]}
    lifecycle = lifecycle_block(ins)
    home_biology_block = home_biology(ins)
    timeline = build_timeline(ins)
    fish3d_viewer = fish3d_files(ins, extra)
    ecology = ecology_block(ins, extra)
    biodesign = biodesign_block(ins, extra)
    formalize_ex = formalize_examples(ins)
    print_v3 = print_v3_block(ins, extra)
    downloads = model_downloads(ins, extra)
    print_law_index = print_laws(ins, extra, downloads)
    demos = demo_videos(ins, extra)
    diffusion = diffusion_pilot(ins, extra)
    recovery_in = recovery_inputs(ins, extra)
    secondary_in = runtime_inputs(ins, extra, "secondary-runtime-inputs")
    fish_hist = fish_history(ins)
    reg_map = regulatory_map(ins)
    claim_reuse = claim_reuse_block(ins)
    gen_bp = genetic_blueprints(ins)
    orx_ex = openresearch_exemplars(ins)
    experimentation = experimentation_block(ins)
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
        "lean_gallery": proofs,
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
        "design_control": design_control,
        "design_review": design_review,
        "lifecycle": lifecycle,
        "home_biology": home_biology_block,
        "timeline": timeline,
        "fish3d_viewer": fish3d_viewer,
        "ecology": ecology,
        "biodesign": biodesign,
        "formalize": formalize_ex,
        "print_v3": print_v3,
        "model_downloads": downloads,
        "print_laws": print_law_index,
        "demo_videos": demos,
        "diffusion_pilot": diffusion,
        "recovery_inputs": recovery_in,
        "secondary_inputs": secondary_in,
        "fish_history": fish_hist,
        "regulatory_map": reg_map,
        "claim_reuse": claim_reuse,
        "genetic_blueprints": gen_bp,
        "openresearch": orx_ex,
        "experimentation": experimentation,
        "resource_inventory": resources,
        "mcp_check": mcp_chk,
        "spec_acceptance_open": len(re.findall(r"^- \[ \]", spec_text, re.M)),
    }
    catalog = {"schema": "frontier-site-catalog-0.1", "mode": "snapshot", "namespace": NAMESPACE, "snapshot": snapshot["label"], "records": build_catalog(snapshot)}
    out = {"snapshot.json": (json.dumps(snapshot, indent=1, ensure_ascii=False) + "\n").encode(),
           "catalog.json": (json.dumps(catalog, indent=1, ensure_ascii=False) + "\n").encode()}
    out.update(files); out.update(extra)
    return out


def generated_artifact_families() -> list[str]:
    return ["results", "fish3d", "molecular", "rd-diffusion", "lean-gallery", "observed-allometry", *(path.name for path in print_families())]


def write(out: dict[str, bytes]) -> None:
    for d in (DATA / "docs", DATA / "results", *(SITE / "artifacts" / name for name in generated_artifact_families())):
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
    pr = [("@artifacts/" + sub + "/" + p.relative_to(SITE / "artifacts" / sub).as_posix()) for sub in generated_artifact_families() for p in (SITE / "artifacts" / sub).rglob("*") if p.is_file()] if (SITE / "artifacts").exists() else []
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
