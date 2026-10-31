"""CLI: python -m connectors.biomodels {search,metadata,fetch,replay} ..."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .client import BioModelsClient, ConnectorError
from .replay import EngineUnavailable, replay_collier1996
from .sbml import UnsupportedSBML

PINNED = {"BIOMD0000001047": "da21ab52edba14b61e41ee87df7a8bb2f367a1206e6e822602f1e75271fae8e2"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="connectors.biomodels")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search"); s.add_argument("query"); s.add_argument("--limit", type=int, default=10)
    m = sub.add_parser("metadata"); m.add_argument("accession")
    f = sub.add_parser("fetch"); f.add_argument("accession"); f.add_argument("--dest", type=Path, required=True)
    r = sub.add_parser("replay"); r.add_argument("accession"); r.add_argument("--dest", type=Path, required=True); r.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    c = BioModelsClient()
    try:
        if a.cmd == "search":
            out = c.search(a.query, a.limit).to_dict()
        elif a.cmd == "metadata":
            out = c.metadata(a.accession)
        elif a.cmd == "fetch":
            out = c.fetch(a.accession, a.dest).to_dict()
        else:
            got = c.fetch(a.accession, a.dest)
            pin = PINNED.get(a.accession)
            if pin is None:
                raise ConnectorError(f"{a.accession} has no pinned digest; add one after reading the model")
            out = replay_collier1996(Path(got.path).read_bytes(), pin, a.out, source={k: v for k, v in got.to_dict().items() if k != "path"}, argv=["python", "-m", "connectors.biomodels", *(argv if argv is not None else sys.argv[1:])])
    except (ConnectorError, UnsupportedSBML, EngineUnavailable, ValueError) as exc:
        print(json.dumps({"status": "refused", "reason": f"{type(exc).__name__}: {exc}"}), file=sys.stderr)
        return 2
    print(json.dumps(out, indent=1, sort_keys=True, default=str))
    return 0 if out.get("all_checks_passed", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
