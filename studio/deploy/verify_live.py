"""Read-only verification of the deployed node; credentials never enter argv or receipts.

Only a browser access session is created. No scientific record is written.
Run inside the documented systemd scope, especially with --screenshots.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import shlex
import urllib.error
import urllib.request

BASE = "https://frontier.morphoswarm.ai"


def access_token(path):
    values = {}
    for line in path.read_text().splitlines():
        key, sep, value = line.strip().removeprefix("export ").partition("=")
        if sep and key in ("FRONTIER_ACCESS_TOKEN", "MORPHOSWARM_STUDIO_TOKEN"):
            parts = shlex.split(value, comments=True)
            if len(parts) == 1:
                values[key] = parts[0]
    token = values.get("FRONTIER_ACCESS_TOKEN") or values.get("MORPHOSWARM_STUDIO_TOKEN")
    if not token or len(token) < 16:
        raise ValueError("No suitable access token in the supplied environment file")
    return token


def verify(token=None, screenshots=None):
    # Reject redirects: a server must never forward the credential to another origin.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    client = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    checks = []

    def call(path, data=None):
        headers = {"Origin": BASE}
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(BASE + path, data=json.dumps(data).encode() if data is not None else None, headers=headers)
        try:
            with client.open(req, timeout=20) as r:
                raw = r.read(4_000_001)
                if len(raw) > 4_000_000:
                    raise ValueError("Response exceeded verification bound")
                return r.status, json.loads(raw)
        except urllib.error.HTTPError as e:
            return e.code, None

    def check(name, condition):
        checks.append({"name": name, "passed": bool(condition)})
        if not condition:
            raise ValueError("Live check failed: " + name)

    status, body = call("/api/health")
    check("public health", status == 200 and body.get("status") == "ok")
    if token is None:
        check("anonymous catalog", call("/api/catalog")[0] == 200)
        status, session = call("/api/session")
        check("anonymous public session", status == 200 and session.get("public_access") is True and session.get("authenticated") is False and bool(session.get("csrf")))
        check("anonymous contribution refused", call("/v1/proposals", {})[0] == 401)
    else:
        check("catalog requires sign-in", call("/api/catalog")[0] == 401)
        check("session created", call("/api/session", {"token": token})[0] == 200)
    summaries = {}
    for name, path in (("catalog", "/api/catalog?limit=10"), ("artifacts", "/api/artifacts?limit=10"),
                       ("attention", "/api/attention"), ("system", "/api/system")):
        status, body = call(path)
        check(name + " returns JSON", status == 200 and isinstance(body, dict))
        summaries[name] = {"response_sha256": hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()}
        if name == "system":
            summaries[name].update(build=body.get("build"), store=body.get("store"), services=body.get("services"))
        if name == "attention":
            summaries[name]["inputs"] = body.get("inputs")
    if screenshots:
        from playwright.sync_api import sync_playwright
        screenshots.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            context = browser.new_context(viewport={"width": 1440, "height": 1000})
            if token is not None:
                response = context.request.post(BASE + "/api/session", data={"token": token}, headers={"Origin": BASE})
                check("browser sign-in", response.status == 200)
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda _error: errors.append(True))
            for route in ("frontier", "engineering", "simulations", "system"):
                page.goto(BASE + "/#/" + route, wait_until="networkidle")
                check("browser " + route + " uses live data", page.evaluate("window.DF.api.isLive()"))
                page.screenshot(path=str(screenshots / (route + ".png")))
            page.set_viewport_size({"width": 390, "height": 844})
            page.goto(BASE + "/#/frontier", wait_until="networkidle")
            page.screenshot(path=str(screenshots / "frontier-mobile.png"))
            check("browser routes without JavaScript exceptions", not errors)
            browser.close()
    return {"checked_at": datetime.now(timezone.utc).isoformat(), "base": BASE, "read_only": True,
            "checks": checks, "responses": summaries, "scope": "HTTP access and rendering; no scientific acceptance or biological validation"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    access = parser.add_mutually_exclusive_group(required=True)
    access.add_argument("--access-env-file", type=Path)
    access.add_argument("--public-read", action="store_true")
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    if not os.environ.get("INVOCATION_ID"):
        parser.error("Run inside the documented systemd scope")
    result = verify(None if args.public_read else access_token(args.access_env_file), args.screenshots)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"checks_passed": len(result["checks"]), "receipt": str(args.receipt)}))


if __name__ == "__main__":
    main()
