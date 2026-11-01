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


def test_print_laws_keep_mass_failure_exact_files_and_display_scope(browser, base):
    from urllib.parse import urlencode

    pg = page(browser)
    pg.goto(base + "#/print-laws")
    pg.wait_for_selector("#print-file")
    text = pg.locator("#main").inner_text()
    assert "20.33 g" in text and "26.07 g" in text and "13.55 g" in text
    assert "not cleared" in text and "not weighed" in text
    assert pg.locator("#main .katex").count() > 5
    assert pg.locator("#main .tex-fallback").count() == 0
    assert pg.get_by_role("link", name="Download this file").get_attribute("href").endswith("r4-daane-printfix/stl/body.stl")
    prop = "artifacts/print-v3/stl/fish3d-v3a-fan-prop-scales.stl"
    pg.select_option("#print-file", prop)
    pg.wait_for_selector("#print-file-title:has-text('fish3d-v3a-fan-prop-scales.stl')")
    assert "No flight-mass budget" in pg.locator("#main").inner_text()
    assert pg.locator("#print-assembly").count() == 0
    withdrawn = "artifacts/glider/r3-daane/stl/pectoral_R.stl"
    pg.goto(base + "#/print-laws?" + urlencode({"file": withdrawn}))
    pg.wait_for_selector("#print-file-title")
    assert "Withdrawn." in pg.locator("#main").inner_text()
    assert pg.get_by_role("link", name="Download this file").count() == 0
    pg.set_viewport_size({"width": 390, "height": 844})
    assert pg.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
    pg.goto(base + "#/home")
    pg.wait_for_selector("#home-model-downloads")
    assert pg.locator('#home-model-downloads a[href*="/print-laws?file="]').count() >= 123
    assert pg.errors == []


def test_every_view_renders_without_errors(browser, base):
    pg = page(browser)
    for route in ["experimentation", "assemblies", "demo", "blueprints", "reuse", "regulatory", "history", "formalize?ex=cantilever", "frontier", "knowledge", "knowledge?tab=graph", "knowledge?tab=mission", "knowledge?tab=catalog", "engineering", "evidence", "work", "belief", "search?q=fisher&tab=catalog"]:
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
    verified = [m for m in snap["simulation_manifests"] if m.get("video_state") in ("present_verified", "present_unpinned")]
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
    for tool in ("frontier_artifacts", "frontier_simulate", "frontier_project_inspect", "frontier_propose"):
        assert tool in pg.locator("#main").inner_text()


def test_system_view_keeps_author_report_and_measured_apart(browser, base):
    pg = page(browser)
    pg.goto(base + "#/work")
    pg.wait_for_selector("h1:has-text('System')")
    txt = pg.locator("#main").inner_text().lower()
    assert "author report" in txt and "measured" in txt and "not reported: a snapshot cannot know it" in txt
    pg.get_by_role("link", name="Resources").click()
    pg.wait_for_selector("h2:has-text('Recorded resource inventory')")
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
    vids = [m for m in snap["simulation_manifests"] if m.get("video_state") in ("present_verified", "present_unpinned")]
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
    for route in ["home", "experimentation", "assemblies", "demo", "blueprints", "reuse", "regulatory", "history", "formalize?ex=cantilever", "studio", "studio/flying-fish", "studio/flying-fish?scale=organism", "entity/Claim/turing-ddi", "graph/Claim/turing-ddi", "frontier", "knowledge", "knowledge?tab=graph", "knowledge?tab=mission", "knowledge?tab=catalog", "engineering", "simulations", "evidence", "work", "work?tab=specs", "work?tab=work", "work?tab=resources", "work?tab=receipts", "work?tab=runtime", "belief", "search?q=fisher&tab=catalog"]:
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


def test_graph_without_a_runtime_does_not_invent_a_neighbourhood(browser, base):
    pg = page(browser)
    pg.goto(base + "#/entity/Claim/turing-ddi")
    pg.wait_for_selector(".entside a:has-text('neighbourhood graph')")
    pg.click(".entside a:has-text('neighbourhood graph')")
    pg.wait_for_selector("#gwrap .empty", timeout=15000)
    txt = pg.locator("#gwrap").inner_text()
    assert "not available on this node" in txt and "does not guess" in txt
    assert pg.locator("#gv").count() == 0, "no drawing without the graph service"
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


def test_project_draft_drives_coverage_and_annotation_drafts_export_in_the_contract_shape(browser, base):
    snap = json.loads((ROOT / "site/data/snapshot.json").read_text())
    pg = page(browser)
    pg.goto(base + "#/studio/flying-fish?scale=molecular")
    pg.wait_for_selector(".studiogrid")
    pd = (snap.get("project_drafts") or {}).get("flying-fish")
    if pd:
        txt = pg.locator("#main").inner_text().lower()
        assert "validated but not submitted" in txt and "project record draft" in txt
        assert "source only" in pg.locator(".studiomain").inner_text().lower()
    pg.select_option("#annkind", "proposed_edit")
    pg.fill("#annbody", "Replace the molecular gap text")
    pg.click("#annsave")
    assert "proposed_edit" in pg.locator("#annlist").inner_text()
    with pg.expect_download() as dl:
        pg.click("#annlist [data-exp]")
    doc = json.loads(Path(dl.value.path()).read_text())
    assert doc["payload"]["kind"] == "proposed_edit" and doc["payload"]["anchor"]["frame"] == "ui_anchor" and doc["payload"]["anchor"]["record"] is None
    assert "not submitted" in doc["note"].lower()


SNAP_REF = lambda: next(c for c in json.loads((ROOT / "site/data/catalog.json").read_text())["records"] if c["ref"]["kind"] == "Claim")["ref"]


def test_entity_pin_is_exact_and_never_replaced_by_a_head(browser, base):
    ref = SNAP_REF()
    pg = page(browser)
    pg.goto(base + f"#/entity/Claim/{ref['id']}?v={ref['version']}&ns={ref['namespace']}")
    pg.wait_for_selector(".entmain", timeout=15000)
    assert "exact pin from the link" in pg.locator("#entity").inner_text()
    pg.goto(base + f"#/entity/Claim/{ref['id']}?v={'0' * 64}&ns={ref['namespace']}")
    pg.wait_for_selector("h1:has-text('Not found')", timeout=15000)
    assert "not replaced by another version" in pg.locator("#entity").inner_text()
    pg.goto(base + f"#/entity/Claim/{ref['id']}")
    pg.wait_for_selector(".entmain", timeout=15000)
    assert "resolved to the current head" in pg.locator("#entity").inner_text()


def test_runtime_graph_renders_object_scope_succinctly_and_with_exact_pins(browser, base):
    """Renderer test with a canned runtime (the static server has no /api): live health and session, an exact record, and the market graph shape."""
    ref = SNAP_REF(); other = {"namespace": "node-a", "kind": "Evidence", "id": "ev-1", "version": "b" * 64}
    pg = page(browser)
    pg.route("**/api/health", lambda r: r.fulfill(json={"mode": "live", "status": "ok"}))
    pg.route("**/api/session", lambda r: r.fulfill(json={"authenticated": False, "public_access": True, "csrf": "x"}))
    pg.route("**/api/catalog*", lambda r: r.fulfill(json={"mode": "live", "namespace": "snapshot", "results": [], "next_cursor": None}))
    pg.route("**/api/record*", lambda r: r.fulfill(json={"mode": "live", "record": {"namespace": ref["namespace"], "kind": "Claim", "id": ref["id"], "version": ref["version"], "payload": {"title": "T", "statement": "S"}}, "local_status": "proposed", "is_head": True, "action": None}))
    pg.route("**/api/graph*", lambda r: r.fulfill(json={"schema": "frontier-graph-0.1", "truncated": False, "counts": {"nodes": 2, "edges": 1},
        "scope": {"visibility": "public", "edge_origin": {"typed": 1, "derived": 0}, "incoming_edges": ["a"]},
        "nodes": [{"id": "c", "type": "Claim", "kind": "Claim", "ref": ref, "title": "Centre", "local_status": "proposed", "is_head": True, "distance": 0}, {"id": "e", "type": "Evidence", "kind": "Evidence", "ref": other, "title": "Neighbour", "local_status": "imported_unreviewed", "is_head": True, "distance": 1}],
        "edges": [{"id": "x", "from": "e", "to": "c", "kind": "targets", "label": "targets"}]}))
    pg.goto(base + f"#/graph/Claim/{ref['id']}?v={ref['version']}&ns={ref['namespace']}")
    pg.wait_for_selector("#gv svg .g-node", timeout=15000)
    txt = pg.locator("#gwrap").inner_text()
    assert "[object Object]" not in txt and "visibility: public" in txt
    hrefs = pg.locator("#gdetail a, #gwrap table a").evaluate_all("els => els.map(e => e.getAttribute('href'))")
    assert any(("v=" + "b" * 64) in h and "ns=node-a" in h for h in hrefs), hrefs
    fills = pg.evaluate("[...document.querySelectorAll('.gsvg .g-node .g-label')].map(e => getComputedStyle(e).fill)")
    assert fills and all(f != "rgb(255, 255, 255)" for f in fills), fills        # labels sit on the cream canvas: never white


def _mock_live(pg, run_handler):
    pg.route("**/api/health", lambda r: r.fulfill(json={"mode": "live", "status": "ok"}))
    pg.route("**/api/session", lambda r: r.fulfill(json={"authenticated": False, "public_access": True, "csrf": "x"}))
    pg.route("**/api/catalog*", lambda r: r.fulfill(json={"mode": "live", "namespace": "n", "results": [], "next_cursor": None}))
    pg.route("**/api/attention", lambda r: r.fulfill(status=503, json={"error": "attention_unavailable", "message": "no"}))
    pg.route("**/api/simulations/run", run_handler)


def test_simulation_preview_widget_follows_the_contract_and_never_clamps(browser, base):
    """Renderer and request-shape test against a canned node: exact envelope, range refusal, completed plot, unknown without frames, safe error text."""
    seen = []
    def handler(route):
        body = json.loads(route.request.post_data); seen.append(body)
        if body["model"] == "bioelectric" and body["parameters"].get("sodium_scale") == 0.35:
            route.fulfill(json={"schema": "frontier.simulation.preview/1", "status": "completed", "model": "bioelectric", "evidence_kind": "SimulationResult", "persisted": False, "calibrated": False,
                "request_sha256": "a" * 64, "effective_request_sha256": "b" * 64, "code_sha256": "c" * 64, "computed_at": "2026-10-31T21:00:00Z", "scope": "Preview only.", "preview_limits": {"duration_ms": [10, 30]},
                "result": {"time_ms": [0, 1, 2, 3], "voltage_mV": [[-70, -70], [-60, -65], [-40, -50], [-30, -45]]}})
        elif body["model"] == "mechanobio":
            route.fulfill(status=429, json={"error": "solver_busy", "message": "Two previews are running."})
        else:
            route.fulfill(json={"schema": "frontier.simulation.preview/1", "status": "unknown", "reason": "compute_budget_exhausted", "model": "bioelectric", "persisted": False, "calibrated": False})
    pg = page(browser)
    _mock_live(pg, handler)
    pg.goto(base + "#/studio/flying-fish?scale=cellular")
    pg.wait_for_selector("#simwidget form", timeout=15000)
    pg.fill("#sw-duration_ms", "99")
    pg.click("#simwidget button[type=submit]")
    assert "not clamped" in pg.locator("#sw-err").inner_text() and not seen, "an out-of-range value must be refused before any request"
    pg.fill("#sw-duration_ms", "30")
    pg.click("#simwidget button[type=submit]")
    pg.wait_for_selector("#sw-out .rescard svg.chart", timeout=15000)
    out = pg.locator("#sw-out").inner_text().lower()
    assert "persisted: false" in out and "calibrated: false" in out and "not calibrated" in out and "completed" in out
    assert set(seen[0]) == {"model", "parameters"} and seen[0]["model"] == "bioelectric" and seen[0]["parameters"]["duration_ms"] == 30
    pg.fill("#sw-sodium_scale", "0.5")
    pg.click("#simwidget button[type=submit]")
    pg.wait_for_selector("#sw-out .rescard .vlabel:has-text('unknown')", timeout=15000)
    assert "compute budget exhausted" in pg.locator("#sw-out").inner_text().lower() and pg.locator("#sw-out svg.chart").count() == 0
    pg.select_option("#sw-model", "mechanobio")
    pg.click("#simwidget button[type=submit]")
    pg.wait_for_selector("#sw-out .adapter-out.unavailable", timeout=15000)
    assert "busy" in pg.locator("#sw-out").inner_text().lower() and "429" in pg.locator("#sw-out").inner_text()
    assert seen[-1] == {"model": "mechanobio", "parameters": {"parameters": {"viscosity_pN_s_nm": 1.0}, "duration_s": 5, "dt_s": 0.01, "frame_count": 101}}


def test_simulation_widget_is_disabled_and_honest_without_a_node(browser, base):
    pg = page(browser)
    pg.goto(base + "#/studio/flying-fish?scale=cellular")
    pg.wait_for_selector("#simwidget form", timeout=15000)
    assert pg.locator("#simwidget button[type=submit]").is_disabled()
    assert "Needs a live node" in pg.locator("#simwidget").inner_text()


_ASSURANCE_FIXTURE = """() => {
  const ev = [{path: 'artifacts/x.json', sha256: 'a'.repeat(64), selector: '$.rows[0]'}];
  const vec = (e, n, x) => ({empirical_validation: {status: e, summary: 'no calibration data', scope: 'none', evidence: []}, numerical_fidelity: {status: n, summary: 'FEM matches closed form', scope: 'scoped controls only', evidence: ev}, cross_scale_transfer: {status: x, summary: 'bridge unsupported', scope: 'cell to organ', evidence: ev}});
  return {schema: 'frontier.design-assurance/1', project_id: 'flying-fish', status: 'unsupported_essential_bridges', biological_success_probability: null, probability_calibrated: false, file_sha256: 'f'.repeat(64),
    dimensions: ['formal_properties', 'numerical_fidelity', 'empirical_validation', 'parameter_coverage', 'cross_scale_transfer', 'ensemble_robustness'],
    nodes: [{id: 'region:body', kind: 'region', label: 'Body', region_ids: ['body'], model_ids: ['m1'], vector: vec('unknown', 'scoped_pass', 'unsupported_bridge')},
            {id: 'region:pectoral-left', kind: 'region', label: 'Pectoral, left', region_ids: ['pectoral-left'], model_ids: ['m2'], vector: vec('unknown', 'failed', 'unknown')},
            {id: 'scale:organ', kind: 'scale', label: 'organ', studio_anchor: 'flying-fish:organ', vector: vec('unknown', 'scoped_pass', 'unknown')}],
    transfer_matrix: {axes: ['m1', 'm2', 'm3'], entries: [{from: 'm1', to: 'm2', status: 'scenario', unit_check: 'dimensions match', assumptions: ['A1'], missing_calibrations: ['cell to organ'], evidence: ev, quantitative_error: null}]},
    dependence_graph: {aggregation: 'no product or sum of confidence'}, project: {unsupported_essential_bridges: ['molecular to fin geometry'], counterexamples: [], next_actions: [{text: 'Find a calibration dataset', blocked_by: ['F002']}], expected_information_gain: null},
    notices: ['regions are UI anchors'], evidence_index: [{path: 'artifacts/x.json', sha256: 'a'.repeat(64), byte_size: 10}]}; }"""


def test_assurance_map_renders_vectors_regions_matrix_and_never_a_percentage(browser, base):
    """Renderer test on a fixture built from the contract fields (the real map is not in this tree)."""
    pg = page(browser)
    pg.goto(base + "#/studio/flying-fish")
    pg.wait_for_selector("#assurance")
    assert "No whole-organism success figure exists" in pg.locator("#assurance").inner_text()
    pg.evaluate("(src) => { const A = (new Function('return ' + src))()(); const host = document.getElementById('assurance'); host.innerHTML = DF.assurancePanel(A).toString(); DF.assuranceWire(host, A, null); }", _ASSURANCE_FIXTURE)
    txt = pg.locator("#assurance").inner_text()
    assert "not computed" in txt and "calibrated: false" in txt and "%" not in txt
    assert pg.is_checked("input[value=empirical_validation]")
    assert pg.locator("#assurance .part.t-unk").count() >= 1, "empirical validation defaults to unknown (neutral)"
    pg.check("input[value=numerical_fidelity]")
    assert pg.locator("#assurance .part[data-region=pectoral-left].t-bad").count() == 1 and pg.locator("#assurance .part[data-region=body].t-good, #assurance .part[data-region=body].t-mid").count() == 1
    pg.click("#assurance .part[data-region=body]")
    d = pg.locator("#asdetail").inner_text()
    assert "scoped controls only" in d and "a" * 12 in d and "$.rows[0]" in d
    pg.click(".mcell[data-from=m1][data-to=m2]")
    assert "Quantitative error: not measured" in pg.locator("#asmcell").inner_text() and "Missing calibrations" in pg.locator("#asmcell").inner_text()
    pg.click(".mcell[data-from=m2][data-to=m3]")
    assert "unknown" in pg.locator("#asmcell").inner_text()
    assert "expected information gain" in txt.lower() and "not computed" in txt.lower()


def test_connect_tab_states_what_is_and_is_not_verified(browser, base):
    pg = page(browser, 390, 900)
    pg.add_init_script("Object.defineProperty(navigator, 'clipboard', {value: {writeText: async (text) => {window.copiedMcp = text;}}});")
    pg.goto(base + "#/home")
    pg.locator('.aboutmenu summary').click()
    pg.get_by_role('link', name='MCP for agents', exact=True).click()
    pg.wait_for_selector("#cn-h")
    txt = pg.locator("#main").inner_text().lower()
    assert "is not tested" in txt and "official mcp sdk client" in txt and "never put a credential" in txt
    assert pg.input_value("#sharelink").startswith("http")
    endpoint = 'https://frontier.morphoswarm.ai/mcp'
    assert pg.locator('#mcp-endpoint').get_attribute('href') == endpoint
    pg.locator('#copy-mcp').click()
    pg.wait_for_function("window.copiedMcp === 'https://frontier.morphoswarm.ai/mcp'")
    pg.get_by_text('Client configuration', exact=True).click()
    pg.locator('#copy-mcp-config').click()
    pg.wait_for_selector('#mcp-config-copied:has-text("Copied.")')
    assert json.loads(pg.evaluate('window.copiedMcp'))['mcpServers']['frontier'] == {'type': 'http', 'url': endpoint}
    assert _overflow(pg) <= 0 and not pg.errors


def test_gallery_has_every_verified_video_with_a_player(browser, base):
    snap = json.loads((ROOT / "site/data/snapshot.json").read_text())
    ids = [m["id"] for m in snap["simulation_manifests"] if m.get("video_state") in ("present_verified", "present_unpinned")]
    pg = page(browser)
    pg.goto(base + "#/simulations")
    pg.wait_for_selector(".simcard")
    assert pg.locator("video").count() == len(ids) and len(ids) >= 4
    for i in ids:
        assert pg.locator(f"#sim-{i} video").count() == 1, i


