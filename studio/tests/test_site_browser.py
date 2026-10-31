"""Browser smoke tests for the Delphi Frontier site (real clicks, drawer, filter, Back, mobile, bad data).

Run capped:  systemd-run --user --scope -p TasksMax=128 -p MemoryMax=4G -p MemorySwapMax=0 -p RuntimeMaxSec=600 \
             python3 -m pytest tests/test_site_browser.py -q
"""
import functools
import http.server
import json
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sync_api = pytest.importorskip("playwright.sync_api")


def serve(directory):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    handler.log_message = lambda *a, **k: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}/"


@pytest.fixture(scope="module")
def base():
    srv, url = serve(ROOT / "site")
    yield url
    srv.shutdown()


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


_OPEN = []


@pytest.fixture(autouse=True)
def _close_pages():
    yield
    while _OPEN:
        _OPEN.pop().close()


def page(browser, w=1280, h=900):
    pg = browser.new_page(viewport={"width": w, "height": h})
    _OPEN.append(pg)
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.on("console", lambda m: pg.errors.append(m.text) if m.type == "error" and "404" not in m.text else None)
    return pg


def test_build_is_current_and_portable():
    r = subprocess.run([sys.executable, "scripts/build_site.py", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout
    src = (ROOT / "scripts/build_site.py").read_text()
    assert "/home/" not in src and "/data/" not in src.replace("site/data", "")
    assert "def test_" not in src


def test_every_view_renders_without_errors(browser, base):
    pg = page(browser)
    for route in ["frontier", "knowledge", "knowledge?tab=graph", "knowledge?tab=mission", "knowledge?tab=catalog", "engineering", "evidence", "work", "belief", "search?q=fisher&tab=catalog"]:
        pg.goto(base + "#/" + route)
        pg.wait_for_selector("#main h1, #main h2", timeout=5000)
        assert pg.locator("#main").inner_text().strip(), route
    assert pg.errors == []


def test_whiteboard_selection_persists_and_back(browser, base):
    pg = page(browser)
    pg.goto(base + "#/frontier")
    pg.wait_for_selector("#wbgraph g.g-node")
    pg.locator("#wbgraph g.g-node", has_text="Turn Davenport").first.click()
    pg.wait_for_selector("#qdetail h3:has-text('Davenport')")
    assert "/frontier/EQ1" in pg.url
    pg.locator("#wbgraph g.g-node", has_text="C1 Wing-loading").first.click()
    pg.wait_for_selector("#qdetail h3:has-text('Wing-loading')")
    pg.go_back()
    pg.wait_for_selector("#qdetail h3:has-text('Davenport')")
    pg.locator("#wbgraph g.g-edge").first.dispatch_event("click")
    assert "edge" in pg.locator("#qdetail").inner_text().lower()


def test_direction_filter_and_search(browser, base):
    pg = page(browser)
    pg.goto(base + "#/frontier")
    pg.get_by_role("link", name="bottom-up (theory fit, literature gap)").click()
    pg.wait_for_selector(".count")
    assert "of 12 questions shown" in pg.locator(".count").inner_text()
    shown = int(pg.locator(".count").inner_text().split(" ")[0])
    assert 0 < shown < 12
    pg.goto(base + "#/frontier?q=zzzznothing")
    pg.wait_for_selector("text=No question matches")


def test_source_drawer_opens_document_escape_and_back(browser, base):
    pg = page(browser)
    pg.goto(base + "#/evidence")
    pg.get_by_role("link", name="Open the full document").first.click()
    pg.wait_for_selector("#drawer:not([hidden]) .md h2, #drawer:not([hidden]) .md p")
    assert "STOPPED" in pg.locator("#drawer").inner_text() or "Verdict" in pg.locator("#drawer").inner_text()
    pg.keyboard.press("Escape")
    pg.wait_for_selector("#drawer", state="hidden")
    assert "src=" not in pg.url


def test_math_renders_with_katex(browser, base):
    pg = page(browser)
    pg.goto(base + "#/knowledge/turing-ddi")
    pg.wait_for_selector("#cdetail .katex")
    assert pg.locator("#cdetail .tex-fallback").count() == 0


def test_engineering_checks_never_fake_a_pass(browser, base):
    pg = page(browser)
    pg.goto(base + "#/engineering")
    pg.wait_for_selector("tr[data-c=C1] .cstat .pill")
    txt = lambda c: pg.locator(f"tr[data-c={c}] .cstat").inner_text().lower()
    assert "pass" in txt("C1")
    for c in ("C2", "C4", "C5", "C6a"):
        assert "pass" not in txt(c) and "cannot evaluate" in txt(c), c
    pg.get_by_role("button", name="Nothing declared").click()
    assert "undetermined" in pg.locator("#verdict").inner_text().lower()
    pg.fill("#f-mass_kg", "-3")
    assert "positive number" in pg.locator("#e-mass_kg").inner_text()
    pg.get_by_role("button", name="Request a solver run").click()
    pg.wait_for_selector(".adapter-out.unavailable")


def test_mobile_has_no_horizontal_page_overflow(browser, base):
    pg = page(browser, 400, 860)
    for route in ["frontier", "knowledge?tab=graph", "engineering", "evidence", "work", "belief"]:
        pg.goto(base + "#/" + route)
        pg.wait_for_timeout(1200)
        assert not pg.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth"), route


def test_malformed_and_missing_data_show_an_error_not_a_blank(browser, tmp_path):
    shutil.copytree(ROOT / "site", tmp_path / "s")
    (tmp_path / "s/data/snapshot.json").write_text("{not json")
    srv, url = serve(tmp_path / "s")
    try:
        pg = page(browser)
        pg.goto(url)
        pg.wait_for_selector("text=Data could not be loaded")
        (tmp_path / "s/data/snapshot.json").write_text(json.dumps({"schema": "wrong"}))
        pg.reload()
        pg.wait_for_selector("text=unexpected shape")
        (tmp_path / "s/data/snapshot.json").unlink()
        pg.reload()
        pg.wait_for_selector("text=Data could not be loaded")
    finally:
        srv.shutdown()
