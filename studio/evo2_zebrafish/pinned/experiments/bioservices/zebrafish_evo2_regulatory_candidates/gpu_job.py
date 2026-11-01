"""Single-GPU Evo 2 job: generate zebrafish regulatory candidates and score controls.

Runs on ONE H100 with `evo2_7b` in bfloat16, which the official repository states
needs no Transformer Engine and no FP8. The 40B checkpoint is deliberately not
used: it requires several H100s, which breaks the event's one-GPU-per-team rule.

What it does, in order, writing after every stage so a timeout still leaves
usable output:

1. Load the frozen input set (prepared and committed before this job existed).
2. Generate candidates in two labelled arms.
3. Build composition-matched negative controls deterministically.
4. Score everything with Evo 2 log-likelihood.
5. Write a manifest naming model, software, hashes, seeds, constraints and runtime.

It makes no functional claim. The output is a set of candidate sequences and
their scores. Nothing here establishes that any candidate is a working
regulatory element, and Evo 2 does not model chromatin accessibility at all, so
no epigenetic property is claimed or implied.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import subprocess
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from experiments.bioservices.sequence_controls import (  # noqa: E402
    dinucleotide_shuffle, gc_matched_random,
)

SEED = 0
N_SAMPLES_PER_ARM = 2
N_DESIGN_TARGETS = 8          # the remaining targets stay fully held out
FEWSHOT_K = 4                 # in-context examples, drawn only from OTHER genes
GENERATE_BP = 1000            # candidate length; with the 1 kb prompt this is <= 2 kb
TEMPERATURE = 1.0
TOP_K = 4                     # the DNA alphabet
MAX_CANDIDATES = 32


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Evo 2 zebrafish regulatory candidate generation")
    ap.add_argument("--input-set", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--model", default="evo2_7b")
    ap.add_argument("--budget-seconds", type=float, default=2400.0,
                    help="internal wall budget for generation + scoring")
    args = ap.parse_args()

    started = time.time()
    os.makedirs(args.out_dir, exist_ok=True)
    inputs = json.load(open(args.input_set))
    targets = inputs["targets"]
    design = targets[:N_DESIGN_TARGETS]
    fully_held_out = targets[N_DESIGN_TARGETS:]
    log(f"input set {inputs['input_set_id']} assembly {inputs['assembly']}: "
        f"{len(design)} design targets, {len(fully_held_out)} fully held out")

    import torch
    from evo2 import Evo2

    torch.manual_seed(SEED)
    rng = random.Random(SEED)
    log(f"loading {args.model} ...")
    t0 = time.time()
    model = Evo2(args.model)
    load_seconds = time.time() - t0
    log(f"loaded in {load_seconds:.1f}s")

    def generate(prompt: str) -> str:
        out = model.generate(prompt_seqs=[prompt], n_tokens=GENERATE_BP,
                             temperature=TEMPERATURE, top_k=TOP_K)
        return out.sequences[0].upper()

    candidates: list[dict] = []

    def flush() -> None:
        with open(os.path.join(args.out_dir, "candidates.json"), "w") as fh:
            json.dump(candidates, fh, indent=2)

    # --- Arm A: native-context continuation, following the Nature paper's shape ---
    for t in design:
        for s in range(N_SAMPLES_PER_ARM):
            if time.time() - started > args.budget_seconds:
                log("budget spent during arm A; stopping cleanly")
                flush()
                break
            seq = generate(t["prompt_seq"])
            candidates.append({
                "arm": "A_native_context",
                "target": t["symbol"], "sample": s,
                "prompt_sha256": t["prompt_sha256"],
                "sequence": seq, "sha256": sha(seq), "length": len(seq),
            })
            log(f"A {t['symbol']} s{s}: {len(seq)} bp")
            flush()

    # --- Arm B: few-shot in-context, following the UNVERIFIED Oct 29 Arc lead ---
    # The examples for a target never include that target, so nothing the model is
    # asked to continue has been shown to it as an answer.
    for t in design:
        others = [o for o in design if o["symbol"] != t["symbol"]]
        for s in range(N_SAMPLES_PER_ARM):
            if time.time() - started > args.budget_seconds or len(candidates) >= MAX_CANDIDATES:
                log("budget or candidate cap reached during arm B; stopping cleanly")
                flush()
                break
            picks = random.Random(f"{SEED}:{t['symbol']}:{s}").sample(others, FEWSHOT_K)
            shots = "".join(p["held_out_seq"] for p in picks)
            seq = generate(shots + t["prompt_seq"])
            candidates.append({
                "arm": "B_fewshot_in_context",
                "target": t["symbol"], "sample": s,
                "fewshot_examples": [p["symbol"] for p in picks],
                "prompt_sha256": t["prompt_sha256"],
                "sequence": seq, "sha256": sha(seq), "length": len(seq),
            })
            log(f"B {t['symbol']} s{s} shots={[p['symbol'] for p in picks]}: {len(seq)} bp")
            flush()

    log(f"generated {len(candidates)} candidates")

    # --- Composition-matched negative controls, built from the candidates themselves ---
    controls: list[dict] = []
    for c in candidates:
        controls.append({"kind": "dinucleotide_shuffle", "of": c["sha256"],
                         "target": c["target"], "arm": c["arm"],
                         "sequence": dinucleotide_shuffle(c["sequence"], rng)})
        gc = (c["sequence"].count("G") + c["sequence"].count("C")) / max(1, len(c["sequence"]))
        controls.append({"kind": "gc_matched_random", "of": c["sha256"],
                         "target": c["target"], "arm": c["arm"],
                         "sequence": gc_matched_random(len(c["sequence"]), gc, rng)})
    for c in controls:
        c["sha256"] = sha(c["sequence"])
    with open(os.path.join(args.out_dir, "controls.json"), "w") as fh:
        json.dump(controls, fh, indent=2)
    log(f"built {len(controls)} composition-matched controls")

    # --- Evo 2 log-likelihood over everything ---
    def score(seq: str) -> float:
        """Mean log-probability per base of ``seq`` under Evo 2."""
        ids = torch.tensor(model.tokenizer.tokenize(seq), dtype=torch.int).unsqueeze(0).to("cuda:0")
        with torch.inference_mode():
            logits, _ = model(ids)
        lp = torch.log_softmax(logits[0][:-1].float(), dim=-1)
        tgt = ids[0][1:].long()
        return float(lp.gather(-1, tgt.unsqueeze(-1)).squeeze(-1).mean())

    scored: list[dict] = []

    def add(kind: str, label: str, seq: str, extra: dict | None = None) -> None:
        rec = {"kind": kind, "label": label, "sha256": sha(seq), "length": len(seq),
               "gc": round((seq.count("G") + seq.count("C")) / max(1, len(seq)), 4),
               "evo2_mean_logprob": score(seq)}
        if extra:
            rec.update(extra)
        scored.append(rec)
        with open(os.path.join(args.out_dir, "scores.json"), "w") as fh:
            json.dump(scored, fh, indent=2)

    for t in targets:
        add("real_held_out", t["symbol"], t["held_out_seq"],
            {"fully_held_out": t in fully_held_out})
    for c in candidates:
        add("generated", f"{c['arm']}:{c['target']}:{c['sample']}", c["sequence"],
            {"arm": c["arm"], "target": c["target"], "candidate_sha256": c["sha256"]})
    for c in controls:
        add(c["kind"], f"{c['arm']}:{c['target']}", c["sequence"],
            {"arm": c["arm"], "target": c["target"], "of": c["of"]})
        if time.time() - started > args.budget_seconds * 1.5:
            log("hard budget reached during scoring; stopping cleanly")
            break
    log(f"scored {len(scored)} sequences")

    manifest = {
        "job": "zebrafish-evo2-regulatory-candidates/v1",
        "outcome_kind": "candidate generation; NOT functional design; no epigenetic claim",
        "model": {
            "checkpoint": args.model,
            "precision": "bfloat16",
            "why_not_40b": "the 40B checkpoint requires several H100s; one GPU per team",
            "license": "Apache-2.0 (ArcInstitute/evo2)",
        },
        "inference": {
            "generate_bp": GENERATE_BP, "temperature": TEMPERATURE, "top_k": TOP_K,
            "arms": ["A_native_context", "B_fewshot_in_context"],
            "fewshot_k": FEWSHOT_K, "samples_per_arm": N_SAMPLES_PER_ARM,
            "max_candidates": MAX_CANDIDATES,
        },
        "seeds": {"torch": SEED, "python_random": SEED,
                  "fewshot_selection": "random.Random(f'{SEED}:{symbol}:{sample}')"},
        "constraints": {
            "design_targets": [t["symbol"] for t in design],
            "fully_held_out": [t["symbol"] for t in fully_held_out],
            "no_target_is_its_own_fewshot_example": True,
            "held_out_never_shown_to_model": True,
        },
        "inputs": {"input_set_id": inputs["input_set_id"], "assembly": inputs["assembly"],
                   "species": inputs["species"], "n_targets": inputs["n_targets"]},
        "software": _software_versions(),
        "runtime": {
            "model_load_seconds": round(load_seconds, 1),
            "total_seconds": round(time.time() - started, 1),
            "budget_seconds": args.budget_seconds,
            "n_candidates": len(candidates), "n_controls": len(controls), "n_scored": len(scored),
        },
        "gpu": _gpu_info(),
    }
    with open(os.path.join(args.out_dir, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2)
    log(f"done in {time.time() - started:.1f}s; manifest written")
    return 0


def _software_versions() -> dict:
    out = {"python": sys.version.split()[0]}
    for mod in ("torch", "evo2", "transformer_engine", "flash_attn", "vortex"):
        try:
            out[mod] = getattr(__import__(mod), "__version__", "present")
        except Exception:
            out[mod] = "absent"
    try:
        out["pip_freeze_sha256"] = hashlib.sha256(
            subprocess.run([sys.executable, "-m", "pip", "freeze"],
                           capture_output=True, text=True, timeout=120).stdout.encode()
        ).hexdigest()
    except Exception:
        out["pip_freeze_sha256"] = "unavailable"
    return out


def _gpu_info() -> dict:
    try:
        import torch

        return {"count": torch.cuda.device_count(),
                "name": torch.cuda.get_device_name(0),
                "capability": list(torch.cuda.get_device_capability(0)),
                "total_memory_gb": round(torch.cuda.get_device_properties(0).total_memory / 1e9, 1)}
    except Exception as exc:
        return {"error": str(exc)[:200]}


if __name__ == "__main__":
    raise SystemExit(main())
