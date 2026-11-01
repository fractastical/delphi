"""Live check against a SCRATCH runtime: the design review panel reads a real Project, challenge and reply written through the Store, and the About routes draw."""
import sys
from playwright.sync_api import expect, sync_playwright

base, token, out = sys.argv[1:4]
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1280, "height": 900}); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    sj = pg.context.request.get(base + "/api/session").json()
    if not sj.get("public_access"):
        r = pg.context.request.post(base + "/api/session", data={"token": token}, headers={"Origin": base}); assert r.status == 200, r.status
    pg.goto(base + "/index.html#/studio/flying-fish"); pg.wait_for_selector("#drlive")
    expect(pg.locator("#drlive .drcard")).to_have_count(1, timeout=20000)
    t = pg.locator("#drlive").inner_text()
    print("DESIGN PANEL:", t[:240].replace("\n", " "))
    assert "1 challenge" in t and "E2E: a static measurement" in t and "1 reply" in t and "E2E reply: which fin?" in t and "none resolved" in t
    assert "Falsifiable next test" in t and "Cyclic loading vs static" in t
    print("PASS design context read from the real API: challenge + reply attached by exact pin, none resolved")
    for route, needle in (("#/about", None), ("#/about/team", None), ("#/about/docs", None), ("#/about/inspirations", None), ("#/generative", None)):
        pg.goto(base + "/index.html" + route); pg.wait_for_timeout(1200)
        body = pg.locator("#main").inner_text()
        assert "could not be drawn" not in body and "Not found" not in body and len(body) > 400, (route, body[:200])
        print("PASS route draws:", route, len(body))
    assert not errs, errs
    b.close()
