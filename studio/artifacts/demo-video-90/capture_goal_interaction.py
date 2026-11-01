#!/usr/bin/env python3
"""Capture the live, non-persistent home goal-routing interaction.

This records typing and submitting one generic prompt, then saves stills of the
input and result. The app routes the text to existing project/questions; it does
not create a record or generate a design.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright


PROMPT = "design a flying fish"
DEFAULT_BASE = "https://frontier.morphoswarm.ai"
SEATTLE = ZoneInfo("America/Los_Angeles")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE)
    parser.add_argument("--output", type=Path, default=Path("artifacts/demo-video-90/sources/goal-interaction"))
    parser.add_argument("--reported-live-sha", default=None,
                        help="exact deployed SHA reported by the coordinator; public health may omit a release SHA")
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    base = args.base_url.rstrip("/")
    started = datetime.now(timezone.utc)
    with tempfile.TemporaryDirectory(prefix="frontier-goal-video-") as temp:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1280, "height": 720},
                device_scale_factor=1,
                record_video_dir=temp,
                record_video_size={"width": 1280, "height": 720},
            )
            page = context.new_page()
            page.goto(base + "/#/home", wait_until="networkidle", timeout=60000)
            page.wait_for_selector("#goalq", timeout=30000)
            initial_url = page.url
            initial_status = page.evaluate("document.readyState")
            page.locator("#goalq").scroll_into_view_if_needed()
            page.locator("#goalq").press_sequentially(PROMPT, delay=65)
            if page.locator("#goalq").input_value() != PROMPT:
                raise RuntimeError("goal input did not match the frozen prompt")
            page.screenshot(path=str(out / "goal-input.png"), full_page=False)
            page.get_by_role("button", name="Find where this lives").click()
            page.wait_for_selector("#gr-h", timeout=30000)
            result_text = page.locator("#goalout").inner_text()
            low = result_text.lower()
            if "does not design an organism" not in low or "flying fish" not in low:
                raise RuntimeError("goal result did not show the expected routing boundary")
            page.wait_for_timeout(1000)
            page.screenshot(path=str(out / "goal-routed-result.png"), full_page=False)
            result_url = page.url
            result_url_hash = hashlib.sha256(result_url.encode("utf-8")).hexdigest()
            health = page.request.get(base + "/api/health", timeout=20000)
            health_status = health.status
            if health_status == 200:
                raw_health = health.json()
                health_body = {key: raw_health[key] for key in
                               ("status", "version", "release_sha", "build", "checked_at") if key in raw_health}
            else:
                health_body = None
            video = page.video
            context.close()
            video_file = video.path() if video is not None else None
            browser.close()
        if not video_file or not Path(video_file).is_file():
            raise RuntimeError("browser did not save a goal interaction recording")
        shutil.copy2(video_file, out / "goal-interaction.webm")
    finished = datetime.now(timezone.utc)
    manifest = {
        "schema": "frontier.demo-video-90.goal-capture/1",
        "capture": "live, read-only goal routing; no Project/Annotation/Action write",
        "source_url": base + "/#/home",
        "initial_route": initial_url,
        "final_route": result_url,
        "final_route_sha256": result_url_hash,
        "prompt": PROMPT,
        "result_text_sha256": hashlib.sha256(result_text.encode("utf-8")).hexdigest(),
        "document_ready_state_at_input": initial_status,
        "viewport_css_px": {"width": 1280, "height": 720},
        "started_utc": started.isoformat(),
        "finished_utc": finished.isoformat(),
        "finished_seattle": finished.astimezone(SEATTLE).strftime("%Y-%m-%d %I:%M:%S %p %Z"),
        "health_status": health_status,
        "health": health_body,
        "release_sha_reported_by_coordinator": args.reported_live_sha,
        "release_sha_observed_from_public_health": (health_body or {}).get("release_sha") or (health_body or {}).get("build"),
        "files": {},
    }
    for filename in ("goal-interaction.webm", "goal-input.png", "goal-routed-result.png"):
        path = out / filename
        manifest["files"][filename] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
    (out / "capture-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"capture_manifest": str(out / "capture-manifest.json"), "files": manifest["files"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
