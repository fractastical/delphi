"""Check public demo bytes, byte-range delivery, captions and actual browser playback.

Run under a bounded systemd scope. Creates no scientific records or sessions.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen

EDITIONS = {
    "artifacts/demo-video": {"frontier-60s": 60, "frontier-120s": 120},
    "artifacts/demo-video-90": {"frontier-90s": 90},
    "artifacts/demo-video-science": {"frontier-science-60s": 60, "frontier-science-120s": 120},
    "artifacts/demo-video-delphi": {"frontier-delphi-60s": 60, "frontier-delphi-120s": 120},
}


def verify(base: str, capture: Path | None = None) -> dict:
    base = base.rstrip("/")
    checks = []

    def check(name, condition):
        checks.append({"name": name, "passed": bool(condition)})
        if not condition:
            raise ValueError("Demo check failed: " + name)

    def fetch(path, limit=16_000_000, headers=None):
        if not path.startswith(tuple(directory + "/" for directory in EDITIONS)) or ".." in Path(path).parts:
            raise ValueError("Media path outside demo subtree")
        with urlopen(Request(base + "/" + path, headers=headers or {}), timeout=30) as response:
            data = response.read(limit + 1)
            if len(data) > limit:
                raise ValueError("Response exceeds media limit")
            return response.status, dict(response.headers.items()), data

    cuts, directories, manifests = {}, {}, {}
    for directory, expected in EDITIONS.items():
        status, _, raw = fetch(directory + "/manifest.json")
        manifest = json.loads(raw)
        check(directory + " complete public manifest", status == 200 and manifest["status"] == "complete")
        entries = manifest["cuts"]
        check(directory + " requested cuts present", len(entries) == len(expected) and {c["id"] for c in entries} == set(expected))
        manifests[directory] = hashlib.sha256(raw).hexdigest()
        for cut in entries:
            cuts[cut["id"]], directories[cut["id"]] = cut, directory
    for name, cut in cuts.items():
        expected_duration = EDITIONS[directories[name]][name]
        check(name + " declared duration", abs(cut["duration_s"] - expected_duration) <= 0.25)
        for role in ("video", "poster", "captions", "transcript"):
            pin = cut["files"][role]
            path = directories[name] + "/" + pin["path"]
            limit = 64_000_000 if role == "video" else 16_000_000
            status, headers, data = fetch(path, limit)
            headers = {key.lower(): value for key, value in headers.items()}
            check(name + " " + role + " exact public bytes",
                  status == 200 and len(data) == pin["bytes"] and hashlib.sha256(data).hexdigest() == pin["sha256"])
            if role == "captions":
                check(name + " WebVTT MIME and header", headers.get("content-type", "").startswith("text/vtt") and data.startswith(b"WEBVTT"))
            if role == "video":
                check(name + " MP4 MIME", headers.get("content-type") == "video/mp4")
                ranged, range_headers, first = fetch(path, 1024, {"Range": "bytes=0-1023"})
                range_headers = {key.lower(): value for key, value in range_headers.items()}
                check(name + " seekable exact byte range",
                      ranged == 206 and first == data[:1024] and range_headers.get("content-range") == f"bytes 0-1023/{len(data)}")

    from playwright.sync_api import sync_playwright
    playback = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        def wait_js(expression, timeout=30):
            # Read through the browser protocol; wait_for_function's in-page
            # string evaluation can be rejected by the site's strict CSP.
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if page.evaluate("() => (" + expression + ")"):
                    return
                page.wait_for_timeout(100)
            raise TimeoutError("Browser state did not become true: " + expression)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        for name in cuts:
            page.goto(base + "/#/demo?cut=" + name, wait_until="domcontentloaded")
            page.wait_for_selector("#demo-video")
            wait_js("document.querySelector('#demo-video').readyState >= 2")
            page.evaluate("async () => {const v=document.querySelector('#demo-video');v.muted=true;await v.play();}")
            wait_js("document.querySelector('#demo-video').currentTime > 0.5", timeout=15)
            state = page.evaluate("""() => {const v=document.querySelector('#demo-video');v.pause();return {
                duration:v.duration,width:v.videoWidth,height:v.videoHeight,time:v.currentTime,
                decodedFrames:v.getVideoPlaybackQuality().totalVideoFrames,source:v.currentSrc};}""")
            check(name + " browser decoded and played",
                  state["width"] == 1920 and state["height"] == 1080 and state["decodedFrames"] > 0
                  and abs(state["duration"] - cuts[name]["duration_s"]) <= 0.25
                  and state["source"].endswith(directories[name] + "/" + cuts[name]["files"]["video"]["path"]))
            page.evaluate("""() => {const v=document.querySelector('#demo-video');
                v.textTracks[0].mode='showing';v.currentTime=v.duration/2;}""")
            wait_js("document.querySelector('#demo-video track').readyState === 2")
            wait_js("!document.querySelector('#demo-video').seeking && document.querySelector('#demo-video').readyState >= 2")
            check(name + " captions loaded and seek completed", page.evaluate("""() => {
                const v=document.querySelector('#demo-video');return v.textTracks[0].cues.length>0
                && Math.abs(v.currentTime-v.duration/2)<0.5;}"""))
            check(name + " no horizontal overflow", page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth"))
            page.locator("#demo-fs").click()
            wait_js("document.fullscreenElement?.id === 'demo-stage'")
            check(name + " fullscreen entered", page.evaluate("document.fullscreenElement.id === 'demo-stage'"))
            page.evaluate("document.exitFullscreen()")
            wait_js("document.fullscreenElement === null")
            check(name + " all seven cuts have direct downloads", page.locator(".demodl a[download][href$='.mp4']").count() == len(cuts))
            if capture:
                capture.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(capture / (name + ".png")))
            playback.append({"id": name, **state})
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(base + "/#/demo", wait_until="domcontentloaded")
        page.wait_for_selector("#demo-video")
        check("mobile defaults to new Delphi 60-second cut", page.locator("#demo-video source").get_attribute("src").endswith("frontier-delphi-60s.mp4"))
        check("mobile has no horizontal overflow", page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth"))
        page.locator(".aboutmenu summary").click()
        check("About exposes Demo videos", page.locator(".aboutmenu a[href$='#/demo']").inner_text() == "Demo videos")
        if capture:
            page.screenshot(path=str(capture / "demo-mobile.png"))
        check("no page errors", not errors)
        browser.close()
    return {"schema": "frontier.demo-video.live-check/1", "checked_at": datetime.now(timezone.utc).isoformat(),
            "base": base, "manifest_sha256": manifests["artifacts/demo-video"],
            "manifest_hashes": manifests, "checks": checks,
            "playback": playback, "scientific_records_written": 0,
            "scope": "Exact public media bytes, delivery and browser decoding/playback; not biological validation."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="https://frontier.morphoswarm.ai")
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--capture", type=Path)
    args = parser.parse_args()
    result = verify(args.base, args.capture)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"checks_passed": len(result["checks"]), "receipt": str(args.receipt)}))


if __name__ == "__main__":
    main()
