"""Bounded read-only local snapshot check; starts and closes its own loopback server."""

from pathlib import Path
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from threading import Thread
from hashlib import sha256
import json
from playwright.sync_api import sync_playwright

site = Path("/data/worktrees/delphi-frontier/codex-demo/site")
out = Path(__file__).resolve().parent


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Quiet, directory=str(site)))
thread = Thread(target=server.serve_forever, daemon=True)
thread.start()
receipts = []
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for width in [1440, 390]:
            page = browser.new_page(viewport={"width": width, "height": 1000})
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            for name in ["tissue-microcarrier", "epithelial-repair"]:
                page.goto(
                    f"http://127.0.0.1:{server.server_port}/#/studio/{name}",
                    wait_until="networkidle",
                )
                page.locator("h1").wait_for()
                page.locator("details").evaluate_all(
                    "(nodes) => nodes.forEach(x => x.open = true)"
                )
                text = page.locator("body").inner_text()
                videos = page.locator("video").evaluate_all(
                    '(nodes) => nodes.map(v => ({controls:v.controls,src:v.querySelector("source")?.getAttribute("src"),label:v.getAttribute("aria-label")}))'
                )
                overflow = page.evaluate(
                    "document.documentElement.scrollWidth > innerWidth + 1"
                )
                assert "[object Object]" not in text and "undefined" not in text
                assert (
                    not overflow
                    and not errors
                    and videos
                    and all(v["controls"] for v in videos)
                )
                assert "not" in text.lower() and (
                    "model" in text.lower() or "benchmark" in text.lower()
                )
                if name == "epithelial-repair":
                    assert (
                        "7 pass" in text
                        and "3 fail" in text
                        and "incomplete" in text
                        and "22.04%" in text
                    )
                    assert "observed threshold bracket (1, 2)" in text
                image = out / f"{name}-{width}.png"
                page.locator("details").evaluate_all(
                    "(nodes) => nodes.forEach(x => x.open = false)"
                )
                page.locator("video").first.scroll_into_view_if_needed()
                page.screenshot(path=str(image), full_page=False)
                receipts.append(
                    {
                        "study": name,
                        "width": width,
                        "page_errors": list(errors),
                        "overflow": overflow,
                        "videos": videos,
                        "screenshot": image.name,
                        "screenshot_sha256": sha256(image.read_bytes()).hexdigest(),
                        "text_sha256": sha256(text.encode()).hexdigest(),
                        "oxygen_family_visible": "A shared design constraint: oxygen transport"
                        in text,
                    }
                )
            page.close()
        browser.close()
finally:
    server.shutdown()
    server.server_close()
receipt = {
    "site_snapshot_sha256": sha256(
        (site / "data/snapshot.json").read_bytes()
    ).hexdigest(),
    "checks": receipts,
    "scope": "Read-only local snapshot; desktop/mobile rendering and controls, no video physics replay.",
}
(out / "browser-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
print(
    json.dumps(
        {
            "pages_checked": len(receipts),
            "all_pass": True,
            "oxygen_present": [x["oxygen_family_visible"] for x in receipts],
        }
    )
)
