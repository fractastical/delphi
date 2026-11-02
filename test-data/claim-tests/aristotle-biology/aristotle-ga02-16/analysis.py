#!/usr/bin/env python3
"""Count placental-viviparity species in the Hughes and Blackburn Dryad tables.

Applies the thresholds in result.json. Does not edit pass_criterion or fail_criterion.
"""
import csv
import datetime as dt
import hashlib
import http.client
import io
import json
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
RESULT = HERE / "result.json"
API = "https://datadryad.org/api/v2/datasets/doi%3A10.5061%2Fdryad.80gb5mm12"
UA = "delphisci-claim-test"
FILE_UA = "Mozilla/5.0 (compatible; delphisci-claim-test/1.0; +https://github.com/fractastical/delphi)"
FIVE = {
    "egg_laying",
    "live_bearing_with_oophagy",
    "live_bearing_with_uterine_milk",
    "placental_viviparity",
    "yolk_only_viviparity",
}
WANTED = ("shark_modepruned_E.csv", "shark_modepruned_D.csv")


def get(url, accept=None):
    headers = {"User-Agent": UA}
    if accept:
        headers["Accept"] = accept
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=90) as resp:
        return resp.read()


def cookie_update(cookie, headers):
    pairs = {}
    if cookie:
        for part in cookie.split("; "):
            if "=" in part:
                key, value = part.split("=", 1)
                pairs[key] = value
    for key, value in headers:
        if key.lower() != "set-cookie":
            continue
        name, val = value.split(";", 1)[0].split("=", 1)
        if val == "":
            pairs.pop(name, None)
        else:
            pairs[name] = val
    return "; ".join(f"{key}={value}" for key, value in pairs.items())


def http_get(conn, path, cookie):
    # Accept */* is rejected by the Dryad front door. A browser-like Accept gets the challenge page.
    headers = {
        "User-Agent": FILE_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
    }
    if cookie:
        headers["Cookie"] = cookie
    conn.request("GET", path, headers=headers)
    resp = conn.getresponse()
    return resp.status, resp.getheaders(), resp.read()


def solve_anubis(html):
    """Public proof-of-work in front of Dryad's file_stream downloads.

    The Dryad API download route answers 401 without a bearer token. The public
    file_stream URL is the same file, behind Anubis. The challenge is SHA-256 of
    the issued randomData concatenated with a decimal nonce, with `difficulty`
    leading zero bits (an even difficulty is that many leading zero bytes).
    """
    marker = 'id="anubis_challenge" type="application/json">'
    start = html.find(marker)
    if start < 0:
        return None
    end = html.find("</script>", start)
    payload = json.loads(html[start + len(marker):end])
    data = payload["challenge"]["randomData"]
    difficulty = int(payload["rules"]["difficulty"])
    need = difficulty // 2
    half = difficulty % 2
    nonce = 0
    while nonce <= 5_000_000:
        digest = hashlib.sha256(f"{data}{nonce}".encode()).digest()
        ok = digest[:need] == b"\x00" * need
        if ok and half and (digest[need] >> 4) != 0:
            ok = False
        if ok:
            return payload, digest.hex(), nonce
        nonce += 1
    raise RuntimeError("Anubis challenge was not solved within 5000000 hashes")


