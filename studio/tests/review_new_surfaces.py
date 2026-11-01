"""Focused browser review of the genotype panel (#/assemblies) and the fidelity card (#/simulations?q=fidelity) on a built site directory.

Not part of the suite: run `SITE_DIR=<built site dir> SHOTS=<dir> python3 tests/review_new_surfaces.py`. It serves the directory on a private ephemeral port
WITH HTTP Range support (so video seeking behaves as on a real server), reads only, and prints one finding per line (OK / FINDING). Nothing is edited."""

import functools
import hashlib
import http.server
import json
import os
import re
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

SITE = Path(os.environ["SITE_DIR"])
SHOTS = Path(os.environ.get("SHOTS", "/tmp"))
FINDINGS = []


def say(ok, msg):
    print(("OK      " if ok else "FINDING ") + msg)
    if not ok:
        FINDINGS.append(msg)


class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send_head(self):  # a minimal single-range implementation, enough for <video> seeking
        rng = self.headers.get("Range")
        path = self.translate_path(self.path.split("?")[0])
        if not rng or not os.path.isfile(path):
            return super().send_head()
        m = re.match(r"bytes=(\d*)-(\d*)", rng)
        size = os.path.getsize(path)
        a = int(m.group(1) or 0)
        b = int(m.group(2)) if m.group(2) else size - 1
        b = min(b, size - 1)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {a}-{b}/{size}")
        self.send_header("Content-Length", str(b - a + 1))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        f = open(path, "rb")
        f.seek(a)
        self._left = b - a + 1
        return f

    def copyfile(self, source, outputfile):
        left = getattr(self, "_left", None)
        if left is None:
            return super().copyfile(source, outputfile)
        outputfile.write(source.read(left))
        self._left = None


def serve():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(H, directory=str(SITE)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}/"


def new_page(b, base, width, tag):
    pg = b.new_page(viewport={"width": width, "height": 900})
    pg.errors, pg.bad = [], []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.on("response", lambda r: pg.bad.append((r.status, r.url)) if r.status >= 400 and "/api/" not in r.url else None)
    return pg


def downloads(pg, base, scope, label, declared=None):
    """Every download/source link in `scope` resolves, with a MIME that is not an HTML error page; sha256 equals the declared one when known."""
    links = pg.locator(f"{scope} a[href]").evaluate_all("els => els.map(e => [e.getAttribute('href'), e.hasAttribute('download'), e.closest('details') ? true : false])")
    seen = set()
    for href, dl, _ in links:
        if not href or href.startswith(("#", "http", "mailto")) or href in seen or not href.startswith("artifacts/"):
            continue
        seen.add(href)
        r = pg.request.get(base + href)
        ct = r.headers.get("content-type", "")
        say(r.status == 200 and "text/html" not in ct, f"{label}: {href} -> {r.status} {ct}")
        if declared and href in declared:
            say(hashlib.sha256(r.body()).hexdigest() == declared[href], f"{label}: {href} sha256 equals the declared {declared[href][:12]}")
    return seen


