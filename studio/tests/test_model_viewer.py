"""The actual-GLB viewer (site/js/model-viewer.js): real mesh load, metre dimensions, orbit/reset,
component selection and the static fallbacks, driven in headless Chromium against a bounded local
HTTP server that serves only site/, artifacts/ and the fixture page."""
import hashlib
import json
import os
import tempfile
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts/fish3d/fish3d-N1-cypselurus-baseline"
BASE = "/artifacts/fish3d/fish3d-N1-cypselurus-baseline/"
ARGS = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist",
        "--num-raster-threads=1", "--disable-dev-shm-usage"]


def _glb_union_size_m():
    """Union bbox of every mesh, from the GLB's own POSITION accessor min/max (metres), read
    without the viewer: x snout->tail, y up, z -left.  Fins and spread pectorals make this larger
    than the 0.1588 m standard length."""
    import struct
    b = (ART / "fish.glb").read_bytes()
    n = struct.unpack("<I", b[12:16])[0]
    g = json.loads(b[20:20 + n])
    lo, hi = [9.0] * 3, [-9.0] * 3
    for m in g["meshes"]:
        for p in m["primitives"]:
            a = g["accessors"][p["attributes"]["POSITION"]]
            lo = [min(x, y) for x, y in zip(lo, a["min"])]
            hi = [max(x, y) for x, y in zip(hi, a["max"])]
    return tuple(h - l for l, h in zip(lo, hi))


class _Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


@pytest.fixture(scope="module")
def server():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "site").symlink_to(ROOT / "site")
        (d / "artifacts").symlink_to(ROOT / "artifacts")
        (d / "index.html").symlink_to(ROOT / "tests/fixtures/model_viewer/index.html")
        srv = ThreadingHTTPServer(("127.0.0.1", 0), partial(_Quiet, directory=str(d)))
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        yield f"http://127.0.0.1:{srv.server_address[1]}"
        srv.shutdown()


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch(args=ARGS)
        except Exception as e:  # no browser installed: not a pass, a skip
            pytest.skip(f"chromium unavailable: {e}")
        yield b
        b.close()


@pytest.fixture
def page(browser):
    ctx = browser.new_context(viewport={"width": 1400, "height": 900})
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    yield pg
    ctx.close()


def _open(page, server, query="?lazy=0"):
    page.goto(server + "/" + query)
    return page.evaluate("window.__v.ready.then(() => window.__v.state())")


def comps_body_x_m(page):
    return page.evaluate("""() => { const o = window.__v; return o.bodyExtentX ? o.bodyExtentX() : null; }""")


def _assert_shaded_mesh(page, cv, png):
    """The mesh pixels (those that differ from the same view with every component hidden) must be
    lit and shaded: a black silhouette has the right outline and no shading (the GLB has no normals)."""
    import io
    from PIL import Image
    names = page.evaluate("window.__v.componentNames()")
    for n in names:
        page.evaluate("n => window.__v.setVisible(n, false)", n)
    bg = Image.open(io.BytesIO(cv.screenshot())).convert("RGB")
    for n in names:
        page.evaluate("n => window.__v.setVisible(n, true)", n)
    img = Image.open(io.BytesIO(png)).convert("RGB")
    px = [(a, b) for a, b in zip(img.getdata(), bg.getdata()) if a != b]
    assert len(px) > 0.01 * img.width * img.height, "no mesh pixels drawn"
    luma = [0.299 * a[0] + 0.587 * a[1] + 0.114 * a[2] for a, _ in px]
    mean = sum(luma) / len(luma)
    var = sum((v - mean) ** 2 for v in luma) / len(luma)
    assert mean > 70, f"mesh renders dark (mean luma {mean:.0f}): unlit/black"
    assert var ** 0.5 > 8, f"mesh is flat (luma std {var ** 0.5:.1f}): no shading"


def test_actual_glb_loads_with_metre_dimensions_and_hash(page, server):
    st = _open(page, server)
    assert st["mode"] == "interactive", st
    assert st["hashChecked"] is True
    assert st["glbSha256"] == hashlib.sha256((ART / "fish.glb").read_bytes()).hexdigest()
    comps = json.loads((ART / "components.json").read_text())["components"]
    assert sorted(st["names"]) == sorted(comps) and len(st["names"]) == 13
    d = page.evaluate("window.__v.dimensions()")
    for got, want in zip((d["x_m"], d["y_m"], d["z_m"]), _glb_union_size_m()):
        assert got == pytest.approx(want, abs=2e-5)
    assert 0.2 < d["x_m"] < 0.26        # metres, not mm: ~231 mm snout-to-caudal-tip incl. fins
    body = comps_body_x_m(page)
    assert body == pytest.approx(0.1588, abs=2e-4)   # standard length, components.json body bbox
    assert page.locator(".mv-stage canvas").count() == 1
    assert page.locator(".mv-badge", has_text="ACTUAL MESH").count() == 1
    assert page.locator(".mv-badge", has_text="not a validated organism").count() == 1
    assert page.locator(".mv-status").inner_text().count("Colours are appearance only") == 1
    assert page.errors == []


def test_orbit_by_keyboard_changes_pixels_and_reset_restores(page, server):
    _open(page, server)
    cv = page.locator(".mv-stage canvas")
    first = cv.screenshot()
    _assert_shaded_mesh(page, cv, first)
    cv.focus()
    for _ in range(6):
        page.keyboard.press("ArrowRight")
    page.keyboard.press("+")
    rotated = cv.screenshot()
    assert rotated != first
    page.get_by_role("button", name="Reset view").click()
    assert cv.screenshot() == first
    cv.focus()
    page.keyboard.press("ArrowLeft")
    page.keyboard.press("0")
    page.evaluate("document.activeElement.blur()")      # the focus ring is not part of the view
    page.wait_for_timeout(100)
    assert cv.screenshot() == first


