"""site/js/ecology-viewer.js: saved-state ecology trajectories (frontier.ecology.trajectory/1) in headless
Chromium against a bounded 127.0.0.1 server that serves only site/, artifacts/ and the fixture page.

The trajectories here are DETERMINISTIC SYNTHETIC TEST FIXTURES written by this module (ballistic motion plus a
yaw, a pitch, an escape flag and a termination).  They exist to test the viewer's mechanics; they are never
shipped on the site and nothing in the viewer holds them.  The fish mesh is the real v3a fish.glb."""
import json
import math
import os
import struct
import tempfile
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

ROOT = Path(__file__).resolve().parents[1]
GLB = ROOT / "artifacts/fish3d/fish3d-v3a-fan/fish.glb"
ARGS = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist",
        "--num-raster-threads=1", "--disable-dev-shm-usage"]
CG = 0.0635260971682413               # cg_from_nose_m of the native baseline (0.4 * standard length, an assumption there)
PANELS = ROOT / "artifacts/fish3d/fish3d-v3a-fan/panels.json"
STL_DIR = ROOT / "artifacts/fish3d/fish3d-v3a-fan/components"
G = 9.81

pytestmark = pytest.mark.skipif(not (GLB.exists() and PANELS.exists()), reason="needs artifacts/fish3d/fish3d-v3a-fan/{fish.glb,panels.json}")


# ---- independent maths (plain python; deliberately not the viewer's code) -------------------------------------
def qmul(a, b):
    return [a[0] * b[0] - a[1] * b[1] - a[2] * b[2] - a[3] * b[3], a[0] * b[1] + a[1] * b[0] + a[2] * b[3] - a[3] * b[2],
            a[0] * b[2] - a[1] * b[3] + a[2] * b[0] + a[3] * b[1], a[0] * b[3] + a[1] * b[2] - a[2] * b[1] + a[3] * b[0]]


def qrot(q, v):
    p = qmul(qmul(q, [0.0, *v]), [q[0], -q[1], -q[2], -q[3]])
    return p[1:]


def expected_world(q, pos, mesh_point_m, cg=CG):
    """world = pos + R(q) * Rz(pi) * (mesh_m - [cg,0,0]), the protocol's mesh_to_body, then the body-to-world pose."""
    b = [mesh_point_m[0] - cg, mesh_point_m[1], mesh_point_m[2]]
    rz = [-b[0], -b[1], b[2]]
    r = qrot(q, rz)
    return [pos[0] + r[0], pos[1] + r[1], pos[2] + r[2]]


def ry(a, v):
    """Rotation about +Y by a (right-handed): x' = x cos a + z sin a, z' = -x sin a + z cos a."""
    return [v[0] * math.cos(a) + v[2] * math.sin(a), v[1], -v[0] * math.sin(a) + v[2] * math.cos(a)]


def to_body(fish_pt, cg=CG):
    """Rz(pi) * (fish_m - [cg,0,0])"""
    return [-(fish_pt[0] - cg), -fish_pt[1], fish_pt[2]]


def expected_fin_world(q, pos, fish_pt, hinge_fish_origin, angle, cg=CG):
    """A fin vertex: body-frame point rotated about +Y through the fin's body-frame hinge by `angle`, then the fish pose."""
    h = to_body(hinge_fish_origin, cg)
    b = to_body(fish_pt, cg)
    r = ry(angle, [b[0] - h[0], b[1] - h[1], b[2] - h[2]])
    r = [r[0] + h[0], r[1] + h[1], r[2] + h[2]]
    w = qrot(q, r)
    return [pos[0] + w[0], pos[1] + w[1], pos[2] + w[2]]


def stl_vertices(name):
    """Unique vertices of a binary component STL (the file native's solver consumed), in metres as stored."""
    b = (STL_DIR / f"{name}.stl").read_bytes()
    n = struct.unpack_from("<I", b, 80)[0]
    seen = set()
    for i in range(n):
        for v in range(3):
            seen.add(struct.unpack_from("<3f", b, 84 + 50 * i + 12 + 12 * v))
    return [list(t) for t in seen]


def glb_vertices(node_name):
    """Vertices of one GLB node as FISH-frame metres (x snout->tail, y left, z dorsal), read from the file:
    glTF (x,y,z) = fish (x,z,-y)  =>  fish = (gx, -gz, gy)."""
    b = GLB.read_bytes()
    n = struct.unpack("<I", b[12:16])[0]
    g = json.loads(b[20:20 + n])
    binoff = 20 + n + 8
    node = next(x for x in g["nodes"] if x["name"] == node_name)
    acc = g["accessors"][g["meshes"][node["mesh"]]["primitives"][0]["attributes"]["POSITION"]]
    bv = g["bufferViews"][acc["bufferView"]]
    off = binoff + bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    out = []
    for i in range(acc["count"]):
        x, y, z = struct.unpack_from("<3f", b, off + 12 * i)
        out.append([x, -z, y])
    return out


# ---- synthetic fixtures ---------------------------------------------------------------------------------------
FIN_NAMES = ["pectoral_L", "pectoral_R", "pelvic_L", "pelvic_R"]
TERM_AT = 60          # fish-02 terminates here for a water-interface style reason (forces stay valid)
DOMAIN_EXIT_AT = 70   # fish-00 leaves the model's domain in the "domain-exit" variant (forces null)
SUMMARY = {"termination_reason": "water interface reached; no water physics modeled", "completed_duration": False}