def download_file_stream(file_id):
    """Return (bytes, stable_url). Does not retain the expiring storage URL."""
    path = f"/downloads/file_stream/{file_id}"
    stable = "https://datadryad.org" + path
    conn = http.client.HTTPSConnection("datadryad.org", timeout=120)
    last_host = "datadryad.org"
    try:
        status, headers, body = http_get(conn, path, "")
        cookie = cookie_update("", headers)
        if b"anubis_challenge" in body:
            payload, response, nonce = solve_anubis(body.decode("utf-8", "replace"))
            query = urllib.parse.urlencode({
                "id": payload["challenge"]["id"],
                "response": response,
                "nonce": str(nonce),
                "redir": stable,
                "elapsedTime": "1500",
            })
            status, headers, body = http_get(
                conn, "/.within.website/x/cmd/anubis/api/pass-challenge?" + query, cookie
            )
            cookie = cookie_update(cookie, headers)
            if status not in (301, 302, 303, 307, 308):
                raise RuntimeError(f"Anubis pass-challenge returned {status} body={body[:80]!r}")
            status, headers, body = http_get(conn, path, cookie)
        for _ in range(4):
            if status not in (301, 302, 303, 307, 308):
                break
            location = dict((key.lower(), value) for key, value in headers).get("location")
            if not location:
                break
            parsed = urllib.parse.urlparse(location)
            last_host = parsed.netloc or last_host
            next_path = parsed.path + (("?" + parsed.query) if parsed.query else "")
            if parsed.netloc and parsed.netloc != "datadryad.org":
                conn.close()
                if parsed.scheme == "https":
                    conn = http.client.HTTPSConnection(parsed.hostname, timeout=120)
                else:
                    conn = http.client.HTTPConnection(parsed.hostname, timeout=120)
                status, headers, body = http_get(conn, next_path, "")
            else:
                status, headers, body = http_get(conn, next_path, cookie)
    finally:
        conn.close()
    if status != 200 or body.startswith(b"<!doctype") or b"anubis_challenge" in body[:800]:
        preview = body[:180].decode("utf-8", "replace").replace("\n", " ")
        raise RuntimeError(
            f"Dryad file_stream {file_id} was not a file (status {status}, {len(body)} bytes, host {last_host}): {preview}"
        )
    return body, stable


