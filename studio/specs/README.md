# delphi-frontier specs

Normative specifications for the Frontier foundation, derived from the implemented, tested code —
not the other way round. The repository had no `specs/` directory before these; its prior normative
text was `CONTRIBUTING-VERIFICATION.md` (the seven verification rules), which these specs honor and
cite rather than restate.

**Specced against** `work/frontier-foundation` @ `42cd967` ("Import 250 sourced open problems;
separate recorded from actionable"), which is ahead of `origin/main` (`4e10ce0`). The integration
owner merges branches; these specs track the authoritative code, so this baseline is stated in each
file and must be re-pinned when the code moves.

**Reviewer status:** every spec here is **single-reader (fable-lead), NOT Codex-reviewed.**
Independent review of the final materials is a separate bounded reviewer at the 18:00 cut. Treat
these as a careful first reading of the code, not as accepted.

Each spec carries `Scope` (in/out), the relevant `Schema`, an `Acceptance` table mapping every
contract to the **named test** that verifies it (or marking it `ASSUMED` where no test pins it), and
`Open questions` for anything proposed-but-not-built. Two rules were followed throughout: nothing is
specced that the code does not do (wants go to Open questions), and known defects are recorded, not
papered over.

| Spec | Subject |
|---|---|
| [SPEC-001](SPEC-001-record-types.md) | The nine record types and their exact field contracts; the `recorded`/`actionable` Problem split; the register finding (250/250 import, 0 actionable, 148/250 unsourced); the remaining no-typed-`unlocks` defect |
| [SPEC-002](SPEC-002-contribution-review-lifecycle.md) | Provisioning and roles; the authenticated write path; the five review statuses, seven dimensions, independence, the acceptance gate; why there is deliberately no composite truth score |
| [SPEC-003](SPEC-003-action-execution-and-leases.md) | The eight-dimension cache key; the `action_state` machine; atomic leasing, expiry and owner fencing; readiness gate; review adjudication; why a `recorded` Problem cannot be actioned |
| [SPEC-004](SPEC-004-bundles-and-federation.md) | Export/import bundles; `imported_unreviewed`; fork-on-conflict; review receipts as untrusted assertions; why a digest is integrity and not a signature, timestamp, or acceptance |

**Verification run (this session), bounded:**
`systemd-run --user --scope -p TasksMax=128 -p MemoryMax=4G -p MemorySwapMax=0 -p RuntimeMaxSec=600
bash scripts/test_postgres.sh` → **16 passed, exit 0.** The register importer was also run against
`/home/ubuntu/git/morphoswarm/data/problems/register.yaml` (sha256 `a0155552…`) → exit 0, 250/250
importable, 0 actionable, provenance 34 / 68 / 148.
