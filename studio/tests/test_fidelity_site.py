"""The fidelity-ladder gallery card: counts and wording come from the returned, hash-checked files; any tamper withholds the whole card."""

import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import fidelity_site as F  # noqa: E402

# The keys build_site.aeroelastic_cards returns for a card, so the gallery renderer (views3) can draw this one unchanged.
CARD_KEYS = {"id", "title", "scales", "evidence_kind", "model", "time", "video", "video_state", "video_href", "poster_href", "provenance_href", "numerical_checks", "parameter_unknowns", "open_questions", "equations", "sources", "limitations", "couplings", "manifest", "native"}


class Ins:
    def __init__(self, root):
        self.root = Path(root)

    def read(self, rel):
        return (self.root / rel).read_bytes()


@pytest.fixture(scope="module")
def built():
    out = {}
    return F.build(Ins(ROOT), out, root=ROOT)[0], out


def stage(tmp_path):
    for rel in [F.HANDOFF, *F.ROLES]:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, tmp_path / rel)
    return tmp_path


def repin(root, rel):
    """Make the handoff declare the new bytes of `rel`, so only the content checks can refuse."""
    h = json.loads((root / F.HANDOFF).read_text())
    for o in h["outputs"]:
        if o["path"] == rel:
            o["sha256"] = F._sha((root / rel).read_bytes())
    (root / F.HANDOFF).write_text(json.dumps(h))


def refused(root):
    out = {}
    c = F.build(Ins(root), out, root=root)
    assert len(c) == 1 and c[0].get("withheld") and c[0]["numerical_checks"] == [] and c[0]["video"] is None and c[0]["video_href"] is None
    assert out == {}, "a withheld card publishes no file"
    return c[0]["withheld"]


def test_card_has_the_aeroelastic_card_shape_and_the_returned_counts(built):
    c, _ = built
    assert CARD_KEYS <= set(c) and c["native"] is True and c["video_state"] == "present_verified"
    assert c["counts"] == {"native_arms": 45, "effect_statuses": {"sign_resolved": 27, "resolved": 0}, "contexts": 3, "undetermined_decisions": 6, "posthoc_rigid_solves": 21}
    t = json.dumps(c)
    assert "no effect magnitude is resolved" in t.lower() and "undetermined in all 3 contexts" in t and "no context is promoted" in t
    assert "posthoc" in t.lower() and "not native arms" in t and "no biological claim" in t and "not a Navier-Stokes solve" in t
    assert not any(k for k in c if "confidence" in k or "score" in k) and "validated improvement" in t and "nothing here is a validated improvement" in t


def test_published_files_are_exactly_the_hash_checked_allowlist(built):
    c, out = built
    assert set(out) == {f"{F.OUT}/{rel.rsplit('/', 1)[1]}" for rel in F.ROLES} and len(out) == 9
    declared = {o["path"]: o["sha256"] for o in json.loads((ROOT / F.HANDOFF).read_text())["outputs"]}
    for rel in F.ROLES:
        assert F._sha(out[f"{F.OUT}/{rel.rsplit('/', 1)[1]}"]) == declared[rel]
    assert [f["label"].split(":")[0] for f in c["figures"]] == ["Fidelity ladder", "Posthoc rigid-solve diagnostic (not frozen, changes no decision)"]
    assert [f["posthoc"] for f in c["figures"]] == [False, True] and all(f["href"].startswith(F.PUBLIC) and len(f["sha256"]) == 64 for f in c["figures"] + c["reports"])
    assert c["video_href"].endswith("coupled-states.mp4") and c["poster_href"].endswith("poster.png") and c["manifest"] == F.HANDOFF


def test_a_changed_output_withholds_the_whole_card(tmp_path):
    root = stage(tmp_path)
    p = root / F.D / "fidelity-ladder.png"
    p.write_bytes(p.read_bytes() + b"\0")
    assert any("fidelity-ladder.png changed" in w for w in refused(root))


