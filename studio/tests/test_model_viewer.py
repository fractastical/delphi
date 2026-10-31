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


def _glb(nodes, meshes, materials, spec):
    """Minimal glTF 2.0 binary writer for the synthetic fixtures (NOT fish data)."""
    import struct
    bin_ = b"".join(b[0] for b in spec)
    g = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}], "nodes": nodes, "meshes": meshes,
         "buffers": [{"byteLength": len(bin_)}]}
    off, views, accs = 0, [], []
    for blob, typ, ct, cnt, extra in spec:
        views.append({"buffer": 0, "byteOffset": off, "byteLength": len(blob)})
        accs.append({"bufferView": len(views) - 1, "componentType": ct, "count": cnt, "type": typ, **extra})
        off += len(blob)
    g["bufferViews"], g["accessors"] = views, accs
    if materials:
        g["materials"] = materials
    js = json.dumps(g).encode()
    js += b" " * (-len(js) % 4)
    bin_ += b"\0" * (-len(bin_) % 4)
    body = struct.pack("<II", len(js), 0x4E4F534A) + js + struct.pack("<II", len(bin_), 0x004E4942) + bin_
    return struct.pack("<III", 0x46546C67, 2, 12 + len(body)) + body


def _write_synthetic(d):
    """Two tiny variants of one synthetic geometry: a nested node holding a two-primitive mesh (one
    primitive with a BLEND material, one with COLOR_0 vertex colours) beside a mesh with no material."""
    import struct
    d.mkdir()
    f = lambda *v: struct.pack("<%df" % len(v), *v)
    tri = f(0, 0, 0, 0.1, 0, 0, 0, 0.05, 0)                       # 0.1 m long
    tri2 = f(0, 0, 0.01, 0.1, 0, 0.01, 0, 0.05, 0.01)
    tri3 = f(0, 0.06, 0, 0.1, 0.06, 0, 0, 0.1, 0)
    col = f(1, 0, 0, 1, 0, 1, 0, 1, 0, 0, 1, 1)                  # RGBA float
    idx = struct.pack("<3H", 0, 1, 2)
    mins = lambda v: {"min": [0.0, 0.0, v], "max": [0.1, 0.05, v]}
    spec = [(tri, "VEC3", 5126, 3, mins(0.0)), (tri2, "VEC3", 5126, 3, mins(0.01)),
             (tri3, "VEC3", 5126, 3, {"min": [0, 0.06, 0], "max": [0.1, 0.1, 0]}),
             (col, "VEC4", 5126, 3, {}), (idx + b"\0\0", "SCALAR", 5123, 3, {})]
    nodes = [{"name": "root", "children": [1, 3]}, {"name": "fan_group", "children": [2]},
             {"name": "fin_fan", "mesh": 0}, {"name": "naked", "mesh": 1}]
    meshes = [{"name": "fin_fan", "primitives": [
                  {"attributes": {"POSITION": 0}, "indices": 4, "material": 0},
                  {"attributes": {"POSITION": 1, "COLOR_0": 3}, "indices": 4}]},
              {"name": "naked", "primitives": [{"attributes": {"POSITION": 2}, "indices": 4}]}]
    mats = [{"name": "membrane", "alphaMode": "BLEND",
             "pbrMetallicRoughness": {"baseColorFactor": [0.8, 0.1, 0.1, 0.35], "metallicFactor": 0, "roughnessFactor": 0.9}}]
    glb = _glb(nodes, meshes, mats, spec)
    comps = {"schema": "synthetic", "components": {"fin_fan": {"params": {"rays": {"status": "assumed", "value": 12, "note": "synthetic"},
                                                                           "outline": {"status": "digitized", "value": "x"}}}}}
    for vid in ("a", "b"):
        (d / f"fish-{vid}.glb").write_bytes(glb + b"")
    h = hashlib.sha256(glb).hexdigest()
    (d / "components.json").write_text(json.dumps(comps))
    for vid, lab in (("a", "Appearance only. Synthetic variant A."), ("b", "Appearance only. Synthetic variant B (bars are a design choice).")):
        (d / f"appearance-{vid}.json").write_text(json.dumps({
            "glb": f"fish-{vid}.glb", "glb_sha256": h, "label": lab, "title": f"variant {vid}", "schema": "frontier.fish3d.appearance/1",
            "elements": [{"element": "bars", "status": "design choice"}, {"element": "back", "status": "sourced (family)", "source": "x"}]}))
    _write_nonuniform(d)
    (d / "wrong.json").write_text(json.dumps({"glb": "fish-b.glb", "glb_sha256": "0" * 64}))
    (d / "poster.png").write_bytes((ART / "render/poster.png").read_bytes())


