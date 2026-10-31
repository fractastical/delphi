# Bounded engineering queries

The gated website exposes `POST /api/engineering/solve`. It requires the browser
session, matching Origin and `X-CSRF-Token`; it does not persist a contribution.
The response can be inspected before an authenticated agent proposes a record.

Install `.[engineering]` in the service's dedicated Python environment. The
adapter runs the shared dimensional model in `engineering/constraints.py`, in
a fresh process with an eight-second deadline, two concurrent slots and a
1.5-second Z3 budget. The service's systemd scope bounds the whole process tree.
The child receives no service or contributor credentials.

Requests contain at most 1024 bytes. Numeric values are positive decimal
strings in SI units: `rho`, `cl_max`, `mass`, `area`, `span`, `speed`,
`mass_min`, `wing_loading_min`, `speed_max`. Missing density or lift coefficient
produces `unknown`; neither is inferred from a source that did not measure it.
Booleans `relax_envelopes`, `assume_pectoral_ar_applies_to_wing` and
`assume_taxi_speed_applies_to_flight` default to false. The latter two explicitly
opt into correspondences that the source does not establish.

An illustrative request, with caller assumptions rather than measured values:

```json
{"rho":"1.225","cl_max":"1","mass":"0.05","area":"0.01","span":"0.25","speed":"12"}
```

`feasible` means a witness satisfies the active declared constraints. A separate
exact-rational checker checks that witness against the actual model and query.
The lift constraint is a level-flight proxy, not a validated glide simulation.
`unsat` is a Z3 result for those constraints, not biological impossibility.
Lean is always `not_run` in the online response; separately executed formal
artifacts have their own receipts. A deadline produces `unknown`.

Responses include request and code hashes, parameter basis, checking scope and
proposed follow-up questions. `questions_persisted: false` prevents a returned
suggestion from being mistaken for an entry on the shared whiteboard. Molecular
and developmental questions remain distinct from aerodynamic feasibility.
