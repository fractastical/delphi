"""The genotype surface: the adapter binds the compiler, ledger and DOE bytes and withholds stale inputs; the renderer shows only what the adapter gives it."""

import copy
import functools
import http.server
import json
import shutil
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import genotype_site as GS  # noqa: E402

NEEDED = [f"{GS.BIO}/{n}" for n in ("genotype-manifest.json", *GS.GENOTYPE_FILES)] + [f"{GS.SEQ}/manifest.json", f"{GS.SEQ}/ledger.json", f"{GS.DOE}/manifest.json", f"{GS.DOE}/instrument-contracts.json", f"{GS.DOE}/result.json"]


class Ins:
    def __init__(self, root):
        self.root = Path(root)

    def read(self, rel):
        return (self.root / rel).read_bytes()


def stage(tmp_path):
    """A copy of exactly the inputs the adapter reads (graph sources and ledger sequences included), so a test can change one byte."""
    graph = json.loads((ROOT / GS.BIO / "genotype-graph.json").read_text())
    ledger = json.loads((ROOT / GS.SEQ / "ledger.json").read_text())
    rels = set(NEEDED) | {s["path"] for s in graph["sources"].values()} | {s["artifact_ref"]["path"] for s in ledger["sequences"] if s.get("artifact_ref")}
    for rel in rels:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, tmp_path / rel)
    return tmp_path


@pytest.fixture(scope="module")
def built():
    out = {}
    return GS.build(Ins(ROOT), out, root=ROOT), out


def test_counts_are_computed_from_the_current_ledger(built):
    g, _ = built
    led = json.loads((ROOT / GS.SEQ / "ledger.json").read_text())
    c = g["ledger"]["counts"]
    assert g["status"] == "current" and g["withheld"] == []
    assert c["sequence_artifacts"] == len(led["sequences"]) == 36 and c["entries"] == len(led["entries"]) == 44
    assert c["sequence_kinds"] == {"natural_reference": 4, "existing_model_output": 32} and c["sequence_identity"] == {"unknown": 4, "None": 32}, "natural references stay unknown as the experimental allele"
    assert c["retained_unscreened_proposals"] == sum(1 for e in led["entries"] if e["direction"] == "inverse_proposal")
    assert [n["id"] for n in g["nodes"]] == ["dna", "expression", "growth_material", "shape_mechanics", "performance", "behavior"] and [i["id"] for i in g["interfaces"]] == ["I1", "I2", "I3", "I4", "I5"]
    assert g["endorsed_candidates"] == 0 and g["single_genome_guaranteed"] is False and g["uncalibrated_interfaces"] == ["I1", "I2", "I3", "I4", "I5"]
    assert not any(k for k in g if "confidence" in k or "score" in k), "no aggregate biological confidence"


def test_contracts_screen_and_premises_come_from_their_files(built):
    g, _ = built
    assert len(g["instrument_contracts"]["rows"]) == 8 and all(r["calibrated"] is False for r in g["instrument_contracts"]["rows"])
    assert (g["design_screen"]["candidates"], g["design_screen"]["survivors"]) == (30, 10) and g["design_screen"]["biological_success_probability"] is None
    assert {p["status"] for p in g["premises"]} == {"context_supported", "contradicted", "unresolved"}
    assert g["formal"]["cutsets"] == g["cutsets"] and g["cutsets"][0]["not_calibrated"] == ["I1", "I2", "I3"]


def test_only_allowlisted_hashed_files_are_published(built):
    g, out = built
    assert set(out) == {"@" + f["path"] for f in g["files"]}
    for f in g["files"]:
        assert GS._sha(out["@" + f["path"]]) == f["sha256"] and f["role"] in ("compiler", "ledger", "sequences", "doe", "manifests")
    assert sorted(f["name"] for f in g["files"] if f["role"] == "sequences") == ["fgf20a-genomic.fasta", "fgf20a-transcript.fasta", "kcnh2a-genomic.fasta", "kcnh2a-transcript.fasta"]
    assert not any("evo2" in k for k in out), "model-output JSON stays a pinned source and is not republished"


@pytest.mark.parametrize("rel,label", [(f"{GS.SEQ}/ledger.json", "ledger"), (f"{GS.DOE}/instrument-contracts.json", "instrument contracts"), (f"{GS.BIO}/genotype-validation.json", "genotype-validation"), (f"{GS.SEQ}/sequences/fgf20a-genomic.fasta", "sequence fgf20a-genomic")])
def test_a_changed_input_is_withheld_with_its_reason_and_never_published(tmp_path, rel, label):
    root = stage(tmp_path)
    (root / rel).write_bytes((root / rel).read_bytes() + b" ")
    out = {}
    g = GS.build(Ins(root), out, root=root)
    assert g["status"] == "partial" and any(w["path"] == rel and "changed" in w["reason"] for w in g["withheld"])
    assert not any(k.endswith("/" + rel.split("/")[-1]) for k in out)
    if rel.endswith("ledger.json"):
        assert g["ledger"] is None