def make_traj(case="synthetic-test-fixture", n_fish=3, frames=121, dt=0.01, extra=None, domain_exit=False):
    fr = []
    for i in range(frames):
        t = round(i * dt, 10)
        fish = []
        for k in range(n_fish):
            stop = TERM_AT if k == 2 else (DOMAIN_EXIT_AT if (domain_exit and k == 0) else None)
            gone = stop is not None and i >= stop
            j = min(i, stop) if stop is not None else i
            tj = j * dt
            yaw = 0.3 * tj * (k + 1)
            pitch = 0.2 * tj if k == 1 else 0.0
            qy = [math.cos(yaw / 2), 0.0, 0.0, math.sin(yaw / 2)]
            qp = [math.cos(pitch / 2), 0.0, math.sin(pitch / 2), 0.0]
            q = qmul(qy, qp)
            nq = math.sqrt(sum(c * c for c in q))
            q = [c / nq for c in q]
            pos = [20.0 * tj, 0.3 * (k - 1), 4.0 - 0.5 * G * tj * tj + 0.01 * k]
            vel = [20.0, 0.0, -G * tj]
            out_of_domain = domain_exit and k == 0 and gone
            reason = None
            if gone:
                reason = "effective alpha beyond the 8 degree domain (domain exit)" if out_of_domain else "synthetic-test-termination"
            fish.append({
                "id": f"fish-{k:02d}", "position_m": pos, "orientation_wxyz": q, "linear_velocity_m_s": vel,
                "angular_velocity_body_rad_s": [0.0, 0.2 if k == 1 else 0.0, 0.3 * (k + 1)],
                "fin_angle_rad": {n: 0.05 * math.sin(3 * tj + m) for m, n in enumerate(FIN_NAMES)},
                "fin_command_rad": [-0.0698] * 4, "fin_actuator_torque_Nm": [0.0] * 4, "fin_effective_alpha_rad": [0.06 + 0.001 * m for m in range(4)],
                "force_model_valid": not out_of_domain,
                "fluid_force_world_N": None if out_of_domain else [-0.09, 0.0, 0.31],
                "force_world_N": None if out_of_domain else [-0.09, 0.0, -0.05 * G],
                "torque_world_Nm": None if out_of_domain else [0.0, 0.001 * k, 0.0],
                "actuator_positive_power_W": 0.001 * i, "positive_actuator_work_J": 1e-5 * i * i, "signed_actuator_work_J": -1e-6 * i,
                "mechanical_energy_J": 0.05 * (0.5 * 400 + G * pos[2]),
                "escape_triggered": bool(k == 1 and i >= 30), "escape_scheduled_time_s": 0.3 if k == 1 else None,
                "active": not gone, "termination_reason": reason})
        fr.append({"time_s": t, "fish": fish})
    traj = {"schema": "frontier.ecology.trajectory/1", "case": {"id": case, "n": n_fish, "feedback": True, "neighbors": False}, "dt_s": 0.0005, "seed": 20261031,
            "world_axes": "right-handed +X initial flight,+Y left,+Z up", "body_axes": "+X nose,+Y left,+Z dorsal", "orientation_order": "wxyz;body-to-world",
            "angular_velocity_frame": "body",
            "geometry": {"path": "artifacts/fish3d/fish3d-v3a-fan", "cg_from_nose_m": CG},
            "assumptions": "SYNTHETIC TEST FIXTURE: viewer mechanics only", "frames": fr, "summary": dict(SUMMARY)}
    traj.update(extra or {})
    return traj


def _eco_run():
    """native's canonical checked run (run-refined): ECO_RUN, or artifacts/ecology/run-refined once it is merged here."""
    for c in (os.environ.get("ECO_RUN"), str(ROOT / "artifacts/ecology/run-refined")):
        if c and (Path(c) / "glide-passive/trajectory.json").exists() and (Path(c) / "summary.json").exists():
            return Path(c).resolve()
    return None


