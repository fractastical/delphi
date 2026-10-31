"""Frontier attention layer: a read-only adapter over exported store records.

Owner: market worker (single-reader, not Codex-reviewed). It reads records and events the store exports; it writes nothing to
the store, adds no record kind, and makes no change to frontier/. Typed unlock edges, bounded actions and decision models live
in a separate, content-hashed *annotation* pinned to an exact Problem version (the store cannot hold them today: SPEC-001
"Known defect"). A proposal for the coupled store change is in the handoff, not applied here.

A claim's truth and its priority are separate: nothing in `rank` reads an Assessment, and no annotation can change one.
"""
