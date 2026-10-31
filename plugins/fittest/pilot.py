"""Fittest pilot: do ML interatomic potentials treat enantiomers identically, and when do they escalate?

Context claim: thompson1917-ch09-03 (molecular asymmetry may start from circularly polarised light).
This does not test the claim. It checks one premise any computational test of it relies on: an
isolated molecule and its mirror image have the same energy under a parity-respecting potential, so
any handedness preference has to come from an external chiral field, which an MLIP does not model.

Geometries are PubChem 3D conformers. Each is sent with its exact mirror image (x -> -x), a random
rotation (control), and a bond-stretched copies at 1.4x, 1.7x and 2x (should escalate). One out-of-calibration-domain
molecule (Cl) checks the domain warning. Standard library plus numpy only.
"""

import hashlib
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ENDPOINT = "https://fittest-mcp.westus2.cloudapp.azure.com/mcp"
PUBCHEM_SDF = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/record/SDF?record_type=3d"
HERE = Path(__file__).parent

MOLECULES = [
    {"name": "L-alanine", "cid": 5950},
    {"name": "L-lactic acid", "cid": 107689},
    {"name": "D-glyceraldehyde", "cid": 79014},
]
OUT_OF_DOMAIN = {"name": "(S)-2-chloropropanoic acid", "cid": 107915}
STRETCHES = (1.4, 1.7, 2.0)
SEED = 20261031