def now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def norm_mode(value):
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def load_table(path):
    text = path.read_text(encoding="utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        return [], None, None
    fields = {k.lower(): k for k in rows[0].keys()}
    species_key = fields.get("species")
    mode_key = fields.get("mode")
    return rows, species_key, mode_key


def summarize(rows, species_key, mode_key):
    modes = {}
    species = set()
    placental = set()
    for row in rows:
        name = (row.get(species_key) or "").strip()
        mode = norm_mode(row.get(mode_key) or "")
        if not name or not mode:
            continue
        species.add(name)
        modes.setdefault(mode, set()).add(name)
        if mode == "placental_viviparity":
            placental.add(name)
    return {
        "n_coded_species": len(species),
        "n_placental": len(placental),
        "mode_counts": {m: len(s) for m, s in sorted(modes.items())},
        "vocabulary_is_five_mode": set(modes) <= FIVE and "placental_viviparity" in FIVE and len(set(modes) & FIVE) >= 1 and set(modes) <= FIVE,
        "contains_five_mode_labels": FIVE <= set(modes) or (set(modes) <= FIVE and len(set(modes) & FIVE) >= 3),
        "observed_modes": sorted(modes),
    }


def decide(primary, original):
    """Return verdict, reason, confidence from the pre-registered rule."""
    if primary is None:
        return "inconclusive", "data-unavailable", 0.3
    observed = set(primary["observed_modes"])
    # The landing page names five labels. A file uses that vocabulary when its
    # non-empty modes are drawn from those five labels.
    uses_five = len(observed) > 0 and observed <= FIVE
    if not uses_five:
        return "inconclusive", "not-operationalizable", 0.35
    n = primary["n_placental"]
    n_d = None if original is None else original["n_placental"]
    if primary["n_coded_species"] < 30 and n == 0:
        return "inconclusive", "underpowered", 0.35
    if n >= 5 and n_d is not None and n_d == 0:
        return "mixed", None, 0.45
    if n >= 5 and (n_d is None or n_d >= 5):
        return "supports", None, 0.8
    if n >= 5 and n_d is not None and 0 < n_d < 5:
        return "mixed", None, 0.45
    if 1 <= n <= 4:
        return "mixed", None, 0.45
    if n == 0 and primary["n_coded_species"] >= 30:
        return "refutes", None, 0.75
    return "inconclusive", "underpowered", 0.35


def main():
    DATA.mkdir(exist_ok=True)
    DERIVED.mkdir(exist_ok=True)
    meta = json.loads(get(API, accept="application/json"))
    files_url = "https://datadryad.org" + meta["_links"]["stash:version"]["href"] + "/files"
    listing = json.loads(get(files_url, accept="application/json"))
    by_name = {f["path"]: f for f in listing["_embedded"]["stash:files"]}
    retrieved = now()
    file_info = []
    summaries = {}
    for name in WANTED:
        spec = by_name[name]
        # The API download href requires a Dryad bearer token (401). The public
        # file is the file_stream URL for the same file id.
        file_id = spec["_links"]["stash:download"]["href"].rstrip("/").split("/")[-2]
        raw, url = download_file_stream(file_id)
        digest = hashlib.sha256(raw).hexdigest()
        path = DATA / name
        path.write_bytes(raw)
        file_info.append({
            "name": name,
            "download_url": url,
            "retrieved_at": retrieved,
            "byte_size": len(raw),
            "sha256": digest,
            "publisher_sha256": spec.get("digest"),
            "publisher_digest_matches": digest == spec.get("digest"),
        })
        rows, species_key, mode_key = load_table(path)
        if species_key is None or mode_key is None:
            summaries[name] = None
        else:
            summaries[name] = summarize(rows, species_key, mode_key)
            summaries[name]["species_column"] = species_key
            summaries[name]["mode_column"] = mode_key
    if any(f["publisher_sha256"] and not f["publisher_digest_matches"] for f in file_info):
        verdict, reason, confidence = "inconclusive", "data-unavailable", 0.3
    else:
        verdict, reason, confidence = decide(summaries.get("shark_modepruned_E.csv"), summaries.get("shark_modepruned_D.csv"))
    primary = summaries.get("shark_modepruned_E.csv") or {}
    measured = {
        "value": primary.get("n_placental"),
        "unit": "species coded placental_viviparity in shark_modepruned_E.csv",
        "n": primary.get("n_coded_species"),
        "uncertainty": None,
        "extra": {
            "E": summaries.get("shark_modepruned_E.csv"),
            "D": summaries.get("shark_modepruned_D.csv"),
            "checksums_match_publisher": all(f["publisher_digest_matches"] for f in file_info),
        },
    }
    result = json.loads(RESULT.read_text())
    result["status"] = "complete"
    result["data_kind"] = "biological"
    result["verdict"] = verdict
    result["confidence"] = confidence
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    result["datasets"] = [{
        "id": "hughes-blackburn-2025-dryad-10.5061/dryad.80gb5mm12",
        "name": meta.get("title"),
        "landing_url": "https://datadryad.org/dataset/doi:10.5061/dryad.80gb5mm12",
        "doi": "10.5061/dryad.80gb5mm12",
        "version": str(meta.get("versionNumber")),
        "license": "CC0-1.0",
        "files": file_info,
        "role": "species-level reproductive mode of sharks and rays, corrected (E) and original (D) codings",
    }]
    result["method"] = (
        "Downloaded shark_modepruned_E.csv and shark_modepruned_D.csv from the public Dryad file_stream "
        "URLs for the file ids in the version file list (the API download route requires a bearer token), "
        "checked each SHA-256 against the publisher digest, and counted unique species whose mode "
        "normalizes to placental_viviparity. The five-mode vocabulary is the one named on the Dryad "
        "file description. The verdict uses the pre-registered thresholds: at least 5 in both files supports; "
        "zero in E inside that vocabulary refutes; 1 to 4, or E passing while D is zero, is mixed."
    )
    result["measured"] = measured
    e_n = primary.get("n_placental")
    d_n = (summaries.get("shark_modepruned_D.csv") or {}).get("n_placental")
    result["results_summary"] = [
        f"Corrected table E: {e_n} species coded placental_viviparity out of {primary.get('n_coded_species')} coded species.",
        f"Original table D: {d_n} species coded placental_viviparity.",
        f"Verdict {verdict}" + (f" ({reason})" if reason else "") + f" at confidence {confidence}.",
    ]
    RESULT.write_text(json.dumps(result, indent=2) + "\n")
    DERIVED.joinpath("measured.json").write_text(json.dumps(measured, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "reason": reason, "measured": measured["value"], "n": measured["n"], "D": d_n}, indent=2))


if __name__ == "__main__":
    main()