def test_a_missing_output_and_an_undeclared_one_are_refused(tmp_path):
    root = stage(tmp_path)
    (root / F.RENDER / "coupled-states.mp4").unlink()
    assert any("coupled-states.mp4 is missing" in w for w in refused(root))
    root2 = stage(tmp_path / "b")
    h = json.loads((root2 / F.HANDOFF).read_text())
    h["outputs"] = [o for o in h["outputs"] if not o["path"].endswith("poster.png")] + [{"path": "artifacts/elsewhere/x.json", "sha256": "0" * 64}]
    (root2 / F.HANDOFF).write_text(json.dumps(h))
    w = refused(root2)
    assert any("not declared in the handoff" in x for x in w) and any("outside" in x for x in w)


def test_a_re_pinned_but_failed_audit_is_still_refused(tmp_path):
    root = stage(tmp_path)
    rel = f"{F.D}/return-audit-report.json"
    a = json.loads((root / rel).read_text())
    a["audit_passed"] = False
    (root / rel).write_text(json.dumps(a))
    repin(root, rel)
    assert any("did not pass" in w for w in refused(root))


def test_changed_decisions_or_statuses_in_the_audit_are_refused(tmp_path):
    for k, mutate in (("decision", lambda r: r["decision"].update(bending="resolved")), ("status", lambda r: r.update(CL_rigid="resolved"))):
        root = stage(tmp_path / k)
        rel = f"{F.D}/return-audit-report.json"
        a = json.loads((root / rel).read_text())
        mutate(a["recomputed_effects_and_decisions"]["chi0.8-u20"])
        (root / rel).write_text(json.dumps(a))
        repin(root, rel)
        assert any("disagree with the returned" in w for w in refused(root)), k


def test_returned_claims_that_disagree_with_the_audit_are_refused(tmp_path):
    root = stage(tmp_path)
    h = json.loads((root / F.HANDOFF).read_text())
    h["native"]["effect_statuses"] = "26 sign_resolved, 1 resolved"
    (root / F.HANDOFF).write_text(json.dumps(h))
    assert any("arm count or effect statuses" in w for w in refused(root))


def test_no_handoff_means_no_card(tmp_path):
    assert F.build(Ins(tmp_path), {}, root=tmp_path) == []


def test_the_frozen_remedy_stays_historical_and_posthoc_evidence_changes_the_next_action(built):
    c, _ = built
    chk = {k["name"]: k["result"] for k in c["numerical_checks"]}
    d = chk["engineering decisions"]
    assert "frozen protocol, written before the return, proposed a finer or span/chord-separated ladder" in d and "historical proposal" in d
    assert "do not support running a finer ladder in the same lattice scheme blindly" in d and d.endswith("diagnosing the scheme")
    assert "the remedy is a finer" not in d, "no present-tense recommendation of a finer ladder"
    q = " ".join(c["open_questions"])
    assert "under diagnosis" in q and "inference from the posthoc rigid solves, not a tested prediction for coupled arms" in q and "Does a finer" not in q


# ------------------------------------------------------------------------------------------------ browser (the card injected into the real gallery, until root generates it)
sync_api = pytest.importorskip("playwright.sync_api")


def _open(browser, base, card, width):
    snap = json.loads((ROOT / "site/data/snapshot.json").read_text())
    snap["simulation_manifests"] = [x for x in snap.get("simulation_manifests", []) if x["id"] != card["id"]] + [card]
    pg = browser.new_page(viewport={"width": width, "height": 900})
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.route("**/data/snapshot.json", lambda r: r.fulfill(json=snap))
    pg.goto(base + "#/simulations?q=fidelity")
    pg.wait_for_selector(".simgrid")
    return pg


@pytest.fixture(scope="module")
def base():
    import functools
    import http.server
    import threading

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


@pytest.mark.parametrize("width", [1440, 390])
def test_card_renders_in_the_gallery_with_the_corrected_wording_and_no_overflow(browser, base, built, width):
    pg = _open(browser, base, built[0], width)
    t = pg.locator(".simgrid").text_content()  # the checks sit inside the card's disclosure, so read text content rather than visible text
    for must in ("45 native arms", "27 sign_resolved, 0 resolved", "historical proposal", "diagnosing the scheme", "posthoc"):
        assert must in t, must
    assert "the remedy is a finer" not in t and pg.errors == []
    assert pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth") <= 0
