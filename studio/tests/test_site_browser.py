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
    for route in ["formalize?ex=cantilever", "frontier", "knowledge", "knowledge?tab=graph", "knowledge?tab=mission", "knowledge?tab=catalog", "engineering", "evidence", "work", "belief", "search?q=fisher&tab=catalog"]:
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
    for route in ["home", "formalize?ex=cantilever", "studio", "studio/flying-fish", "studio/flying-fish?scale=organism", "entity/Claim/turing-ddi", "graph/Claim/turing-ddi", "frontier", "knowledge", "knowledge?tab=graph", "knowledge?tab=mission", "knowledge?tab=catalog", "engineering", "simulations", "evidence", "work", "work?tab=specs", "work?tab=work", "work?tab=resources", "work?tab=receipts", "work?tab=runtime", "belief", "search?q=fisher&tab=catalog"]:
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
    pg = page(browser)
    pg.goto(base + "#/work?tab=connect")
    pg.wait_for_selector("#cn-h")
    txt = pg.locator("#main").inner_text().lower()
    assert "is not tested" in txt and "official mcp sdk client" in txt and "never put a credential" in txt
    assert pg.input_value("#sharelink").startswith("http")


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
    assert pg.locator(".tablewrap td:has-text('preregistered')").count() == 0   # date-only verdicts are not placed on the dated timeline
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
    assert hrefs == ["#/about", "#/about/team", "#/about/docs", "#/about/inspirations", "#/generative"]
    assert pg.locator("nav[aria-label=Views] > ul > li > a:has-text('Generative')").count() == 0   # not a top-level item
    assert not pg.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
    pg2 = page(browser, 400, 800)
    pg2.goto(base + "#/home"); pg2.wait_for_selector(".aboutmenu summary")
    assert not pg2.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")


def test_system_built_tab_reports_counters_only_with_unknowns_and_no_scorecard(browser, base):
    pg = page(browser)
    pg.goto(base + "#/work?tab=built")
    pg.wait_for_selector("#bt-h")
    t = pg.locator("#main").text_content()
    for q in ("Agents", "Model calls and tokens", "GPU jobs (own H100)", "GPU container work seconds", "CPU jobs (own)", "GPU utilisation", "Cost"):
        assert q in t, q
    assert "CPU seconds are not recorded: unknown" in t and "Total distinct agents and currently active agents: unknown" in t
    assert "1037.4 s" in t and "GPU kernel seconds and billed GPU seconds: unknown" in t and "not a count of agents" in t and "Provider COMPLETED means the container ended" in t and "Reuse by anyone outside this team is not recorded" in t
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


def test_home_offers_the_v3_display_props_with_hash_exact_stl_downloads(browser, base):
    import hashlib
    snap = json.loads((ROOT / "site/data/snapshot.json").read_text())
    assert snap["print_v3"]["refused"] == []
    for f in snap["print_v3"]["forms"]:
        for x in f["files"]:
            b = (ROOT / "site" / x["href"]).read_bytes()
            assert len(b) == x["bytes"] and hashlib.sha256(b).hexdigest() == x["sha256"], x["href"]
    pg = page(browser)
    pg.goto(base + "#/home"); pg.wait_for_selector(".printv3 select")
    assert pg.locator(".printv3 option").all_inner_texts() == ["fish3d-v3a-fan-prop", "fish3d-v3b-glide-pose-prop"]
    assert pg.locator(".printv3 .v3links a[download]").count() == 3
    pg.select_option(".printv3 select", "fish3d-v3b-glide-pose-prop")
    hrefs = pg.locator(".printv3 .v3links a").evaluate_all("els => els.map(e => e.getAttribute('href'))")
    assert all("fish3d-v3b-glide-pose-prop" in h and h.endswith(".stl") for h in hrefs), hrefs
    assert "printer and resin unknown" in pg.locator(".printv3").text_content() and "not organisms" in pg.locator(".printv3 .v3info").text_content()
    assert pg.request.get(base + hrefs[0]).status == 200


def test_morpheus_full_horizon_chart_is_labelled_a_chart_not_a_spatial_movie(browser, base):
    pg = page(browser)
    pg.goto(base + "#/simulations"); pg.wait_for_selector("#sim-morpheus-full-horizon-chart video")
    t = pg.locator("#sim-morpheus-full-horizon-chart").text_content()
    assert "not a spatial tissue movie" in t and "draws no cell shapes or fields" in t and "No sha256 is declared" in t and "256 cells" in t and "128 cells" in t
