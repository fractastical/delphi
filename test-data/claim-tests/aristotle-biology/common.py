"""Shared fetch and text helpers for the Aristotle claim tests.

Downloads stay in each test's data/ directory, which claim-tests/.gitignore
excludes. Nothing here chooses a verdict.
"""
import hashlib
import html
import json
import os
import re
from datetime import datetime, timezone

import requests

UA = {"User-Agent": "Mozilla/5.0 (compatible; delphi-claim-test/1.0; research)"}
FROZEN = (
    "hypothesis",
    "pass_criterion",
    "fail_criterion",
    "planned_datasets",
    "test_contract",
    "claim_id",
    "claim_iri",
    "project",
    "interpretation",
    "agent",
)


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url, dest, timeout=90):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    r = requests.get(url, headers=UA, timeout=timeout)
    r.raise_for_status()
    open(dest, "wb").write(r.content)
    return {
        "download_url": url,
        "retrieved_at": now(),
        "byte_size": len(r.content),
        "sha256": hashlib.sha256(r.content).hexdigest(),
    }


def strip_html(raw):
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", "replace")
    raw = re.sub(r"(?is)<script\b.*?</script>", " ", raw)
    raw = re.sub(r"(?is)<style\b.*?</style>", " ", raw)
    raw = re.sub(r"(?is)<[^>]+>", " ", raw)
    raw = html.unescape(raw)
    raw = raw.replace("\xa0", " ")
    return re.sub(r"\s+", " ", raw).strip()


def sentences(text):
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if len(p.strip()) > 40]


def load_result(path):
    with open(path) as f:
        return json.load(f)


def write_result(path, result, payload):
    frozen = {k: result[k] for k in FROZEN if k in result}
    result.update(payload)
    result.update(frozen)
    result["status"] = "complete"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(result, f, indent=2)
        f.write("\n")
    derived = os.path.join(os.path.dirname(path), "derived")
    os.makedirs(derived, exist_ok=True)
    with open(os.path.join(derived, "summary.json"), "w") as f:
        json.dump(payload.get("measured"), f, indent=2)
        f.write("\n")
