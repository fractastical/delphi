"""Independent protocol critique and data-access audit via Gemini.

Reuses the configured client in Delphi Evolve's ``gpuops/scientific_services``
**unmodified** -- its path, checksum, repository commit and licence are recorded
in the output. Only this harness's tighter caps are applied, by setting the
client's module-level budget globals before any call:

    at most 4 calls, 100,000 input tokens, 24,000 output tokens including thinking.

The budget is reserved to a ledger before the first call, not reconciled after.

**What comes back is model opinion.** It is a lead to check, never a finding.
Nothing here is treated as verification of anything, and the audit prompt says so
to the model as well, so it is not invited to validate the work.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

GPUOPS = "/data/worktrees/delphi-evolve/gpuops"
sys.path.insert(0, GPUOPS)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from connectors.bioservices.receipts import sha256_file, utc_now, write_json  # noqa: E402

MAX_CALLS, MAX_IN, MAX_OUT = 4, 100_000, 24_000

SYSTEM = (
    "You are auditing a computational protocol written by another agent. Your job is to find what is "
    "wrong with it, not to approve it. Be specific and terse. Where you cannot verify something from "
    "your own knowledge, say so explicitly and label it unverifiable rather than guessing. Do not "
    "congratulate. Do not restate the protocol back. If a criticism would not change a conclusion, "
    "say that it is cosmetic."
)

CRITIQUE_PROMPT = """Below is a frozen protocol for a computational replication on public data.

Give me, in order of how badly it would damage the inference:
1. Methodological defects that would make the reported comparison invalid or uninterpretable.
2. Statistical defects, especially in the paired bootstrap and the permutation null.
3. Places where the protocol claims more than its design can support.
4. Anything it should have pre-registered and did not.

Be concrete. If a defect has a cheap fix, name the fix in one line. If the protocol
has already anticipated an objection, do not raise it as if it had not.

--- PROTOCOL ---
{protocol}
"""

ACCESS_PROMPT = """I am auditing the data-access and parameter claims of a computational protocol.
For EACH claim below, answer in one line: CONSISTENT / INCONSISTENT / UNVERIFIABLE, then why.

Treat "UNVERIFIABLE" as the correct answer whenever you would otherwise be guessing from memory;
I would rather have an honest gap than a confident wrong number. Do not invent checksums,
row counts or URLs.

CLAIMS
1. ProteinGym v1.3 distributes DMS substitution assays as a zip at
   https://marks.hms.harvard.edu/proteingym/ProteinGym_v1.3/DMS_ProteinGym_substitutions.zip
2. ProteinGym's curated data and code are MIT licensed, while the underlying measurements
   belong to the source publications.
3. The assays KCNJ2_MOUSE_Coyote-Maestas_2022_surface and KCNJ2_MOUSE_Coyote-Maestas_2022_function
   come from a multiparametric deep mutational scan of Kir2.1 reported by Coyote-Maestas et al.
   in 2022, measuring surface expression and channel function on overlapping variant sets.
4. UniProtKB P35561 is KCNJ2_MOUSE, the mouse inward-rectifier potassium channel Kir2.1,
   and its canonical sequence is 428 residues.
5. ProteinGym's published reference table reports ESM-2 (650M) Spearman correlations of
   about 0.352 for the surface assay and about 0.382 for the function assay.
6. facebook/esm2_t33_650M_UR50D is a 650M-parameter masked protein language model whose
   tokenizer prepends a cls token, so residue position p is token index p.
7. The masked-marginal variant score log p(mut | x_masked at i) - log p(wt | x_masked at i)
   is the scoring convention introduced for ESM in Meier et al. 2021.
8. For masked marginals, the number of forward passes needed scales with the number of
   DISTINCT MUTATED POSITIONS, not with the number of variants.

