"""Columnar xz encoding of cell tables (much smaller than row JSON; the injected-files limit is about 45 KB). Lossless: decode(encode(x)) == x."""
import json, lzma
KEYS = ["id", "model", "params", "Dv", "L", "NA", "K", "T", "eps", "seed"]


def encode(cells, extra=None):
    d = {k: [c[k] for c in cells] for k in KEYS}
    d["extra"] = extra or {}
    return lzma.compress(json.dumps(d, sort_keys=True, separators=(",", ":"), allow_nan=False).encode(), preset=9 | lzma.PRESET_EXTREME)


def decode(path):
    d = json.loads(lzma.decompress(open(path, "rb").read()))
    cells = [{k: d[k][i] for k in KEYS} for i in range(len(d["id"]))]
    return cells, d.get("extra", {})