def test_real_assurance_map_equation_registry_and_ensembles_render(browser, base):
    snap = json.loads((ROOT / "site/data/snapshot.json").read_text())
    A = snap.get("assurance")
    pg = page(browser)
    pg.goto(base + "#/studio/flying-fish")
    pg.wait_for_selector("#assurance")
    if not A or A.get("error"):
        assert "No whole-organism success figure exists" in pg.locator("#assurance").inner_text()
        return
    pg.wait_for_selector("#assurance .part", timeout=15000)
    txt = pg.locator("#assurance").inner_text()
    assert "No whole-organism success figure exists" in txt and "not computed" in txt
    assert pg.is_checked("input[value=empirical_validation]")
    assert pg.locator("#assurance .eqcard .katex").count() >= 1, "equation registry is rendered with KaTeX"
    assert pg.locator("#assurance .eqcard .tex-fallback").count() == 0
    assert "predicate declared before the runs" in txt and "not a probability of biological success" in txt.replace("\n", " ")
    pg.check("input[value=numerical_fidelity]")
    styled = pg.evaluate("() => [...document.querySelectorAll('#assurance .part .shape')].some((s) => s.style.fill)")
    assert styled, "parts are coloured from the map's own display legend"
    assert "Colors are categorical evidence states" in pg.locator("#aslegend").inner_text()
    n = len(A["transfer_matrix"]["axes"])
    assert pg.locator("#assurance .mcell").count() == n * n - n


def test_frontier_shows_the_3d_fish_above_the_open_questions(browser, base):
    pg = page(browser)
    pg.goto(base + "#/frontier")
    pg.wait_for_selector("#fishmini canvas, #fishmini svg")
    fish_y = pg.locator("#fishmini").bounding_box()["y"]
    board_y = pg.locator("#wb-h").bounding_box()["y"]
    assert fish_y < board_y, (fish_y, board_y)


def test_knowledge_infinite_scroll_appends_one_page_at_a_time_with_retry_and_end(browser, base):
    import json as _j
    from urllib.parse import urlparse, parse_qs
    calls = []

    def rec(i):
        return {"record": {"namespace": "n", "kind": "Claim", "id": f"c{i:03d}", "version": "a" * 64, "payload": {"title": f"Claim {i}", "statement": f"S{i}"}}, "local_status": "proposed", "is_head": True}

    def catalog(route):
        q = parse_qs(urlparse(route.request.url).query); after = q.get("after", [""])[0]; calls.append(after)
        if after == "c049" and calls.count("c049") == 1:
            return route.fulfill(status=503, json={"error": "x", "message": "temporarily down"})
        start = int(after[1:]) + 1 if after else 0
        end = min(start + 50, 120)
        route.fulfill(json={"mode": "live", "namespace": "n", "results": [rec(i) for i in range(start, end)], "next_cursor": None if end >= 120 else f"c{end - 1:03d}"})

    pg = page(browser)
    pg.route("**/api/health", lambda r: r.fulfill(json={"mode": "live", "status": "ok"}))
    pg.route("**/api/session", lambda r: r.fulfill(json={"authenticated": False, "public_access": True, "csrf": "x"}))
    pg.route("**/api/catalog*", catalog)
    pg.goto(base + "#/knowledge")
    pg.wait_for_selector("#cblist .claimcard")
    pg.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    pg.wait_for_selector("#cbmore [role=alert]")           # scrolling (or the sentinel) asked for page 2 and the node refused
    assert pg.locator("#cblist .claimcard").count() == 50 and "Page 1" not in pg.locator("#main").inner_text()
    pg.click("#cbmore [data-more]")                       # retry
    pg.wait_for_function("document.querySelectorAll('#cblist .claimcard').length === 100")
    pg.evaluate("window.scrollTo(0, document.body.scrollHeight)")   # scrolling alone loads the last page
    pg.wait_for_function("document.querySelectorAll('#cblist .claimcard').length === 120")
    assert "End of the list" in pg.locator("#cbmore").inner_text()
    assert len(pg.locator("#cblist .claimcard").evaluate_all("els => [...new Set(els.map(e => e.textContent))]")) == 120


def test_home_and_frontier_offer_all_six_printable_models_with_stl_download(browser, base):
    names = ["A-precursor-short-fin", "B-two-wing-glider", "C-four-wing-glider", "N1-cypselurus-baseline", "N2-area-x1.3", "N3-area-x1.3-ar-x1.2"]
    for route in ("#/home", "#/frontier"):
        pg = page(browser)
        pg.goto(base + route)
        pg.wait_for_selector(".printmodels select")
        assert pg.locator(".printmodels option").all_inner_texts() == names
        pg.select_option(".printmodels select", "N2-area-x1.3")
        dl = pg.locator(".printmodels a[download]")
        assert dl.get_attribute("href").endswith("artifacts/print/stl/N2-area-x1.3.stl") and dl.get_attribute("download") == "N2-area-x1.3.stl"
        info = pg.locator(".printmodels p").inner_text()
        assert " mm" in info and "does not change" in info


def test_windtunnel_behavior_and_scale_growth_cards_keep_partial_assumed_and_missed(browser, base):
    pg = page(browser)
    pg.goto(base + "#/simulations")
    for cid in ("windtunnel-2d", "behavior-cpg", "scale-erk-wave"):
        pg.wait_for_selector(f"#sim-{cid} video")
    wt = pg.locator("#sim-windtunnel-2d").text_content()
    assert "FAIL" in wt and "PARTIAL" in wt and "not validated flight" in wt and "not computed (null)" in wt
    er = pg.locator("#sim-scale-erk-wave").text_content()
    assert "ASSUMED" in er and "LINEAR" in er and "MISS" in er and "rise 10 90 h" in er and "synchronous" in er.lower()
    pg.locator("#sim-scale-erk-wave details.simdet:has-text('Equations')").evaluate("d => d.open = true")
    pg.wait_for_selector("#sim-scale-erk-wave .eq-math .katex")
    assert pg.locator("#sim-scale-erk-wave .katex-error").count() == 0
    assert "no biological or fluid-force success is tested" in pg.locator("#sim-behavior-cpg").text_content()
    pg.goto(base + "#/studio/flying-fish?scale=neural")
    pg.wait_for_function("document.querySelector('#main').textContent.includes('Rhythm-generator')")
    assert pg.locator(".artcard video").count() >= 1


def test_design_review_prompts_and_local_challenge_draft_in_the_contract_shape(browser, base):
    pg = page(browser)
    pg.goto(base + "#/studio/flying-fish")
    pg.wait_for_selector("#designreview")
    t = pg.locator("#designreview").text_content()
    assert "not a vote" in t.lower() and "source-only prompt" in t and "No node is connected" in t and "never holds a credential" in t
    assert pg.locator("#designreview .drprompts .drcard").count() == 4
    pg.click("[data-seed=release-convention]")
    assert pg.input_value("#drform select[name=dimension]") == "aerodynamics"
    pg.fill("#drform textarea[name=scope]", "Organism-scale glide model only.")
    pg.fill("#drform textarea[name=alternative]", "A sourced fixed release.")
    pg.fill("#drform input[name=member_index]", "3")
    pg.click("#drform button[type=submit]")
    d = pg.evaluate("() => JSON.parse(localStorage.getItem('frontier-design-review-draft:flying-fish'))")
    pl = d[0]["payload"]
    assert pl["kind"] == "challenge" and pl["design_review"]["dimension"] == "aerodynamics" and pl["design_review"]["member_index"] == 3 and pl["design_review"]["evidence_refs"] == []
    assert pl["anchor"]["record"]["kind"] == "Project" and pl["anchor"]["record"]["version"].startswith("UNPINNED")
    assert "not submitted" in pg.locator("#drdrafts").text_content()
    pg.fill("#drform textarea[name=evidence_refs]", "not-a-pin")
    pg.fill("#drform textarea[name=body]", "x"); pg.fill("#drform textarea[name=scope]", "s"); pg.fill("#drform textarea[name=alternative]", "a"); pg.fill("#drform textarea[name=falsifiable_next_test]", "t")
    pg.click("#drform button[type=submit]")
    assert "Not an exact pin" in pg.locator("#drerr").inner_text()


def test_design_review_shows_live_challenges_with_replies_and_no_resolution(browser, base):
    v = "b" * 64
    proj = {"namespace": "n", "kind": "Project", "id": "project-flying-fish-mission", "version": v}
    ch = {"namespace": "n", "kind": "Annotation", "id": "ann-1", "version": "c" * 64}

    def ann(ref, payload, mi=None):
        return {"ref": ref, "record": {"payload": payload}, "local_status": "proposed", "anchor_ref": proj, "member_index": mi, "thread_root_ref": ref}
    ctx = {"schema": "frontier.project.design-context/1", "project": {}, "members": [], "withheld_unlicensed": 2,
           "annotations": [ann(ch, {"kind": "challenge", "body": "Stiffness measured in one regime is assumed in another.", "anchor": {"record": proj}, "design_review": {"dimension": "biology", "evidence_basis": "assumption", "scope": "Member 3 glide model.", "alternative": "Depends on strain rate.", "falsifiable_next_test": "Static vs cyclic loads.", "evidence_refs": []}}, 3),
                           ann({"namespace": "n", "kind": "Annotation", "id": "ann-2", "version": "d" * 64}, {"kind": "comment", "body": "Agreed, which fin?", "anchor": {"record": proj}, "reply_to": {"version": ch["version"], "id": ch["id"], "kind": ch["kind"], "namespace": ch["namespace"]}})],   # property order differs from the root ref
           "pagination": {"limit": 50, "returned": 2, "next_cursor": None, "truncated": False}, "interpretation": "Annotations are authored challenges or replies, not votes."}
    seen = []
    pg = page(browser)
    pg.route("**/api/health", lambda r: r.fulfill(json={"mode": "live", "status": "ok"}))
    pg.route("**/api/session", lambda r: r.fulfill(json={"authenticated": False, "public_access": True, "csrf": "x"}))
    other = {"record": {"namespace": "n", "kind": "Project", "id": "other-fish-project", "version": "e" * 64, "payload": {"title": "Flying fish (a different project)"}}, "local_status": "proposed", "is_head": True}
    pg.route("**/api/catalog*", lambda r: r.fulfill(json={"mode": "live", "namespace": "n", "next_cursor": None, "results": [other, {"record": {**proj, "payload": {"title": "Mission"}}, "local_status": "proposed", "is_head": True}]}))
    pg.route("**/api/design/context*", lambda r: (seen.append(r.request.url), r.fulfill(json=ctx))[1])
    pg.goto(base + "#/studio/flying-fish")
    pg.wait_for_selector("#drlive .drcard")
    t = pg.locator("#drlive").inner_text()
    assert "1 challenge" in t and "none resolved" in t and "open: no resolution state exists" in t.lower() and "1 reply" in t and "2 withheld" in t
    assert "Stiffness measured" in t and "Falsifiable next test" in t and "member 3" in t.lower()
    assert seen and f"version={v}" in seen[0] and "kind=Project" in seen[0]
    assert "id=project-flying-fish-mission" in seen[0] and "other-fish-project" not in seen[0]
    assert "1 reply" in t, "a reply whose reply_to lists its properties in another order still attaches to its challenge"


def test_lifecycle_panel_shows_unknowns_and_the_borrowed_parameter_label(browser, base):
    pg = page(browser)
    pg.goto(base + "#/studio/flying-fish?scale=developmental")
    pg.wait_for_selector(".lifecycle table")
    t = pg.locator(".lifecycle").text_content()
    assert "not a flying fish" in t and "Not claimed: a living whole-fish bioprint is feasible" in t
    assert pg.locator(".lifecycle .tablewrap").first.locator("tbody tr").count() == 10 and pg.locator(".lifecycle td .pill.no, .lifecycle td .no").count() >= 1
    assert "borrowed parameters, not a feasibility statement" in t and "SIZING AID UNDER BORROWED PARAMETERS" in t
    href = pg.locator(".lifecycle a:has-text('life-cycle document')").get_attribute("href")
    assert href


def test_home_shows_the_fish3d_turntable_with_its_limits_and_download(browser, base):
    for route in ("#/home", "#/frontier"):
        pg = page(browser)
        pg.goto(base + route)
        pg.wait_for_selector(".turntable video")
        t = pg.locator(".turntable").text_content()
        assert "not an organism" in t and "not an aerodynamic result" in t
        assert pg.locator(".turntable a[download]").get_attribute("href").endswith("turntable.mp4")
    pg.goto(base + "#/simulations")
    pg.wait_for_selector("#sim-fish3d-render video")
    assert "Not claimed: aerodynamic performance or validity" in pg.locator("#sim-fish3d-render").text_content()


def test_design_review_never_attaches_an_unrelated_fish_project(browser, base):
    seen = []
    other = {"record": {"namespace": "n", "kind": "Project", "id": "some-other-fish", "version": "e" * 64, "payload": {"title": "Flying fish"}}, "local_status": "proposed", "is_head": True}
    pg = page(browser)
    pg.route("**/api/health", lambda r: r.fulfill(json={"mode": "live", "status": "ok"}))
    pg.route("**/api/session", lambda r: r.fulfill(json={"authenticated": False, "public_access": True, "csrf": "x"}))
    pg.route("**/api/catalog*", lambda r: r.fulfill(json={"mode": "live", "namespace": "n", "next_cursor": None, "results": [other]}))
    pg.route("**/api/design/context*", lambda r: (seen.append(r.request.url), r.fulfill(json={}))[1])
    pg.goto(base + "#/studio/flying-fish")
    pg.wait_for_selector("#drlive")
    pg.wait_for_function("document.querySelector('#drlive').textContent.includes('project-flying-fish-mission')")
    assert "no Project record" in pg.locator("#drlive").text_content() and not seen


def test_home_leads_with_sourced_anatomy_assumptions_and_the_actual_candidate(browser, base):
    pg = page(browser, 1700, 900)
    pg.goto(base + "#/home")
    pg.wait_for_selector(".grounding .region", state="attached")
    assert pg.evaluate("document.querySelector('.grounding details.regiondet').open") is False, "the per-region cards are collapsed by default"
    assert pg.locator("#grnote").is_visible() and "not a validated fish" in pg.locator("#grnote").text_content(), "the scientific scope stays visible"
    assert "N1 baseline reference" in pg.locator(".grounding .groundgrid h3").first.text_content()
    t = pg.locator(".grounding").text_content()
    assert "Start from real fish anatomy." in t and "not a validated fish" in t and "no biological or aerodynamic validation is claimed" in t
    pg.select_option("#fishcand", "fish3d-N1-cypselurus-baseline")
    pg.wait_for_function("document.querySelector('#grnote').textContent.includes('flat fin plates')")
    t = pg.locator(".grounding").text_content()
    assert "Not biorealistic and not validated" in t and "lattice scales" in t and "decorative eyes" in t
    assert "length ∝ SL" in t and "R² 0.98" in t and "raw data unavailable" in t.lower() or "UNAVAILABLE" in t
    assert "not 51 empirically learned laws" in t
    assert pg.locator(".grounding .region").count() == 9 and pg.locator(".grounding .region .assumed").count() >= 5
    assert pg.locator(".grounding .printmodels select").count() == 1 and pg.locator(".grounding .turntable video").count() == 1
    y_ground = pg.locator(".grounding").bounding_box()["y"]; y_paths = pg.locator(".paths").bounding_box()["y"]
    assert y_ground < y_paths
    # wide desktop uses the room; paragraphs stay readable; no horizontal overflow
    assert pg.locator("main").bounding_box()["width"] > 1400
    assert pg.evaluate("document.querySelector('.lede').getBoundingClientRect().width") <= 900
    assert not pg.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
    assert pg.locator("svg.mark").count() == 1


def test_system_built_tab_links_evidence_keeps_failures_and_labels_the_repo_public(browser, base):
    pg = page(browser)
    pg.goto(base + "#/work?tab=built")
    pg.wait_for_selector("#bt-h")
    t = pg.locator("#main").text_content()
    assert "public source" in t and "github.com/kganjam/delphi-frontier" in t
    assert "private until" not in t
    assert "ResourceExhausted" in t and "UREQ_TOS_NOT_ACCEPTED" in t and "INCONCLUSIVE" in t and "POSITIVE" in t
    assert "actual spend" in t.lower() or "Unknown" in t
    assert pg.locator("tbody tr").count() >= 13
    timeline = json.loads((ROOT / "site/data/snapshot.json").read_text())["timeline"]
    # A dated telemetry filename may contain "preregistered". Check the actual
    # invariant: date-only verdicts are not promoted onto the timed record.
    assert all("T" in row["time"] for row in timeline["rows"])
    dated = pg.locator("table").filter(has=pg.locator("caption", has_text="Dated build and run records"))
    assert dated.locator("tbody tr").count() == len(timeline["rows"])
    assert not pg.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")


def test_home_mounts_the_actual_glb_viewer_with_a_working_fallback(browser, base):
    pg = page(browser)
    pg.goto(base + "#/home")
    pg.wait_for_selector("#fish-viewer.mv")
    ids = pg.locator("#fishcand option").evaluate_all("els => els.map(e => e.value)")
    assert ids[0] == "fish3d-N1-cypselurus-baseline" and ids[1:] == ["fish3d-v3a-fan", "fish3d-v3b-glide-pose", "fish3d-v3c-daane-length"]
    assert pg.input_value("#fishcand") == "fish3d-v3a-fan"
    assert "pectoral camber" in pg.locator("#fishknobs").text_content()
    pg.locator("#fish-viewer").scroll_into_view_if_needed()
    pg.wait_for_function("document.querySelector('#fish-viewer').textContent.length > 40", timeout=20000)
    pg.select_option("#fishcand", "fish3d-N1-cypselurus-baseline")
    pg.wait_for_function("document.querySelector('#fishknobs').textContent.includes('flat fin plates')")
    assert pg.errors == []
    for rel in ("fish3d-N1-cypselurus-baseline/fish.glb", "fish3d-v3a-fan/fish-adult-fao.glb", "fish3d-v3b-glide-pose/appearance-adult-fao.json", "fish3d-v3c-daane-length/components.json"):
        r = pg.request.get(base + "artifacts/fish3d/" + rel)
        assert r.status == 200, rel
    assert not pg.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")


