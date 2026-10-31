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
        "spec_acceptance_open": len(re.findall(r"^- \[ \]", spec_text, re.M)),
    }
    catalog = {"schema": "frontier-site-catalog-0.1", "mode": "snapshot", "namespace": NAMESPACE, "snapshot": snapshot["label"], "records": build_catalog(snapshot)}
    out = {"snapshot.json": (json.dumps(snapshot, indent=1, ensure_ascii=False) + "\n").encode(),
           "catalog.json": (json.dumps(catalog, indent=1, ensure_ascii=False) + "\n").encode()}
    out.update(files)
    return out


def write(out: dict[str, bytes]) -> None:
    for sub in ("docs", "results"):
        if (DATA / sub).exists():
            shutil.rmtree(DATA / sub)
    for name, b in out.items():
        dest = DATA / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b)


def check(out: dict[str, bytes]) -> list[str]:
    stale = [n for n, b in out.items() if not (DATA / n).exists() or (DATA / n).read_bytes() != b]
    extra = [p.relative_to(DATA).as_posix() for sub in ("docs", "results") if (DATA / sub).exists() for p in (DATA / sub).glob("*")]
    return stale + [f"unexpected {e}" for e in extra if e not in out]


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
