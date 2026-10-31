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
    for route in ["home", "studio/flying-fish", "studio/flying-fish?scale=organ", "entity/Claim/turing-ddi", "frontier", "knowledge?tab=graph", "engineering", "simulations", "evidence", "work", "work?tab=receipts", "belief"]:
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


def test_coupling_manifest_verdicts_are_shown_with_their_scope(browser, base):
    snap = json.loads((ROOT / "site/data/snapshot.json").read_text())
    pg = page(browser)
    pg.goto(base + "#/simulations")
    pg.wait_for_selector("#cp-h, h2:has-text('Couplings between the models')")
    txt = pg.locator("#main").inner_text().lower()
    M = snap.get("coupling_manifest")
    if not M:
        assert "no coupling manifest is present" in txt
        return
    assert "registered calibrations: none" in txt and "not biology" in txt
    assert pg.locator("section[aria-labelledby=cp-h] tbody tr").count() >= len(M["couplings"])
    assert str(M["counts"]["refused"]) + " refused" in txt


_AUDIT = """() => { const bad = []; const name = (e) => (e.getAttribute('aria-label') || e.getAttribute('title') || e.textContent || '').trim();
  document.querySelectorAll('img').forEach((i) => { if (!i.hasAttribute('alt')) bad.push('img without alt'); });
  document.querySelectorAll('button,a[href]').forEach((e) => { if (!name(e) && !e.querySelector('img[alt]')) bad.push('control without a name: ' + e.outerHTML.slice(0, 60)); });
  document.querySelectorAll('input:not([type=hidden]),select,textarea').forEach((e) => { const l = (e.id && document.querySelector('label[for="' + e.id + '"]')) || e.closest('label') || e.getAttribute('aria-label'); if (!l) bad.push('unlabelled field: ' + e.outerHTML.slice(0, 60)); });
  let prev = 0; document.querySelectorAll('h1,h2,h3,h4').forEach((h) => { const n = +h.tagName[1]; if (prev && n > prev + 1) bad.push('heading jump h' + prev + ' to h' + n); prev = n; });
  if (document.querySelectorAll('h1').length !== 1) bad.push('h1 count');
  const ids = {}; document.querySelectorAll('[id]').forEach((e) => { if (ids[e.id]) bad.push('duplicate id ' + e.id); ids[e.id] = 1; });
  return bad; }"""


def test_accessibility_basics_on_every_view(browser, base):
    pg = page(browser)
    for route in ["home", "studio", "studio/flying-fish", "studio/flying-fish?scale=organism", "entity/Claim/turing-ddi", "graph/Claim/turing-ddi", "frontier", "knowledge", "knowledge?tab=graph", "knowledge?tab=mission", "knowledge?tab=catalog", "engineering", "simulations", "evidence", "work", "work?tab=specs", "work?tab=work", "work?tab=resources", "work?tab=receipts", "work?tab=runtime", "belief", "search?q=fisher&tab=catalog"]:
        pg.goto(base + "#/" + route)
        pg.wait_for_selector("#main h1")
        pg.wait_for_timeout(500)
        assert pg.evaluate(_AUDIT) == [], route


def test_archive_release_is_a_claim_not_a_measurement_and_long_cells_are_clipped(browser, base):
    """Regressions found on the live public site: an archive deployment reports claimed_sha, and declared artifact text can be thousands of characters."""
    pg = page(browser)
    pg.goto(base + "#/work")
    pg.wait_for_selector("h1:has-text('System')")
    out = pg.evaluate("""() => DF.liveSystem({report: {schema: 'frontier.system/1', generated_at: 'x', claimed_sha: '12eb390c255f362a546ab1b216f801814c1a75d5', deployed_sha: null,
      release: {mode: 'measured', checkout_sha: null, sha: null, directory_claim: {sha: '12eb390c255f362a546ab1b216f801814c1a75d5', marker_matches_name: true, label: 'claim: dir name',
      contents: {checked: true, matches_recorded_tree: true, files_hashed: 543, seconds: 0.05, tree_sha_computed: 'abc', meaning: 'm'}}}}}).toString()""")
    assert "claim, not measured" in out and "12eb390c255f362a546ab1b216f801814c1a75d5" in out and "match" in out
    assert "Running release (measured)" not in out
    clipped = pg.evaluate("() => DF.clipCell('x'.repeat(3000)).toString()")
    assert clipped.count("x") == 220 + 3000 and "show all (3000 characters)" in clipped and DF_short(pg)


def DF_short(pg):
    return pg.evaluate("() => DF.clipCell('short').toString() === 'short'")