def test_betse_morpheus_openfold_and_md_cards_keep_their_limits(browser, base):
    pg = page(browser)
    pg.goto(base + "#/simulations")
    for cid in ("betse-tissue", "morpheus-multicell", "molecular-md"):
        pg.wait_for_selector(f"#sim-{cid} video")
    pg.wait_for_selector("#sim-openfold2-kcnj13")
    assert "not a fish fin" in pg.locator("#sim-betse-tissue").text_content() and "No sha256 is declared" in pg.locator("#sim-betse-tissue").text_content()
    assert "not calibrated" in pg.locator("#sim-morpheus-multicell").text_content().lower() and "600 s cap" in pg.locator("#sim-morpheus-multicell").text_content()
    md = pg.locator("#sim-molecular-md").text_content()
    assert "not achieved" in md and "not computed (null)" in md and "300 K is the target, not the observation" in md
    of = pg.locator("#sim-openfold2-kcnj13").text_content()
    assert "No video file" in of and "not a calibrated probability" in of.replace("calibrated probability of", "calibrated probability") or "calibrated probability" in of
    assert "PREDICTED" in of


def test_about_menu_lists_every_destination_and_works_without_a_mouse(browser, base):
    pg = page(browser)
    pg.goto(base + "#/home")
    pg.wait_for_selector(".aboutmenu summary")
    pg.focus(".aboutmenu summary"); pg.keyboard.press("Enter")
    hrefs = pg.locator(".aboutmenu details[open] a").evaluate_all("els => els.map(e => e.getAttribute('href'))")
    assert hrefs == ["#/about", "#/about/blog", "#/about/team", "#/about/docs", "#/about/inspirations", "#/generative", "#/demo", "#/faq", "#/proofs", "#/work?tab=connect"]
    assert pg.locator("nav[aria-label=Views] > ul > li > a:has-text('Generative')").count() == 0   # not a top-level item
    assert not pg.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
    pg2 = page(browser, 400, 800)
    pg2.goto(base + "#/home"); pg2.wait_for_selector(".aboutmenu summary")
    assert not pg2.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")



def test_about_team_shows_the_team_crest_and_the_off_the_clock_clip(browser, base):
    """The team page shows the crest image and the short slingshot clip, served from site/artifacts/team (web.py streams MP4 only from
    the artifact subtree). The clip is muted and looped, and it autoplays only when the visitor has not asked for reduced motion."""
    team = ROOT / "site" / "artifacts" / "team"
    for w, motion in ((1280, "no-preference"), (400, "reduce")):
        pg = browser.new_page(viewport={"width": w, "height": 900}, reduced_motion=motion); _OPEN.append(pg); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(base + "#/about/team"); pg.wait_for_selector(".about-team img")
        img, v = pg.locator(".about-team img"), pg.locator("#team-fun-video")
        img.scroll_into_view_if_needed()
        pg.wait_for_function("(() => { const i = document.querySelector('.about-team img'); return i.complete && i.naturalWidth === 1600; })()")
        assert "The Delphi Team" in img.get_attribute("alt") and "Distributed epistemic layer" in pg.locator(".about-team-crest figcaption").text_content()
        assert v.evaluate("v => v.muted && v.loop && v.controls && v.playsInline") and v.evaluate("v => v.autoplay") is (motion != "reduce")
        for attr, name in ((v.locator("source").get_attribute("src"), "team-darts-slingshot.mp4"), (v.get_attribute("poster"), "team-darts-slingshot-poster.jpg")):
            assert attr == "artifacts/team/" + name and (team / name).is_file()
            assert pg.request.get(base + attr).status == 200
        assert "Off the clock" in pg.locator(".about-team-fun figcaption").text_content()
        # the media sits above the role cards, and nothing overflows the narrow viewport
        assert pg.locator(".about-team").bounding_box()["y"] < pg.locator(".about-cards").bounding_box()["y"]
        assert not pg.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
        assert not errs, errs

def test_system_built_tab_reports_counters_only_with_unknowns_and_no_scorecard(browser, base):
    pg = page(browser)
    pg.goto(base + "#/work?tab=built")
    pg.wait_for_selector("#bt-h")
    t = pg.locator("#main").text_content()
    for q in ("Recorded participants", "Recorded subagents", "Native running snapshot", "Contributing harnesses", "Native collaborators", "Live harness processes", "Model calls and tokens", "GPU jobs (own H100)", "GPU container work seconds", "CPU jobs (own)", "GPU utilisation", "Cost"):
        assert q in t, q
    assert "CPU seconds are not recorded: unknown" in t and "not a census or concurrent-worker count" in t
    timeline = json.loads((ROOT / "site/data/snapshot.json").read_text())["timeline"]
    for counter in timeline["counters"]:
        assert counter["value"] in t
    assert "historical team jobs" in t and "GPU kernel seconds and billed GPU seconds: unknown" in t and "not a count of agents" in t and "Provider COMPLETED means the container ended" in t and "Reuse by anyone outside this team is not recorded" in t
    assert "%" not in pg.locator(".tablewrap").first.text_content()
    assert "scorecard" not in t.lower() and "rubric" not in t.lower()


def test_cuda_md_card_and_warmstart_bytes_are_exact(browser, base):
    import hashlib
    b = (ROOT / "site/artifacts/molecular/warmstart-v3.tar.xz").read_bytes()
    assert len(b) == 1809144 and hashlib.sha256(b).hexdigest() == "4154fcdc3784fa1bfe6c667cdc20fabc346e8c482d9010ad5646a10eea78c3bf"
    pg = page(browser)
    pg.goto(base + "#/simulations")
    pg.wait_for_selector("#sim-molecular-md-cuda video")
    t = pg.locator("#sim-molecular-md-cuda").text_content()
    assert "three 100 ps" in t and "Equilibrated ensemble: not established" in t and "not computed (null)" in t and "not a confidence interval" in t
    assert "0.2 ps CPU setup run" in pg.locator("#sim-molecular-md").text_content()


def _overflow(pg):
    return pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")


def test_frontier_question_table_keeps_bounded_columns_and_short_rows(browser, base):
    pg = page(browser, 1280, 900)
    pg.goto(base + "#/frontier")
    pg.wait_for_selector(".qtable tbody tr")
    m = pg.evaluate("""() => { const t = document.querySelector('.qtable'); const wrap = t.closest('.tablewrap'); const a = t.querySelector('tbody td:first-child');
      return {table: t.getBoundingClientRect().width, wrap: wrap.getBoundingClientRect().width, id: a.getBoundingClientRect().width,
              rows: [...t.querySelectorAll('tbody tr')].map(r => r.getBoundingClientRect().height)}; }""")
    assert m["table"] <= m["wrap"] + 1, m
    assert m["id"] <= 180, m
    assert max(m["rows"]) <= 190, m


def test_phone_pages_do_not_widen_and_the_nav_wraps_into_view(browser, base):
    pg = page(browser, 400, 800)
    for route in ("#/knowledge", "#/frontier", "#/work?tab=runtime", "#/work?tab=built", "#/studio/flying-fish", "#/simulations"):
        pg.goto(base + route)
        pg.wait_for_timeout(1200)
        assert _overflow(pg) <= 0, (route, _overflow(pg))
    pg.goto(base + "#/home"); pg.wait_for_selector(".aboutmenu summary")
    edges = pg.evaluate("[...document.querySelectorAll('nav[aria-label=Views] > ul > li')].map(li => { const r = li.getBoundingClientRect(); return [li.textContent.trim().slice(0, 10), Math.round(r.left), Math.round(r.right)]; })")
    assert all(l >= 0 and r <= 400 for _, l, r in edges), edges
    assert [e[0] for e in edges][-2:] == ["System", "About"] or any(e[0].startswith("System") for e in edges), edges


def test_large_json_trees_are_collapsed_by_default(browser, base):
    pg = page(browser)
    for route in ("#/work?tab=runtime", "#/work?tab=resources", "#/work?tab=built"):
        pg.goto(base + route); pg.wait_for_timeout(1200)
        big = pg.evaluate("""() => [...document.querySelectorAll('pre, .tree')].filter(e => e.textContent.length > 2000 && !e.closest('details') ).length""")
        assert big == 0, (route, big)


def test_live_question_table_with_long_ids_and_text_stays_inside_its_panel(browser, base):
    def rec(i):
        long_id = f"problem-{i:03d}-" + "x" * 56
        return {"record": {"namespace": "n", "kind": "Problem", "id": long_id, "version": "a" * 64, "payload": {
            "question": "Does a very long and detailed open question about cross scale calibration keep its row readable? " * 3,
            "known_state": "A long statement of what is known. " * 12, "next_action_text": "A bounded next action. " * 6, "problem_kind": "design", "completeness": "actionable",
            "approach": "top_down", "scales": ["organ", "organism"], "context_tags": ["tag-" + "y" * 30], "dependencies": []}}, "local_status": "proposed", "is_head": True}
    for w, h in ((1280, 900), (400, 800)):
        pg = page(browser, w, h)
        pg.route("**/api/health", lambda r: r.fulfill(json={"mode": "live", "status": "ok"}))
        pg.route("**/api/session", lambda r: r.fulfill(json={"authenticated": False, "public_access": True, "csrf": "x"}))
        pg.route("**/api/attention", lambda r: r.fulfill(status=503, json={"error": "attention_unavailable", "message": "no"}))
        pg.route("**/api/catalog*", lambda r: r.fulfill(json={"mode": "live", "namespace": "n", "next_cursor": None, "results": [rec(i) for i in range(30)]}))
        pg.goto(base + "#/frontier")
        pg.wait_for_selector(".livepanel table tbody tr")
        m = pg.evaluate("""() => { const t = document.querySelector('.livepanel table'); const wrap = t.closest('.tablewrap'); const a = t.querySelector('tbody td:first-child');
          return {table: t.getBoundingClientRect().width, wrap: wrap.getBoundingClientRect().width, id: a.getBoundingClientRect().width,
                  rows: [...t.querySelectorAll('tbody tr')].map(r => r.getBoundingClientRect().height), page: document.documentElement.scrollWidth - document.documentElement.clientWidth}; }""")
        assert m["page"] <= 0, (w, m)
        if w > 500:
            assert m["id"] <= 230 and max(m["rows"]) <= 200, (w, m)
        else:
            assert m["table"] <= m["wrap"] + 1, (w, m)        # phone: stacked cards (see the card test), never wider than the panel


def test_phone_knowledge_filters_with_long_facet_values_do_not_widen_the_page(browser, base):
    def rec(i):
        return {"record": {"namespace": "n", "kind": "Claim", "id": f"c{i:03d}", "version": "a" * 64, "payload": {"title": f"Claim {i}", "statement": "S" * 200, "prior_review": {"delphi_original": {"delphi_graph": {"thinker": "A thinker with an extremely long name " * 3, "work": "A work title that is also far too long for one line " * 3, "year": 1990 + i % 30}}}}}, "local_status": "proposed", "is_head": True}
    pg = page(browser, 400, 800)
    pg.route("**/api/health", lambda r: r.fulfill(json={"mode": "live", "status": "ok"}))
    pg.route("**/api/session", lambda r: r.fulfill(json={"authenticated": False, "public_access": True, "csrf": "x"}))
    pg.route("**/api/catalog*", lambda r: r.fulfill(json={"mode": "live", "namespace": "n", "next_cursor": None, "results": [rec(i) for i in range(12)]}))
    pg.goto(base + "#/knowledge")
    pg.wait_for_selector("#cblist .claimcard")
    assert _overflow(pg) <= 0, _overflow(pg)


def test_attention_json_is_collapsed_and_filled_only_when_opened(browser, base):
    big = {"schema": "frontier.attention/1", "generated_at": "t", "namespace": "n", "view": {"rows": [{"ref": {"id": f"p{i}"}, "store": {"question": "q" * 400}} for i in range(120)]}}
    pg = page(browser)
    pg.route("**/api/health", lambda r: r.fulfill(json={"mode": "live", "status": "ok"}))
    pg.route("**/api/session", lambda r: r.fulfill(json={"authenticated": False, "public_access": True, "csrf": "x"}))
    pg.route("**/api/catalog*", lambda r: r.fulfill(json={"mode": "live", "namespace": "n", "next_cursor": None, "results": []}))
    pg.route("**/api/attention", lambda r: r.fulfill(json={"report": big}))
    pg.goto(base + "#/work?tab=work")
    pg.wait_for_selector("details.rawjson")
    assert pg.evaluate("document.querySelector('details.rawjson pre').textContent.length") == 0
    assert pg.evaluate("document.querySelector('details.rawjson').open") is False
    pg.click("details.rawjson summary")
    pg.wait_for_function("document.querySelector('details.rawjson pre').textContent.length > 10000")


def test_simulation_preview_never_prints_an_object_for_structured_errors_or_digest_maps(browser, base):
    def handler(route):
        body = json.loads(route.request.post_data)
        if body["model"] == "mechanobio":
            route.fulfill(status=400, json={"error": {"code": "parameter_out_of_range", "message": {"field": "dt_s", "limit": 0.1}}})
        else:
            route.fulfill(json={"schema": "frontier.simulation.preview/1", "status": "completed", "model": "bioelectric", "evidence_kind": "SimulationResult", "persisted": False, "calibrated": False,
                "request_sha256": "a" * 64, "effective_request_sha256": "b" * 64, "code_sha256": {"model.py": "c" * 64, "run.py": "d" * 64, "model_files": {"a.py": "e" * 64, "nested": {"b.py": "f" * 64}}}, "computed_at": "2026-10-31T21:00:00Z", "scope": "Preview only.",
                "result": {"time_ms": [0, 1, 2], "voltage_mV": [[-70, -70], [-60, -65], [-40, -50]]}})
    pg = page(browser)
    _mock_live(pg, handler)
    pg.goto(base + "#/studio/flying-fish?scale=cellular")
    pg.wait_for_selector("#simwidget form", timeout=15000)
    pg.fill("#sw-duration_ms", "30")
    pg.click("#simwidget button[type=submit]")
    pg.wait_for_selector("#sw-out .rescard svg.chart", timeout=15000)
    t = pg.locator("#sw-out").text_content()
    assert "[object Object]" not in t and "model.py" in t and "run.py" in t and "model_files" in t and "b.py" in t
    pg.select_option("#sw-model", "mechanobio")
    pg.click("#simwidget button[type=submit]")
    pg.wait_for_selector("#sw-out .adapter-out.unavailable", timeout=15000)
    t = pg.locator("#sw-out").text_content()
    assert "[object Object]" not in t and "parameter_out_of_range" in t and "HTTP 400" in t


def test_live_questions_unknown_id_empty_filter_and_assessment_are_readable(browser, base):
    def rec(i):
        return {"record": {"namespace": "n", "kind": "Problem", "id": f"q{i}", "version": "a" * 64, "payload": {"question": f"Question {i}?", "known_state": "Known.", "next_action_text": "Do.", "problem_kind": "design", "completeness": "actionable", "approach": "top_down", "scales": ["organ"], "context_tags": [], "dependencies": []}}, "local_status": "proposed", "is_head": True}
    att = {"report": {"schema": "frontier.attention/1", "generated_at": "t", "namespace": "n", "view": {"rows": [{"ref": {"namespace": "n", "kind": "Problem", "id": "q1", "version": "a" * 64}, "store": {"question": "Question 1?", "known_state": "Known.", "next_action_text": "Do.", "problem_kind": "design", "completeness": "actionable", "approach": "top_down", "scales": ["organ"], "context_tags": [], "dependencies": []},
        "assessment": {"truth": {"label": "unknown", "evidence": ["e1", "e2"]}, "reviewer": None}, "actions": [], "interest_issuers": {}, "why_priority": [], "register_labels": []}]}}}
    pg = page(browser)
    pg.route("**/api/health", lambda r: r.fulfill(json={"mode": "live", "status": "ok"}))
    pg.route("**/api/session", lambda r: r.fulfill(json={"authenticated": False, "public_access": True, "csrf": "x"}))
    pg.route("**/api/attention", lambda r: r.fulfill(json=att["report"]))
    pg.route("**/api/catalog*", lambda r: r.fulfill(json={"mode": "live", "namespace": "n", "next_cursor": None, "results": [rec(1)]}))
    pg.goto(base + "#/frontier?live=q1")
    pg.wait_for_selector("#lqdetail h3, #lqdetail h4")
    t = pg.locator("#lqdetail").text_content()
    assert "[object Object]" not in t and "{" not in t and "label: unknown" in t and "e1; e2" in t
    pg.goto(base + "#/frontier?live=does-not-exist")
    pg.wait_for_selector("#lqdetail .detail-empty")
    t = pg.locator("#lqdetail").text_content()
    assert "No such question" in t and "does-not-exist" in t and "Question 1" not in t
    pg.goto(base + "#/frontier?lq=zzzz-nothing")
    pg.wait_for_selector(".livepanel .count")
    assert "No live question matches these filters" in pg.locator(".livepanel").text_content()


def test_ranked_results_say_when_nothing_contains_the_query_and_print_no_raw_index_json(browser, base):
    items = [{"type": "record", "ref": {"namespace": "n", "kind": "Claim", "id": "c1", "version": "a" * 64}, "title": "Fin allometry", "snippet": "Pectoral length scales with body length.", "kind": "Claim", "local_status": "proposed", "score": 0.62, "score_kind": "cosine", "why_matched": ["embedding"]}]
    pg = page(browser)
    pg.route("**/api/health", lambda r: r.fulfill(json={"mode": "live", "status": "ok"}))
    pg.route("**/api/session", lambda r: r.fulfill(json={"authenticated": False, "public_access": True, "csrf": "x"}))
    pg.route("**/api/attention", lambda r: r.fulfill(status=503, json={"error": "attention_unavailable", "message": "no"}))
    pg.route("**/api/catalog*", lambda r: r.fulfill(json={"mode": "live", "namespace": "n", "next_cursor": None, "results": []}))
    pg.route("**/api/discovery*", lambda r: r.fulfill(json={"items": items, "mode": "hybrid", "index": {"name": "frontier-index", "model": "gemini-embedding-001", "documents": 2444, "nested": {"a": 1}}}))
    pg.goto(base + "#/search?q=qzxvbnm&tab=catalog")
    pg.wait_for_selector("#dr-h")
    pg.wait_for_function("document.querySelector('#main').textContent.includes('Fin allometry')")
    t = pg.locator("#main").text_content()
    assert "No result contains your words" in t and "{" not in pg.locator("#dr-h").locator("xpath=..").text_content()
    assert "documents 2444" in t
    pg.goto(base + "#/search?q=fin&tab=catalog")
    pg.wait_for_function("document.querySelector('#main').textContent.includes('Fin allometry')")
    assert "No result contains your words" not in pg.locator("#main").text_content()


def test_malformed_entity_route_makes_no_request_and_navigation_moves_focus_to_main(browser, base):
    seen = []
    pg = page(browser)
    pg.on("request", lambda r: seen.append(r.url) if "/api/" in r.url else None)
    pg.goto(base + "#/frontier"); pg.wait_for_selector(".board")
    pg.evaluate("location.hash = '#/entity/Bogus/x'")
    pg.wait_for_selector("h1:has-text('Not found')")
    t = pg.locator("#main").text_content()
    assert "not a record kind this site knows" in t and "HTTP 400" not in t
    assert not [u for u in seen if "Bogus" in u]
    pg.evaluate("location.hash = '#/knowledge'"); pg.wait_for_selector("#cbrowse")
    assert pg.evaluate("document.activeElement && document.activeElement.id") == "main"