Then, separately: name any access, licensing or versioning risk in using these sources for a
public replication that I have not listed.
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Gemini protocol critique and data-access audit")
    ap.add_argument("--protocol", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--model", default=None, help="pin a model id exactly; otherwise a preferred text model")
    ap.add_argument("--ledger", default=None,
                    help="budget ledger path; share it across runs so the cap spans them all")
    args = ap.parse_args()

    from scientific_services import gemini_client as gc  # noqa: E402

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    # The ledger is shared across runs on purpose: a per-run ledger would reset
    # the cap every time the script was invoked, which is not a cap.
    gc.LEDGER = Path(args.ledger) if args.ledger else out_dir / "usage_ledger.json"
    gc.MAX_CALLS, gc.MAX_IN, gc.MAX_OUT = MAX_CALLS, MAX_IN, MAX_OUT

    provenance = {
        "reused_client": {
            "repo": "kganjam/delphi-evolve (gpuops)",
            "path": f"{GPUOPS}/scientific_services/gemini_client.py",
            "sha256": sha256_file(f"{GPUOPS}/scientific_services/gemini_client.py"),
            "common_sha256": sha256_file(f"{GPUOPS}/scientific_services/common.py"),
            "license": "Apache-2.0 (see gpuops/LICENSE and gpuops/NOTICE)",
            "modified": False,
            "configuration_applied": {
                "ledger": str(gc.LEDGER), "max_calls": MAX_CALLS,
                "max_input_tokens": MAX_IN, "max_output_tokens_incl_thinking": MAX_OUT,
            },
        },
        "budget_reserved_utc": utc_now(),
        "epistemic_status": "model opinion; every claim is a lead until checked independently",
    }
    write_json(str(out_dir / "audit_provenance.json"), provenance)

    client = gc.Gemini()
    model = args.model or _pick_model(client)
    print(f"model pinned: {model}")

    protocol_text = Path(args.protocol).read_text()
    calls = [
        ("protocol-critique", CRITIQUE_PROMPT.format(protocol=protocol_text), 8000),
        ("data-access-audit", ACCESS_PROMPT, 6000),
    ]

    records = []
    for label, prompt, max_out in calls:
        try:
            rec = client.generate(model, prompt, system=SYSTEM, max_output_tokens=max_out,
                                  temperature=0.2, label=label, out_dir=out_dir)
        except gc.BudgetExceeded as exc:
            print(f"{label}: STOPPED on budget: {exc}")
            break
        except Exception as exc:
            print(f"{label}: FAILED {type(exc).__name__}: {str(exc)[:300]}")
            break
        um = rec.get("usage_metadata", {})
        records.append({
            "label": label, "model_requested": rec["model_requested"],
            "model_version_returned": rec["model_version_returned"],
            "http_status": rec["http_status"], "finish_reason": rec["finish_reason"],
            "input_tokens": um.get("promptTokenCount"),
            "output_tokens": um.get("candidatesTokenCount"),
            "thinking_tokens": um.get("thoughtsTokenCount"),
            "elapsed_s": rec["elapsed_s"],
        })
        print(f"{label}: HTTP {rec['http_status']} model={rec['model_version_returned']} "
              f"in={um.get('promptTokenCount')} out={um.get('candidatesTokenCount')} "
              f"thinking={um.get('thoughtsTokenCount')}")
        print("--- response ---")
        print(rec["response_text"])
        print("--- end ---\n")

    ledger = json.loads(gc.LEDGER.read_text()) if gc.LEDGER.exists() else {}
    write_json(str(out_dir / "audit_summary.json"), {
        "provenance": provenance, "calls": records,
        "ledger_totals": {k: ledger.get(k) for k in ("calls", "input_tokens", "output_tokens")},
        "caps": {"max_calls": MAX_CALLS, "max_input_tokens": MAX_IN, "max_output_tokens": MAX_OUT},
    })
    return 0


def _pick_model(client) -> str:
    """List models and pin a concrete id, so the record names what actually ran."""
    import urllib.request

    req = urllib.request.Request(f"{gc_base()}/models", headers={"x-goog-api-key": client._key})
    with urllib.request.urlopen(req, timeout=60) as r:
        names = [m["name"].removeprefix("models/") for m in json.loads(r.read()).get("models", [])
                 if "generateContent" in m.get("supportedGenerationMethods", [])]
    # Exact ids only. A prefix match once selected `gemini-3-pro-image-preview`
    # for a text critique, because it begins with "gemini-3-pro"; an image model
    # answered a methodology question and the record would have read as if the
    # text Pro had. Name the model exactly, or fail and make the caller choose.
    text_only = [n for n in names if "image" not in n and "tts" not in n and "embedding" not in n]
    for prefer in ("gemini-3.1-pro-preview", "gemini-3-pro-preview", "gemini-2.5-flash", "gemini-2.0-flash"):
        if prefer in text_only:
            return prefer
    if not text_only:
        raise RuntimeError(
            f"no text Gemini model supports generateContent on this key; saw {names[:10]}")
    raise RuntimeError(
        f"none of the preferred text models is available; pass --model explicitly. Available: {text_only[:15]}")


def gc_base() -> str:
    from scientific_services import gemini_client as gc
    return gc.BASE


if __name__ == "__main__":
    raise SystemExit(main())