def test_entity_page_is_readable_with_equation_and_optional_raw_view(browser, base):
    pg = page(browser)
    pg.goto(base + "#/entity/Claim/turing-ddi")
    pg.wait_for_selector("#entity h1:has-text('')", timeout=15000)
    pg.wait_for_selector(".entmain .katex", timeout=15000)
    txt = pg.locator("#main").inner_text()
    assert "Statement" in txt and "Context" in txt and "Limitations" in txt and "Assumptions" in txt
    assert "Imported or upstream labels are assertions" in txt
    assert pg.locator(".advraw pre").is_hidden(), "the raw envelope is an advanced view, collapsed by default"
    pg.locator(".advraw summary").click()
    assert "turing-ddi" in pg.locator(".advraw pre").inner_text()
    pg.goto(base + "#/entity/Claim/no-such-id")
    pg.wait_for_selector("h1:has-text('Not found')", timeout=15000)


def test_search_autocomplete_is_typed_keyboard_operable_and_honest(browser, base):
    pg = page(browser)
    pg.goto(base + "#/frontier")
    pg.wait_for_selector("#gq")
    pg.fill("#gq", "f")
    assert pg.locator("#ac-list").is_hidden(), "one character does not search"
    pg.fill("#gq", "fisher")
    pg.wait_for_selector("#ac-list [role=option]", timeout=10000)
    assert pg.get_attribute("#gq", "aria-expanded") == "true"
    assert pg.locator("#ac-list .acg").count() >= 1
    assert "lexical" in pg.locator("#ac-list .acf").inner_text().lower() and "semantic" not in pg.locator("#ac-list .acf").inner_text().lower().replace("semantic index is not connected", "")
    pg.press("#gq", "ArrowDown")
    assert pg.get_attribute("#gq", "aria-activedescendant")
    pg.press("#gq", "Enter")
    pg.wait_for_selector("#entity h1, .entmain", timeout=10000)
    assert "/entity/" in pg.url
    pg.goto(base + "#/frontier")
    pg.wait_for_selector("#gq")
    pg.fill("#gq", "zzzzqqqq")
    pg.wait_for_selector("#ac-list .ace", timeout=10000)
    assert "No match" in pg.locator("#ac-list .ace").inner_text()
    pg.press("#gq", "Escape")
    assert pg.locator("#ac-list").is_hidden()


def test_two_entry_paths_studio_and_frontier_are_clear_and_cross_linked(browser, base):
    pg = page(browser)
    pg.goto(base)
    pg.wait_for_selector(".paths .path.studio")
    assert pg.locator(".brand").inner_text().lower().startswith("morphoswarm")
    nav = pg.locator("header nav a").all_inner_texts()
    assert nav[:2] == ["Studio", "Frontier"], nav
    assert pg.locator(".path.studio a:has-text('Open the Flying fish studio')").count() == 1
    assert pg.locator(".path.frontier a:has-text('Open the Frontier')").count() == 1
    pg.locator(".path.studio a:has-text('Open the Flying fish studio')").click()
    pg.wait_for_selector(".studiogrid")
    assert "/studio/flying-fish" in pg.url
    assert pg.locator("header nav a[aria-current=page]").inner_text() == "Studio"


def test_studio_subsystems_show_models_gaps_questions_and_local_only_drafts(browser, base):
    pg = page(browser)
    pg.goto(base + "#/studio/flying-fish?scale=cellular")
    pg.wait_for_selector(".studiogrid")
    txt = pg.locator(".studiomain").inner_text().lower()
    assert "collier 1996" in txt or "delta-notch" in txt
    assert pg.locator(".studiomain video").count() >= 0
    pg.get_by_role("link", name="Molecular", exact=False).first.click()
    pg.wait_for_selector("text=No model is attached at this scale")
    assert "daane" in pg.locator(".studiomain").inner_text().lower()
    pg.fill("#annbody", "Check the Daane transfer claim")
    pg.click("#annsave")
    assert "local draft, not submitted" in pg.locator("#annlist").inner_text()
    assert "nothing is submitted" in pg.locator("#ann-h ~ .note").inner_text().lower()
    pg.locator("#annlist [data-del]").first.click()
    assert "No drafts" in pg.locator("#annlist").inner_text()
    pg.goto(base + "#/studio/not-a-project")
    pg.wait_for_selector("h1:has-text('No such project')")


def test_goal_text_routes_to_project_subsystem_and_work_without_generating_anything(browser, base):
    pg = page(browser)
    pg.goto(base + "#/home")
    pg.wait_for_selector("#goalq")
    pg.fill("#goalq", "make a fin that can glide")
    pg.click(".goalform button")
    pg.wait_for_selector("#gr-h", timeout=15000)
    txt = pg.locator("#goalout").inner_text().lower()
    assert "does not design an organism" in txt and "flying fish" in txt and "organism" in txt
    pg.fill("#goalq", "zzzz qqqq")
    pg.click(".goalform button")
    pg.wait_for_selector("text=No project covers this goal", timeout=15000)
    assert "no open question matches" in pg.locator("#goalout").inner_text().lower()