def _graph_issues(pg, selector):
    return pg.evaluate("""(sel) => { const svg = document.querySelector(sel + ' svg'); if (!svg) return {missing: true};
      const box = svg.getBoundingClientRect(); const labels = [...svg.querySelectorAll('.g-label, .g-sub, .col-title, text')].map(t => ({r: t.getBoundingClientRect(), s: t.textContent.trim()})).filter(x => x.s && x.r.width > 0);
      const out = labels.filter(x => x.r.left < box.left - 1 || x.r.right > box.right + 1).map(x => x.s.slice(0, 30));
      const hosts = svg.closest('.graphhost'); const hostBox = hosts ? hosts.getBoundingClientRect() : box;
      const overlaps = []; const lab = [...svg.querySelectorAll('.g-label, .g-elabel')].map(t => ({r: t.getBoundingClientRect(), s: t.textContent.trim()}));
      for (let i = 0; i < lab.length; i++) for (let j = i + 1; j < lab.length; j++) { const a = lab[i].r, b = lab[j].r; const ox = Math.min(a.right, b.right) - Math.max(a.left, b.left), oy = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top); if (ox > 2 && oy > 2) overlaps.push([lab[i].s.slice(0, 20), lab[j].s.slice(0, 20)]); }
      return {outside: out, overlaps: overlaps.slice(0, 5), n: labels.length}; }""", selector)


def test_frontier_board_graph_labels_stay_inside_the_drawing_and_do_not_overlap(browser, base):
    for w, h in ((1280, 900), (400, 800)):
        pg = page(browser, w, h)
        pg.goto(base + "#/frontier"); pg.wait_for_selector("#wbgraph svg")
        g = _graph_issues(pg, "#wbgraph")
        assert g.get("outside") == [] and g.get("overlaps") == [], (w, g)


def test_home_viewer_is_destroyed_on_candidate_change_and_on_leaving_and_the_note_follows_the_candidate(browser, base):
    pg = page(browser)
    pg.goto(base + "#/home")
    pg.wait_for_selector("#fish-viewer.mv")
    pg.wait_for_function("window.DF && DF.fishViewer && typeof DF.fishViewer.destroy === 'function'")
    pg.evaluate("() => { window.__destroyed = 0; const v = DF.fishViewer; const d = v.destroy.bind(v); v.destroy = () => { window.__destroyed++; d(); }; }")
    note = pg.locator("#grnote").text_content()
    assert "Ray-supported fins" in note and "not a validated fish" in note and "flat fin plates" not in note and "N1 baseline reference" in note
    assert "N1 baseline reference" in pg.locator(".grounding h3").first.text_content() or "N1 baseline reference" in pg.locator(".grounding").text_content()
    pg.select_option("#fishcand", "fish3d-N1-cypselurus-baseline")
    pg.wait_for_function("document.querySelector('#grnote').textContent.includes('flat fin plates')")
    assert pg.evaluate("window.__destroyed") == 1, "changing candidate must destroy the previous viewer"
    pg.wait_for_function("DF.fishViewer && typeof DF.fishViewer.destroy === 'function'")
    pg.evaluate("() => { window.__destroyed = 0; const v = DF.fishViewer; const d = v.destroy.bind(v); v.destroy = () => { window.__destroyed++; d(); }; }")
    pg.evaluate("location.hash = '#/knowledge'"); pg.wait_for_selector("#cbrowse")
    assert pg.evaluate("window.__destroyed") == 1 and pg.evaluate("DF.fishViewer") is None, "leaving Home must destroy the viewer"
    assert pg.locator("canvas.mv-canvas, #fish-viewer canvas").count() == 0


def test_v3_candidates_declare_no_video_so_the_fallback_cannot_offer_a_missing_turntable(browser, base):
    snap = json.loads((ROOT / "site/data/snapshot.json").read_text())
    for c in snap["fish3d_viewer"]["candidates"][1:]:
        assert c["variants"] and all("video" in v and v["video"] is None for v in c["variants"]), c["id"]


def _formalize_handler(route):
    """Serve the node's real checker: the request body goes through frontier.formalize.propose, exactly as POST /api/formalize/propose does."""
    import sys
    sys.path.insert(0, str(ROOT))
    from frontier.formalize import http_status, propose
    result = propose(json.loads(route.request.post_data))
    route.fulfill(status=http_status(result), json=result)


def test_formalize_page_shows_six_separate_parts_and_the_real_checker_verdicts(browser, base):
    pg = page(browser)
    pg.goto(base + "#/formalize")
    pg.wait_for_selector("#fz-src")
    for sec in ("fz-src", "fz-prop", "fz-sym"):
        assert pg.locator("#" + sec).count() == 1
    assert pg.locator("section[aria-labelledby=fz-res]").count() == 0 and pg.locator("#fzgo").is_disabled(), "no node: nothing checked, nothing shown"
    pg = page(browser)                                   # a fresh page: the mocks must be in place before the first load decides live vs snapshot
    pg.route("**/api/health", lambda r: r.fulfill(json={"mode": "live", "status": "ok"}))
    pg.route("**/api/session", lambda r: r.fulfill(json={"authenticated": False, "public_access": True, "csrf": "x"}))
    pg.route("**/api/catalog*", lambda r: r.fulfill(json={"mode": "live", "namespace": "n", "next_cursor": None, "results": []}))
    pg.route("**/api/attention", lambda r: r.fulfill(status=503, json={"error": "attention_unavailable", "message": "no"}))
    pg.route("**/api/formalize/propose", _formalize_handler)
    pg.goto(base + "#/formalize?ex=cantilever"); pg.wait_for_selector("#fzgo:not([disabled])")
    pg.click("#fzgo")
    pg.wait_for_selector("section[aria-labelledby=fz-lean]", timeout=20000)
    res = pg.locator("section[aria-labelledby=fz-res]").text_content()
    assert "checked" in res and "C1" in res and "witness" in res.lower() and "E = " in res and "dimensions consistent" in res
    unres = pg.locator("section[aria-labelledby=fz-unres]").text_content()
    assert "U1" in unres and "translation" in unres.lower() and "witness" not in unres.lower()
    lean = pg.locator("section[aria-labelledby=fz-lean]").text_content()
    assert "not_run" in lean and "generated_not_compiled" in lean and "Nothing is compiled" in lean
    pg.goto(base + "#/formalize?ex=cantilever-L2"); pg.wait_for_selector("#fzgo:not([disabled])")
    pg.click("#fzgo"); pg.wait_for_selector("section[aria-labelledby=fz-res]", timeout=20000)
    bad = pg.locator("section[aria-labelledby=fz-res]").text_content()
    assert "checked" not in bad.split("Request")[0].split("calibrated")[0] and ("invalid" in bad or "dimension fault" in bad), bad[:300]
    pg.goto(base + "#/formalize?ex=run-cantilever-gemini-1")
    pg.wait_for_selector("#main h1")
    assert "not valid JSON" in pg.locator("#main").text_content() and pg.locator("#fzgo").count() == 0


def test_formalize_page_has_no_overflow_on_a_phone_and_is_reachable_from_the_studio_nav(browser, base):
    pg = page(browser, 400, 800)
    pg.goto(base + "#/formalize?ex=run-cantilever-gemini-3"); pg.wait_for_selector("#fz-sym")
    assert pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth") <= 0
    pg.goto(base + "#/studio/flying-fish"); pg.wait_for_selector(".subnav")
    assert pg.locator(".subnav a:has-text('Proposal checker')").count() == 1


def test_knowledge_and_belief_graph_labels_stay_inside_the_drawing_and_do_not_overlap(browser, base):
    for w, h in ((1280, 900), (400, 800)):
        pg = page(browser, w, h)
        for route, sel in (("#/knowledge?tab=graph", ".graphhost"), ("#/belief", ".graphhost")):
            pg.goto(base + route); pg.wait_for_selector(sel + " svg")
            g = _graph_issues(pg, sel)
            assert g.get("outside") == [] and g.get("overlaps") == [], (w, route, g)


def test_most_edge_labels_stay_visible_after_collision_avoidance(browser, base):
    pg = page(browser, 1280, 900)
    for route, sel in (("#/frontier", "#wbgraph"), ("#/knowledge?tab=graph", ".graphhost"), ("#/belief", ".graphhost")):
        pg.goto(base + route); pg.wait_for_selector(sel + " svg")
        n = pg.evaluate(f"[document.querySelectorAll('{sel} .g-elabel').length, document.querySelectorAll('{sel} .g-elabel.g-hid').length]")
        print("EDGE-LABELS", route, n)
        assert n[0] == 0 or n[1] <= n[0] * 0.5, (route, n)


def test_about_menu_exposes_state_closes_on_escape_and_returns_focus(browser, base):
    for w in (1280, 400):
        pg = page(browser, w, 800)
        pg.goto(base + "#/home"); pg.wait_for_selector(".aboutmenu summary")
        sm = pg.locator(".aboutmenu summary")
        assert sm.get_attribute("aria-expanded") == "false" and sm.get_attribute("aria-controls") == "aboutlist"
        pg.focus(".aboutmenu summary"); pg.keyboard.press("Enter")
        pg.wait_for_function("document.querySelector('.aboutmenu details').open")
        pg.wait_for_function("document.querySelector('.aboutmenu summary').getAttribute('aria-expanded') === 'true'")   # the toggle event is asynchronous
        box = pg.locator(".aboutmenu details[open] > ul").bounding_box()
        assert box["x"] >= -1 and box["x"] + box["width"] <= w + 1, (w, box)
        pg.keyboard.press("Escape")
        pg.wait_for_function("!document.querySelector('.aboutmenu details').open")
        pg.wait_for_function("document.querySelector('.aboutmenu summary').getAttribute('aria-expanded') === 'false'")
        assert pg.evaluate("document.activeElement.tagName") == "SUMMARY"
        pg.click(".aboutmenu summary"); pg.wait_for_function("document.querySelector('.aboutmenu details').open")
        pg.mouse.click(5, 400)
        pg.wait_for_function("!document.querySelector('.aboutmenu details').open")


def test_phone_question_tables_become_cards_with_every_column_reachable(browser, base):
    def rec(i):
        return {"record": {"namespace": "n", "kind": "Problem", "id": f"problem-{i:03d}-" + "x" * 40, "version": "a" * 64, "payload": {"question": "A long question about calibration across scales. " * 4, "known_state": "k", "next_action_text": "n", "problem_kind": "design", "completeness": "actionable", "approach": "top_down", "scales": ["organ"], "context_tags": [], "dependencies": []}}, "local_status": "proposed", "is_head": True}
    pg = page(browser, 400, 800)
    pg.route("**/api/health", lambda r: r.fulfill(json={"mode": "live", "status": "ok"}))
    pg.route("**/api/session", lambda r: r.fulfill(json={"authenticated": False, "public_access": True, "csrf": "x"}))
    pg.route("**/api/attention", lambda r: r.fulfill(status=503, json={"error": "attention_unavailable", "message": "no"}))
    pg.route("**/api/catalog*", lambda r: r.fulfill(json={"mode": "live", "namespace": "n", "next_cursor": None, "results": [rec(i) for i in range(12)]}))
    pg.goto(base + "#/frontier"); pg.wait_for_selector(".livepanel .qtable tbody tr")
    for sel in (".livepanel .qtable", ".board .qtable"):
        m = pg.evaluate(f"""() => {{ const t = document.querySelector('{sel}'); const wrap = t.closest('.tablewrap'); const tr = t.querySelector('tbody tr'); const tds = [...tr.children].map(td => td.getBoundingClientRect()); const w = wrap.getBoundingClientRect();
            return {{ wrapScroll: wrap.scrollWidth - wrap.clientWidth, within: tds.every(r => r.left >= w.left - 1 && r.right <= w.right + 1), labels: [...tr.children].map(td => td.dataset.label || '') }}; }}""")
        assert m["wrapScroll"] <= 1 and m["within"] and all(m["labels"]), (sel, m)


def test_simulation_gallery_has_filters_a_count_jump_links_and_lazy_players(browser, base):
    pg = page(browser, 400, 800)
    pg.goto(base + "#/simulations"); pg.wait_for_selector(".simtools")
    n_all = pg.locator(".simcard").count()
    t = pg.locator(".simtools .count").text_content()
    assert f"Showing {n_all} of {n_all}" in t and "have a player" in t
    assert pg.locator("video").evaluate_all("els => els.every(v => v.preload === 'none')"), "players must not preload"
    assert pg.locator(".sjump button").count() == n_all
    pg.select_option(".simtools select[name=scale]", "molecular"); pg.click(".simtools button[type=submit]")
    pg.wait_for_function(f"document.querySelectorAll('.simcard').length < {n_all}")
    n = pg.locator(".simcard").count()
    assert f"Showing {n} of {n_all}" in pg.locator(".simtools .count").text_content() and "(filtered)" in pg.locator(".simtools .count").text_content()
    last = pg.locator(".sjump button").last
    target = last.get_attribute("data-jump"); last.click()
    pg.wait_for_function(f"document.activeElement && document.activeElement.closest('#{target}')")
    assert pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth") <= 0
    pg.goto(base + "#/simulations?q=zzznotthere"); pg.wait_for_selector(".simtools")
    assert "No simulation card matches" in pg.locator("#main").text_content() and pg.locator(".simcard").count() == 0


def test_cfd3d_cards_keep_the_failed_reference_and_unresolved_fins(browser, base):
    pg = page(browser)
    pg.goto(base + "#/simulations")
    for cid in ("cfd3d-gpu-L128-Re1000", "cfd3d-gpu-L192-Re1000"):
        pg.wait_for_selector(f"#sim-{cid} video")
        t = pg.locator(f"#sim-{cid}").text_content()
        assert "C1 sphere reference" in t and "FAILED" in t and "sub-grid shells" in t and "Fin flow is not resolved" in t and "not swimming-, taxiing- or flight-validated" in t
    import hashlib
    b = (ROOT / "site/artifacts/molecular/warmstart-v3.tar.xz").read_bytes()
    assert hashlib.sha256(b).hexdigest() == "4154fcdc3784fa1bfe6c667cdc20fabc346e8c482d9010ad5646a10eea78c3bf"


def test_design_review_shows_challenges_left_on_the_earlier_project_version(browser, base):
    snap = json.loads((ROOT / "site/data/snapshot.json").read_text())
    hist = snap["design_review"]["history"][0]["ref"]; head = snap["design_review"]["current_project"]["ref"]
    from urllib.parse import urlparse, parse_qs
    seen = []
    ch = {"namespace": "delphi-frontier", "kind": "Annotation", "id": "old-challenge", "version": "c" * 64}

    def ctx(route):
        q = parse_qs(urlparse(route.request.url).query); v = q["version"][0]; seen.append(v)
        rows = [] if v == head["version"] else [{"ref": ch, "record": {"payload": {"kind": "challenge", "body": "Old-version challenge text.", "anchor": {"record": hist}, "design_review": {"dimension": "validation", "evidence_basis": "unknown", "scope": "s", "alternative": "a", "falsifiable_next_test": "t", "evidence_refs": []}}}, "local_status": "proposed", "anchor_ref": hist, "member_index": None}]
        route.fulfill(json={"schema": "frontier.project.design-context/1", "annotations": rows, "withheld_unlicensed": 0, "pagination": {"limit": 50, "returned": len(rows), "next_cursor": None, "truncated": False}, "interpretation": "Annotations are authored challenges or replies, not votes."})
    pg = page(browser)
    pg.route("**/api/health", lambda r: r.fulfill(json={"mode": "live", "status": "ok"}))
    pg.route("**/api/session", lambda r: r.fulfill(json={"authenticated": False, "public_access": True, "csrf": "x"}))
    pg.route("**/api/attention", lambda r: r.fulfill(status=503, json={"error": "attention_unavailable", "message": "no"}))
    pg.route("**/api/catalog*", lambda r: r.fulfill(json={"mode": "live", "namespace": "delphi-frontier", "next_cursor": None, "results": [{"record": {**head, "payload": {"title": "Mission"}}, "local_status": "proposed", "is_head": True}]}))
    pg.route("**/api/design/context*", ctx)
    pg.goto(base + "#/studio/flying-fish")
    pg.wait_for_selector(".drprev .drcard", timeout=20000)
    t = pg.locator("#drlive").text_content()
    assert "0</b> challenges" in pg.locator("#drlive .drhead").inner_html() or "0 challenges" in t
    assert "Earlier version of this Project" in t and "Old-version challenge text." in t and "were not moved" in t and "22 declared members" in t
    assert head["version"] in seen and hist["version"] in seen, seen


def test_home_offers_print_revisions_with_hash_exact_stl_downloads(browser, base):
    import hashlib
    snap = json.loads((ROOT / "site/data/snapshot.json").read_text())
    assert snap["print_v3"]["refused"] == []
    for f in snap["print_v3"]["forms"]:
        for x in f["files"]:
            b = (ROOT / "site" / x["href"]).read_bytes()
            assert len(b) == x["bytes"] and hashlib.sha256(b).hexdigest() == x["sha256"], x["href"]
    pg = page(browser)
    pg.goto(base + "#/home"); pg.wait_for_selector(".printv3 select")
    catalog = snap["model_downloads"]
    assert not catalog["refused"]
    links = pg.locator("#home-model-downloads a[download]").evaluate_all("els => els.map(e => e.getAttribute('href'))")
    assert {"artifacts/print", "artifacts/print-v2", "artifacts/print-v3"} <= {g["id"] for g in catalog["groups"]}
    for group in catalog["groups"]:
        for file in group["files"]:
            assert (file["href"] in links) != bool(file.get("withdrawn"))
            data = (ROOT / "site" / file["href"]).read_bytes()
            assert len(data) == file["bytes"] and hashlib.sha256(data).hexdigest() == file["sha256"]
    assert pg.locator("#home-model-downloads").evaluate("e => !!(e.compareDocumentPosition(document.querySelector('#fishmini')) & Node.DOCUMENT_POSITION_FOLLOWING)")
    assert pg.locator("#home-model-downloads > p a").first.is_visible()
    assert pg.locator(".printv3 option").all_inner_texts() == [f["title"] for f in snap["print_v3"]["forms"]]
    assert {"fish3d-v3a-fan-prop", "fish3d-v3b-glide-pose-prop"} <= set(pg.locator(".printv3 option").evaluate_all("els => els.map(e => e.value)"))
    assert pg.locator(".printv3 .v3links a[download]").count() == 3
    pg.select_option(".printv3 select", "fish3d-v3b-glide-pose-prop")
    hrefs = pg.locator(".printv3 .v3links a").evaluate_all("els => els.map(e => e.getAttribute('href'))")
    assert all("fish3d-v3b-glide-pose-prop" in h and h.endswith(".stl") for h in hrefs), hrefs
    assert "printer and resin unknown" in pg.locator(".printv3").text_content() and "not organisms" in pg.locator(".printv3 .v3info").text_content()
    assert pg.request.get(base + hrefs[0]).status == 200
    latest = [f for f in snap["print_v3"]["forms"] if f["family"] == "print-v4"]
    assert len(latest) >= 2
    assert len({f["id"] for f in latest}) == len(latest)
    for width in (1440, 390):
        pg.set_viewport_size({"width": width, "height": 960})
        cards = pg.locator(".latest-prints .print-study")
        assert cards.count() == len(latest)
        for i, form in enumerate(latest):
            card = cards.nth(i)
            card.scroll_into_view_if_needed()
            pg.wait_for_function("i => { const e = document.querySelectorAll('.print-study img')[i]; return e.complete && e.naturalWidth > 0; }", arg=i)
            assert form["short"].casefold() in card.inner_text().casefold()
            assert "Calculated mass" in card.inner_text() and "Not weighed" in card.inner_text()
            assert f'{form["mass_conditional_g"]["smooth"]:.2f} g' in card.inner_text()
            assert card.locator("a[download]").count() == 2
            assert all("print-v4/stl/" in h for h in card.locator("a[download]").evaluate_all("els => els.map(e => e.getAttribute('href'))"))
        assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert not pg.errors


