"""The #/proofs page in a real browser. The snapshot is the repository's, with the Lean gallery added from the helper, because the builder does not
publish it yet; a stale family and hostile source text are injected to prove they are refused and never run as HTML."""
import copy
import functools
import hashlib
import http.server
import json
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sync_api = pytest.importorskip("playwright.sync_api")
import lean_gallery as L  # noqa: E402


class Ins:
    seen = {}

    def read(self, rel):
        return (ROOT / rel).read_bytes()


def serve():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT / "site"))
    handler.log_message = lambda *a, **k: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}/"


@pytest.fixture(scope="module")
def base():
    srv, url = serve()
    yield url
    srv.shutdown()


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture(scope="module")
def gallery():
    return L.build(Ins(), {}, root=ROOT)


def snapshot_with(g):
    s = json.loads((ROOT / "site/data/snapshot.json").read_text()); s["lean_gallery"] = g
    return s


def open_page(browser, base, snap, width=1280):
    pg = browser.new_page(viewport={"width": width, "height": 900}); pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.route("**/data/snapshot.json", lambda r: r.fulfill(json=snap))
    pg.goto(base + "#/proofs"); pg.wait_for_selector(".proof")
    return pg


def overflow(pg):
    return pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")


def test_each_family_shows_real_source_receipt_mutants_and_downloads(browser, base, gallery):
    pg = open_page(browser, base, snapshot_with(gallery))
    t = pg.locator("#main").inner_text()
    for must in ("recorded runs", "mathematics, not biology", "Mathlib", "proposal checker", "does not compile it"):
        assert must in t, must
    assert pg.locator(".proof").count() == 3 and pg.locator("h1").text_content() == "Lean proofs"
    for f in gallery["families"]:
        sec = pg.locator(f"#proof-{f['id']}")
        assert "recorded compile matches these files" in sec.inner_text()
        assert sec.locator(".proofthms details").count() == len(f["theorems"])
        src = (ROOT / f["files"][0]["path"].replace("artifacts/lean-gallery/" + f["id"] + "/", "engineering/formal/" if f["id"] != "cantilever-guard" else "engineering/formalize/lean/")).read_text()
        rows = sec.locator(".proofsrc .ll")
        assert rows.count() == len(src.splitlines()) == len(f["source"].splitlines())
        assert rows.nth(0).locator("code").text_content() == src.splitlines()[0]
        negs = sec.locator(".proofneg li")
        assert negs.count() == len(f["negative_blocks"]) and sec.locator(".proofneg .pill:has-text('rejected by Lean')").count() == len(f["negative_blocks"])
        body = sec.inner_text()
        assert "Classical.choice, Quot.sound, propext" in body and "standard axioms only" in body and "Exit 1 is the expected result" in body
        for x in f["files"]:
            a = sec.locator(f"a[href='{x['path']}'][download]")
            assert a.count() == 1 and x["sha256"][:8] in sec.locator(".prooffiles").inner_text().replace(" ", "")
    geo = pg.locator("#proof-geometric-similarity").inner_text()
    assert "conflict_instance" in geo and "unsat" in geo and "10" in geo
    assert pg.locator("#proof-cantilever-guard").inner_text().count("What it does not prove") == 1 and "anything about biology" in pg.locator("#proof-cantilever-guard").inner_text()
    pg.locator(".proof .eq-math .katex").first.wait_for(timeout=15000)
    assert pg.locator(".proof .katex-error").count() == 0 and not pg.errors


def test_stale_family_is_withheld_not_green_and_hostile_text_is_inert(browser, base, gallery):
    g = copy.deepcopy(gallery)
    stale = g["families"][1]
    stale.update({"status": "stale", "reasons": ["UnitAlgebra.lean changed since the receipt: pinned 34c70e0a1b22, found 000000000000"], "files": [], "theorems": [], "negative_blocks": []}); stale.pop("source", None)
    ev = g["families"][2]
    ev["theorems"][0]["doc"] = "<img src=x onerror=window.__pwn=1> <b>bold</b>"; ev["source"] = "-- <script>window.__pwn=2</script>\ntheorem t : True := trivial"
    pg = open_page(browser, base, snapshot_with(g))
    sec = pg.locator("#proof-unit-algebra"); txt = sec.inner_text()
    assert "Withheld" in txt and "stale" in txt and "changed since the receipt" in txt and "recorded compile matches" not in txt
    assert sec.locator(".lcode").count() == 0 and sec.locator("a[download]").count() == 0 and sec.locator(".pill.ok, .pill.st-ok").count() == 0
    idx = pg.locator(".proofindex li").nth(1).inner_text(); assert "stale or failed" in idx and "compiled, recorded" not in idx
    ev_sec = pg.locator("#proof-cantilever-guard"); ev_sec.locator(".proofthms details").first.locator("summary").click()
    assert "<img src=x" in ev_sec.locator(".proofthms").first.inner_text() and pg.locator("#proof-cantilever-guard img").count() == 0
    ev_sec.locator(".proofsrc summary").click()
    assert "<script>window.__pwn=2</script>" in ev_sec.locator(".proofsrc").inner_text()
    assert pg.evaluate("window.__pwn") is None and pg.locator("#main script").count() == 0


@pytest.mark.parametrize("width", [1440, 390])
def test_readable_code_without_widening_the_page_and_reachable_from_the_menu(browser, base, gallery, width):
    pg = open_page(browser, base, snapshot_with(gallery), width)
    assert overflow(pg) <= 0
    src = pg.locator("#proof-geometric-similarity .proofsrc"); src.locator("summary").click()
    box = src.locator(".lcode")
    assert box.get_attribute("tabindex") == "0" and box.get_attribute("aria-label").startswith("Lean source")
    assert box.bounding_box()["width"] <= width and overflow(pg) <= 0
    fs = float(pg.evaluate("getComputedStyle(document.querySelector('#proof-geometric-similarity .ll code')).fontSize[0] === undefined ? 0 : parseFloat(getComputedStyle(document.querySelector('#proof-geometric-similarity .ll code')).fontSize)"))
    assert fs >= 12.5, fs
    assert box.evaluate("e => e.scrollWidth > e.clientWidth") in (True, False)      # long lines scroll inside the box, never the page
    pg.locator(".aboutmenu summary").click()
    link = pg.locator(".aboutmenu a[href$='#/proofs']")
    assert link.count() == 1 and link.text_content() == "Lean proofs" and link.get_attribute("aria-current") == "page"
    pg.click(".proofindex a[data-f=cantilever-guard]")
    assert pg.evaluate("document.activeElement.id") == "proof-cantilever-guard-h" and "f=cantilever-guard" in pg.evaluate("location.hash")
    assert overflow(pg) <= 0


def test_page_is_honest_when_the_gallery_is_absent(browser, base):
    s = json.loads((ROOT / "site/data/snapshot.json").read_text()); s.pop("lean_gallery", None)
    pg = browser.new_page(); pg.route("**/data/snapshot.json", lambda r: r.fulfill(json=s))
    pg.goto(base + "#/proofs"); pg.wait_for_selector("#main h1")
    assert "not in this snapshot" in pg.locator("#main").inner_text() and pg.locator(".proof").count() == 0
