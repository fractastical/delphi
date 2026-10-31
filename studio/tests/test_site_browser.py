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
    text = pg.locator(".count").inner_text()
    shown, total = int(text.split(" ")[0]), int(text.split(" of ")[1].split(" ")[0])
    assert 0 < shown < total
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


def test_artifact_download_link_only_for_declared_downloadable_https(browser, base):
    """Formatter unit test on synthetic input (the scratch live node holds no artifacts): never links an undeclared file."""
    pg = page(browser)
    pg.goto(base + "#/evidence")
    pg.wait_for_selector("#main h1")
    rows = pg.evaluate("""() => DF.liveArtifacts([
      {artifact: {title: 'a', uri: 'https://x.example/a.stl', sha256: 'a'.repeat(64), byte_size: 1, role: 'geometry', availability: 'downloadable'}, relation: 'supports', evidence_kind: 'simulated'},
      {artifact: {title: 'b', uri: 'https://x.example/b.csv', sha256: 'b'.repeat(64), byte_size: 1, role: 'output', availability: 'referenced'}},
      {artifact: {title: 'c', uri: 'urn:sha256:' + 'c'.repeat(64), sha256: 'c'.repeat(64), byte_size: 1, role: 'certificate', availability: 'referenced'}}
    ]).map(r => [r.type, r.download])""")
    assert rows == [["geometry", "https://x.example/a.stl"], ["data", None], ["proof", None]]


def test_recorded_results_show_lean_receipt_scope_and_honest_absence(browser, base):
    pg = page(browser)
    pg.goto(base + "#/engineering")
    pg.wait_for_selector("#rr-h")
    sec = pg.locator("section[aria-labelledby=rr-h]").inner_text().lower()
    assert "not run by this page" in sec and "not about any fish" in sec
    snap = json.loads((ROOT / "site/data/snapshot.json").read_text())
    if snap["simulation"]:
        assert "glide simulation" in sec and "authors' own caveat" in sec
        pg.locator("details.pareto summary").click()
        pg.locator("[data-pareto]").first.click()
        assert float(pg.input_value("#f-mass_kg")) > 0 and pg.input_value("#f-standard_length_m") == ""
    else:
        assert "no recorded simulation results are present" in sec and "no mesh" in sec


def test_simulation_gallery_never_invents_a_video(browser, base):
    pg = page(browser)
    pg.goto(base + "#/simulations")
    pg.wait_for_selector(".simcard, .empty")
    snap = json.loads((ROOT / "site/data/snapshot.json").read_text())
    verified = [m for m in snap["simulation_manifests"] if m.get("video_state") == "present_verified"]
    assert pg.locator("video").count() == len(verified), "a player may appear only for a verified video file"
    html = pg.evaluate("""() => DF.views.simulations(Object.assign({}, DF.api.state.snapshot, {simulation: null, simulation_manifests: [
      {id: 'ok', title: 'ok', scales: ['cellular'], video_state: 'present_verified', video_href: 'artifacts/simulations/ok/v.mp4', manifest: 'm'},
      {id: 'miss', title: 'miss', scales: ['cellular'], video_state: 'declared_but_missing', manifest: 'm'},
      {id: 'bad', title: 'bad', scales: ['cellular'], video_state: 'digest_mismatch', manifest: 'm'},
      {id: 'none', title: 'none', scales: ['cellular'], video_state: 'none', manifest: 'm'}]})).html.toString()""")
    assert html.count("<video") == 1 and "artifacts/simulations/ok/v.mp4" in html
    assert html.count("No video file.") == 3 and "does not match its declared sha256" in html


def test_attestation_card_states_it_is_not_a_population_rate(browser, base):
    pg = page(browser)
    pg.goto(base + "#/evidence")
    pg.wait_for_selector("#ev-att")
    txt = pg.locator("section[aria-labelledby=ev-att]").inner_text().lower()
    assert "not a population rate" in txt and "15 of 15" in txt and "4" in txt


def test_mcp_tools_come_from_the_document(browser, base):
    pg = page(browser)
    pg.goto(base + "#/work?tab=runtime")
    pg.wait_for_selector("h2:has-text('Declared capabilities')")
    assert "frontier_artifacts" in pg.locator("#main").inner_text()


def test_system_view_keeps_author_report_and_measured_apart(browser, base):
    pg = page(browser)
    pg.goto(base + "#/work")
    pg.wait_for_selector("h1:has-text('System')")
    txt = pg.locator("#main").inner_text().lower()
    assert "author report" in txt and "measured" in txt and "not reported: a snapshot cannot know it" in txt
    pg.get_by_role("link", name="Resources").click()
    pg.wait_for_selector("h2:has-text('actual versus unknown')")
    assert pg.locator("#main").inner_text().lower().count("unknown") >= 3
    pg.get_by_role("link", name="Receipts").click()
    pg.wait_for_selector("h2:has-text('What has been measured')")
    assert "does not cover" not in pg.locator("#main").inner_text().lower() and "receipt" in pg.locator("#main").inner_text().lower()
    pg.get_by_role("link", name="Specs and goals").click()
    pg.wait_for_selector("h2:has-text('SPEC-005 acceptance rows')")
    pg.get_by_role("link", name="SPEC-005", exact=False).first.click()
    pg.wait_for_selector("#drawer:not([hidden]) .md")
    assert "Solver and Lean boundary" in pg.locator("#drawer").inner_text()
    pg.go_back()
    pg.wait_for_selector("#drawer", state="hidden")


def test_print_forms_and_videos_match_their_declared_bytes(browser, base):
    """Whatever artifacts the tree provides: every offered file exists and equals its declared sha256; absence is stated."""
    import hashlib
    snap = json.loads((ROOT / "site/data/snapshot.json").read_text())
    pg = page(browser)
    pg.goto(base + "#/engineering")
    pg.wait_for_selector("#pf-h")
    pf = snap.get("print_forms")
    if not pf:
        assert "no printable-form study is present" in pg.locator("section[aria-labelledby=pf-h]").inner_text().lower()
    else:
        for f in pf["forms"]:
            for key in ("stl", "stand_stl", "image", "image_on_stand"):
                ent = f["files"].get(key)
                if ent:
                    assert hashlib.sha256((ROOT / "site" / ent["href"]).read_bytes()).hexdigest() == ent["sha256"] == ent["declared_sha256"], (f["id"], key)
        pg.locator("[data-loadmesh]").first.click()
        pg.wait_for_selector(".meshhost canvas")
        assert pg.locator(".meshhost .viewbar button").count() == 4
    pg.goto(base + "#/simulations")
    pg.wait_for_selector(".simcard, .empty")
    vids = [m for m in snap["simulation_manifests"] if m.get("video_state") == "present_verified"]
    assert pg.locator("video").count() == len(vids)
    for m in vids:
        assert (ROOT / "site" / m["video_href"]).is_file()


def test_frontier_labels_snapshot_versus_live_views(browser, base):
    pg = page(browser)
    pg.goto(base + "#/frontier")
    pg.wait_for_selector("#livepanel h2")
    assert "snapshot" in pg.locator("#livepanel").inner_text().lower()
    assert "curated mission projection from the snapshot" in pg.locator("section.board").inner_text().lower()