def test_validation_built_against_other_instrument_bytes_is_withheld(tmp_path):
    root = stage(tmp_path)
    p = root / GS.BIO / "genotype-validation.json"
    v = json.loads(p.read_text())
    v["instrument_contracts_ref"]["sha256"] = "0" * 64
    p.write_text(json.dumps(v))
    man = root / GS.BIO / "genotype-manifest.json"
    m = json.loads(man.read_text())
    for f in m["files"]:
        if f["path"].endswith("genotype-validation.json"):
            f["sha256"] = GS._sha(p.read_bytes())
    man.write_text(json.dumps(m))
    g = GS.build(Ins(root), {}, root=root)
    assert any("DOE now declares" in w["reason"] for w in g["withheld"]) and g["cutsets"] == [] and all(i["validation"] is None for i in g["interfaces"])


def test_a_missing_input_tree_returns_nothing(tmp_path):
    assert GS.build(Ins(tmp_path), {}, root=tmp_path) is None


# ------------------------------------------------------------------------------------------------ browser
sync_api = pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def base():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT / "site"))
    handler.log_message = lambda *a, **k: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}/"
    srv.shutdown()


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def open_page(browser, base, genotype, width):
    snap = json.loads((ROOT / "site/data/snapshot.json").read_text())
    snap["genotype"] = genotype
    pg = browser.new_page(viewport={"width": width, "height": 900})
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.route("**/data/snapshot.json", lambda r: r.fulfill(json=snap))
    pg.goto(base + "#/assemblies")
    pg.wait_for_selector("#genotype")
    return pg


def overflow(pg):
    return pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")


@pytest.mark.parametrize("width", [1440, 390])
def test_the_panel_shows_counts_withholds_nothing_and_never_overflows(browser, base, built, width):
    pg = open_page(browser, base, built[0], width)
    t = pg.locator("#genotype").inner_text()
    for must in ("proposals, not DNA", "0 endorsed", "36", "44", "sequence artifacts", "contextual entries", "retained unscreened proposals", "Six nodes, five interfaces", "What follows by structure", "none is calibrated", "30 candidates were screened down to 10"):
        assert must in t, must
    assert "does not create DNA" in t and "contradicted by the source" in t and "Withheld" not in t
    assert pg.locator(".gif").count() == 5 and pg.locator("#genotype table").count() == 3
    link = pg.locator("#genotype a", has_text="sequence-evidence manifest")
    href = link.get_attribute("href")
    assert href == built[0]["manifests"]["sequence_evidence"]["href"] and href in {f["path"] for f in built[0]["files"]}, "the link points at a published file, not a repository path"
    assert "@" + href in built[1], "the builder writes exactly this file into the site (HTTP 200 is checked by tests/review_new_surfaces.py on a built site)"
    pg.locator("#gif-I1 summary").click()
    assert "validation slice" in pg.locator("#gif-I1").inner_text().lower()
    assert overflow(pg) <= 0 and pg.errors == []
    for w in pg.locator("#genotype .tablewrap").all():  # tables scroll in their own box, never widen the page
        assert w.evaluate("e => getComputedStyle(e).overflowX") in ("auto", "scroll")


def test_stale_inputs_are_shown_as_withheld_and_hostile_text_is_inert(browser, base, built):
    g = copy.deepcopy(built[0])
    g["status"] = "partial"
    g["withheld"] = [{"path": "artifacts/sequence-evidence/ledger.json", "label": "ledger", "reason": "changed since its manifest was written: <img src=x onerror=window.__pwned=1>"}]
    g["ledger"] = None
    pg = open_page(browser, base, g, 390)
    t = pg.locator("#genotype").inner_text()
    assert "Withheld" in t and "partial" in t and "The ledger is withheld" in t and "withheld" in t
    assert pg.evaluate("window.__pwned") is None and pg.locator("#genotype img").count() == 0 and pg.errors == []
    assert overflow(pg) <= 0


def test_without_a_genotype_block_the_assemblies_page_is_unchanged(browser, base):
    pg = browser.new_page(viewport={"width": 1280, "height": 900})
    snap = json.loads((ROOT / "site/data/snapshot.json").read_text())
    snap.pop("genotype", None)
    pg.route("**/data/snapshot.json", lambda r: r.fulfill(json=snap))
    pg.goto(base + "#/assemblies")
    pg.wait_for_selector(".asmatrix")
    assert pg.locator("#genotype").count() == 0


def test_the_three_pinning_manifests_are_published_as_their_actual_bytes_with_unambiguous_names(built):
    g, out = built
    ms = g["manifests"]
    assert set(ms) == {"genotype", "sequence_evidence", "doe"} and all(ms.values())
    assert sorted(m["name"] for m in ms.values()) == ["crossscale-doe-manifest.json", "genotype-manifest.json", "sequence-evidence-manifest.json"], "two sources are both called manifest.json"
    for key, m in ms.items():
        src = (ROOT / m["source"]).read_bytes()
        assert out["@" + m["href"]] == src and GS._sha(src) == m["sha256"], key
        assert m["href"] == f"{GS.PUBLIC}/manifests/{m['name']}" and any(f["path"] == m["href"] and f["role"] == "manifests" and f["source"] == m["source"] for f in g["files"])
    assert sum(1 for f in g["files"] if f["role"] == "manifests") == 3


def test_a_missing_manifest_is_not_published_and_its_link_is_withheld(tmp_path):
    root = stage(tmp_path)
    (root / GS.SEQ / "manifest.json").unlink()
    out = {}
    g = GS.build(Ins(root), out, root=root)
    assert g["manifests"]["sequence_evidence"] is None and g["status"] == "partial" and any(w["path"].endswith("sequence-evidence/manifest.json") for w in g["withheld"])
    assert not any("sequence-evidence-manifest" in k for k in out)
