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
    assert "mode live" in pg.locator("#ccount").inner_text()
    pg.goto(base + "/index.html#/evidence"); expect(pg.locator("#artifacts")).not_to_have_text("Loading…", timeout=15000)
    print("artifacts rows:", pg.locator("#artifacts tbody tr").count())
    pg.goto(base + "/index.html#/engineering"); pg.wait_for_selector("#candform")
    pg.get_by_role("button", name="Cypselurus-type, 0.1 kg").click()   # span/area are float arithmetic: must still be sent as exact decimals

    def solve(label, **fields):
        for k in ("rho", "cl_max", "mass_min", "wing_loading_min", "speed_max"):
            pg.fill("#f-" + k, str(fields.get(k, "")))
        pg.get_by_role("button", name="Request a solver run").click()
        out = pg.locator("[data-out=solve]")
        expect(out.locator(".verdictbox, .unavailable")).to_be_visible(timeout=60000)
        assert out.locator(".unavailable").count() == 0 and "Request failed" not in out.inner_text(), out.inner_text()[:300]
        status = out.locator(".vlabel").inner_text().strip().lower()
        txt = out.inner_text()
        print(label, "->", status, "|", txt[:160].replace("\n", " "))
        assert "frontier.engineering.solve/1" in txt
        return status, txt

    st, txt = solve("FEASIBLE", rho="1.225", cl_max="1", mass_min="0.05")
    assert st == "feasible", st
    low = txt.lower()
    assert "witness" in low and "independent witness check: passed" in low and "not run online" in low, txt[:800]
    pg.screenshot(path=f"{out}/live-solver.png", full_page=True)
    st, txt = solve("UNSAT", rho="1.225", cl_max="1", mass_min="0.2")
    assert st == "unsat" and "conflict" in txt.lower(), st
    st, txt = solve("UNKNOWN-RHO-CL")      # blank rho / CL must stay unknown, never defaulted
    assert st in ("unknown", "not decided") or "unset" in txt.lower(), (st, txt[:300])
    rows = pg.locator("[data-out=solve] tr", has_text="rho")
    assert "unknown" in rows.first.inner_text().lower(), rows.first.inner_text()
    assert not errs, errs
    print("ALL LIVE CHECKS PASSED"); b.close()
