"""Fail-closed completeness audit of the returned RD-DDPM pilot outputs. Reads files only; never edits them. `ok: true` printed by the job is NOT evidence: this checks identities and counts
from the preregistered design (see the independent review). Non-finite JSON values are located and converted to explicit status objects, never silently dropped or published as numbers."""
import hashlib, json, math, os, sys

FROZEN = {"code_sha256": "25455430ef138b49e6bac151a144e338269a81ce5c2f576387f8805bbb1a400a", "config_sha256": "bc77ebc55010b9c8ac910c2b31868ec0dbf2d1e3785a06ec3ef1aa028ea2b210"}
METHODS = ["ddpm", "ddpm_shuffled_condition", "nearest1_pooled", "nearest5_pooled", "nearest10_pooled"]      # nearest10_pooled is the deterministic MEAN-FIELD baseline
EXPECT = {"train_steps": 30000, "n_conditions": 160, "train_runs": 4200, "train_rows_if_no_failures": 16800, "ensemble_runs": 1280, "log_lines": 301,
          "test_param": {"n_runs": 600, "n_rows": 2400, "per_tau": 600}, "test_seed": {"n_runs": 300, "n_rows": 1200, "per_tau": 300}, "timing_batch": 1024, "timing_repeats": 3, "taus": [50, 100, 150, 200]}


class NonFinite(dict): pass


def load_strict(path):
    """json.load that keeps NaN/Infinity visible: returns (obj with NonFinite markers, list of JSON paths)."""
    hits = []
    obj = json.loads(open(path).read(), parse_constant=lambda c: NonFinite(status="nonfinite", token=c))
    def walk(o, p):
        if isinstance(o, NonFinite): hits.append(p)
        elif isinstance(o, dict): [walk(v, f"{p}/{k}") for k, v in o.items()]
        elif isinstance(o, list): [walk(v, f"{p}[{i}]") for i, v in enumerate(o)]
    walk(obj, ""); return obj, hits


def sha_file(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()


def audit(d):
    """d: directory holding control.json, evaluation.json, checkpoint.pt, examples.npz, train_loss.jsonl (the unpacked parts)."""
    P = []; need = lambda c, msg: P.append(msg) if not c else None
    files = ["control.json", "evaluation.json", "checkpoint.pt", "examples.npz", "train_loss.jsonl"]
    for f in files: need(os.path.exists(os.path.join(d, f)), f"missing file {f}")
    if P: return {"complete": False, "problems": P, "nonfinite_paths": []}
    ev, nf = load_strict(os.path.join(d, "evaluation.json")); ctl, nfc = load_strict(os.path.join(d, "control.json"))
    need(ctl.get("ok") is True and ctl.get("env", {}).get("cuda_available") is True, "control gate not ok on CUDA")
    need(ev.get("smoke") is False and ev.get("env", {}).get("device") == "cuda", "not a full CUDA run")
    ds = ev.get("dataset", {}); tr = ev.get("train", {})
    for k, v in FROZEN.items(): need(ds.get(k) == v, f"{k} differs from the frozen value")
    need(tr.get("steps") == EXPECT["train_steps"], f"training steps {tr.get('steps')} != {EXPECT['train_steps']}")
    need(tr.get("checkpoint_sha256") == sha_file(os.path.join(d, "checkpoint.pt")), "checkpoint sha256 in evaluation.json does not match the returned file")
    need(ds.get("train", {}).get("runs") == EXPECT["train_runs"], "training run count")
    need(ds.get("train", {}).get("rows") == EXPECT["train_rows_if_no_failures"] - 4 * ds.get("train", {}).get("failed_runs", 0), "training row count inconsistent with failed runs")
    need(sum(1 for _ in open(os.path.join(d, "train_loss.jsonl"))) == EXPECT["log_lines"] or open(os.path.join(d, "train_loss.jsonl")).read().count("\n") + 1 == EXPECT["log_lines"], "training loss log length")
    ee = ev.get("ensemble_eval", {}); per = ee.get("per_condition", [])
    need(len(per) == EXPECT["n_conditions"] and ee.get("n_conditions") == EXPECT["n_conditions"], f"conditions {len(per)}/{ee.get('n_conditions')} != {EXPECT['n_conditions']}")
    need(ee.get("ensemble_failed_runs") == 0, f"ensemble solver runs failed: {ee.get('ensemble_failed_runs')} (retain and interpret under the original failure rule)")
    skipped = [r for r in per if "skipped" in r]; need(not skipped, f"{len(skipped)} skipped conditions")
    miss = [(r.get("setting_id"), r.get("tau")) for r in per if any(m not in r for m in METHODS)]; need(not miss, f"{len(miss)} conditions lack one of the five methods")
    need(sorted({r.get("tau") for r in per}) == EXPECT["taus"], "snapshot times")
    mg = ev.get("held_out_marginals", {})
    for name, e in (("test_param", EXPECT["test_param"]), ("test_seed", EXPECT["test_seed"])):
        m = mg.get(name, {}) if isinstance(mg, dict) else {}
        need(m.get("n_runs") == e["n_runs"] and m.get("n_rows") == e["n_rows"], f"{name} counts {m.get('n_runs')}/{m.get('n_rows')}")
        need(all(m.get("by_tau", {}).get(str(t), {}).get("n") == e["per_tau"] for t in EXPECT["taus"]), f"{name} per-tau counts")
    tm = ev.get("timings", {}); need(tm.get("batch") == EXPECT["timing_batch"] and len(tm.get("ddpm_sampling_seconds", [])) == EXPECT["timing_repeats"], "timing protocol")
    need(ev.get("train", {}).get("frozen_before_holdout_generation") is True, "freeze flag")
    return {"complete": not P, "problems": P, "nonfinite_paths": nf + nfc, "train_failed_runs_disclosed": ds.get("train", {}).get("failed_runs"),
            "note": "complete=false is a failed or partial run, never an empty valid result; non-finite entries must be shown as status 'nonfinite', not as numbers"}


if __name__ == "__main__":
    r = audit(sys.argv[1]); print(json.dumps(r, indent=1)); sys.exit(0 if r["complete"] else 4)
