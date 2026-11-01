"""Offline capped worker: reads one request JSON on stdin, writes one response JSON on stdout.  No network,
no shell, no file writes; resource limits are applied before any model-supplied byte is parsed."""
from __future__ import annotations

import json
import resource
import sys


def main() -> int:
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
        # Two public solver slots share the web service's 1GiB cgroup.
        # Bound each child below that total so an expression-expansion failure
        # cannot consume the service's whole memory allowance.
        resource.setrlimit(resource.RLIMIT_AS, (384 * 1024**2, 384 * 1024**2))
        resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    except (ValueError, OSError):
        pass
    from .grammar import GrammarError, SCHEMA_ERROR
    from .service import compute
    data = sys.stdin.buffer.read(20000)
    try:
        req = json.loads(data.decode("utf-8"))
        out = compute(req)
        code = 0
    except GrammarError as e:
        out, code = {"schema": SCHEMA_ERROR, "code": e.code, "calibrated": False, "detail": e.detail[:300]}, 0
    except Exception as e:  # noqa: BLE001
        out, code = {"schema": SCHEMA_ERROR, "code": "solver_unavailable", "calibrated": False, "detail": type(e).__name__}, 1
    sys.stdout.write(json.dumps(out, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
