#!/usr/bin/env python3
"""Polite NCBI E-utilities helper: <=2 req/s, exponential backoff on 429/5xx."""
import time
import urllib.error
import urllib.parse
import urllib.request

E = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
UA = {"User-Agent": "zrs-comparative-analysis/1.0 (MorphoSwarm hackathon artifact)"}
_last = [0.0]
MIN_GAP = 0.5


def get(path, params=None, data=None, retries=6, timeout=180):
    """Returns (status, body_text, url). Raises after `retries` failures."""
    url = E + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    delay = 2.0
    last = None
    for _ in range(retries):
        gap = time.time() - _last[0]
        if gap < MIN_GAP:
            time.sleep(MIN_GAP - gap)
        try:
            req = urllib.request.Request(url, data=data, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                _last[0] = time.time()
                return r.status, r.read().decode("utf-8", "replace"), url
        except urllib.error.HTTPError as e:
            _last[0] = time.time()
            last = e
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(delay)
                delay *= 2
                continue
            raise
        except Exception as e:
            _last[0] = time.time()
            last = e
            time.sleep(delay)
            delay *= 2
    raise RuntimeError(f"E-utilities failed for {url}: {last}")