def main():
    srv, base = serve()
    snap = json.loads((SITE / "data/snapshot.json").read_text())
    g = snap.get("genotype")
    say(bool(g), "snapshot carries the genotype block")
    card = next((m for m in snap["simulation_manifests"] if m["id"] == "aeroelastic-fidelity-v1"), None)
    say(bool(card), "snapshot carries the aeroelastic-fidelity-v1 card")
    with sync_playwright() as p:
        b = p.chromium.launch()
        for width, tag in ((1440, "desktop"), (390, "mobile")):
            # ---------------------------------------------------------------- genotype
            pg = new_page(b, base, width, tag)
            pg.goto(base + "#/assemblies")
            pg.wait_for_selector("#genotype", timeout=15000)
            pg.wait_for_timeout(500)
            t = pg.locator("#genotype").text_content()
            for must in ("proposals, not DNA", "0 endorsed", "does not create DNA", "36", "44", "none is calibrated"):
                say(must in t, f"[{tag}] genotype shows {must!r}")
            say("Withheld" not in t.split("Source files")[0][:1500] or g["status"] != "current", f"[{tag}] genotype status {g['status']} and no stray Withheld notice")
            for i in range(pg.locator(".gif").count()):  # open each interface and make sure the slice is there
                pg.locator(".gif summary").nth(i).click()
            say(pg.locator(".gif[open]").count() == 5 and "validation slice" in pg.locator("#genotype").inner_text().lower(), f"[{tag}] five interface expanders open with validation slices")
            for d in pg.locator("#genotype details").all():
                d.evaluate("e => e.open = true")
            say(pg.locator("#genotype tbody tr").count() >= 36 + 44 + 8, f"[{tag}] sequence, entry and instrument tables hold their rows ({pg.locator('#genotype tbody tr').count()})")
            declared = {f["path"]: f["sha256"] for f in g["files"]}
            say(len(downloads(pg, base, "#genotype", f"[{tag}] genotype download", declared)) >= len(declared), f"[{tag}] every published genotype file is linked")
            say("[object Object]" not in t and "undefined" not in t and "NaN" not in t, f"[{tag}] no [object Object]/undefined/NaN in the panel")
            say(pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth") <= 0, f"[{tag}] genotype: no horizontal page overflow")
            say(pg.errors == [] and not pg.bad, f"[{tag}] genotype: no page errors / failed requests {pg.errors[:2]} {pg.bad[:3]}")
            pg.locator("#genotype").screenshot(path=str(SHOTS / f"genotype-{tag}.png"))
            pg.close()
            # ---------------------------------------------------------------- fidelity
            pg = new_page(b, base, width, tag)
            pg.goto(base + "#/simulations?q=fidelity")
            pg.wait_for_selector(".simgrid", timeout=15000)
            pg.wait_for_timeout(500)
            say(pg.locator(".simgrid > *").count() == 1, f"[{tag}] fidelity filter leaves exactly one card ({pg.locator('.simgrid > *').count()})")
            for d in pg.locator(".simgrid details").all():
                d.evaluate("e => e.open = true")
            t = pg.locator(".simgrid").text_content()
            for must in ("45 native arms", "27 sign_resolved, 0 resolved", "undetermined in all 3 contexts", "no context is promoted", "historical proposal", "diagnosing the scheme", "posthoc", "Navier-Stokes", "no biological claim"):
                say(must in t, f"[{tag}] fidelity card says {must!r}")
            say("the remedy is a finer" not in t and not re.search(r"biological(ly)? (fidelity|valid)", t.replace("no biological", "")), f"[{tag}] no finer-ladder recommendation and no biological-fidelity claim")
            say(not re.search(r"\$[^$]{1,40}\$|\\\\(frac|Delta|alpha)", t), f"[{tag}] no raw TeX in the card text")
            say("[object Object]" not in t and "undefined" not in t and "NaN" not in t, f"[{tag}] no [object Object]/undefined/NaN in the card")
            declared = {}
            for f in (card.get("figures") or []) + (card.get("reports") or []):
                declared[f["href"]] = f["sha256"]
            declared[card["video_href"]] = card["video"]["sha256"]
            downloads(pg, base, ".simgrid", f"[{tag}] fidelity link", declared)
            for h in declared:  # every declared file really serves with its declared hash, linked or not
                r = pg.request.get(base + h)
                say(r.status == 200 and hashlib.sha256(r.body()).hexdigest() == declared[h], f"[{tag}] declared file {h.rsplit('/', 1)[1]} serves with its declared sha256")
            imgs = pg.locator(".simgrid img").evaluate_all("els => els.map(e => [e.currentSrc.split('/').pop(), e.complete && e.naturalWidth > 0])")
            say(bool(imgs) and all(ok for _, ok in imgs), f"[{tag}] images decode: {imgs}")
            v = pg.locator(".simgrid video").first
            say(v.count() == 1, f"[{tag}] card has a video element")
            if v.count():
                v.scroll_into_view_if_needed()
                say(v.get_attribute("preload") == "none", f"[{tag}] video is lazy (preload=none), so playback is the first request for its bytes")
                v.evaluate("e => { e.muted = true; return e.play().catch(x => String(x)); }")  # as a viewer pressing play
                pg.wait_for_function("document.querySelector('.simgrid video').readyState >= 2", timeout=20000)
                dur = v.evaluate("e => e.duration")
                say(dur and dur > 0, f"[{tag}] video metadata loads on play, duration {dur:.1f}s")
                pg.wait_for_timeout(1200)
                t1 = v.evaluate("e => e.currentTime")
                say(t1 > 0.2, f"[{tag}] video plays (currentTime {t1:.2f}s)")
                v.evaluate("e => { e.pause(); e.currentTime = e.duration / 2; }")
                pg.wait_for_function("e => !document.querySelector('.simgrid video').seeking", timeout=15000)
                t2 = v.evaluate("e => e.currentTime")
                say(abs(t2 - dur / 2) < 0.6, f"[{tag}] video seeks to the middle (currentTime {t2:.2f}s of {dur:.1f}s; needs Range support, served with it)")
                say(v.evaluate("e => !e.error"), f"[{tag}] video has no decode error")
            say(pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth") <= 0, f"[{tag}] fidelity: no horizontal page overflow")
            say(pg.errors == [] and not pg.bad, f"[{tag}] fidelity: no page errors / failed requests {pg.errors[:2]} {pg.bad[:3]}")
            pg.locator(".simgrid").screenshot(path=str(SHOTS / f"fidelity-{tag}.png"))
            pg.close()
        b.close()
    srv.shutdown()
    print(f"\n{len(FINDINGS)} finding(s)")
    return 1 if FINDINGS else 0


if __name__ == "__main__":
    sys.exit(main())
