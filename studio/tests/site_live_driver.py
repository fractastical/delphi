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
    pg.fill("#f-rho", "1.225"); pg.fill("#f-cl_max", "1"); pg.fill("#f-mass_min", "0.2"); pg.fill("#f-wing_loading_min", "100"); pg.fill("#f-speed_max", "20")
    pg.get_by_role("button", name="Request a solver run").click()
    pg.wait_for_selector("[data-out=solve] .verdictbox", timeout=60000)
    txt = pg.locator("[data-out=solve]").inner_text(); print("SOLVER:", txt[:400].replace("\n", " | "))
    assert "frontier.engineering.solve/1" in txt
    pg.screenshot(path=f"{out}/live-solver.png", full_page=True)
    # unknowns stay unknown: blank rho/CL must not be defaulted
    pg.fill("#f-rho", ""); pg.fill("#f-cl_max", "")
    pg.get_by_role("button", name="Request a solver run").click(); pg.wait_for_timeout(3000)
    print("UNKNOWN-RHO:", pg.locator("[data-out=solve]").inner_text()[:300].replace("\n", " | "))
    assert not errs, errs
    print("ALL LIVE CHECKS PASSED"); b.close()
