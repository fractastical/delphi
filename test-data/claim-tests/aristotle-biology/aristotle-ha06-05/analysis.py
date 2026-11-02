#!/usr/bin/env python3
"""Test aristotle-ha06-05 against AnAge incubation and adult weight in birds."""

import hashlib
import io
import json
import math
import ssl
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

URL = "https://genomics.senescence.info/species/dataset.zip"
HERE = Path(__file__).resolve().parent


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "DelphiClaimTest/1.0"})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
        data = resp.read()
        retrieved = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return data, retrieved


def betacf(a, b, x, max_iter=200, eps=3e-14):
    am = 1.0
    bm = 1.0
    az = 1.0
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    bz = 1.0 - qab * x / qap
    for m in range(1, max_iter + 1):
        em = float(m)
        tem = em + em
        d = em * (b - em) * x / ((qam + tem) * (a + tem))
        ap = az + d * am
        bp = bz + d * bm
        d = -(a + em) * (qab + em) * x / ((a + tem) * (qap + tem))
        app = ap + d * az
        bpp = bp + d * bz
        aold = az
        am = ap / bpp
        bm = bp / bpp
        az = app / bpp
        bz = 1.0
        if abs(az - aold) < eps * abs(az):
            return az
    raise RuntimeError("betacf did not converge")


def betai(a, b, x):
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    ln_beta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(math.log(x) * a + math.log(1.0 - x) * b - ln_beta) / a
    if x < (a + 1.0) / (a + b + 2.0):
        return front * betacf(a, b, x)
    return 1.0 - math.exp(math.log(x) * a + math.log(1.0 - x) * b - ln_beta) / b * betacf(b, a, 1.0 - x)


def spearman(xs, ys):
    def ranks(values):
        order = sorted(range(len(values)), key=lambda i: values[i])
        ranked = [0.0] * len(values)
        i = 0
        while i < len(values):
            j = i
            while j + 1 < len(values) and values[order[j + 1]] == values[order[i]]:
                j += 1
            # Average rank, 1-based.
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                ranked[order[k]] = avg
            i = j + 1
        return ranked

    n = len(xs)
    rx, ry = ranks(xs), ranks(ys)
    mean_x = sum(rx) / n
    mean_y = sum(ry) / n
    num = sum((a - mean_x) * (b - mean_y) for a, b in zip(rx, ry))
    den_x = math.sqrt(sum((a - mean_x) ** 2 for a in rx))
    den_y = math.sqrt(sum((b - mean_y) ** 2 for b in ry))
    rho = num / (den_x * den_y)
    if abs(rho) >= 1.0:
        p = 0.0
        t = None
    else:
        t = rho * math.sqrt((n - 2) / (1.0 - rho * rho))
        df = n - 2
        # Two-sided p from the t distribution via the regularized incomplete beta.
        x = df / (df + t * t)
        p = betai(df / 2.0, 0.5, x)
    return rho, t, p


def number(value):
    value = (value or "").strip()
    if not value:
        return None
    try:
        out = float(value)
    except ValueError:
        return None
    if not math.isfinite(out) or out <= 0:
        return None
    return out


def main():
    blob, retrieved = fetch(URL)
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        name = next(n for n in zf.namelist() if n.endswith("anage_data.txt"))
        raw = zf.read(name)
    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    header = lines[0].split("\t")
    col = {name: i for i, name in enumerate(header)}
    mass_i = col["Adult weight (g)"]
    inc_i = col["Gestation/Incubation (days)"]
    class_i = col["Class"]
    egg_cols = [
        name
        for name in header
        if "copulat" in name.lower() or "egg formation" in name.lower() or "laying" in name.lower()
    ]
    masses = []
    incubations = []
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) <= max(mass_i, inc_i, class_i):
            continue
        if parts[class_i].strip() != "Aves":
            continue
        mass = number(parts[mass_i])
        inc = number(parts[inc_i])
        if mass is None or inc is None:
            continue
        masses.append(math.log10(mass))
        incubations.append(inc)
    n = len(masses)
    if n >= 3:
        rho, t, p = spearman(masses, incubations)
    else:
        rho, t, p = None, None, None
    if n < 50 or rho is None:
        verdict, reason = "inconclusive", "underpowered" if n else "data-unavailable"
    elif rho > 0 and p < 0.05:
        verdict, reason = "supports", None
    else:
        verdict, reason = "refutes", None

    measured = {
        "value": rho,
        "unit": "Spearman rho of log10(adult weight in grams) versus incubation days",
        "n": n,
        "uncertainty": None,
        "extra": {
            "spearman_rho": rho,
            "t_statistic": t,
            "p_value_two_sided": p,
            "egg_formation_columns": egg_cols,
            "egg_formation": "untested",
            "verdict_from_criteria": verdict,
            "reason": reason,
        },
    }
    out = {
        "retrieved_at": retrieved,
        "zip_byte_size": len(blob),
        "zip_sha256": hashlib.sha256(blob).hexdigest(),
        "table_name": name,
        "table_byte_size": len(raw),
        "table_sha256": hashlib.sha256(raw).hexdigest(),
        "measured": measured,
    }
    derived = HERE / "derived"
    derived.mkdir(exist_ok=True)
    (derived / "measured.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