def fetch(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        body = r.read()
    return body, {
        "download_url": url,
        "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
    }


def parse_sdf(text):
    lines = text.splitlines()
    n_atoms, n_bonds = int(lines[3][:3]), int(lines[3][3:6])
    symbols, coords = [], []
    for line in lines[4 : 4 + n_atoms]:
        parts = line.split()
        coords.append([float(parts[0]), float(parts[1]), float(parts[2])])
        symbols.append(parts[3])
    bonds = []
    for line in lines[4 + n_atoms : 4 + n_atoms + n_bonds]:
        bonds.append((int(line[:3]) - 1, int(line[3:6]) - 1))
    return symbols, np.array(coords), bonds


def stretch_heavy_bond(symbols, R, bonds, factor):
    """Move one side of the first heavy-atom bond outward so the bond is `factor` times longer."""
    i, j = next((a, b) for a, b in bonds if symbols[a] != "H" and symbols[b] != "H")
    adj = {k: set() for k in range(len(symbols))}
    for a, b in bonds:
        adj[a].add(b)
        adj[b].add(a)
    side, stack = {j}, [j]
    while stack:
        k = stack.pop()
        for m in adj[k]:
            if m != i and m not in side:
                side.add(m)
                stack.append(m)
    shift = (R[j] - R[i]) * (factor - 1)
    R = R.copy()
    for k in side:
        R[k] += shift
    return R, (symbols[i], symbols[j])


def random_rotation(rng):
    q, r = np.linalg.qr(rng.normal(size=(3, 3)))
    q *= np.sign(np.diag(r))
    if np.linalg.det(q) < 0:
        q[:, 0] *= -1
    return q


class Mcp:
    def __init__(self, url):
        self.url, self.sid, self.next_id = url, None, 1

    def _post(self, payload):
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.sid:
            headers["mcp-session-id"] = self.sid
        req = urllib.request.Request(self.url, json.dumps(payload).encode(), headers)
        with urllib.request.urlopen(req, timeout=300) as r:
            self.sid = r.headers.get("mcp-session-id", self.sid)
            body = r.read().decode()
        for line in body.splitlines():
            if line.startswith("data: "):
                return json.loads(line[6:])
        return json.loads(body) if body.strip() else None

    def request(self, method, params=None):
        msg = {"jsonrpc": "2.0", "id": self.next_id, "method": method, "params": params or {}}
        self.next_id += 1
        out = self._post(msg)
        if "error" in out:
            raise RuntimeError(out["error"])
        return out["result"]

    def connect(self):
        info = self.request("initialize", {
            "protocolVersion": "2025-03-26", "capabilities": {},
            "clientInfo": {"name": "delphisci-fittest-pilot", "version": "0.1.0"},
        })
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return info["serverInfo"]

    def call(self, tool, args):
        result = self.request("tools/call", {"name": tool, "arguments": args})
        if result.get("structuredContent") is not None:
            return result["structuredContent"]
        return json.loads(result["content"][0]["text"])


def main():
    rng = np.random.default_rng(SEED)
    files, structures, meta = [], [], []

    def add(label, kind, base, symbols, R):
        structures.append({"symbols": symbols, "R": np.round(R, 6).tolist()})
        meta.append({"label": label, "kind": kind, "base": base, "n_atoms": len(symbols)})

    for mol in MOLECULES + [OUT_OF_DOMAIN]:
        body, rec = fetch(PUBCHEM_SDF.format(cid=mol["cid"]))
        files.append({"molecule": mol["name"], "cid": mol["cid"], **rec})
        symbols, R, bonds = parse_sdf(body.decode())
        R = R - R.mean(axis=0)
        name = mol["name"]
        if mol is OUT_OF_DOMAIN:
            add(name, "out-of-domain", name, symbols, R)
            continue
        add(name, "original", name, symbols, R)
        add(f"mirror of {name}", "mirror", name, symbols, R * np.array([-1.0, 1.0, 1.0]))
        add(f"rotated {name}", "rotation", name, symbols, R @ random_rotation(rng).T)
        for factor in STRETCHES:
            Rs, bond = stretch_heavy_bond(symbols, R, bonds, factor)
            add(f"{name}, {bond[0]}-{bond[1]} bond x{factor}", "stretched", name, symbols, Rs)

    client = Mcp(ENDPOINT)
    server = client.connect()
    status = client.call("swarm_status", {})
    response = client.call("check_structures", {"structures": structures})
    results = response.get("results", response.get("structures", response))

    rows = [{**m, "raw": r} for m, r in zip(meta, results)]

    checks = []
    for mol in MOLECULES:
        name = mol["name"]
        orig = next(x for x in rows if x["label"] == name)
        for kind in ("mirror", "rotation"):
            other = next(x for x in rows if x["base"] == name and x["kind"] == kind)
            entry = {"molecule": name, "transform": kind}
            a, b = orig["raw"].get("served_energy_eV"), other["raw"].get("served_energy_eV")
            entry["delta_served_energy_eV"] = None if a is None or b is None else abs(a - b)
            per_a, per_b = orig["raw"].get("per_model") or {}, other["raw"].get("per_model") or {}
            if isinstance(per_a, dict) and isinstance(per_b, dict):
                entry["delta_energy_by_model_eV"] = {
                    k: abs(per_a[k]["energy_eV"] - per_b[k]["energy_eV"])
                    for k in per_a if isinstance(per_a.get(k), dict) and "energy_eV" in per_a[k]
                    and isinstance(per_b.get(k), dict) and "energy_eV" in per_b[k]
                }
            entry["same_verdict"] = orig["raw"].get("verdict") == other["raw"].get("verdict")
            checks.append(entry)

    out = {
        "context_claim": "thompson1917-ch09-03",
        "endpoint": ENDPOINT,
        "server": server,
        "run_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "seed": SEED,
        "stretch_factors": list(STRETCHES),
        "geometry_files": files,
        "swarm_status": status,
        "invariance_checks": checks,
        "structures": rows,
    }
    (HERE / "pilot-results.json").write_text(json.dumps(out, indent=2) + "\n")

    for x in rows:
        r = x["raw"]
        print(f"{x['label']:<42} {str(r.get('verdict')):<12} trust={r.get('trust_score')} "
              f"ci={r.get('trust_score_90ci')} labels={r.get('labels_behind_score')} "
              f"model={r.get('recommended')} sigmaF={r.get('sigma_F')} "
              f"reasons={r.get('verdict_reasons')} warn={r.get('domain_warning')}")
    for c in checks:
        print(c)


if __name__ == "__main__":
    sys.exit(main())