def test_claim_browser_filters_cards_and_drills_down(browser, base):
    pg = page(browser)
    pg.goto(base + "#/knowledge")
    pg.wait_for_selector(".claimcards .claimcard")
    n = int(pg.locator("#cbrowse .count").inner_text().split(" ")[0])
    assert n >= 21 and "not structured fields" in pg.locator("#cbrowse").inner_text()
    pg.fill("#cbrowse input[name=q]", "turing")
    pg.click("#cbrowse button[type=submit]")
    pg.wait_for_url("**q=turing**")
    pg.wait_for_selector(".claimcards .claimcard")
    assert int(pg.locator("#cbrowse .count").inner_text().split(" ")[0]) < n
    pg.locator(".claimcard a").first.click()
    pg.wait_for_selector(".entmain h2:has-text('Statement')", timeout=15000)


def test_graph_view_exists_is_keyboard_operable_and_says_how_it_was_built(browser, base):
    pg = page(browser)
    pg.goto(base + "#/entity/Claim/turing-ddi")
    pg.wait_for_selector(".entside a:has-text('neighbourhood graph')")
    pg.click(".entside a:has-text('neighbourhood graph')")
    pg.wait_for_selector("#gv svg .g-node", timeout=15000)
    assert "Derived in this browser" in pg.locator("#gwrap").inner_text()
    assert "Zoom in" in pg.locator(".gtools").inner_text()
    pg.locator("#gv .g-node").first.focus()
    pg.keyboard.press("Enter")
    assert "Open the page" in pg.locator("#gdetail").inner_text()
    pg.goto(base + "#/graph/Claim/no-such")
    pg.wait_for_selector("text=could not be built", timeout=15000)


def test_snapshot_document_and_download_links_use_types_the_runtime_serves(browser, base):
    """Regression for the live 404s: the runtime serves .md and .csv only in narrow places, so documents ship as .txt and CSVs live under artifacts/."""
    import os
    snap = json.loads((ROOT / "site/data/snapshot.json").read_text())
    hrefs = [d["href"] for d in snap["documents"]]
    sim = snap.get("simulation") or {}
    hrefs += [f["href"] for f in sim.get("files", [])] + [f["href"] for f in (sim.get("controlled") or {}).get("files", [])]
    for h in hrefs:
        assert (ROOT / "site" / h).is_file(), h
        ext = os.path.splitext(h)[1]
        assert ext != ".md", h
        assert ext != ".csv" or h.startswith("artifacts/"), h
    pg = page(browser)
    pg.goto(base + "#/evidence?src=doc:2026-10-31-oca2-exon21-molino-RESULT")
    pg.wait_for_selector("#drawer:not([hidden]) .md", timeout=15000)


def test_live_style_question_table_row_click_and_id_not_wrapped(browser, base):
    pg = page(browser)
    pg.goto(base + "#/frontier")
    pg.wait_for_selector("#livepanel h2")
    # snapshot mode shows no live table; the curated table keeps ids on one line and rows are links
    h = pg.evaluate("() => { const a = document.querySelector('.qtable td:first-child a'); return a ? a.getBoundingClientRect().height : 0; }")
    assert 0 < h < 30, h


def test_evidence_overview_is_short_and_artifacts_have_their_own_paged_tab(browser, base):
    pg = page(browser)
    pg.goto(base + "#/evidence")
    pg.wait_for_selector("#ev-a")
    assert pg.evaluate("document.documentElement.scrollHeight") < 8000
    pg.click("a:has-text('Open the artifacts index')")
    pg.wait_for_selector("#artifacts table", timeout=15000)
    assert pg.locator("#artifacts tbody tr").count() <= 20


def test_genomic_slice_is_data_with_receipts_or_an_honest_absence(browser, base):
    snap = json.loads((ROOT / "site/data/snapshot.json").read_text())
    pg = page(browser)
    pg.goto(base + "#/studio/flying-fish?scale=molecular")
    pg.wait_for_selector(".studiogrid")
    txt = pg.locator(".studiomain").inner_text().lower()
    G = snap.get("genomics")
    if not G:
        assert "no genomic data slice is present" in txt
        return
    assert "data, not a model" in txt and "nothing here is a prediction" in txt
    assert pg.locator(".studiomain table tbody tr").count() >= len(G["genes"])
    assert all("?" not in r["url"] for r in G["receipts"]), "signed or query-bearing URLs must not be shipped"