def test_generative_page_shows_recorded_denoising_and_retains_failed_audit(browser, base):
    import hashlib
    pilot = json.loads((ROOT / "site/data/snapshot.json").read_text())["diffusion_pilot"]
    assert not pilot["refused"]
    for file in pilot["files"]:
        data = (ROOT / "site" / file["href"]).read_bytes()
        assert len(data) == file["bytes"] and hashlib.sha256(data).hexdigest() == file["sha256"]
    pg = page(browser)
    pg.goto(base + "#/generative")
    pg.wait_for_selector("#diffusion-recorded img")
    text = pg.locator("#diffusion-recorded").text_content()
    assert "Strict secondary audit: failed" in text and "Denoising steps are not physical time" in text
    assert "No inference speedup demonstrated" in text
    assert "157 finite DDPM metrics" in text and "zero solver-amplitude denominator" in text
    assert pg.locator("#diffusion-recorded img").count() == 3


def test_morpheus_full_horizon_chart_is_labelled_a_chart_not_a_spatial_movie(browser, base):
    pg = page(browser)
    pg.goto(base + "#/simulations"); pg.wait_for_selector("#sim-morpheus-full-horizon-chart video")
    t = pg.locator("#sim-morpheus-full-horizon-chart").text_content()
    assert "not a spatial tissue movie" in t and "draws no cell shapes or fields" in t and "Verified against its declared sha256" in t and "256 cells" in t and "128 cells" in t
    assert pg.locator("#sim-morpheus-full-horizon-chart video").get_attribute("poster").endswith("full_horizon_chart_poster.png")


def test_recovery_inputs_are_published_exactly_and_the_failed_run_is_not_called_complete(browser, base):
    import hashlib
    b = (ROOT / "site/artifacts/rd-diffusion/primary-runtime-inputs.tar.xz").read_bytes()
    assert len(b) == 5007988 and hashlib.sha256(b).hexdigest() == "4c43b04106469764c1d24450a29c1e200914e3b7952c417bb62508fd52862a5d"
    pg = page(browser)
    pg.goto(base + "#/work?tab=built"); pg.wait_for_selector("#bt-h")
    t = pg.locator("#main").text_content()
    # Since 89726ac a separate evaluation of the retained checkpoint is published; the primary timeout must still read as a failure and nothing as validated biology.
    assert "primary run: failed" in t and "The primary timeout remains a failure" in t and "strict secondary audit failed" in t and "not evaluated performance or validated biology" in t
    assert "no evaluation or generated examples are present" not in t, "the retired no-evaluation sentence would contradict the published diffusion pilot"
    href = pg.locator("a[download][href$='primary-runtime-inputs.tar.xz']").get_attribute("href")
    assert href == "artifacts/rd-diffusion/primary-runtime-inputs.tar.xz"
    assert pg.request.get(base + href).status == 200


def test_contributor_credential_lives_in_memory_only_and_the_composer_mounts(browser, base):
    snap = json.loads((ROOT / "site/data/snapshot.json").read_text())
    cp = snap["design_review"]["current_project"]["ref"]
    pg = page(browser)
    sent = []
    pg.on("request", lambda r: sent.append((r.url, r.headers.get("authorization"), r.headers.get("cookie"))) if "/v1/" in r.url else None)
    pg.route("**/api/health", lambda r: r.fulfill(json={"mode": "live", "status": "ok"}))
    pg.route("**/api/session", lambda r: r.fulfill(json={"authenticated": False, "public_access": True, "csrf": "x"}))
    pg.route("**/api/attention", lambda r: r.fulfill(status=503, json={"error": "attention_unavailable", "message": "no"}))
    pg.route("**/api/catalog*", lambda r: r.fulfill(json={"mode": "live", "namespace": cp["namespace"], "next_cursor": None, "results": [{"record": {**cp, "payload": {"title": "Mission", "members": []}}, "local_status": "proposed", "is_head": True}]}))
    pg.route("**/api/design/context*", lambda r: r.fulfill(json={"schema": "frontier.project.design-context/1", "project": {}, "members": [], "annotations": [], "withheld_unlicensed": 0, "pagination": {"limit": 50, "returned": 0, "next_cursor": None, "truncated": False}, "interpretation": "x"}))
    pg.route("**/api/record*", lambda r: r.fulfill(json={"mode": "live", "record": {**cp, "payload": {"title": "Mission", "members": []}}, "local_status": "proposed", "is_head": True}))
    pg.route("**/v1/read/identity", lambda r: r.fulfill(json={"principal": {"actor": "e2e-actor", "roles": ["contributor"]}}) if r.request.headers.get("authorization") == "Bearer secret-token-1234567890" else r.fulfill(status=401, json={"error": "unauthorized", "message": "no"}))
    pg.goto(base + "#/studio/flying-fish")
    pg.wait_for_selector("#ctform")
    assert pg.get_attribute("#ctinput", "type") == "password" and pg.get_attribute("#ctinput", "autocomplete") == "off"
    pg.wait_for_selector(".annotation-composer", timeout=15000)
    pg.fill("#ctinput", "wrong-token-0000000000"); pg.click("#ctconnect")
    pg.wait_for_function("document.querySelector('#ctstatus').textContent.includes('Not connected')")
    assert pg.input_value("#ctinput") == ""
    pg.fill("#ctinput", "secret-token-1234567890"); pg.click("#ctconnect")
    pg.wait_for_function("document.querySelector('#ctstatus').textContent.includes('Connected as')")
    assert pg.input_value("#ctinput") == "" and "e2e-actor" in pg.locator("#ctstatus").text_content()
    storage = pg.evaluate("JSON.stringify([Object.entries(localStorage), Object.entries(sessionStorage), document.cookie, location.href])")
    assert "secret-token-1234567890" not in storage, "the credential must live in memory only"
    assert any(a == "Bearer secret-token-1234567890" and c is None for _, a, c in sent), sent
    pg.click("#ctdisconnect")
    pg.wait_for_function("document.querySelector('#ctstatus').textContent.includes('Disconnected')")
    assert pg.evaluate("DF.api.hasContributor()") is False
    pg.fill("#ctinput", "secret-token-1234567890"); pg.click("#ctconnect")
    pg.wait_for_function("DF.api.hasContributor() === true")
    pg.evaluate("location.hash = '#/knowledge'")
    pg.wait_for_selector("#cbrowse")
    assert pg.evaluate("DF.api.hasContributor()") is False, "leaving the page forgets the credential"


def test_fish_history_lists_only_stated_lineage_and_separates_siblings_revisions_and_props(browser, base):
    snap = json.loads((ROOT / "site/data/snapshot.json").read_text())
    H = snap["fish_history"]
    # every edge is backed by the manifest field it names: re-read the manifests, do not trust the snapshot
    p2 = json.loads((ROOT / "artifacts/print-v2/manifest.json").read_text())["edition"]["supersedes"]
    rev = {(e["from"], e["to"]) for e in H["edges"] if e["relation"] == "revision" and not e["from"].startswith("glider-")}
    assert rev == set(p2.items()) and len(rev) == 6
    v3 = json.loads((ROOT / "artifacts/fish3d/v3-index.json").read_text())
    for vid in v3["candidates"]:
        cj = json.loads((ROOT / f"artifacts/fish3d/{vid}/candidate.json").read_text())
        assert {"from": vid, "to": cj["baseline_candidate"]}.items() <= next(e for e in H["edges"] if e["from"] == vid and e["relation"] == "variant of").items()
    props = json.loads((ROOT / "artifacts/print-v3/downloads.json").read_text())["forms"]
    for f in props:
        assert any(e["from"] == f["id"] and e["to"] == f["source_candidate"] and e["relation"] == "printed from" for e in H["edges"])
    assert H["launch_prototype"]["exists"] is True and len(H["launch_prototype"]["revisions"]) == 5
    gl = {m["id"]: json.loads((ROOT / f"artifacts/glider/{m['id']}/manifest.json").read_text()) for m in []}
    import pathlib
    man = {d.name: json.loads((d / "manifest.json").read_text()) for d in (ROOT / "artifacts/glider").iterdir() if (d / "manifest.json").exists()}
    for rid, m in man.items():
        edge = [e for e in H["edges"] if e["from"] == "glider-" + rid and e["relation"] == "revision"]
        assert (not m["parent_revision"] and not edge) or (len(edge) == 1 and edge[0]["to"] == "glider-" + m["parent_revision"]), rid
    known = json.loads((ROOT / "artifacts/glider/KNOWN_DEFECTS.json").read_text())
    bad = set(known["right_hand_print_files_are_left_parts"]["revisions"])
    flagged = {n["revision"] for n in H["nodes"] if n.get("known_defect")}
    assert flagged == bad and "r4-daane-printfix" not in flagged
    pg = page(browser)
    pg.goto(base + "#/history"); pg.wait_for_selector("#fhgraph svg")
    t = pg.locator("#main").text_content()
    assert "Chronological revision" in t and "Sibling variants" in t and "Derivation" in t and "not a launch prototype" in t and "Launch glider print sets exist as manifests" in t and "untested" in t
    assert "not the date the design was made" in t or "not a design date" in t or "a repository fact" in t
    assert pg.locator("#fhgraph .g-node").count() == len(H["nodes"]) == 25
    pg.goto(base + "#/history?sel=fish3d-v3a-fan-prop"); pg.wait_for_selector("#fhdetail h3")
    d = pg.locator("#fhdetail").text_content()
    assert "fish3d-v3a-fan-prop" in d and "printed from" in d and "fish3d-v3a-fan" in d and "artifacts/print-v3/downloads.json" in d
    g = _graph_issues(pg, "#fhgraph")
    assert g.get("outside") == [] and g.get("overlaps") == [], g
    pg2 = page(browser, 400, 800)
    pg2.goto(base + "#/history"); pg2.wait_for_selector("#fhgraph svg")
    assert pg2.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth") <= 0
    pg.goto(base + "#/home"); pg.wait_for_selector("#fishnote")
    assert pg.locator("a:has-text('fish design history')").count() >= 1


def test_stale_sentences_are_gone_and_cost_cites_the_dated_google_receipt(browser, base):
    snap = json.loads((ROOT / "site/data/snapshot.json").read_text())
    cost = next(c for c in snap["timeline"]["counters"] if c["quantity"] == "Cost")
    # The Cost counter now cites the dated Google Cloud allocation snapshot (reservations, not usage) and still infers no spend from credits.
    assert "terms-of-service" not in cost["note"] and "Google Cloud allocation snapshot (20" in cost["note"] and "No dollar estimate or zero spend inferred from credits" in cost["note"] and "spend remains unknown" in cost["note"]
    pg = page(browser)
    pg.goto(base + "#/studio/flying-fish?scale=molecular"); pg.wait_for_selector("#pl-h")
    t = pg.locator("#main").text_content()
    assert "not available from this page" not in t and "Waiting for the genomic" not in t and "Panels waiting for a contract" not in t and "Waiting for bounded proposals" not in t
    assert "Related panels and their status" in t and "proposal checker" in t and "Contribute panel" in t
    assert pg.locator("#pl-h").locator("xpath=..").locator("a[href='#/formalize']").count() == 1


def test_regulatory_map_page_keeps_source_only_scope_unknown_bridges_and_no_execution(browser, base):
    R = json.loads((ROOT / "site/data/snapshot.json").read_text())["regulatory_map"]
    src = json.loads((ROOT / "artifacts/fish-regulatory-map/map.json").read_text())
    assert [r["id"] for r in R["rows"]] == [r["id"] for r in src["rows"]] and len(R["rows"]) == 7 and len(R["datasets"]) == 4 and len(R["coupling_ports"]) == 4
    assert all(c["value"] is None and c["status"] == "unknown" for c in R["coupling_ports"]) and all(a["status"].endswith("not-executed") for a in R["next_actions"])
    assert "local_response_path" not in json.dumps(R), "local file paths must not be published"
    pg = page(browser)
    pg.goto(base + "#/regulatory"); pg.wait_for_selector(".regprog")
    t = pg.locator("#main").text_content()
    assert "source-only" in t and "flying-fish transfer unknown" in t and "not computed (null)" in t and "not available" in t
    assert pg.locator(".regprog").count() == 7 and pg.evaluate("[...document.querySelectorAll('.regprog')].every(d => !d.open)")
    assert "transfer validated: false" in t and "Demonstrated." in t and "Inferred, not demonstrated." in t and "Missing bridge." in t
    assert t.count("unknown") >= 4 and "none (null)" in t and "none executed" in t
    assert "A retrieved response is not independent experimental verification" in t
    pg.goto(base + "#/regulatory?row=pectoral-fin-field"); pg.wait_for_selector(".regprog[open]")
    assert pg.locator(".regprog[open]").get_attribute("id") == "rg-pectoral-fin-field"
    pg2 = page(browser, 400, 800)
    pg2.goto(base + "#/regulatory"); pg2.wait_for_selector(".regprog")
    assert pg2.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth") <= 0
    pg.goto(base + "#/studio/flying-fish"); pg.wait_for_selector(".subnav")
    assert pg.locator(".subnav a:has-text('Regulatory applicability')").count() == 1


def test_claim_reuse_page_shows_the_dispute_and_claims_no_benefit(browser, base):
    C = json.loads((ROOT / "site/data/snapshot.json").read_text())["claim_reuse"]
    audit = json.loads((ROOT / "artifacts/claim-reuse/audit.json").read_text())
    assert C["distinct_actions"] == audit["distinct_current_action_ids_with_recorded_input_use"] == 2 and len(C["cases"]) == 2
    for n in ("below", "above"):
        a = json.loads((ROOT / f"docs/reviews/fin-reuse-review-run/readback/assessment-{n}.json").read_text())["record"]["payload"]
        r = next(x for x in C["reviews"] if x["case"] == n)
        assert r["decision"] == a["decision"] == "disputed" and r["dimensions"]["empirical_relevance"]["status"] == a["dimensions"]["empirical_relevance"]["status"] == "insufficient"
    pg = page(browser)
    pg.goto(base + "#/reuse"); pg.wait_for_selector("#ru-3")
    t = pg.locator("#main").text_content()
    assert "not a saving of time or cost" in t and "not a collective benefit" in t and "not biological evidence" in t
    assert "disputed" in t and "insufficient" in t and "outside: a retained counterexample" in t and "inside" in t
    assert "0.111111" in t and "0.090909" in t and "agreed with each finding and changed no record" in t
    assert "typed uses link" in t or "typed <code>uses</code>" in pg.locator("#ru-1").inner_html()
    pg2 = page(browser, 400, 800)
    pg2.goto(base + "#/reuse"); pg2.wait_for_selector("#ru-3")
    assert pg2.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth") <= 0
    pg.goto(base + "#/studio/flying-fish"); pg.wait_for_selector(".subnav")
    assert pg.locator(".subnav a:has-text('Claim reuse and dispute')").count() == 1


def test_genetic_blueprints_show_construct_blocks_unknowns_equations_and_no_sequence(browser, base):
    G = json.loads((ROOT / "site/data/snapshot.json").read_text())["genetic_blueprints"]
    src = json.loads((ROOT / "artifacts/genetic-blueprints/blueprints.json").read_text())
    assert [d["id"] for d in G["designs"]] == [d["id"] for d in src["designs"]] and len(G["designs"]) == 4
    pg = page(browser)
    pg.goto(base + "#/blueprints"); pg.wait_for_selector(".bpdesign")
    t = pg.locator("#main").text_content()
    assert pg.locator(".bpdesign").count() == 4 and pg.locator(".bpconstruct").count() == 4 and pg.locator(".bpconstruct .bpblock").count() == 16
    assert pg.locator(".bpdesign").first.locator(".bpstep").count() == 8
    assert "proposed, not executed" in t or "proposed design, NOT executed" in t
    assert pg.locator("mark.unk").count() >= 20, "unknowns must be conspicuous"
    assert "No DNA sequence, effector, coefficient or result is given" in t and "flying-fish transfer: unknown; not claimed" in t
    assert pg.locator("section[aria-labelledby=bp-eq] .katex").count() >= 2 and pg.locator("section[aria-labelledby=bp-eq] tbody tr").count() == 4
    eq = pg.locator("section[aria-labelledby=bp-eq]").text_content()
    for u in ("transcripts per cell per second", "per second (s⁻¹)", "protein molecules per transcript per second", "transcript count per cell", "protein molecules per cell", "time in seconds"):
        assert u in eq, u
    assert "does not supply a value" in eq and pg.locator("section[aria-labelledby=bp-eq] mark.unk").count() >= 8, "units declared, values still unknown"
    assert "do not change" not in t and "They can change copy number, integration locus and therefore expression" in t
    links = pg.locator("section[aria-labelledby=bp-src] td[data-label=Source] a").evaluate_all("els => els.map(e => e.href)")
    assert links and all(h.startswith("https://") for h in links) and len(links) == len(src["citation_table"]) > 0, links
    import re
    assert not re.search(r"\b[ACGT]{20,}\b", t), "no DNA sequence may appear"
    assert len(src["comparison"]["rows"]) >= 6
    assert pg.locator("section[aria-labelledby=bp-cmp] tbody tr").count() == len(src["comparison"]["rows"]) and "Not a ranking" in t
    pg.click("a[data-cite]:visible >> nth=0")
    pg2 = page(browser, 400, 800)
    pg2.goto(base + "#/blueprints"); pg2.wait_for_selector(".bpdesign")
    assert pg2.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth") <= 0
    pg.goto(base + "#/studio/flying-fish"); pg.wait_for_selector(".subnav")
    assert pg.locator(".subnav a:has-text('Genetic blueprints')").count() == 1


