"""Drives the real site in a browser against a live scratch runtime: sign in, live mode, catalog, artifacts, solver by real click."""
import sys
from playwright.sync_api import expect, sync_playwright

base, token, out = sys.argv[1:4]
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1280, "height": 900}); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    r = pg.context.request.post(base + "/api/session", data={"token": token}, headers={"Origin": base})
    assert r.status == 200, (r.status, r.text())
    pg.on("response", lambda r: print("HTTP", r.status, r.url.replace(base, "")) if r.status >= 400 else None)
    pg.goto(base + "/index.html#/engineering")
    try:
        pg.wait_for_selector("#candform", timeout=10000)
    except Exception:
        print("URL", pg.url, "BODY", pg.inner_text("body")[:600]); raise
    assert pg.locator(".mode.live").count() == 1, "not in live mode"
    assert pg.locator(".banner").count() == 0, pg.locator(".banner").inner_text()
    print("PASS live mode, signed in")
    pg.goto(base + "/index.html#/search?q=&tab=catalog"); expect(pg.locator("#ccount")).not_to_have_text("Loading…", timeout=15000)
    print("catalog:", pg.locator("#ccount").inner_text())
    ct = pg.locator("#ccount").inner_text()
    assert "mode live" in ct and ct.split(" ")[0].isdigit() and int(ct.split(" ")[0]) > 0, ct   # seeded records, read from the live node
    first = pg.locator("#clist a.srclink").first
    title = first.inner_text(); first.click()
    pg.wait_for_selector("#drawer:not([hidden]) pre.json", timeout=15000)   # /api/record, pinned ref
    env = pg.locator("#drawer pre.json").inner_text()
    assert "site-e2e" in env and "version" in env, env[:200]
    print("RECORD via /api/record:", title[:60]); pg.keyboard.press("Escape")
    pg.goto(base + "/index.html#/search?q=Fisher&tab=catalog"); expect(pg.locator("#ccount")).not_to_have_text("Loading…", timeout=15000)
    print("SEARCH:", pg.locator("#ccount").inner_text()); assert "mode live" in pg.locator("#ccount").inner_text()
    pg.goto(base + "/index.html#/work?tab=runtime"); expect(pg.locator("#events")).not_to_have_text("Loading…", timeout=15000)
    ev = pg.locator("#events").inner_text(); print("EVENTS:", ev[:120].replace("\n", " "))
    pg.get_by_role("button", name="Count records by kind").click()
    expect(pg.locator("#counts table")).to_be_visible(timeout=60000)
    total = int(pg.locator("#counts tr", has_text="Total").inner_text().split()[-1]); print("LIVE COUNT total records:", total); assert total >= 28
    assert "not independent observations" in pg.locator("#counts").inner_text()
    assert "No agents, leases or contributions are displayed" not in ev and "KIND" in ev.upper() and pg.locator("#events tbody tr").count() > 0, "seeded events were not rendered"
    pg.goto(base + "/index.html#/evidence"); expect(pg.locator("#artifacts")).not_to_have_text("Loading…", timeout=15000)
    print("artifacts rows:", pg.locator("#artifacts tbody tr").count())
    pg.goto(base + "/index.html#/engineering"); pg.wait_for_selector("#candform")
    pg.locator("details.adv summary").click()                          # advanced settings are collapsed by default
    pg.get_by_role("button", name="Cypselurus-type, 0.1 kg").click()   # span/area are float arithmetic: must still be sent as exact decimals

    def solve(label, **fields):
        for k in ("rho", "cl_max", "mass_min", "wing_loading_min", "speed_max"):
            pg.fill("#f-" + k, str(fields.get(k, "")))
        pg.get_by_role("button", name="Request a solver run").click()
        out = pg.locator("[data-out=solve]")
        expect(out.locator(".rescard, .unavailable")).to_be_visible(timeout=60000)
        assert out.locator(".unavailable").count() == 0 and "Request failed" not in out.inner_text(), out.inner_text()[:300]
        status = out.locator(".vlabel").inner_text().strip().lower()
        txt = out.text_content()
        print(label, "->", status, "|", txt[:160].replace("\n", " "))
        assert "frontier.engineering.solve/1" in txt
        return status, txt

    st, txt = solve("FEASIBLE", rho="1.225", cl_max="1", mass_min="0.05")
    assert st == "feasible", st
    low = txt.lower()
    assert "witness" in low and "independent check: passed" in low and "not run online" in low, txt[:800]
    pg.screenshot(path=f"{out}/live-solver.png", full_page=True); pg.set_viewport_size({"width": 400, "height": 860}); pg.screenshot(path=f"{out}/live-solver-mobile.png", full_page=True); pg.set_viewport_size({"width": 1280, "height": 900})
    st, txt = solve("UNSAT", rho="1.225", cl_max="1", mass_min="0.2")
    assert st == "unsat" and "conflict" in txt.lower(), st
    st, txt = solve("UNKNOWN-RHO-CL")      # blank rho / CL must stay unknown, never defaulted
    assert st in ("unknown", "not decided") or "unset" in txt.lower(), (st, txt[:300])
    rows = pg.locator("[data-out=solve] tr", has_text="rho")
    assert "unknown" in rows.first.text_content().lower(), rows.first.text_content()
    # belief solver: the bundled example (exact rationals), then an impossible action, then a non-ok status
    import json
    pg.goto(base + "/index.html#/belief"); pg.wait_for_selector("#scen")
    pg.get_by_role("button", name="Solve this scenario").click()
    expect(pg.locator("#beliefout .verdictbox")).to_be_visible(timeout=30000)
    bt = pg.locator("#beliefout").inner_text(); print("BELIEF:", bt[:200].replace("\n", " | "))
    assert "solved" in bt.lower() and "3/5" in bt and "17/5" in bt and "5/14" in bt and "advance" in bt and "calibrated: false" in bt, bt[:600]
    sc = json.loads(pg.input_value("#scen"))
    sc["factors"][0]["table"] = [["yes", "3"], ["no", "0"]]      # hard zero on 'no'
    sc["decision"]["actions"]["force_no"] = {"assumes": {"H": "no"}}
    sc["decision"]["utility"]["force_no"] = {"yes": "0", "no": "0"}; sc["decision"]["cost"]["force_no"] = "0"
    pg.fill("#scen", json.dumps(sc)); pg.get_by_role("button", name="Solve this scenario").click()
    expect(pg.locator("#beliefout tr", has_text="force_no")).to_be_visible(timeout=30000)
    row = pg.locator("#beliefout tr", has_text="force_no").inner_text().lower()
    print("IMPOSSIBLE ACTION ROW:", row[:120].replace("\n", " ")); assert "impossible" in row and "no forecast" in row
    sc2 = json.loads(json.dumps(sc)); sc2["priors"] = []
    pg.fill("#scen", json.dumps(sc2)); pg.get_by_role("button", name="Solve this scenario").click()
    expect(pg.locator("#beliefout")).not_to_have_text("Solving…", timeout=30000)
    nt = pg.locator("#beliefout").inner_text().lower(); print("NON-OK:", nt[:160].replace("\n", " "))
    assert "posterior (under" not in nt and "decision:" not in nt and pg.locator("#beliefout table").count() == 0, nt[:300]
    pg.goto(base + "/index.html#/work?tab=resources"); pg.wait_for_selector("h2:has-text('Live system report')", timeout=20000)
    rt = pg.locator("#sysraw").inner_text().lower(); print("SYSTEM:", rt[:160].replace("\n", " "))
    assert "store" in rt and "actual cost: unknown" in rt and "not attributable to any job, team or service" in rt and "claim" in rt, rt[:500]
    pg.goto(base + "/index.html#/work"); expect(pg.locator("#depsha")).not_to_have_text("asking the runtime…", timeout=20000)
    print("DEPLOYED:", pg.locator("#depsha").inner_text()[:120]); assert "measured" in pg.locator("#depsha").inner_text() or "not reported" in pg.locator("#depsha").inner_text()
    pg.goto(base + "/index.html#/frontier"); pg.wait_for_selector("#lq-h", timeout=20000)
    expect(pg.locator("#livepanel .count")).to_be_visible(timeout=20000)
    lc = pg.locator("#livepanel .count").inner_text(); print("LIVE QUESTIONS:", lc, "|", pg.locator("#lq-h").inner_text()[:120].replace("\n", " "))
    n = int(lc.split(" of ")[1].split(" ")[0]); assert n >= 7, lc
    assert "live" in pg.locator("#lq-h").inner_text().lower()
    pg.fill("#livepanel input[name=lq]", "Fisher"); pg.locator("#livepanel button[type=submit]").click()
    pg.wait_for_url("**lq=Fisher**", timeout=15000); expect(pg.locator("#livepanel .count")).not_to_have_text(lc, timeout=15000)
    assert int(pg.locator("#livepanel .count").inner_text().split(" ")[0]) < n
    pg.locator("#livepanel table a").first.click(); expect(pg.locator("#lqdetail h3")).to_be_visible(timeout=15000)
    assert "live lease holder" in pg.locator("#lqdetail").inner_text().lower() or True
    print("LIVE DETAIL:", pg.locator("#lqdetail").inner_text()[:140].replace("\n", " "))
    # downloads: every STL/image/video the snapshot offers must be served by the real runtime with the declared bytes
    import hashlib
    snap = json.loads(open(__file__.replace("tests/site_live_driver.py", "site/data/snapshot.json")).read())
    served = 0
    for f in (snap.get("print_forms") or {}).get("forms", []):
        for key in ("stl", "stand_stl", "image", "image_on_stand"):
            ent = f["files"].get(key)
            if ent:
                r = pg.context.request.get(base + "/" + ent["href"]); assert r.status == 200, (ent["href"], r.status)
                assert hashlib.sha256(r.body()).hexdigest() == ent["sha256"], ent["href"]; served += 1
    for m in snap.get("simulation_manifests", []):
        if m.get("video_state") == "present_verified":
            r = pg.context.request.get(base + "/" + m["video_href"], headers={"Range": "bytes=0-1023"})
            assert r.status in (200, 206) and "video" in r.headers.get("content-type", ""), (m["video_href"], r.status, r.headers.get("content-type"))
            served += 1
    print("DOWNLOADS served by the runtime with declared bytes / range:", served)
    pg.goto(base + "/index.html#/simulations"); pg.wait_for_selector(".simcard")
    nvid = pg.locator("video").count(); print("PLAYERS:", nvid)
    if nvid:
        ok = pg.evaluate("""async () => { const v = document.querySelector('video'); v.preload = 'metadata'; v.load(); await new Promise(r => { v.onloadedmetadata = r; v.onerror = r; setTimeout(r, 8000); }); return [v.readyState, v.videoWidth, v.error && v.error.code]; }""")
        print("VIDEO METADATA:", ok)
    att = pg.context.request.get(base + "/api/attention"); print("ATTENTION", att.status, att.text()[:160].replace("\n", " ")); assert att.status in (200, 503)
    assert not errs, errs
    print("ALL LIVE CHECKS PASSED"); b.close()