@pytest.fixture(scope="module")
def tdir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture(scope="module")
def server(tdir):
    d = tdir / "root"
    d.mkdir()
    (d / "site").symlink_to(ROOT / "site")
    (d / "artifacts").symlink_to(ROOT / "artifacts")
    (d / "index.html").symlink_to(ROOT / "tests/fixtures/ecology_viewer/index.html")
    (d / "traj").mkdir()
    eco = _eco_run()
    if eco:
        (d / "eco").symlink_to(eco)

    class H(SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), partial(H, directory=str(d)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", d / "traj"
    srv.shutdown()


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch(args=ARGS)
        except Exception as e:
            pytest.skip(f"chromium unavailable: {e}")
        yield b
        b.close()


@pytest.fixture
def page(browser):
    ctx = browser.new_context(viewport={"width": 1400, "height": 1000})
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    yield pg
    ctx.close()


def put(server, name, obj):
    (server[1] / name).write_text(json.dumps(obj))
    return f"/traj/{name}"


def open_cases(page, server, cases):
    page.goto(f"{server[0]}/?cases={quote(json.dumps(cases))}")
    return page.evaluate("window.__v.ready.then(() => window.__v.state())")


def readout(page):
    return {tr.locator("th").inner_text(): tr.locator("td").inner_text() for tr in page.locator(".ev-readout tr").all()}


def nums(s):
    return [float(x) for x in s.replace("[", " ").replace("]", " ").replace(",", " ").split() if x[0] in "-0123456789"][:4]


@pytest.fixture
def good(server):
    return put(server, "good.json", make_traj())


# ---- tests ----------------------------------------------------------------------------------------------------
def test_loads_saved_states_with_counts_from_the_file_and_fixed_labels(page, server, good):
    st = open_cases(page, server, [{"id": "a", "label": "A", "url": good}])
    assert st["mode"] == "ready" and st["frames"] == 121 and st["fish"] == ["fish-00", "fish-01", "fish-02"], st
    assert "from the file: 121 saved states, 3 fish, 1.200 s" in page.locator(".ev-receipt").inner_text()
    assert page.locator(".ev-badge", has_text="ACTUAL SAVED STATES").count() == 1
    assert "not CFD" in page.locator(".ev-disclosure").inner_text() and "not a validated flying fish" in page.locator(".ev-disclosure").inner_text()
    assert "Showing saved states only" in page.locator(".ev-mode").inner_text()
    assert st["omitted"] == ["scales"] and "scales" not in str(st["meshComponents"])
    assert page.errors == []


@pytest.mark.parametrize("frame,fish", [(0, "fish-00"), (50, "fish-01"), (100, "fish-01"), (30, "fish-00")])
def test_rendered_mesh_matches_the_protocol_transform(page, server, good, frame, fish):
    """Vertices of the actual scene graph vs an independent calculation from the GLB bytes and the saved state."""
    open_cases(page, server, [{"id": "a", "label": "A", "url": good}])
    traj = make_traj()
    page.evaluate("i => window.__v.seekIndex(i)", frame)
    fa = next(f for f in traj["frames"][frame]["fish"] if f["id"] == fish)
    verts = glb_vertices("body")
    for vi in (0, 1, 777, len(verts) // 2, len(verts) - 1):
        got = page.evaluate("([id, vi]) => window.__v.sceneVertexWorld(id, 'body', vi)", [fish, vi])
        want = expected_world(fa["orientation_wxyz"], fa["position_m"], verts[vi])
        assert got == pytest.approx(want, abs=2e-5), (frame, fish, vi, got, want)       # float32 vertex storage


def test_identity_orientation_puts_the_nose_at_position_plus_cg(page, server, good):
    open_cases(page, server, [{"id": "a", "label": "A", "url": good}])
    p0 = make_traj()["frames"][0]["fish"][0]["position_m"]
    nose = page.evaluate("window.__v.fishPointWorld('fish-00', [0, 0, 0], 0, false)")
    assert nose == pytest.approx([p0[0] + CG, p0[1], p0[2]], abs=1e-9)     # q = identity at t = 0 for f0: body +X is nose
    verts = glb_vertices("body")
    snout = min(range(len(verts)), key=lambda i: verts[i][0])
    got = page.evaluate("([id, vi]) => window.__v.sceneVertexWorld(id, 'body', vi)", ["fish-00", snout])
    assert verts[snout][0] == pytest.approx(0.0, abs=1e-4)                  # the mesh's snout is its x = 0 end
    assert got == pytest.approx([p0[0] + CG, p0[1] + verts[snout][1] * -1, p0[2] + verts[snout][2]], abs=2e-4)


def test_scrub_shows_exactly_the_saved_state(page, server, good):
    open_cases(page, server, [{"id": "a", "label": "A", "url": good}])
    traj = make_traj()
    page.locator('[data-fish="fish-01"] button').click()
    page.evaluate("window.__v.seekIndex(50)")
    ro = readout(page)
    a = traj["frames"][50]["fish"][1]
    assert nums(ro["position_m"]) == pytest.approx(a["position_m"], abs=1e-3)
    assert nums(ro["orientation_wxyz"]) == pytest.approx(a["orientation_wxyz"], abs=1e-3)
    assert nums(ro["linear_velocity_m_s"])[:3] == pytest.approx(a["linear_velocity_m_s"], abs=1e-3)
    assert nums(ro["angular_velocity_body_rad_s"])[:3] == pytest.approx(a["angular_velocity_body_rad_s"], abs=1e-3)
    assert float(ro["fin_angle_rad[pectoral_R]"]) == pytest.approx(a["fin_angle_rad"]["pectoral_R"], abs=1e-4)
    assert ro["force_model_valid"] == "true"
    assert ro["escape_triggered"] == "true" and ro["active"] == "true" and ro["termination_reason"] == "null"
    assert "saved state 51" in page.locator(".ev-clock").inner_text() and "t = 0.500 s" in page.locator(".ev-clock").inner_text()
    page.locator(".ev-side input[type=range]").fill("10")
    assert "saved state 11" in page.locator(".ev-clock").inner_text()
    assert nums(readout(page)["position_m"]) == pytest.approx(traj["frames"][10]["fish"][1]["position_m"], abs=1e-3)


def test_play_pause_advances_and_stops(page, server, good):
    open_cases(page, server, [{"id": "a", "label": "A", "url": good}])
    page.evaluate("window.__v.seekIndex(0)")
    page.get_by_role("button", name="Play").click()
    page.wait_for_function("window.__v.state().frame > 3", timeout=8000)
    page.get_by_role("button", name="Pause").click()
    f1 = page.evaluate("window.__v.state().frame")
    page.wait_for_timeout(300)
    assert page.evaluate("window.__v.state().frame") == f1 and f1 > 3
    assert page.locator("button", has_text="Play").get_attribute("aria-pressed") == "false"


def test_interpolation_is_labelled_and_numbers_stay_saved_states(page, server, good):
    open_cases(page, server, [{"id": "a", "label": "A", "url": good}])
    traj = make_traj()
    page.locator('[data-fish="fish-01"] button').click()
    page.evaluate("window.__v.setInterpolate(true)")
    page.evaluate("window.__v.seek(0.005)")
    assert "Interpolated render between saved states, not a saved state" in page.locator(".ev-mode").inner_text()
    a, b = traj["frames"][0]["fish"][1], traj["frames"][1]["fish"][1]
    mid = [(x + y) / 2 for x, y in zip(a["position_m"], b["position_m"])]
    p = page.evaluate("window.__v.fishPointWorld('fish-01', [CG, 0, 0], 0.005, true)".replace("CG", repr(CG)))
    # the mesh point at the body origin (mesh x = cg) is the position itself
    assert p == pytest.approx(mid, abs=1e-9)
    assert nums(readout(page)["position_m"]) == pytest.approx(a["position_m"], abs=1e-3)       # numbers: nearest SAVED state
    page.evaluate("window.__v.setInterpolate(false)")
    assert "Showing saved states only" in page.locator(".ev-mode").inner_text()
    off = page.evaluate("window.__v.fishPointWorld('fish-01', [%r, 0, 0], 0.005, false)" % CG)
    assert off == pytest.approx(a["position_m"], abs=1e-9)             # no interpolation: last saved state


def test_terminated_fish_keeps_its_last_actual_state_and_says_why(page, server, good):
    open_cases(page, server, [{"id": "a", "label": "A", "url": good}])
    traj = make_traj()
    page.locator('[data-fish="fish-02"] button').click()
    page.evaluate("window.__v.seekIndex(100)")
    assert "Terminated: synthetic-test-termination" in page.locator(".ev-readout").inner_text()
    assert "terminated: synthetic-test-termination" in page.locator('[data-fish="fish-02"]').inner_text()
    held = traj["frames"][TERM_AT]["fish"][2]["position_m"]
    assert nums(readout(page)["position_m"]) == pytest.approx(held, abs=1e-3)
    page.evaluate("window.__v.setInterpolate(true)")
    for t in (0.595, 0.9):          # across and beyond the termination: no extrapolation or tween toward a state
        p = page.evaluate("t => window.__v.fishPointWorld('fish-02', [%r, 0, 0], t, true)" % CG, t)
        want = traj["frames"][59 if t < 0.6 else TERM_AT]["fish"][2]["position_m"]
        assert p == pytest.approx(want, abs=1e-9), (t, p, want)
    assert page.locator('[data-fish="fish-01"]').inner_text().count("escape triggered") == 1


def test_selecting_a_fish_by_click_and_by_list(page, server, good):
    open_cases(page, server, [{"id": "a", "label": "A", "url": good}])
    x, y = page.evaluate("window.__v.screenOf('fish-01')")
    page.mouse.click(x, y)
    assert page.evaluate("window.__v.state().selected") == "fish-01"
    assert page.locator('[data-fish="fish-01"]').get_attribute("aria-current") == "true"
    page.locator('[data-fish="fish-00"] button').click()
    assert page.evaluate("window.__v.state().selected") == "fish-00"
    page.mouse.click(5, 5)           # empty page area, outside the canvas: nothing changes
    assert page.evaluate("window.__v.state().selected") == "fish-00"
    box = page.locator(".ev-stage canvas").bounding_box()
    page.mouse.click(box["x"] + 4, box["y"] + 4)         # empty corner of the canvas deselects
    assert page.evaluate("window.__v.state().selected") is None


@pytest.mark.parametrize("name,mutate,needle", [
    ("schema", lambda t: t.update(schema="frontier.ecology.trajectory/2"), "expected frontier.ecology.trajectory/1"),
    ("units", lambda t: t.update(units="CGS"), 'expected "SI"'),
    ("cg", lambda t: t["geometry"].pop("cg_from_nose_m"), "cg_from_nose_m"),
    ("time", lambda t: t["frames"][5].update(time_s=t["frames"][4]["time_s"]), "is not after"),
    ("ids", lambda t: t["frames"][7]["fish"][1].update(id="zz"), "fish ids differ from frame 0"),
    ("quat", lambda t: t["frames"][3]["fish"][0].update(orientation_wxyz=[2, 0, 0, 0]), "not a unit quaternion"),
    ("nan", lambda t: t["frames"][3]["fish"][0].update(position_m=[None, 0, 0]), "position_m"),
    ("fins-missing-key", lambda t: t["frames"][2]["fish"][0]["fin_angle_rad"].pop("pelvic_R"), "fin_angle_rad keys/values differ"),
    ("fins-as-array", lambda t: t["frames"][0]["fish"][0].update(fin_angle_rad=[0.0, 0.0, 0.0, 0.0]), "fin_angle_rad must be an object keyed by component id"),
    ("noreason", lambda t: t["frames"][70]["fish"][2].update(termination_reason=None), "inactive without a termination_reason"),
    ("no-validity-flag", lambda t: t["frames"][4]["fish"][1].pop("force_model_valid"), "force_model_valid missing"),
    ("null-force-while-valid", lambda t: t["frames"][9]["fish"][1].update(force_world_N=None), "force_world_N is null but force_model_valid is not false"),
    ("zeroed-nonvec-force", lambda t: t["frames"][9]["fish"][1].update(torque_world_Nm=[0, 0]), "torque_world_Nm"),
    ("legacy-angvel-name", lambda t: [f.update(angular_velocity_rad_s=f.pop("angular_velocity_body_rad_s")) for fr in t["frames"] for f in fr["fish"]], "angular_velocity_body_rad_s"),
])
def test_invalid_trajectory_is_refused_with_the_field_named_and_nothing_is_drawn(page, server, name, mutate, needle):
    t = make_traj(frames=80)
    mutate(t)
    url = put(server, f"bad-{name}.json", t)
    st = open_cases(page, server, [{"id": "a", "label": "A", "url": url}])
    assert st["mode"] == "unavailable", st
    txt = page.locator(".ev-note").inner_text()
    assert txt.startswith("Trajectory not available") and needle in txt, txt
    assert page.locator(".ev-fish li").count() == 0 and page.locator(".ev-readout").inner_text() == ""
    assert page.locator("button", has_text="Play").is_disabled() and page.locator(".ev-side input[type=range]").is_disabled()
    assert st["frames"] == 0 and st["dynObjects"] == 0


def test_missing_file_is_unavailable_not_a_placeholder(page, server):
    st = open_cases(page, server, [{"id": "a", "label": "A", "url": "/traj/no-such-case.json"}])
    assert st["mode"] == "unavailable" and "HTTP 404" in st["reason"] and st["dynObjects"] == 0
    assert "Trajectory not available" in page.locator(".ev-note").inner_text()


def test_case_switch_replaces_the_scene_without_leaking(page, server, good):
    two = put(server, "two.json", make_traj(case="two", n_fish=2, frames=50))
    open_cases(page, server, [{"id": "a", "label": "A", "url": good}, {"id": "b", "label": "B", "url": two}])
    n3 = page.evaluate("window.__v.state().dynObjects")
    page.locator('.ev-cases button[data-case="b"]').click()
    page.wait_for_function("window.__v.state().caseId === 'b' && window.__v.state().fish.length === 2")
    st = page.evaluate("window.__v.state()")
    assert st["frames"] == 50 and st["dynObjects"] < n3 and page.locator(".ev-fish li").count() == 2
    assert "from the file: 50 saved states, 2 fish" in page.locator(".ev-receipt").inner_text()
    page.locator('.ev-cases button[data-case="a"]').click()
    page.wait_for_function("window.__v.state().caseId === 'a' && window.__v.state().fish.length === 3")
    assert page.evaluate("window.__v.state().dynObjects") == n3
    assert page.errors == []


def test_sources_and_equations_render_as_safe_links(page, server):
    extra = {"equations": [{"id": "rigid-body", "equation": "M(q)*vdot+c(q,v)=tau+J^T*f", "source": "MuJoCo https://mujoco.readthedocs.io/en/stable/computation/index.html#general-framework"},
                           {"id": "evil", "equation": "x", "source": "javascript:alert(1)"}],
             "sources": [{"url": "https://mujoco.readthedocs.io/en/stable/computation/fluid.html", "scope": "fluid model"},
                         {"url": "javascript:alert(2)", "scope": "bad"}],
             "provenance": {"solver": "MuJoCo 3.17.0", "protocol_sha256": "abc"},
             "threat": {"center_world_m": [4, -0.2, 3.95], "radius_m": 0.32, "window_s": [0.2, 0.22]}, "neighbor_radius_m": 0.47,
             "summary": {"min_height_m": 3.1}}
    url = put(server, "links.json", make_traj(extra=extra, frames=40))
    open_cases(page, server, [{"id": "a", "label": "A", "url": url}])
    hrefs = [a.get_attribute("href") for a in page.locator(".ev-links a").all()]
    assert hrefs == ["https://mujoco.readthedocs.io/en/stable/computation/index.html#general-framework",
                     "https://mujoco.readthedocs.io/en/stable/computation/fluid.html"], hrefs
    assert page.locator(".ev-links a").first.get_attribute("rel") == "noopener noreferrer"
    assert "javascript:alert(1)" in page.locator(".ev-links").inner_text()           # shown as text, not a link
    rc = page.locator(".ev-receipt").inner_text()
    assert "solver: MuJoCo 3.17.0" in rc and "min_height_m: 3.1" in rc and "sha256 " in rc
    assert page.evaluate("window.__v.state().dynObjects") > 3 * 2 + 3            # threat sphere and neighbour ring were built


def test_keyboard_controls_step_and_restart(page, server, good):
    open_cases(page, server, [{"id": "a", "label": "A", "url": good}])
    page.locator(".ev-stage canvas").focus()
    for _ in range(3):
        page.keyboard.press("ArrowRight")
    assert page.evaluate("window.__v.state().frame") == 3
    page.keyboard.press("ArrowLeft")
    assert page.evaluate("window.__v.state().frame") == 2
    page.keyboard.press("0")
    assert page.evaluate("window.__v.state().frame") == 0
    page.keyboard.press(" ")
    assert page.evaluate("window.__v.state().playing") is True
    page.keyboard.press(" ")
    assert page.evaluate("window.__v.state().playing") is False


def test_chart_marks_escape_and_termination_from_the_data(page, server, good):
    open_cases(page, server, [{"id": "a", "label": "A", "url": good}])
    page.locator('[data-fish="fish-02"] button').click()
    page.locator(".ev-side select").last.select_option("height")
    ch = page.evaluate("window.__v.state().chart")
    assert ch == {"metric": "height", "fish": "fish-02", "escape_index": -1, "terminated_index": TERM_AT, "force_invalid_index": -1, "points": 121, "plotted": 121}, ch
    assert "height z (m) for fish-02 over time, from 121 saved states" in page.locator(".ev-chart").get_attribute("aria-label")
    page.locator('[data-fish="fish-01"] button').click()
    ch = page.evaluate("window.__v.state().chart")
    assert ch["escape_index"] == 30 and ch["terminated_index"] == -1
    page.locator(".ev-side select").last.select_option("fin:pectoral_R")
    assert "fin angle pectoral_R (rad)" in page.locator(".ev-chart").get_attribute("aria-label")


# ---- native-contract specifics ---------------------------------------------------------------------------------
# hinge points as they appear in native's run-v2/glide-passive/model.xml (body pos of each fin body) at cg 0.0635260971682413
MODEL_XML_HINGES = {"pectoral_L": [0.022909891950093547, -0.010735917334193901, 0.006174301010223053],
                    "pectoral_R": [0.022909891950093547, 0.010735917334193901, 0.006174301010223053],
                    "pelvic_L": [-0.022957003715466412, -0.009726300378000693, -0.0045324333089832155],
                    "pelvic_R": [-0.022957003715466412, 0.009726300378000693, -0.0045324333089832155]}


def test_fin_hinges_are_where_the_solvers_model_puts_them(page, server, good):
    open_cases(page, server, [{"id": "a", "label": "A", "url": good}])
    got = page.evaluate("window.__v.hingeBody()")
    assert sorted(got) == sorted(MODEL_XML_HINGES)
    for k, want in MODEL_XML_HINGES.items():
        assert got[k] == pytest.approx(want, abs=1e-12), k          # Rz(pi)*(panels origin - [cg,0,0]) == model.xml's body pos
    fins = json.loads(PANELS.read_text())["fins"]
    for k in got:
        assert got[k] == pytest.approx(to_body(fins[k]["fin_plane"]["origin_m"]), abs=1e-12)


@pytest.mark.parametrize("frame,fish,comp", [(0, "fish-00", "pectoral_L"), (40, "fish-01", "pectoral_R"), (90, "fish-00", "pelvic_L"), (25, "fish-01", "pelvic_R")])
def test_fin_vertices_rotate_about_body_y_through_the_hinge(page, server, good, frame, fish, comp):
    open_cases(page, server, [{"id": "a", "label": "A", "url": good}])
    fa = next(f for f in make_traj()["frames"][frame]["fish"] if f["id"] == fish)
    page.evaluate("i => window.__v.seekIndex(i)", frame)
    origin = json.loads(PANELS.read_text())["fins"][comp]["fin_plane"]["origin_m"]
    angle = fa["fin_angle_rad"][comp]
    assert abs(angle) > 1e-3 or frame == 0
    verts = glb_vertices(comp)
    for vi in (0, 3, len(verts) // 2, len(verts) - 1):
        got = page.evaluate("([id, c, vi]) => window.__v.sceneVertexWorld(id, c, vi)", [fish, comp, vi])
        want = expected_fin_world(fa["orientation_wxyz"], fa["position_m"], verts[vi], origin, angle)
        assert got == pytest.approx(want, abs=2e-5), (comp, vi, got, want)
    # and the angle really moves the mesh: the same vertex at zero angle is elsewhere (so a no-op rotation would fail above)
    rest = expected_fin_world(fa["orientation_wxyz"], fa["position_m"], verts[3], origin, 0.0)
    moved = expected_fin_world(fa["orientation_wxyz"], fa["position_m"], verts[3], origin, angle)
    assert frame == 0 or math.dist(rest, moved) > 1e-5


@pytest.mark.parametrize("comp", ["body", "pectoral_L", "pelvic_R"])
def test_glb_mesh_is_the_same_metre_geometry_native_used(comp):
    """The viewer draws the GLB; native's solver consumed the component STLs. Same vertices, in METRES (no *0.001)."""
    g, s = glb_vertices(comp), stl_vertices(comp)
    lo = lambda vs: [min(v[i] for v in vs) for i in range(3)]
    hi = lambda vs: [max(v[i] for v in vs) for i in range(3)]
    assert lo(g) == pytest.approx(lo(s), abs=1e-5) and hi(g) == pytest.approx(hi(s), abs=1e-5), comp
    if comp == "body":
        assert hi(s)[0] == pytest.approx(0.158815, abs=1e-5) and lo(s)[0] == pytest.approx(0.0, abs=1e-4)       # native's confirmed bound, metres


def test_domain_exit_states_show_null_forces_as_failure_not_physics(page, server):
    url = put(server, "exit.json", make_traj(domain_exit=True, frames=100))
    st = open_cases(page, server, [{"id": "a", "label": "A", "url": url}])
    assert st["mode"] == "ready", st
    page.locator('[data-fish="fish-00"] button').click()
    page.evaluate("window.__v.seekIndex(80)")
    txt = page.locator(".ev-readout").inner_text()
    assert "Force model invalid at this state" in txt and "not zero" in txt and "nothing here is validated physics" in txt
    ro = readout(page)
    assert ro["force_world_N"] == "null" and ro["fluid_force_world_N"] == "null" and ro["torque_world_Nm"] == "null" and ro["force_model_valid"] == "false"
    assert "effective alpha beyond the 8 degree domain" in ro["termination_reason"]
    assert "Out-of-domain / numerical-failure state at this saved state: fish-00" in page.locator(".ev-status").inner_text()
    assert "force model invalid" in page.locator('[data-fish="fish-00"]').inner_text()
    page.evaluate("window.__v.seekIndex(10)")             # before the exit the same fish is valid and shows numbers
    assert readout(page)["force_model_valid"] == "true" and readout(page)["force_world_N"] != "null"
    assert "Out-of-domain" not in page.locator(".ev-status").inner_text()
    page.locator(".ev-side select").last.select_option("norm:force_world_N")
    ch = page.evaluate("window.__v.state().chart")
    assert ch["force_invalid_index"] == DOMAIN_EXIT_AT and ch["plotted"] == DOMAIN_EXIT_AT and ch["points"] == 100, ch      # null points are gaps, not zeros


def test_a_terminated_fish_with_valid_forces_is_not_called_a_failure(page, server, good):
    open_cases(page, server, [{"id": "a", "label": "A", "url": good}])
    page.locator('[data-fish="fish-02"] button').click()
    page.evaluate("window.__v.seekIndex(100)")
    ro = readout(page)
    assert ro["active"] == "false" and ro["force_model_valid"] == "true" and ro["force_world_N"] != "null"
    assert "Force model invalid" not in page.locator(".ev-readout").inner_text()
    assert "Out-of-domain" not in page.locator(".ev-status").inner_text()


def test_run_end_status_comes_from_the_files_summary(page, server, good):
    open_cases(page, server, [{"id": "a", "label": "A", "url": good}])
    s = page.locator(".ev-status").inner_text()
    assert "Run ended at t = 1.200 s: water interface reached; no water physics modeled (did not complete the planned duration)" in s
    assert "completed_duration: false" in page.locator(".ev-receipt").inner_text()
    assert page.locator(".ev-receipt .ev-false").count() == 1


def test_receipts_are_shown_and_every_false_flag_is_surfaced(page, server, good):
    (server[1] / "rcpt.json").write_text(json.dumps({"glide-feedback": {"discrepancy": {"passes_frozen_discrepancy_bounds": False, "max_position_difference_m": 0.445},
                                                                          "actuator_checks": {"torque": True}}, "other": {"x": 1}}))
    st = open_cases(page, server, [{"id": "a", "label": "A", "url": good, "receipts": [{"label": "dt-halving receipt", "url": "/traj/rcpt.json", "select": "glide-feedback"}]}])
    assert st["mode"] == "ready" and st["receiptFalse"] == 1
    assert "False receipt flag(s), verbatim from the files: dt-halving receipt: discrepancy.passes_frozen_discrepancy_bounds." in page.locator(".ev-status").inner_text()
    d = page.locator(".ev-rcpt")
    assert "dt-halving receipt — 1 false flag(s)" in d.locator("summary").inner_text() and d.get_attribute("open") is not None
    assert "discrepancy.passes_frozen_discrepancy_bounds: false" in d.inner_text() and "discrepancy.max_position_difference_m: 0.4450" in d.inner_text()
    assert "other" not in d.inner_text()
    assert page.locator(".ev-rcpt .ev-false").count() == 1
    bad = open_cases(page, server, [{"id": "a", "label": "A", "url": good, "receipts": [{"label": "x", "url": "/traj/no-receipt.json"}]}])
    assert bad["mode"] == "unavailable" and "/traj/no-receipt.json: HTTP 404" in bad["reason"]
    bad = open_cases(page, server, [{"id": "a", "label": "A", "url": good, "receipts": [{"label": "x", "url": "/traj/rcpt.json", "select": "nope"}]}])
    assert bad["mode"] == "unavailable" and "no entry nope" in bad["reason"]


def test_superseded_mm_transform_text_is_flagged_and_placement_stays_metres(page, server):
    t = make_traj(frames=20)
    t["geometry"]["mesh_mm_to_body_m"] = "Rz(pi)*(mesh_mm*0.001-[cg_from_nose_m,0,0])"
    url = put(server, "legacy-mm.json", t)
    st = open_cases(page, server, [{"id": "a", "label": "A", "url": url}])
    assert st["mode"] == "ready" and any("superseded millimetre transform" in n for n in st["notes"])
    assert "superseded millimetre transform" in page.locator(".ev-receipt").inner_text()
    verts = glb_vertices("body")
    fa = t["frames"][0]["fish"][0]
    got = page.evaluate("([id, vi]) => window.__v.sceneVertexWorld(id, 'body', vi)", ["fish-00", 5])
    assert got == pytest.approx(expected_world(fa["orientation_wxyz"], fa["position_m"], verts[5]), abs=2e-5)     # metres, not *0.001


def test_a_fin_component_missing_from_panels_or_mesh_is_refused_by_name(page, server):
    t = make_traj(frames=10)
    for fr in t["frames"]:
        for f in fr["fish"]:
            f["fin_angle_rad"]["anal"] = 0.0           # a component that exists in panels.json and in the GLB: allowed
    ok = open_cases(page, server, [{"id": "a", "label": "A", "url": put(server, "anal.json", t)}])
    assert ok["mode"] == "ready" and "anal" in ok["fins"]
    for fr in t["frames"]:
        for f in fr["fish"]:
            f["fin_angle_rad"]["fluke_7"] = 0.0
    st = open_cases(page, server, [{"id": "a", "label": "A", "url": put(server, "fluke.json", t)}])
    assert st["mode"] == "unavailable" and "fluke_7" in st["reason"]


REAL = ["glide-passive", "glide-feedback", "escape-neighbors", "escape-no-neighbors"]


@pytest.mark.skipif(_eco_run() is None, reason="needs native's run-refined (set ECO_RUN or merge artifacts/ecology/run-refined)")
def test_all_four_real_refined_cases_load_with_their_receipts_and_the_rendered_mesh_matches_the_saved_states(page, server):
    run = _eco_run()
    summary = json.loads((run / "summary.json").read_text())
    cases = [{"id": c, "label": c, "url": f"/eco/{c}/trajectory.json",
              "receipts": [{"label": "run summary", "url": "/eco/summary.json", "select": c}]} for c in REAL]
    bad = []
    page.on("response", lambda r: bad.append((r.status, r.url)) if r.status >= 400 else None)
    st = open_cases(page, server, cases)
    for c in REAL:
        if st["caseId"] != c:
            assert page.evaluate("id => window.__v.setCase(id)", c) is True
        st = page.evaluate("window.__v.state()")
        t = json.loads((run / c / "trajectory.json").read_text())
        fr = t["frames"]
        assert st["mode"] == "ready" and st["frames"] == len(fr) and len(st["fish"]) == len(fr[0]["fish"]), (c, st["mode"], st.get("reason"))
        assert st["fins"] == FIN_NAMES and st["omitted"] == ["scales"]
        flat = []

        def walk(o):
            if isinstance(o, dict):
                [walk(v) for v in o.values()]
            else:
                flat.append(o)
        walk(summary[c])
        assert st["receiptFalse"] == sum(1 for x in flat if x is False), c          # every false flag in the file is counted, none hidden
        # rendered mesh vs real saved states: a body vertex and a fin vertex at three real frames
        verts = glb_vertices("body")
        fverts = glb_vertices("pectoral_L")
        origin = json.loads(PANELS.read_text())["fins"]["pectoral_L"]["fin_plane"]["origin_m"]
        cg = t["geometry"]["cg_from_nose_m"]
        for i in (0, len(fr) // 2, len(fr) - 1):
            page.evaluate("i => window.__v.seekIndex(i)", i)
            a = fr[i]["fish"][0]
            gb = page.evaluate("([id, vi]) => window.__v.sceneVertexWorld(id, 'body', vi)", [a["id"], 11])
            assert gb == pytest.approx(expected_world(a["orientation_wxyz"], a["position_m"], verts[11], cg), abs=2e-5), (c, i)
            gf = page.evaluate("([id, vi]) => window.__v.sceneVertexWorld(id, 'pectoral_L', vi)", [a["id"], 7])
            assert gf == pytest.approx(expected_fin_world(a["orientation_wxyz"], a["position_m"], fverts[7], origin, a["fin_angle_rad"]["pectoral_L"], cg), abs=2e-5), (c, i)
    assert bad == [], bad
    # the school cases end with a terminal out-of-domain state whose forces are intentionally null
    page.evaluate("id => window.__v.setCase(id)", "escape-neighbors")
    page.locator('[data-fish="fish-00"] button').click()
    page.evaluate("window.__v.seekIndex(86)")
    ro = readout(page)
    assert ro["force_model_valid"] == "false" and ro["force_world_N"] == "null" and ro["torque_world_Nm"] == "null" and ro["fluid_torque_about_body_origin_world_Nm"] == "null"
    assert "Out-of-domain / numerical-failure state" in page.locator(".ev-status").inner_text()
    assert "completed_duration" in page.locator(".ev-status").inner_text()        # the false flags are named, not summarised as "failed"
    assert "center_of_mass_world_m" in ro and "fin_angular_velocity_rad_s" in ro        # refined fields shown verbatim
    page.evaluate("window.__v.seekIndex(40)")
    assert readout(page)["force_model_valid"] == "true" and readout(page)["force_world_N"] != "null"