def test_component_list_selection_shows_provenance_and_exact_mesh(page, server):
    _open(page, server)
    comps = json.loads((ART / "components.json").read_text())["components"]
    page.locator('[data-comp="pectoral_L"] .mv-name').click()
    assert page.evaluate("window.__v.state().selected") == "pectoral_L"
    det = page.locator(".mv-detail")
    assert "pectoral_L" in det.inner_text()
    link = det.locator("a")
    assert link.get_attribute("href").endswith("components/pectoral_L.stl")
    assert comps["pectoral_L"]["stl_sha256"] in det.inner_text()
    stl = ART / "components/pectoral_L.stl"
    assert hashlib.sha256(stl.read_bytes()).hexdigest() == comps["pectoral_L"]["stl_sha256"]
    statuses = {s.inner_text() for s in det.locator(".mv-st").all()}
    assert {"assumed", "figure_read"} <= statuses            # provenance is shown per parameter
    page.locator('[data-comp="scales"] .mv-name').click()
    assert "assumed" in page.locator(".mv-detail").inner_text()


def test_click_on_mesh_selects_a_real_component_and_toggle_hides(page, server):
    _open(page, server)
    cv = page.locator(".mv-stage canvas")
    box = cv.bounding_box()
    hit = None
    for fx in (0.5, 0.45, 0.55, 0.4, 0.6, 0.35):
        for fy in (0.5, 0.45, 0.55):
            page.mouse.click(box["x"] + box["width"] * fx, box["y"] + box["height"] * fy)
            hit = page.evaluate("window.__v.state().selected")
            if hit:
                break
        if hit:
            break
    assert hit in page.evaluate("window.__v.componentNames()"), "no click landed on the mesh"
    assert page.locator(f'[data-comp="{hit}"][aria-current="true"]').count() == 1
    page.locator('[data-comp="scales"] input').uncheck()
    assert page.evaluate("window.__v.state().visible.scales") is False
    page.get_by_role("button", name="Show all components").click()
    assert page.evaluate("window.__v.state().visible.scales") is True


def test_hero_layout_is_wide_on_desktop_and_stacks_on_mobile(page, server):
    _open(page, server)
    w = page.locator(".mv-stage").bounding_box()["width"]
    side = page.locator(".mv-list").bounding_box()
    assert w > 800 and side["x"] > page.locator(".mv-stage").bounding_box()["x"] + w - 5
    page.set_viewport_size({"width": 390, "height": 800})
    page.wait_for_timeout(200)
    s, l = page.locator(".mv-stage").bounding_box(), page.locator(".mv-list").bounding_box()
    assert l["y"] >= s["y"] + s["height"] - 1 and s["width"] <= 390


def test_fallback_when_webgl_is_unavailable(page, server):
    page.add_init_script("""
      const g = HTMLCanvasElement.prototype.getContext;
      HTMLCanvasElement.prototype.getContext = function (t, ...r) {
        return /webgl/.test(t) ? null : g.call(this, t, ...r); };""")
    st = _open(page, server)
    assert st["mode"] == "fallback" and "WebGL" in st["reason"]
    assert page.locator(".mv-stage canvas").count() == 0
    assert page.evaluate("document.querySelector('.mv-stage img').naturalWidth") > 0
    assert page.locator(".mv-status").get_attribute("data-state") == "fallback"
    assert page.locator(".mv-badge", has_text="ACTUAL MESH").count() == 1   # labels survive
    page.get_by_role("button", name="Play turntable video").click()
    assert page.locator(".mv-stage video").evaluate("v => !v.hidden && v.src.endsWith('turntable.mp4')")


def test_fallback_when_glb_bytes_do_not_match_recorded_hash(page, server):
    real = (ART / "fish.glb").read_bytes()
    bad = real[:-4] + bytes((b + 1) % 256 for b in real[-4:])
    page.route("**/fish.glb", lambda r: r.fulfill(status=200, body=bad, content_type="model/gltf-binary"))
    st = _open(page, server)
    assert st["mode"] == "fallback" and "sha256" in st["reason"]
    assert page.locator(".mv-stage canvas").count() == 0


def test_fallback_when_glb_is_missing(page, server):
    page.route("**/fish.glb", lambda r: r.fulfill(status=404, body="no"))
    st = _open(page, server)
    assert st["mode"] == "fallback" and "404" in st["reason"]


def test_lazy_mount_does_not_fetch_the_glb_until_visible(page, server):
    seen = []
    page.on("request", lambda r: seen.append(r.url))
    page.goto(server + "/?lazy=1")
    page.set_viewport_size({"width": 1400, "height": 900})
    page.evaluate("window.__v.ready")        # in view on this page, so it loads
    assert any(u.endswith("/fish.glb") for u in seen)
    seen.clear()
    page.goto(server + "/?lazy=1&pad=6000")
    page.wait_for_timeout(500)
    assert not any(u.endswith("/fish.glb") for u in seen)
    assert page.evaluate("window.__v.state().mode") == "pending"
    page.evaluate("window.scrollTo(0, 6000)")
    page.evaluate("window.__v.ready")
    assert any(u.endswith("/fish.glb") for u in seen)