def test_openresearch_exemplars_are_local_recorder_provenance_not_a_cloud_dispatcher(browser, base):
    O = json.loads((ROOT / "site/data/snapshot.json").read_text())["openresearch"]
    facts = json.loads((ROOT / "connectors/biomodels/orx/orx_facts.json").read_text())
    assert len(O["exemplars"]) == 2 and O["exemplars"][0]["commit"] == facts["commit_sha"]
    assert [x["sha256"] for x in O["exemplars"][0]["outputs"]] == [x["sha256"] for x in facts["outputs"]]
    assert all(e["backend"] == "local_job" for e in O["exemplars"])
    pg = page(browser)
    pg.goto(base + "#/work?tab=built"); pg.wait_for_selector("#bt-h")
    t = pg.locator("#main").text_content()
    assert "Recorded OpenResearch runs (local exemplars)" in t and "not a cloud dispatcher" in t and "none of these runs used a remote backend" in t
    assert "database exit code null" in t and "Collier 1996 replay v4" in t and "Neumann-mode Turing scan" in t
    pg2 = page(browser, 400, 800)
    pg2.goto(base + "#/work?tab=built"); pg2.wait_for_selector("#bt-h")
    assert pg2.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth") <= 0


_FOCUS_JS = """() => { const e = document.activeElement; if (!e || e === document.body) return null; const cs = getComputedStyle(e); const r = e.getBoundingClientRect();
  return {tag: e.tagName, ring: (cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0) || cs.boxShadow !== 'none', vis: cs.visibility !== 'hidden' && r.width > 0}; }"""


def test_every_keyboard_stop_has_a_visible_focus_style_on_a_phone(browser, base):
    """The video element itself must show our ring when it first takes focus. Further Tab presses move through the browser's own media controls
    (activeElement stays the same <video>), which the browser styles; those are not counted as page stops."""
    for route in ("#/home", "#/frontier", "#/simulations", "#/studio/flying-fish"):
        pg = page(browser, 400, 860); pg.goto(base + route); pg.wait_for_timeout(1200)
        bad = []; last = None
        for _ in range(45):
            pg.keyboard.press("Tab")
            ident = pg.evaluate("(() => { const e = document.activeElement; if (!e || e === document.body) return null; if (!e.__stop) e.__stop = Math.random(); return e.__stop; })()")
            r = pg.evaluate(_FOCUS_JS)
            if ident is not None and ident == last:
                continue                                   # same element still active: focus is inside its native controls
            last = ident
            if r and r["vis"] and not r["ring"]:
                bad.append(r["tag"])
        assert bad == [], (route, bad)
        pg.close()


def test_bare_graph_route_makes_no_unnamed_link_and_the_skip_link_keeps_the_route(browser, base):
    pg = page(browser)
    pg.goto(base + "#/graph"); pg.wait_for_selector("h1:has-text('Neighbourhood graph')")
    hrefs = pg.locator("#main a").evaluate_all("els => els.map(e => e.getAttribute('href'))")
    assert all(h and h != "#/entity//" and "entity//" not in h for h in hrefs) and "No record is selected" in pg.locator("#main").text_content()
    pg = page(browser)                                  # a fresh page: Tab starts from the top of the document
    pg.goto(base + "#/frontier"); pg.wait_for_selector(".board")
    pg.keyboard.press("Tab")
    assert pg.evaluate("document.activeElement.className") == "skip" and pg.locator(".skip").is_visible()
    pg.keyboard.press("Enter")
    assert pg.evaluate("document.activeElement.id") == "main" and pg.evaluate("location.hash") == "#/frontier", "the skip link must move focus without changing the route"


def test_a_failed_script_shows_a_retry_message_not_a_blank_page(browser, base):
    pg = page(browser)
    pg.route("**/js/util.js", lambda r: r.fulfill(status=429, body="Too Many Requests"))
    pg.goto(base + "#/frontier")
    pg.wait_for_selector(".bootfail", timeout=15000)
    t = pg.locator(".bootfail").text_content()
    assert "could not finish loading" in t and "util.js" in t and pg.locator(".bootfail button:has-text('Try again')").count() == 1


def test_session_limit_shows_a_retry_state_and_public_reads_stay_available(browser, base):
    calls = {"n": 0}

    def session(route):
        calls["n"] += 1
        route.fulfill(status=429, json={"error": "rate_limited", "message": "slow down"}) if calls["n"] < 3 else route.fulfill(json={"authenticated": False, "public_access": True, "csrf": "x"})
    pg = page(browser)
    pg.route("**/api/health", lambda r: r.fulfill(json={"mode": "live", "status": "ok"}))
    pg.route("**/api/session", session)
    pg.route("**/api/catalog*", lambda r: r.fulfill(json={"mode": "live", "namespace": "n", "next_cursor": None, "results": []}))
    pg.route("**/api/attention", lambda r: r.fulfill(status=503, json={"error": "attention_unavailable", "message": "no"}))
    pg.goto(base + "#/home")
    pg.wait_for_selector("#sessbanner button:has-text('Retry')", timeout=15000)
    t = pg.locator("#sessbanner").text_content()
    assert "limiting new browser sessions" in t and "snapshot still work" in t and "sign in" not in t.lower()
    assert pg.locator("h1").count() >= 1, "pages still draw while the session is limited"
    pg.click("#sessbanner button")
    pg.wait_for_function("!document.querySelector('#sessbanner')", timeout=15000)


def test_blueprints_show_actors_claim_ledger_cell_programs_and_filters_that_are_not_validation(browser, base):
    src = json.loads((ROOT / "artifacts/genetic-blueprints/blueprints.json").read_text())
    G = json.loads((ROOT / "site/data/snapshot.json").read_text())["genetic_blueprints"]
    assert len(G["actors"]["actors"]) == len(src["regulatory_actors"]["actors"]) > 0 and len(G["claim_ledger"]["rows"]) == len(src["claim_use_ledger"]["rows"]) > 0 and len(G["cell_programs"]) == len(src["cell_program_blueprints"]) > 0
    pg = page(browser)
    pg.goto(base + "#/blueprints"); pg.wait_for_selector("section[aria-labelledby=bp-act]")
    t = pg.locator("#main").text_content()
    assert pg.locator("section[aria-labelledby=bp-act] tbody tr").count() == len(G["actors"]["actors"])
    assert pg.locator("section[aria-labelledby=bp-led] tbody tr").count() == len(G["claim_ledger"]["rows"])
    assert pg.locator("section[aria-labelledby=bp-cpb] article").count() == len(G["cell_programs"])
    assert "NONE identified" in t and "A marker or an inferred network role is not a validated driver" in t and "UNDECLARED" in t
    roles = set(pg.locator("section[aria-labelledby=bp-act] td[data-label=Role]").all_inner_texts())
    assert {"TF", "marker"} <= {r.strip() for r in roles}
    d1 = "bp-1-regeneration-enhancer-reporter"
    pg.goto(base + f"#/blueprints?design={d1}"); pg.wait_for_selector(".bpdesign")
    t = pg.locator("#main").text_content()
    assert pg.locator(".bpdesign").count() == 1 and "Filtered view" in t and "not validated expression" in t and "nothing here shows measured expression of any construct" in t
    n_led = pg.locator("section[aria-labelledby=bp-led] tbody tr").count()
    assert 0 < n_led < len(G["claim_ledger"]["rows"])
    pg.goto(base + "#/blueprints?region=pectoral"); pg.wait_for_selector(".bptools")
    t = pg.locator("#main").text_content()
    assert "Filtered view" in t and ("No design in this package binds that region" in t or pg.locator(".bpdesign").count() >= 1)
    pg.goto(base + "#/blueprints?cls=measured"); pg.wait_for_selector(".bptools")
    assert set(pg.locator("section[aria-labelledby=bp-act] td[data-label='Evidence class']").all_inner_texts()) <= {"measured"}
    pg.goto(base + "#/home"); pg.wait_for_selector("#regctx")
    hrefs = pg.locator("#regctx a").evaluate_all("els => els.map(e => e.getAttribute('href'))")
    assert any(h.startswith("#/blueprints?region=") for h in hrefs) and "#/regulatory" in hrefs
    pg2 = page(browser, 400, 800)
    pg2.goto(base + "#/blueprints"); pg2.wait_for_selector(".bptools")
    assert pg2.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth") <= 0


def test_experimentation_page_keeps_context_states_absence_and_invents_no_observation(browser, base):
    snap = json.loads((ROOT / "site/data/snapshot.json").read_text())
    X = snap["experimentation"]
    spec = (ROOT / "specs/SPEC-013-adaptive-experimentation.md").read_text()
    assert len(X["bridges"]) == 7 and all(b["bridge"] in spec for b in X["bridges"])
    pg = page(browser)
    pg.goto(base + "#/experimentation?scale=organ&region=pectoral-fin-field&intervention=loading"); pg.wait_for_selector("#ex-cur")
    t = pg.locator("#main").text_content()
    assert "Plans, not results" in t and "no wet-lab observation has been made" in t and "scale Organ" in t and "pectoral-fin-field" in t and "loading" in t
    if X["planner"] is None:
        assert "No candidate intervention, readout, control or replicate unit is recorded" in t and "nothing is invented" in t
    assert "Wet-lab protocols frozen" in t and "Computational protocols frozen" in t and "0: no observation from this proposed experiment exists" in t and "Results ingested" in t and "proposal → ready → running → failed → completed → review" in t
    pg.click("a:has-text('Across scales')"); pg.wait_for_selector("#ex-br")
    assert pg.locator("section[aria-labelledby=ex-br] tbody tr").count() == 7 and "unknown bridge" in pg.locator("#main").text_content()
    assert "scale=organ" in pg.evaluate("location.hash") and "region=pectoral-fin-field" in pg.evaluate("location.hash") and "tab=cross" in pg.evaluate("location.hash")
    pg.select_option("form[data-form=ex] select[name=scale]", "cellular"); pg.click("form[data-form=ex] button[type=submit]")
    pg.wait_for_function("location.hash.includes('scale=cellular')")
    assert "region=pectoral-fin-field" in pg.evaluate("location.hash"), "changing the scale keeps the region"
    pg.goto(base + "#/studio/flying-fish?scale=tissue"); pg.wait_for_selector(".subnav")
    assert pg.locator(".subnav a[href*='experimentation'][href*='scale=tissue']").count() == 1
    pg2 = page(browser, 400, 800)
    pg2.goto(base + "#/experimentation?tab=cross"); pg2.wait_for_selector("#ex-br")
    assert pg2.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth") <= 0


def test_experimentation_renders_the_planner_result_prospective_only(browser, base):
    r = json.loads((ROOT / "artifacts/experimental-design/result.json").read_text())
    by = {d["id"]: d for d in r["designs"]}
    assert r["measurement_rows"] == [] and r["selected_design_id"] == "mixed_load_deflection"
    for w in (1280, 400):
        pg = page(browser, w, 900)
        pg.goto(base + "#/experimentation?scale=organ"); pg.wait_for_selector("#ex-plan")
        t = pg.locator("#ex-plan").text_content()
        for did, d in by.items():
            row = pg.locator(f"#plan-{did}").text_content()
            assert str(float(f"{d['expected_target_posterior_variance']:.6g}")) in row and str(d["identifiability"]["rank"]) + " of 2" in row, did
        assert "prospective only" in t and "assumption based" in t and "0 measurement rows" in t
        assert "selected under these assumptions" in pg.locator("#plan-mixed_load_deflection").text_content()
        assert "selected under" not in pg.locator("#plan-deflection_only").text_content() and "nullspace" in pg.locator("#plan-deflection_only").text_content()
        assert "probability of biological success" in t or "probability of biological success" in pg.locator("#main").text_content()
        assert "matches the planner manifest" in t
        if w == 400:
            assert _overflow(pg) <= 0
        pg.close()


def test_ecology_page_plays_published_saved_states_and_keeps_limits(browser, base):
    run = ROOT / "artifacts/ecology/run-refined"
    summ = json.loads((run / "summary.json").read_text())
    rec = {f["path"]: f["sha256"] for f in json.loads((run / "receipt.json").read_text())["files"]}
    for w in (1280, 400):
        pg = page(browser, w, 900); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("response", lambda r: errs.append(f"{r.status} {r.url}") if r.status >= 400 and "/api/" not in r.url else None)
        pg.goto(base + "#/ecology"); pg.wait_for_selector("#eco-host .ev-cases button", timeout=20000)
        assert pg.locator("#eco-host .ev-cases button").count() == 4
        pg.locator("#eco-host canvas").first.wait_for(timeout=20000)
        t = pg.locator("#main").text_content()
        assert "computed reduced model" in t and "empirical validation: unknown" in t and "not stated" not in t.split("What each run ended on")[1].split("Rendered movies")[0]
        for cid, s in summ.items():
            row = pg.locator(f"#eco-{cid}").text_content()
            assert s["main"]["termination_reason"] in row and str(float(f"{s['main']['last_time_s']:.4g}")) in row, cid
        assert pg.locator("section[aria-labelledby=eco-m] video").count() == 2
        assert not errs, errs
        if w == 400:
            assert _overflow(pg) <= 0
        pg.close()
    for a in ("glide-passive", "escape-neighbors"):
        b = (ROOT / f"site/artifacts/ecology/run-refined/{a}/trajectory.json").read_bytes()
        import hashlib
        assert hashlib.sha256(b).hexdigest() == rec[f"artifacts/ecology/run-refined/{a}/trajectory.json"]


def test_demo_page_empty_state_is_honest_and_entry_points_exist(browser, base):
    snap = json.loads((ROOT / "site/data/snapshot.json").read_text())
    pg = page(browser, 1280, 900)
    pg.goto(base + "#/demo"); pg.wait_for_selector("#main h1")
    t = pg.locator("#main").text_content()
    if not (snap.get("demo_videos") or {}).get("cuts"):
        assert "No demo video is published in this snapshot yet" in t and pg.locator("video").count() == 0
    pg.goto(base + "#/home"); pg.wait_for_selector(".herowatch a")
    assert pg.locator(".herowatch a").get_attribute("href").endswith("#/demo")
    pg.locator(".aboutmenu summary").click()
    assert pg.locator(".aboutmenu a[href$='#/demo']").count() == 1
    assert not pg.errors, pg.errors


def test_demo_page_shows_published_cuts_with_controls_downloads_and_provenance(browser, base):
    snap = json.loads((ROOT / "site/data/snapshot.json").read_text())
    mp4 = "artifacts/simulations/windtunnel-2d/windtunnel.mp4"; poster = "artifacts/simulations/windtunnel-2d/poster.png"
    snap["demo_videos"] = {"cuts": [
        {"id": "frontier-120s", "title": "Long tour & more", "duration_s": 120.0, "href": mp4, "poster_href": poster, "subtitles_href": "data/catalog.json", "transcript_href": "data/snapshot.json", "manifest_href": "data/snapshot.json"},
        {"id": "frontier-60s", "title": "Short tour", "duration_s": 60.0, "href": mp4, "poster_href": poster, "subtitles_href": None, "manifest_href": "data/snapshot.json"}],
        "limits": ["The video describes the site; it adds no evidence."]}
    for w in (1280, 400):
        pg = page(browser, w, 900)
        pg.route("**/data/snapshot.json", lambda r: r.fulfill(json=snap))
        pg.goto(base + "#/demo"); pg.wait_for_selector("#demo-video")
        # no cut parameter: the compact 60 s cut plays, and the CTA offers the long one
        assert pg.locator(".democut[aria-current=page]").text_content().startswith("1 minute") and pg.locator("#demo-switch").text_content() == "Watch the full 2-minute tour"
        assert "cut=frontier-120s" in pg.locator("#demo-switch").get_attribute("href")
        assert pg.locator("#demo-video").get_attribute("controls") is not None and pg.locator("#demo-video").get_attribute("poster") == poster
        assert [pg.locator(".demostory li b").nth(i).text_content() for i in range(4)] == ["Goal", "Multiscale evidence", "Next experiment", "Reusable agent work"]
        # concept headline; the film comes before the story cards and starts inside the first screen on desktop
        assert "A design studio for" in pg.locator("h1").text_content() and "Start with a flying fish" in pg.locator(".demohead .lede").text_content()
        vt, st = pg.locator("#demo-video").bounding_box()["y"], pg.locator(".demostory").bounding_box()["y"]
        assert vt < st and (w < 900 or vt < 600), (vt, st)
        assert pg.locator(".democta a:has-text('Open the studio')").count() == 1
        # both cuts are linked, and both have downloads
        assert pg.locator(".democut").count() == 2 and pg.locator(".demodl li a[download][href$='windtunnel.mp4']").count() == 2
        assert "burned into the video" in pg.locator("figcaption").text_content() and "No separate caption track" in pg.locator("figcaption").text_content() and pg.locator("track").count() == 0
        assert "Long tour & more" in pg.locator(".demotabs").text_content() and "&amp;" not in pg.locator(".demotabs").text_content()
        assert pg.locator("#demo-fs").is_visible() and "Fullscreen" in pg.locator("#demo-fs").get_attribute("aria-label")
        pg.click(".democut:has-text('2 minutes')"); pg.wait_for_selector(".democut[aria-current=page]:has-text('2 minutes')")
        assert pg.locator("track[kind=captions]").count() == 1 and "cut=frontier-120s" in pg.evaluate("location.hash")
        assert pg.locator("#demo-switch").text_content() == "Watch the 1-minute version"
        assert pg.locator("a:has-text('Transcript (TXT)')").count() == 1 and pg.locator("a:has-text('Captions (VTT)')").count() == 1
        pg.locator(".demolimits summary").click(); assert "adds no evidence" in pg.locator(".demolimits").text_content()
        box = pg.locator("#demo-video").bounding_box()
        assert box["width"] <= w and (w < 900 or box["width"] >= 640)
        if w == 400:
            assert _overflow(pg) <= 0
        pg.close()


def test_demo_page_defaults_to_latest_published_cut_and_preserves_old_downloads(browser, base):
    snap = json.loads((ROOT / "site/data/snapshot.json").read_text())
    cuts = {c["id"]: c for c in (snap.get("demo_videos") or {}).get("cuts", [])}
    if "frontier-60s" not in cuts:
        return
    pg = page(browser, 1280, 900)
    pg.goto(base + "#/demo"); pg.wait_for_selector("#demo-video")
    expected = cuts.get("frontier-delphi-60s") or cuts.get("frontier-science-60s") or cuts.get("frontier-90s") or cuts["frontier-60s"]
    assert pg.locator("#demo-video source").get_attribute("src") == expected["href"]
    assert pg.locator(".demodl li").count() == len(cuts) and pg.locator(".demodl a[download]").count() >= len(cuts)