def _write_nonuniform(d):
    """fish-nu.glb: two OVERLAPPING nodes under a root, each a two-sheet box (quads at local z = -0.5 and +0.5),
    with non-uniform node scales ([2,1,3] and [1,1,0.5]) so a local-frame distance differs from the world one."""
    import struct
    f = lambda *v: struct.pack("<%df" % len(v), *v)
    quad = lambda z: [(-1, -1, z), (1, -1, z), (1, 1, z), (-1, 1, z)]
    pts = quad(-0.5) + quad(0.5)
    pos = f(*[c for p in pts for c in p])
    idx = struct.pack("<12H", 0, 1, 2, 0, 2, 3, 4, 5, 6, 4, 6, 7)
    spec = [(pos, "VEC3", 5126, 8, {"min": [-1, -1, -0.5], "max": [1, 1, 0.5]}), (idx, "SCALAR", 5123, 12, {})]
    nodes = [{"name": "root", "children": [1, 2]},
             {"name": "slab", "mesh": 0, "scale": [2, 1, 3]},
             {"name": "plate", "mesh": 1, "scale": [1, 1, 0.5], "translation": [0.3, 0.2, 1.0]}]
    meshes = [{"name": "slab", "primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]},
              {"name": "plate", "primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}]
    (d / "fish-nu.glb").write_bytes(_glb(nodes, meshes, None, spec))


@pytest.fixture(scope="module")
def server():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "site").symlink_to(ROOT / "site")
        (d / "artifacts").symlink_to(ROOT / "artifacts")
        (d / "index.html").symlink_to(ROOT / "tests/fixtures/model_viewer/index.html")
        _write_synthetic(d / "synthetic")
        if os.environ.get("MV_FISH_DIR"):     # run against an uncommitted candidate dir, e.g. a v3 snapshot
            (d / "extern").symlink_to(Path(os.environ["MV_FISH_DIR"]).resolve())
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
    st_text = page.locator(".mv-status").inner_text()
    assert "flat appearance-only colours" in st_text and "sha256 matches render/render.json" in st_text
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


SYN = "/synthetic/"
SYN_VARIANTS = json.dumps([{"id": "a", "glb": "fish-a.glb", "appearance": "appearance-a.json", "poster": "poster.png", "video": None},
                           {"id": "b", "glb": "fish-b.glb", "appearance": "appearance-b.json", "poster": "poster.png", "video": None}])


def _open_syn(page, server, variants=SYN_VARIANTS):
    from urllib.parse import quote
    page.goto(f"{server}/?lazy=0&base={SYN}&variants={quote(variants)}")
    return page.evaluate("window.__v.ready.then(() => window.__v.state())")


def test_source_materials_and_any_node_structure_are_kept(page, server):
    st = _open_syn(page, server)
    assert st["mode"] == "interactive", st
    # any node: a nested node with a provenance record is one component holding both of its primitives,
    # and the wrapper nodes (root, fan_group) do not swallow it
    assert sorted(st["names"]) == ["fin_fan", "naked"]
    info = page.evaluate("window.__v.componentInfo('fin_fan')")
    kinds = sorted(m["kind"] for m in info["materials"])
    assert kinds == ["glb_material", "vertex_colors"]
    memb = next(m for m in info["materials"] if m["kind"] == "glb_material")
    lin = lambda c: round(255 * (12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055))
    want = "#%02x%02x%02x" % tuple(lin(c) for c in (0.8, 0.1, 0.1))   # glTF baseColorFactor is linear
    assert memb["color"] == want == "#e75959" and memb["transparent"] is True and memb["opacity"] == pytest.approx(0.35, abs=1e-3)
    vc = next(m for m in info["materials"] if m["kind"] == "vertex_colors")
    assert vc["vertexColors"] is True
    naked = page.evaluate("window.__v.componentInfo('naked')")
    assert naked["materials"][0]["kind"] == "flat_default"
    assert st["materials"]["source"].startswith("mixed")
    assert "Colours: mixed" in page.locator(".mv-status").inner_text()
    # a node without a components.json record is listed as such and claims nothing
    assert page.locator('[data-comp="naked"] .mv-name').inner_text().endswith("(no record)")
    page.locator('[data-comp="naked"] .mv-name').click()
    assert "No provenance record" in page.locator(".mv-detail").inner_text()
    assert st["noProvenance"] == ["naked"] and page.locator('[data-comp="fin_fan"] .mv-name').inner_text() == "fin_fan"


def test_variants_switch_with_labels_hash_and_stable_view(page, server):
    st = _open_syn(page, server)
    assert st["variant"] == "a" and st["hashChecked"] is True and st["hashSource"] == "appearance-a.json"
    assert "Synthetic variant A" in page.locator(".mv-appearance").inner_text()
    assert page.locator(".mv-appearance .mv-st", has_text="design choice").count() == 1
    assert page.locator(".mv-variants button").count() == 2
    page.evaluate("window.__v.select('naked')")
    ok = page.evaluate("window.__v.setVariant('b')")
    assert ok is True
    st2 = page.evaluate("window.__v.state()")
    assert st2["variant"] == "b" and st2["mode"] == "interactive" and st2["selected"] is None
    assert "Synthetic variant B" in page.locator(".mv-appearance").inner_text()
    assert page.locator('.mv-variants button[aria-pressed="true"]').get_attribute("data-variant") == "b"
    assert st2["dims"]["x_m"] == pytest.approx(0.1, abs=1e-6)


def test_variant_hash_mismatch_falls_back_not_verified(page, server):
    bad = json.dumps([{"id": "b", "glb": "fish-b.glb", "appearance": "wrong.json", "poster": "poster.png", "video": None}])
    st = _open_syn(page, server, bad)
    assert st["mode"] == "fallback" and "sha256" in st["reason"] and "wrong.json" in st["reason"]


def test_no_recorded_hash_is_not_reported_as_verified(page, server):
    one = json.dumps([{"id": "a", "glb": "fish-a.glb", "poster": "poster.png", "video": None}])
    st = _open_syn(page, server, one)
    assert st["mode"] == "interactive" and st["hashChecked"] is None
    assert "hash not recorded" in page.locator(".mv-status").inner_text()


def test_latency_and_pick_bounds_on_the_real_mesh(page, server):
    st = _open(page, server)
    p = st["perf"]
    assert p["total_ms"] < 15000 and p["first_frame_ms"] is not None and p["first_frame_ms"] < 20000, p
    cv = page.locator(".mv-stage canvas")
    box = cv.bounding_box()
    page.mouse.click(box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.5)
    pick = page.evaluate("window.__v.state().perf.last_pick_ms")
    meth = page.evaluate("window.__v.state().perf.pick_method")
    assert meth == "cpu-triangle-bounds", meth
    assert pick is not None and pick < 600, f"pick took {pick} ms"
    t0 = page.evaluate("performance.now()")
    for _ in range(10):
        page.keyboard.press("ArrowRight")
    assert page.evaluate("performance.now()") - t0 < 4000          # ten orbit steps stay interactive
    print("perf", p, "pick_ms", pick)


@pytest.mark.skipif(not (os.environ.get("MV_FISH_DIR") or any((ROOT / "artifacts/fish3d").glob("*/appearance-*.json"))),
                    reason="no fish3d candidate with appearance-*.json present")
def test_real_v3_candidate_keeps_its_vertex_colours_and_provenance(page, server):
    import struct
    from urllib.parse import quote
    if os.environ.get("MV_FISH_DIR"):
        d, base = Path(os.environ["MV_FISH_DIR"]), "/extern/"
    else:
        d = sorted((ROOT / "artifacts/fish3d").glob("*/appearance-*.json"))[0].parent
        base = f"/artifacts/fish3d/{d.name}/"
    apps = sorted(d.glob("appearance-*.json"))
    vs = []
    for a in apps:
        j = json.loads(a.read_text())
        vs.append({"id": j["option"], "glb": j["glb"], "appearance": a.name,
                   "poster": f"preview-{j['option']}.png", "video": None})
    if (d / "fish.glb").exists() and (d / "build.json").exists():     # exact geometry, no materials, hash from build.json
        vs.append({"id": "exact-geometry", "glb": "fish.glb", "appearance": None, "poster": vs[0]["poster"], "video": None})
    page.goto(f"{server}/?lazy=0&base={base}&variants={quote(json.dumps(vs))}")
    st = page.evaluate("window.__v.ready.then(() => window.__v.state())")
    assert st["mode"] == "interactive", st
    for v in vs:
        if v["id"] != st["variant"]:
            assert page.evaluate("id => window.__v.setVariant(id)", v["id"]) is True
        st = page.evaluate("window.__v.state()")
        raw = (d / v["glb"]).read_bytes()
        n = struct.unpack("<I", raw[12:16])[0]
        gj = json.loads(raw[20:20 + n])
        has_color = any("COLOR_0" in p["attributes"] for m in gj["meshes"] for p in m["primitives"])
        assert st["hashChecked"] is True, (v, st["hashSource"])
        assert sorted(st["names"]) == sorted(x["name"] for x in gj["nodes"] if "mesh" in x)
        gm = gj.get("materials", [])
        if gm:              # a declared material (alpha mode, double-sided, metalness) must survive as-is
            prims = {x["name"]: gj["meshes"][x["mesh"]]["primitives"][0] for x in gj["nodes"] if "mesh" in x}
            for nm, pr in prims.items():
                want = gm[pr["material"]]
                info = page.evaluate("n => window.__v.componentInfo(n)", nm)["materials"][0]
                assert "glb_material" in info["kind"], (nm, info)
                assert info["transparent"] == (want.get("alphaMode") == "BLEND"), (nm, want, info)
                if want.get("alphaMode") == "BLEND":
                    assert info["opacity"] == pytest.approx(want["pbrMetallicRoughness"]["baseColorFactor"][3], abs=1e-3)
            assert any(w.get("alphaMode") == "BLEND" for w in gm) and st["materials"]["glb_material"] == len(prims)
        if has_color:       # the source colours must not be replaced by flat defaults
            assert st["materials"]["flat_default"] == 0 and st["materials"]["vertex_colors"] > 0, st["materials"]
        if v["appearance"]:
            assert json.loads((d / v["appearance"]).read_text())["label"] in page.locator(".mv-appearance").inner_text()
        else:
            assert st["hashSource"] == "build.json" and st["materials"]["flat_default"] == len(st["names"])
            assert page.locator(".mv-appearance").inner_text().strip() == ""


def test_fast_pick_agrees_with_threes_raycaster_over_a_grid(page, server):
    _open(page, server)
    pts = [(x / 20, y / 20) for x in range(-7, 8, 2) for y in range(-5, 6, 2)]   # 8 x 6, around the fish
    res = page.evaluate("pts => pts.map(([x, y]) => window.__v._pickCompare(x, y))", pts)
    hits = [r for r in res if r[1] is not None]
    assert len(hits) >= 8, "grid never touched the mesh, so agreement proves nothing"
    assert [r for r in res if r[0] != r[1]] == [], [r for r in res if r[0] != r[1]]
    assert len({r[1] for r in hits}) >= 2          # more than one component is exercised


@pytest.mark.parametrize("heavy", [0, 1000000])      # 0 forces the triangle-bounds path, 1e6 the Raycaster path
def test_pick_distance_is_world_distance_under_nonuniform_scaled_overlapping_nodes(page, server, heavy):
    from urllib.parse import quote
    v = json.dumps([{"id": "nu", "glb": "fish-nu.glb", "poster": "poster.png", "video": None}])
    page.goto(f"{server}/?lazy=0&heavy={heavy}&base={SYN}&variants={quote(v)}")
    st = page.evaluate("window.__v.ready.then(() => window.__v.state())")
    assert st["mode"] == "interactive" and sorted(st["names"]) == ["plate", "slab"], st
    pts = [(x / 10, y / 10) for x in range(-8, 9) for y in range(-8, 9)]
    res = page.evaluate("pts => pts.map(([x, y]) => window.__v._pickCompare(x, y))", pts)
    hits = [r for r in res if r[1] is not None]
    assert {r[1] for r in hits} == {"plate", "slab"}, "the fixture must exercise both overlapping nodes"
    assert len(hits) > 40
    for fast_name, ray_name, fast_d, ray_d in hits:
        assert fast_name == ray_name
        assert fast_d == pytest.approx(ray_d, rel=1e-5, abs=1e-9), (fast_name, fast_d, ray_d)
    assert all(r[0] is None for r in res if r[1] is None)        # no hit where Raycaster has none
    want = "bounds" if heavy == 0 else "raycaster"                 # the size threshold really selects the path
    for n in ("plate", "slab"):
        assert page.evaluate("n => window.__v.componentInfo(n).pickPaths", n) == [want], (n, heavy)
