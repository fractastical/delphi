"""Check public demo bytes, byte-range delivery, captions and actual browser playback.

Run under a bounded systemd scope. Creates no scientific records or sessions.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen


def verify(base: str, capture: Path | None = None) -> dict:
    base = base.rstrip("/")
    checks = []

    def check(name, condition):
        checks.append({"name": name, "passed": bool(condition)})
        if not condition:
            raise ValueError("Demo check failed: " + name)

    def fetch(path, limit=16_000_000, headers=None):
        if not path.startswith("artifacts/demo-video/") or ".." in Path(path).parts:
            raise ValueError("Media path outside demo subtree")
        with urlopen(Request(base + "/" + path, headers=headers or {}), timeout=30) as response:
            data = response.read(limit + 1)
            if len(data) > limit:
                raise ValueError("Response exceeds media limit")
            return response.status, dict(response.headers.items()), data

    status, _, raw = fetch("artifacts/demo-video/manifest.json")
    manifest = json.loads(raw)
    check("complete public manifest", status == 200 and manifest["status"] == "complete")
    cuts = {cut["id"]: cut for cut in manifest["cuts"]}
    check("both requested cuts present", set(cuts) == {"frontier-60s", "frontier-120s"})
    for name, cut in cuts.items():
        expected_duration = 60 if name == "frontier-60s" else 120
        check(name + " declared duration", abs(cut["duration_s"] - expected_duration) <= 0.25)
        for role in ("video", "poster", "captions", "transcript"):
            pin = cut["files"][role]
            path = "artifacts/demo-video/" + pin["path"]
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
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        for name in ("frontier-60s", "frontier-120s"):
            page.goto(base + "/#/demo?cut=" + name, wait_until="domcontentloaded")
            page.wait_for_selector("#demo-video")
            page.wait_for_function("document.querySelector('#demo-video').readyState >= 2", timeout=30000)
            page.evaluate("async () => {const v=document.querySelector('#demo-video');v.muted=true;await v.play();}")
            page.wait_for_function("document.querySelector('#demo-video').currentTime > 0.5", timeout=15000)
            state = page.evaluate("""() => {const v=document.querySelector('#demo-video');v.pause();return {
                duration:v.duration,width:v.videoWidth,height:v.videoHeight,time:v.currentTime,
                decodedFrames:v.getVideoPlaybackQuality().totalVideoFrames,source:v.currentSrc};}""")
            check(name + " browser decoded and played",
                  state["width"] == 1920 and state["height"] == 1080 and state["decodedFrames"] > 0
                  and abs(state["duration"] - cuts[name]["duration_s"]) <= 0.25)
            check(name + " no horizontal overflow", page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth"))
            if capture:
                capture.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(capture / (name + ".png")))
            playback.append({"id": name, **state})
        check("no page errors", not errors)
        browser.close()
    return {"schema": "frontier.demo-video.live-check/1", "checked_at": datetime.now(timezone.utc).isoformat(),
            "base": base, "manifest_sha256": hashlib.sha256(raw).hexdigest(), "checks": checks,
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