def test_no_page_prints_markup_or_object_placeholders(browser, base):
    import re as _re
    bad = _re.compile(r"<span|</?b>|<a href|class=\"|\[object \w+\]")
    pg = page(browser, 1280, 900)
    for r in ("assemblies", "blueprints", "blueprints?design=bp-2-development-versus-regeneration-contrast", "blueprints?region=pectoral-fin-field", "regulatory", "reuse", "history", "experimentation", "experimentation?tab=cross", "ecology", "formalize", "engineering", "simulations", "studio/flying-fish"):
        pg.goto(base + "#/" + r); pg.wait_for_selector("#main h1"); pg.wait_for_timeout(500)
        t = pg.locator("#main").text_content()
        m = bad.search(t)
        assert not m, (r, t[max(0, m.start() - 80):m.start() + 80])


def test_engineering_cell_tab_opens_cellular_and_names_its_group(browser, base):
    pg = page(browser, 1280, 900)
    pg.goto(base + "#/engineering?scale=organism"); pg.wait_for_selector(".tabs7")
    pg.click(".tabs7 a:text-is('Cell')")
    pg.wait_for_selector(".scalecard h3")
    assert pg.locator(".scalecard h3").text_content() == "Cellular scale" and "scale=cellular" in pg.evaluate("location.hash")
    t = pg.locator("#main").text_content()
    assert "The Cell tab holds 2 scales: Subcellular and Cellular" in t
    pg.goto(base + "#/engineering?scale=subcellular"); pg.wait_for_selector(".scalecard h3")
    assert pg.locator(".scalecard h3").text_content() == "Subcellular scale"
    assert pg.locator(".tabs7 a[aria-current=page]").text_content() == "Cell"


def test_ecology_uncertainty_section_states_scope_and_matches_the_aggregate(browser, base):
    import hashlib
    eco = ROOT / "artifacts/ecology"
    agg = json.loads((eco / "uncertainty-aggregate/summary.json").read_text())
    want = {f["path"]: f["sha256"] for f in json.loads((eco / "uncertainty-manifest.json").read_text())["files"]}
    for rel in ("uncertainty-aggregate/paired-sensitivity.png", "uncertainty-aggregate/summary.json", "uncertainty-initial/paired-sensitivity.png"):
        b = (ROOT / "site/artifacts/ecology" / rel).read_bytes()
        assert hashlib.sha256(b).hexdigest() == want[f"artifacts/ecology/{rel}"], rel
    assert agg["scenario_count"] == agg["computed_count"] == 28 and len(agg["paired_comparisons"]) == 14
    for w in (1280, 400):
        pg = page(browser, w, 900)
        pg.goto(base + "#/ecology"); pg.wait_for_selector("#eco-u img")
        t = pg.locator("#eco-u").text_content()
        for must in ("assumed engineering scenarios", "not biological confidence", "edge of the reused VLM domain", "Interactions between settings are not estimated", "28 scenarios, 28 computed, 28 passing"):
            assert must in t, must
        assert pg.locator("#eco-u tbody tr").count() == 14
        first = agg["paired_comparisons"][0]
        row = pg.locator("#eco-u tbody tr").first.text_content()
        assert str(float(f"{first['positive_work_difference_J']:.4g}")) in row and str(first["seed"]) in row
        pg.locator("#eco-u img").evaluate("i => i.decode()")
        assert pg.locator("#eco-u img").evaluate("i => i.naturalWidth") > 100
        assert pg.locator("#eco-u a[href$='paired-sensitivity.provenance.json']").count() >= 1
        if w == 400:
            assert _overflow(pg) <= 0
        pg.close()


def test_studio_scale_selector_is_near_the_top_and_the_selected_scale_leads_with_equations(browser, base):
    for w, h in ((1440, 900), (390, 800)):
        pg = page(browser, w, h)
        pg.goto(base + "#/studio/flying-fish?scale=organ"); pg.wait_for_selector(".studiogrid")
        rail, grid = pg.locator(".rail").bounding_box(), pg.locator(".studiogrid").bounding_box()
        assert rail["y"] < (600 if w >= 900 else 750), (w, rail)
        assert pg.locator(".projectwide").bounding_box()["y"] > grid["y"] + grid["height"] - 5       # project-wide panels moved below the workspace
        for anchor in ("#assurance", "#annkind", "#simwidget"):
            assert pg.locator(anchor).count() == 1, anchor
        main = [t.strip() for t in pg.locator(".studiomain h3").all_text_contents()]
        assert main.index("Equations and claims") < main.index("Parameters and unknowns") < main.index("Media") < main.index("Model"), main
        if w >= 900:
            top = pg.locator(".rail").bounding_box()["y"]
            pg.mouse.wheel(0, 700); pg.wait_for_timeout(300)
            assert abs(pg.locator(".rail").bounding_box()["y"] - 76) < 12 and top > 76, "rail stays in view on desktop"
        else:
            assert _overflow(pg) <= 0
            for i in range(11):
                assert pg.locator(".subsys").nth(i).bounding_box()["width"] <= w
        pg.close()


def test_studio_scale_selector_works_from_the_keyboard_and_keeps_deep_links(browser, base):
    pg = page(browser, 1280, 900)
    pg.goto(base + "#/studio/flying-fish?scale=organ"); pg.wait_for_selector(".subsys.on")
    pg.locator(".subsys").nth(3).focus()                                   # Cellular
    pg.keyboard.press("Enter"); pg.wait_for_selector(".studiomain h2:has-text('Cellular scale')")
    assert "scale=cellular" in pg.evaluate("location.hash") and pg.locator(".subsys[aria-current=true]").count() == 1
    assert pg.locator(".subsys[aria-current=true] b").text_content() == "Cellular"
    pg.goto(base + "#/studio/flying-fish?scale=molecular"); pg.wait_for_selector(".studiomain h2:has-text('Molecular scale')")
    assert pg.locator(".rail").count() == 1 and pg.locator("nav[aria-label='Subsystems by scale']").count() == 1


def test_assemblies_page_keeps_six_axes_apart_and_the_v3b_failure_visible(browser, base):
    import hashlib
    bio = ROOT / "artifacts/biodesign-compiler"
    R = json.loads((bio / "report.json").read_text())
    want = {f["path"]: f["sha256"] for f in json.loads((bio / "manifest.json").read_text())["files"]}
    for rel, sha in want.items():
        assert hashlib.sha256((ROOT / "site" / rel).read_bytes()).hexdigest() == sha, rel
    assert R["retained_failures"] == ["fish3d-v3b"] and len(R["compiled"]) == 3
    for w in (1280, 400):
        pg = page(browser, w, 900)
        pg.goto(base + "#/assemblies"); pg.wait_for_selector("#as-axes")
        assert pg.locator(".asmatrix tbody tr").count() == 6
        for c in R["compiled"]:
            for k, a in c["axes"].items():
                row = pg.locator(f"#axis-{k}").text_content()
                assert a["status"] in row, (c["assembly"], k, a["status"])
        t = pg.locator("#main").text_content()
        assert "no single score" in t and "Retained failure" in t and "NOT CONVERGED" in t
        # the retained failure sits on the model-domain axis of v3b and v3b's lift is flagged unusable
        v3b = next(c for c in R["compiled"] if c["assembly"] == "fish3d-v3b")
        assert v3b["axes"]["model_domain"]["status"] == "fail" and "NOT CONVERGED" in v3b["axes"]["model_domain"]["reading"]
        cells = pg.locator("#axis-model_domain td").all_text_contents()
        assert len(cells) == 3 and cells[1].startswith("fail") and "NOT CONVERGED" in cells[1], cells
        rows = {r.locator("td").first.text_content().strip(): r.locator("td").nth(3).text_content() for r in pg.locator("section[aria-labelledby=as-cmp] tbody tr").all()}
        assert rows["v3b glide pose"].strip() == "no" and rows["v3a ray-fan"].strip() == "yes", rows
        assert pg.locator(".asbridges article").count() == 3 and all("expression->growth" in x for x in pg.locator(".asbridges article").all_text_contents())
        assert pg.locator("section[aria-labelledby=as-pins] tbody tr:has-text('genetic blueprint') :text('shared by all variants')").count() >= 1
        assert pg.locator(".asdiff").count() == len(R["layer_revision_diff"]) == 3
        for banned in ("biologically valid", "whole genome was designed"):
            assert banned not in t.replace("no variant is shown to be biologically valid", "").replace("No whole genome is designed here", ""), banned
        assert pg.locator("a[href$='artifacts/biodesign-compiler/report.json']").count() >= 1 and pg.locator("a[href='#/experimentation?tab=cross']").count() == 1
        if w == 400:
            assert _overflow(pg) <= 0
        pg.close()


def test_aeroelastic_and_nca_cards_follow_the_review_wording_and_pin_their_media(browser, base):
    import hashlib
    ae = json.loads((ROOT / "artifacts/aeroelastic/index.json").read_text())
    nca = json.loads((ROOT / "artifacts/nca-seed-placement/index.json").read_text())
    orig = json.loads((ROOT / "artifacts/nca-pattern/index.json").read_text())
    for rel, sha in ((ae["artifacts"]["video"]["path"], ae["artifacts"]["video"]["sha256"]), (nca["artifacts"]["video"]["path"], nca["artifacts"]["video"]["sha256"]), (orig["artifacts"]["video"]["path"], orig["artifacts"]["video"]["sha256"])):
        assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == sha, rel
    pg = page(browser)
    pg.goto(base + "#/simulations")
    for cid in ("aeroelastic-coupling", "nca-pattern", "nca-seed-placement"):
        pg.wait_for_selector(f"#sim-{cid} video")
    a = pg.locator("#sim-aeroelastic-coupling").text_content()
    for must in ("Bending-only, torsion-rigid scaffold", "fixed-alpha, assumed-release", "bookkeeping, not an independent transfer validation", "not a demonstrated useful flight improvement", "cannot resolve smaller paired effects", "Independent review B1", "Independent review B2", "36 arms"):
        assert must in a, must
    assert "coarse 8x2" not in a and "not a production mesh" not in a, "the production arms replace the earlier coarse slice"
    P = ae["production"]; r_cl, o_cl, t_cl = P["nominal_fine"]["CL"]
    assert f"{r_cl:.6f}" in a and f"{o_cl:.6f}" in a and f"{t_cl:.6f}" in a and "3.84e-06" in a and "all declared arms returned" in a
    n = pg.locator("#sim-nca-seed-placement").text_content()
    assert "32 of 48 passed" in n and "original 0 of 12 to corrected seed 12 of 12" in n and "original 0 of 12 to corrected seed 8 of 12" in n and "original 0 of 12 to corrected seed 0 of 12" in n
    assert "not fresh held-out cases" in n and "reused from parent" in n and "tissue regeneration" in n and "Not generalisation" in n
    o = pg.locator("#sim-nca-pattern").text_content()
    assert "0 of 48 passed" in o and "unchanged" in o
    pg.goto(base + "#/studio/flying-fish?scale=tissue")
    pg.wait_for_function("document.querySelector('#main').textContent.includes('corrected seed placement')")
    t = pg.locator("#main").text_content()
    assert "original run: 0 of 48" in t and "corrected seed placement: 32 of 48" in t
    pg.goto(base + "#/studio/flying-fish?scale=organ")
    pg.wait_for_function("document.querySelector('#main').textContent.includes('Static aeroelastic coupling')")
    curriculum = json.loads((ROOT / "artifacts/nca-curriculum/index.json").read_text())
    for width in (1440, 390):
        pg.set_viewport_size({"width": width, "height": 900})
        pg.goto(base + "#/simulations")
        card = pg.locator("#sim-nca-curriculum")
        if card.locator(".sim-sources").get_attribute("open") is None:
            card.locator(".sim-sources summary").click()
        assert "Sources and provenance" in card.inner_text()
        assert card.locator(".eqcard").count() == 0
        sources = card.locator(".sim-sources li a")
        assert sources.count() == 4
        for link in sources.all():
            assert link.is_visible()
            key = link.inner_text().replace(" ", "_")
            response = pg.request.get(base + link.get_attribute("href"))
            assert response.status == 200
            assert hashlib.sha256(response.body()).hexdigest() == curriculum["artifacts"][key]["sha256"]
        for label, key in (("View result chart", "training_plot"), ("Inspect rendering provenance", "render_provenance")):
            response = pg.request.get(base + card.get_by_role("link", name=label).get_attribute("href"))
            assert response.status == 200
            assert hashlib.sha256(response.body()).hexdigest() == curriculum["artifacts"][key]["sha256"]
        response = pg.request.get(base + card.get_by_role("link", name="Inspect model manifest").get_attribute("href"))
        assert response.status == 200 and response.json() == curriculum
        assert "No aggregate benefit" in card.text_content()
        assert _overflow(pg) <= 0
    assert pg.errors == []


def test_assemblies_axis_cells_are_short_with_checks_in_a_disclosure(browser, base):
    R = json.loads((ROOT / "artifacts/biodesign-compiler/report.json").read_text())
    uc = R["compiled"][0]["axes"]["units_context"]
    for w in (1280, 400):
        pg = page(browser, w, 900)
        pg.goto(base + "#/assemblies"); pg.wait_for_selector("#axis-units_context")
        row = pg.locator("#axis-units_context")
        shown = row.inner_text()                                   # closed disclosures are not part of inner_text
        assert "4 composable" in shown and "5 SCENARIO" in shown and "4 refused" in shown and "not these variants" in shown
        assert "failed checks" not in shown and "mapping" not in shown, "full fields stay collapsed"
        if w >= 900:
            assert row.bounding_box()["height"] < 330, row.bounding_box()
        assert pg.locator(".asinspect[open]").count() == 0
        # failure stays visible without opening anything
        assert "NOT CONVERGED" in pg.locator("#axis-model_domain").inner_text() and "fail" in pg.locator("#axis-model_domain").inner_text()
        pg.locator("#axis-units_context .asinspect summary").first.click()
        opened = row.inner_text()
        assert uc["refused"][0]["coupling"] in opened and "scope" in opened and "mapping" in opened
        assert pg.locator("#axis-units_context dl.astree").count() >= 1
        if w == 400:
            assert _overflow(pg) <= 0
        pg.close()


def _load_faq(pg, base):
    pg.goto(base + "#/home"); pg.wait_for_selector("#main h1")
    if "js/faq.js" not in (ROOT / "site/index.html").read_text():          # the shell registers it; until then the test registers the view itself
        pg.add_script_tag(path=str(ROOT / "site/js/faq.js"))
    pg.evaluate("location.hash = '#/faq'"); pg.wait_for_selector(".faqitem")


def test_faq_answers_are_grounded_hedged_and_linked_to_real_documents(browser, base):
    import re as _re
    snap = json.loads((ROOT / "site/data/snapshot.json").read_text())
    site_docs = {d["id"]: d["href"] for d in snap["documents"]}
    for w in (1280, 400):
        pg = page(browser, w, 900)
        _load_faq(pg, base)
        assert pg.locator(".faqitem").count() == 10 and pg.locator(".faqindex li").count() == 10
        t = pg.locator("#main").inner_text()
        for must in ("not an established fact", "never \"accepted\"", "no accept tool", "no shared token", "not complete genomics", "gap in source coverage is not a claim that a gene is lost",
                     "tie", "not evidence that agents coordinate better", "not verified here", "No organism was built", "we do not claim a decentralised architecture was exercised", "no running federated network"):
            assert must.lower() in t.lower().replace("’", "'"), must
        assert not _re.search(r"\b\d+\s+(autonomous\s+)?agents\b", t), "no agent count is stated"
        for a in pg.locator(".faqlinks a[target=_blank]").all():
            href = a.get_attribute("href")
            assert href.startswith("https://github.com/kganjam/delphi-frontier/blob/main/") and (ROOT / href.split("/blob/main/")[1]).is_file(), href
        for a in pg.locator(".faqlinks a:not([target])").all():
            href = a.get_attribute("href")
            if href.startswith("data/docs/"):
                assert href in site_docs.values(), href
        assert all(pg.locator(f"#faq-{q} .faqlinks a").count() >= 2 for q in ("claims", "mcp", "scales", "hosting", "nanopub", "genomes", "lean", "collective", "compute", "organism"))
        pg.click(".faqindex a[data-q=lean]")
        assert pg.evaluate("document.activeElement.id") == "faq-lean-h" and "q=lean" in pg.evaluate("location.hash")
        if w == 400:
            assert _overflow(pg) <= 0
        pg.close()


def test_system_audit_separates_contributors_activity_and_model_receipts(browser, base):
    snap = json.loads((ROOT / 'site/data/snapshot.json').read_text())
    audit = snap['timeline']['audits']
    assert audit['contributors']['data']['counts']['distinct_contributing_harness_ids_supported_minimum'] == 11
    assert audit['contributors']['data']['counts']['native_contributors_supported_minimum'] == 3
    assert len(audit['models']['data']['entries']) == 15
    assert all(a['path'] in {i['path'] for i in snap['inputs']} for a in audit.values())
    for route, width in (('#/work?tab=built', 1440), ('#/work?tab=built', 390), ('#/work?tab=resources', 390)):
        pg = page(browser, width, 900)
        pg.goto(base + route)
        pg.wait_for_selector('.contributor-audit')
        t = pg.locator('#main').inner_text()
        assert 'At least 11 distinct harness identities' in t and 'Native collaborators' in t
        assert 'At least 23' in t and 'Recorded subagents' in t and '4 native + 8 nested Claude' in t
        assert '1 coordinator + 3 children' in t and '22:07:30 PDT' in t
        assert 'not a count of agents working' in t
        assert 'none in this tree' not in t
        pg.locator('.contributor-audit > summary').click()
        pg.locator('.model-usage-audit > summary').click()
        pg.locator('.repository-activity-audit > summary').click()
        assert pg.locator('.repository-activity-audit tbody tr').count() == 4
        assert '1,252 across four repositories' in t
        assert 'fractastical/delphi' in pg.locator('.repository-activity-audit').inner_text()
        assert 'Commits are not participants' in pg.locator('.repository-activity-audit').inner_text()
        assert pg.locator('.model-usage-audit tbody tr').count() == 15
        assert 'provider completed science runner failed' in pg.locator('.model-usage-audit').inner_text()
        assert 'No BioNeMo or BioNeMo NIM execution is established' in pg.locator('.model-usage-audit').inner_text()
        pg.locator('.model-usage-audit tbody details > summary').first.click()
        source = pg.locator('.model-usage-audit tbody details a').first.get_attribute('href')
        assert audit['models']['data']['source_tree_commit'] in source
        assert pg.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        assert not pg.errors


def test_tables_keep_badges_on_one_line_stack_on_phones_and_say_when_they_scroll(browser, base):
    import pathlib
    js = (pathlib.Path(__file__).parent / "_tblmeasure.js").read_text()
    routes = ["frontier", "studio/flying-fish", "engineering", "evidence", "evidence?tab=artifacts", "work?tab=work", "work?tab=resources", "blueprints", "simulations", "experimentation", "formalize", "ecology", "reuse", "regulatory", "history", "assemblies"]
    for w in (1440, 768, 390):
        pg = page(browser, w, 900)
        for r in routes:
            pg.goto(base + "#/" + r); pg.wait_for_selector("#main h1"); pg.wait_for_timeout(500)
            for t in pg.evaluate(js):
                if not t["stacked"]:
                    assert t["pillWraps"] == 0, (r, w, t)                    # a badge in a scrolling or normal table never spans two lines
                if t["scrolls"]:
                    assert t["cue"], (r, w, t)                               # edge shadows are drawn
            wraps = pg.locator("#main .tablewrap").evaluate_all("els => els.filter(e => e.scrollWidth > e.clientWidth + 1).map(e => !!(e.previousElementSibling && e.previousElementSibling.classList.contains('tablehint')))")
            assert all(wraps), (r, w, wraps)                                  # every table that scrolls sideways says so above it
        if w == 390:
            pg.goto(base + "#/evidence"); pg.wait_for_selector("#main .stackable")
            assert pg.evaluate("getComputedStyle(document.querySelector('#main .stackable td')).display") == "block" and pg.locator("#main .stackable td[data-label]").count() > 0
        if w == 1440:
            pg.goto(base + "#/studio/flying-fish"); pg.wait_for_selector("table.matrix")
            assert pg.evaluate("getComputedStyle(document.querySelector('table.matrix tbody tr > :first-child')).position") == "sticky" and pg.locator("table.matrix").evaluate("t => t.closest('.tablewrap').previousElementSibling.classList.contains('tablehint')")
            pg.goto(base + "#/frontier"); pg.wait_for_selector("#main table")
            assert pg.evaluate("[...document.querySelectorAll('#main .tablewrap')].every(w => w.scrollWidth <= w.clientWidth + 1)"), "no Frontier table hides a column on desktop"
            split = pg.evaluate((pathlib.Path(__file__).parent / "_wordsplit.js").read_text())
            assert split == [], ("plain words are split across lines in a table cell", split)
        pg.close()


def test_new_ninety_second_cut_is_featured_with_accurate_label_and_old_cuts(browser, base):
    snap = json.loads((ROOT / 'site/data/snapshot.json').read_text())
    old = [c for c in snap['demo_videos']['cuts'] if not c['id'].startswith(('frontier-science-', 'frontier-delphi-'))]
    assert {c['id'] for c in old} >= {'frontier-60s', 'frontier-120s'}
    latest = dict(old[0], id='frontier-90s', title='New narrated tour', duration_s=90)
    snap['demo_videos']['cuts'] = [c for c in old if c['id'] != 'frontier-90s'] + [latest]
    for width in (1440, 390):
        pg = page(browser, width, 900)
        pg.route('**/data/snapshot.json', lambda r: r.fulfill(json=snap))
        pg.goto(base + '#/demo')
        pg.wait_for_selector('.democut[aria-current=page]')
        assert pg.locator('.democut[aria-current=page] b').inner_text() == '90 seconds'
        assert 'new 90-second tour' in pg.locator('.demohead').inner_text().lower()
        assert pg.locator('.demodl li').count() == 3
        pg.locator('.democut[href$="frontier-60s"]').click()
        pg.wait_for_selector('.democut[aria-current=page]:has-text("1 minute")')
        assert pg.locator('#demo-video source').get_attribute('src') == next(c['href'] for c in old if c['id'] == 'frontier-60s')
        assert _overflow(pg) <= 0 and not pg.errors
        pg.close()


def test_science_pair_is_featured_and_earlier_videos_remain_playable(browser, base):
    snap = json.loads((ROOT / 'site/data/snapshot.json').read_text())
    old = [c for c in snap['demo_videos']['cuts'] if not c['id'].startswith(('frontier-science-', 'frontier-delphi-'))]
    new = [dict(old[0], id=f'frontier-science-{seconds}s', title=title, duration_s=seconds)
           for seconds, title in [(60, 'Lean for biology'), (120, 'Design across scales')]]
    snap['demo_videos']['cuts'] = old + new
    for width in (1440, 390):
        pg = page(browser, width, 960)
        pg.route('**/data/snapshot.json', lambda r: r.fulfill(json=snap))
        pg.goto(base + '#/demo')
        pg.wait_for_selector('#demo-video')
        assert 'Lean for biology' in pg.locator('.demohead').inner_text()
        assert pg.locator('.democut[aria-current=page]').get_attribute('href').endswith('frontier-science-60s')
        assert pg.locator('nav[aria-label="Choose a cut"] .democut').count() == 2
        assert pg.locator('.demodl li').count() == len(old) + 2
        pg.locator('#demo-switch').click()
        pg.wait_for_selector('.democut[aria-current=page][href$="frontier-science-120s"]')
        assert pg.locator('#demo-switch').get_attribute('href').endswith('frontier-science-60s')
        pg.locator('.demoarchive summary').click()
        pg.locator('.demoarchive .democut[href$="frontier-60s"]').click()
        pg.wait_for_selector('.demoarchive .democut[aria-current=page]')
        assert pg.locator('#demo-video source').get_attribute('src') == next(c['href'] for c in old if c['id'] == 'frontier-60s')
        assert pg.locator('.demoarchive').evaluate('e => e.open')
        assert _overflow(pg) <= 0 and not pg.errors
        pg.close()


def test_single_ray_card_preserves_same_equation_scope_and_source_discrepancy(browser, base):
    pg = page(browser)
    pg.goto(base + '#/simulations')
    pg.wait_for_selector('#sim-fin-ray-bilaminar')
    card = pg.locator('#sim-fin-ray-bilaminar')
    assert card.locator('video').count() == 0
    text = card.text_content()
    for phrase in ('24/24', 'same-equation', 'UNRESOLVED', 'G=200 is not 200 Pa', 'no measured flying-fish material or whole-fin validation'):
        assert phrase in text
    assert card.locator('.tex-fallback').count() == 0 and card.locator('.katex').count() == 3
    image = card.locator('img').first
    assert pg.request.get(base + image.get_attribute('src')).ok
    assert not pg.errors


def test_observed_update_card_keeps_worsening_separate_from_observations(browser, base):
    import hashlib
    expected = json.loads((ROOT / "artifacts/observed-allometry/publication.json").read_text())
    csv = next(x for x in expected["files"] if x["path"].endswith("source-observations.csv"))
    for width in (1440, 390):
        pg = page(browser, width, 900)
        pg.goto(base + "#/simulations?q=Observed-data")
        card = pg.locator("#sim-observed-allometry-update")
        card.wait_for()
        text = card.text_content()
        assert "109 preserved-specimen rows" in text and "WORSENED: 0.047089 → 0.066057" in text
        assert "5.55846 → 5.45984" in text and "imported_unreviewed" in text
        assert "no independent biological validation" in text
        assert card.locator("video").count() == 0
        pg.wait_for_function("document.querySelector('#sim-observed-allometry-update img').naturalWidth > 0")
        response = pg.request.get(base + card.get_by_role("link", name="Source observations CSV").get_attribute("href"))
        assert response.status == 200 and hashlib.sha256(response.body()).hexdigest() == csv["sha256"]
        assert _overflow(pg) <= 0 and pg.errors == []
        pg.goto(base + "#/studio/flying-fish?scale=organ")
        pg.wait_for_function("document.querySelector('#main').textContent.includes('Observed-data update')")
        assert pg.get_by_role("link", name="Lean proof gallery").count() == 1
        assert pg.locator("img[alt*='Observed-data update']").count() == 1
        assert _overflow(pg) <= 0 and pg.errors == []
        pg.close()


def test_delphi_and_science_pairs_remain_distinct_and_selectable(browser, base):
    snap = json.loads((ROOT / 'site/data/snapshot.json').read_text())
    old = [c for c in snap['demo_videos']['cuts'] if c['id'] in {'frontier-60s', 'frontier-90s', 'frontier-120s'}]
    cuts = [dict(old[0], id=f'frontier-{edition}-{seconds}s', title=f'{edition} {seconds}', duration_s=seconds)
            for edition in ('science', 'delphi') for seconds in (60, 120)]
    snap['demo_videos']['cuts'] = old + cuts
    for width in (1440, 390):
        pg = page(browser, width, 960)
        pg.route('**/data/snapshot.json', lambda r: r.fulfill(json=snap))
        pg.goto(base + '#/demo')
        pg.wait_for_selector('#demo-video')
        assert pg.locator('.democut[aria-current=page]').get_attribute('href').endswith('frontier-delphi-60s')
        assert pg.locator('nav[aria-label="Choose a cut"] .democut').count() == 4
        assert pg.locator('.demoarchive .democut').count() == len(old)
        for edition in ('delphi', 'science'):
            pg.locator(f'.democut[href$="frontier-{edition}-60s"]').click()
            pg.wait_for_selector(f'.democut[aria-current=page][href$="frontier-{edition}-60s"]')
            assert pg.locator('#demo-switch').get_attribute('href').endswith(f'frontier-{edition}-120s')
            pg.locator('#demo-switch').click()
            pg.wait_for_selector(f'.democut[aria-current=page][href$="frontier-{edition}-120s"]')
            assert pg.locator('#demo-switch').get_attribute('href').endswith(f'frontier-{edition}-60s')
        assert pg.get_by_role('link', name='Explore Delphi', exact=True).get_attribute('href') == 'https://kavitakoolkarni-bio.github.io/delphi-portal/#about'
        assert _overflow(pg) <= 0 and not pg.errors
        pg.close()


def test_project_navigation_resets_scroll_but_same_page_queries_preserve_it(browser, base):
    for width in (1440, 390):
        pg = page(browser, width, 844)
        pg.goto(base + '#/studio')
        pg.wait_for_selector('a[href="#/studio/tissue-microcarrier"]')
        pg.locator('a[href="#/studio/tissue-microcarrier"]').click()
        pg.wait_for_selector('#rs-gap')
        pg.wait_for_function('window.scrollY === 0')
        assert pg.locator('#main h1').bounding_box()['y'] >= 0
        pg.evaluate('window.scrollTo(0, 400)')
        pg.evaluate("location.hash = '#/studio/tissue-microcarrier?detail=1'")
        pg.wait_for_function("DF.route.params.detail === '1'")
        assert abs(pg.evaluate('window.scrollY') - 400) <= 1
        pg.evaluate("location.hash = '#/studio/epithelial-repair'")
        pg.wait_for_function("DF.route.path === '/studio/epithelial-repair' && window.scrollY === 0")
        assert pg.locator('#main h1').bounding_box()['y'] >= 0
        assert pg.evaluate("document.activeElement.id") == 'main'
        assert 'observed fish' not in pg.locator('#foot').inner_text()
        assert _overflow(pg) <= 0 and not pg.errors
        pg.close()


@pytest.mark.parametrize("width", [1440, 390])
def test_reuse_studies_pair_real_recordings_with_controls_and_conditional_proofs(browser, base, width):
    import hashlib

    snapshot = json.loads((ROOT / "site/data/snapshot.json").read_text())
    pg = page(browser, width, 900)
    for study in ("tissue-microcarrier", "epithelial-repair"):
        cards = [c for c in snapshot["reuse_studies"]["visuals"] if c["study"] == study]
        assert cards, "Every published secondary study must have its own recorded artifact"
        pg.goto(base + "#/studio/" + study)
        pg.wait_for_selector("#rs-results")
        assert pg.locator(".reuse-result").count() == len(cards)
        assert pg.locator("#rs-rule").count() == 1
        assert pg.locator("#main .katex").count() >= 1
        assert pg.locator("#main .tex-fallback").count() == 0
        text = pg.locator("#main").inner_text()
        assert "unknown" in text and "does not establish tissue viability" in text
        assert "No wound simulation exists in this node yet" not in text
        assert "linking it to living tissue" in text or "calibrating them" in text.lower()
        assert "Wing loading" not in text and "[object Object]" not in text
        assert pg.locator('a[href="#/proofs?f=steady-oxygen-bound"]').count() == 1
        if study == "tissue-microcarrier":
            assert "45 g" in text and "50 × 30 × 30 mm" in text
            assert pg.locator("#rs-followup").count() == 0
            pg.locator(".reuse-diagnostic").evaluate("e => e.open = true")
            assert "15.574%" in pg.locator(".reuse-diagnostic").inner_text()
        else:
            assert "G1b" in text and "incomplete" in text
            assert pg.locator(".reuse-pair video").count() == 2
            assert pg.locator('.reuse-result a[href$="epithelial-card-errata.md"]').count() >= 1
            pg.locator("#rs-followup > summary").click()
            followup = pg.locator("#rs-followup").inner_text()
            assert "240 model runs" in followup and "FAIL" in followup
            assert "do not use this proportional rule" in followup
            assert "Longer-horizon closure" in followup and "remain unknown" in followup
            assert pg.locator('#rs-followup a[href="#/proofs?f=scaled-threshold-intervals"]').count() == 1
            assert pg.locator("#rs-followup tbody tr").count() == 2
            if width < 600:
                assert pg.locator("#rs-followup caption").bounding_box()["width"] >= 0.9 * pg.locator("#rs-followup .tablewrap").bounding_box()["width"]
            pg.wait_for_function("document.querySelector('#rs-followup img').naturalWidth > 0")
            f = snapshot["reuse_studies"]["sweep_followup"]
            for file in f["downloads"] + [{"href": f["figure_href"], "sha256": f["figure_sha256"]}]:
                response = pg.request.get(base + file["href"])
                assert response.ok and hashlib.sha256(response.body()).hexdigest() == file["sha256"]
        for video in pg.locator(".reuse-video").all():
            video.evaluate("v => { v.muted = true; return v.play(); }")
            pg.wait_for_function("v => v.currentTime > 0.1 && !v.error", arg=video.element_handle())
            video.evaluate("v => v.pause()")
        for card in cards:
            for file in card["media"].values():
                response = pg.request.get(base + file["path"])
                assert response.ok
                assert hashlib.sha256(response.body()).hexdigest() == file["sha256"]
            for file in card["downloads"]:
                response = pg.request.get(base + file["href"])
                assert response.ok
                assert hashlib.sha256(response.body()).hexdigest() == file["sha256"]
        assert pg.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
    assert pg.errors == []


@pytest.mark.parametrize("width", [1440, 390])
def test_system_operations_shows_dated_receipts_and_expandable_details(browser, base, width):
    projection = json.loads((ROOT / "site/artifacts/system-operations/operations.json").read_text())
    pg = page(browser, width, 900)
    pg.goto(base + "#/system?tab=operations")
    pg.wait_for_selector("#op-h")
    text = pg.locator("#opsroot").inner_text()
    assert "Latest source observation" in text and "historical sampled intervals" in text
    assert "unknown right now" in text and "spend unknown" in text
    assert "Preparation and partial results" in text and "not an audit queue" in text
    assert "18" in text and "failed" in text
    assert "363" in text and "32.3 / 37" in text
    assert "biological validation" not in text.lower() or "no biological validation" in text.lower()
    assert pg.locator("#opsroot details.ops-detail[open]").count() == 0
    sources = pg.locator('details.ops-detail', has=pg.locator('summary', has_text="Show receipts, pin status and digests"))
    sources.locator("summary").click()
    assert sources.locator("tbody tr").count() == len(projection["sources"])
    assert _overflow(pg) <= 0 and not pg.errors
    pg.close()


def test_operations_missing_samples_remain_unknown_and_load_failure_is_visible(browser, base):
    projection = json.loads((ROOT / "site/artifacts/system-operations/operations.json").read_text())
    for row in projection["plans"]["sampled_utilization"]["windows"]:
        row["gpu_utilization_pct_mean"] = None
        row["gpu_utilization_pct_max"] = None
    pg = page(browser, 390, 900)
    pg.route("**/artifacts/system-operations/operations.json", lambda route: route.fulfill(json=projection))
    pg.goto(base + "#/system?tab=operations")
    pg.wait_for_selector("#op-p")
    text = pg.locator('[aria-labelledby="op-p"]').inner_text()
    assert "unknown / unknown" in text and "0.0 /" not in text and "NaN" not in text
    assert _overflow(pg) <= 0 and not pg.errors
    pg.close()
    pg = page(browser, 390, 900)
    pg.route("**/artifacts/system-operations/operations.json", lambda route: route.fulfill(status=404, body="missing"))
    pg.goto(base + "#/system?tab=operations")
    pg.wait_for_selector("#opsroot .note")
    assert "Unavailable" in pg.locator("#opsroot").inner_text()
    assert "not zero activity" in pg.locator("#opsroot").inner_text()
    assert not pg.errors
    pg.close()


@pytest.mark.parametrize("width", [1440, 390])
def test_about_blog_docs_groups_and_lean_page_are_readable(browser, base, width):
    """Blog posts come from docs/blog/*.md through the snapshot, load their body, and never overflow; the Documentation page groups every
    snapshot document exactly once; the Lean page opens with a plain-language gloss per family and keeps the detail inside folded sections."""
    posts = sorted((ROOT / "docs" / "blog").glob("*.md"))
    assert len(posts) >= 4
    pg = page(browser, width, 900)
    pg.goto(base + "#/about/blog"); pg.wait_for_selector(".about-posts article")
    assert pg.locator(".about-posts article").count() == len(posts) and _overflow(pg) <= 0
    pg.goto(base + "#/about/blog/lean-for-biology"); pg.wait_for_selector("#post-body h3")
    body = pg.locator("#post-body").inner_text()
    assert "What Lean cannot tell you" in body and "Loading" not in body and "Date:" not in body and _overflow(pg) <= 0
    assert pg.locator('#post-body a[href="#/proofs"]').count() == 1       # in-site links work and are not opened in a new tab
    pg.goto(base + "#/about/blog/no-such-post"); pg.wait_for_selector(".about-hero")
    assert "Post not found" in pg.locator(".about-page").inner_text()
    pg.goto(base + "#/about/docs"); pg.wait_for_selector(".about-docs article")
    snap = json.loads((ROOT / "site" / "data" / "snapshot.json").read_text())
    assert pg.locator(".about-docs article").count() == len(snap["documents"]) and "*" not in pg.locator(".about-page").inner_text()
    assert pg.locator(".about-section h2").count() >= 4 and _overflow(pg) <= 0
    pg.goto(base + "#/proofs"); pg.wait_for_selector(".proof-plain")
    fams = len(snap["lean_gallery"]["families"])
    assert pg.locator(".proofindex-cards a").count() == fams and pg.locator(".proof-plain").count() == fams
    assert pg.locator("details.pfold:not([open])").count() >= fams * 3 and _overflow(pg) <= 0
    assert not pg.errors
    pg.close()
