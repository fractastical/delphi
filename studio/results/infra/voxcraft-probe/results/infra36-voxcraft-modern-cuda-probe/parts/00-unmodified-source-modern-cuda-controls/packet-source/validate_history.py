#!/usr/bin/env python3
"""Validate a voxcraft-sim .history file against the structure its source actually emits.

The expected format was read from voxcraft-sim at commit
dd8668f99ff74fb2fc2ee60deb91287a3b519d8f, NOT from documentation:

  src/VX3/VX3_SimulationManager.cu:40-48   {{{setting}}}<rescale>, <matcolor>, <voxel_size>
  src/VX3/VX3_SimulationManager.cu:56-57   "real_stepsize: N ; recommendedTimeStep F; ..."
  src/VX3/VX3_SimulationManager.cu:70-89   "<<<Step{j} Time:{t}>>>" then, per SURFACE voxel,
                                           15 comma-terminated numeric fields then ';',
                                           then "<<<>>>"

  The 15 fields, in order:
    0-2   pos.x, pos.y, pos.z                       (metres * 1000, %.1f)
    3     orient.AngleDegrees()                     (%.1f)
    4-6   orient.x, orient.y, orient.z              (%.2f)
    7-9   cornerOffset(NNN).x/.y/.z                 (metres * 1000, %.1f)
    10-12 cornerOffset(PPP).x/.y/.z                 (metres * 1000, %.1f)
    13    mat->matid                                (%d)
    14    localSignal                               (%.1f)

  cornerOffset = (0.5 * baseSize()).Scale(strains)  [src/VX3/VX3_Voxel.cu:147-158]
  and baseSize() carries the thermal factor, so (PPP.x - NNN.x) is the voxel's
  current x extent including both thermal actuation and elastic strain. That is
  the quantity the actuation discriminator uses.

NOTE ON A SILENT FAILURE MODE: the history is written by printf from INSIDE a
__global__ kernel, so it passes through the CUDA device printf FIFO ring buffer
(enlarged by VXA.GPU.PrintfFIFOSize, default multiplier 50). If that buffer
overflows, lines are DROPPED SILENTLY. A "file is non-empty" check would pass on
truncated output. That is why step indices are checked for exact contiguity at
the stride the program itself reports, rather than merely for presence.

Exit 0 only if every check passes. Exit 2 on a structural failure, 3 on a
discriminator failure, 4 on inconclusive.
"""
import sys, re, json, math, argparse

FIELDS = 15

def parse(path):
    txt = open(path, 'r', errors='replace').read()
    out = {"bytes": len(txt), "voxel_size": None, "real_stepsize": None,
           "frames": [], "diverged": False, "errors": []}
    if "Diverged" in txt:
        out["diverged"] = True
    m = re.search(r"\{\{\{setting\}\}\}<voxel_size>([^<]+)</voxel_size>", txt)
    if m:
        try: out["voxel_size"] = float(m.group(1))
        except ValueError: out["errors"].append("voxel_size not numeric")
    m = re.search(r"real_stepsize:\s*(\d+)\s*;", txt)
    if m: out["real_stepsize"] = int(m.group(1))
    for fm in re.finditer(r"<<<Step(\d+) Time:([^>]+)>>>(.*?)<<<>>>", txt, re.S):
        step = int(fm.group(1))
        try: t = float(fm.group(2))
        except ValueError:
            out["errors"].append(f"step {step}: Time not numeric"); continue
        blocks = [b for b in fm.group(3).split(';') if b.strip()]
        vox = []
        for b in blocks:
            # The emitter writes each of the 15 fields as "<value>," so a well-formed block
            # splits into exactly 15 values plus ONE trailing empty. Do NOT filter empties
            # generally: that would silently absorb a doubled comma, which is one of the
            # shapes a truncated or interleaved device-printf stream produces.
            raw = b.split(',')
            while raw and raw[0].strip() == '':   # leading newline/whitespace between blocks
                raw.pop(0)
            if len(raw) != FIELDS + 1 or raw[-1].strip() != '':
                out["errors"].append(f"step {step}: voxel block splits into {len(raw)} comma-separated "
                                     f"items, expected {FIELDS} values plus one trailing empty")
                continue
            parts = raw[:FIELDS]
            if any(p.strip() == '' for p in parts):
                out["errors"].append(f"step {step}: voxel block has an empty field"); continue
            try: nums = [float(p) for p in parts]
            except ValueError:
                out["errors"].append(f"step {step}: non-numeric field"); continue
            if not all(math.isfinite(n) for n in nums):
                out["errors"].append(f"step {step}: non-finite field"); continue
            vox.append(nums)
        out["frames"].append({"step": step, "t": t, "n_vox": len(vox),
                              "mean_extent_x": (sum(v[10]-v[7] for v in vox)/len(vox)) if vox else None})
    return out

def extent_stats(frames):
    e = [f["mean_extent_x"] for f in frames if f["mean_extent_x"] is not None]
    if not e: return None
    return {"n": len(e), "min": min(e), "max": max(e), "ptp": max(e)-min(e), "mean": sum(e)/len(e)}

def check(p, expect_vox, min_frames):
    fail = []
    if p["bytes"] == 0: fail.append("history file is empty")
    if p["diverged"]: fail.append("simulation reported Diverged")
    if p["voxel_size"] is None or not (p["voxel_size"] > 0 and math.isfinite(p["voxel_size"])):
        fail.append("no finite positive <voxel_size> setting line")
    if p["real_stepsize"] is None or p["real_stepsize"] < 1:
        fail.append("no 'real_stepsize: N' line with N >= 1")
    fr = p["frames"]
    if len(fr) < min_frames: fail.append(f"only {len(fr)} frames, need >= {min_frames}")
    if fr:
        steps = [f["step"] for f in fr]; ts = [f["t"] for f in fr]
        if steps != sorted(steps) or len(set(steps)) != len(steps):
            fail.append("step indices not strictly increasing")
        if ts != sorted(ts): fail.append("Time not non-decreasing")
        if not all(math.isfinite(t) and t >= 0 for t in ts): fail.append("non-finite or negative Time")
        rs = p["real_stepsize"]
        if rs:
            gaps = {steps[i+1]-steps[i] for i in range(len(steps)-1)}
            if gaps and gaps != {rs}:
                fail.append(f"step stride {sorted(gaps)} != reported real_stepsize {rs}; "
                            f"history is NOT contiguous, which is the device-printf-FIFO truncation signature")
        ns = {f["n_vox"] for f in fr}
        if len(ns) != 1: fail.append(f"voxel count varies across frames: {sorted(ns)}")
        elif expect_vox and ns != {expect_vox}: fail.append(f"voxel count {ns.pop()} != expected {expect_vox}")
    fail += p["errors"][:5]
    return fail

ap = argparse.ArgumentParser()
ap.add_argument("--actuated", required=True); ap.add_argument("--passive", required=True)
ap.add_argument("--expect-voxels", type=int, default=32)
ap.add_argument("--min-frames", type=int, default=3)
ap.add_argument("--min-actuated-ptp", type=float, default=0.5,
                help="history units (mm). CTE 0.01 x amplitude 10, clipped at 0 by "
                     "EnableExpansion=0, predicts 10.0 -> 9.0 mm, so ptp ~ 1.0.")
ap.add_argument("--discriminator-ratio", type=float, default=3.0)
ap.add_argument("--out", default="validation.json")
a = ap.parse_args()

A, Pv = parse(a.actuated), parse(a.passive)
res = {"schema": "frontier.voxcraft-history-validation/1",
       "expected_structure": "see module docstring; read from source at dd8668f9",
       "actuated": {"parse": {k: v for k, v in A.items() if k != "frames"},
                    "frames": len(A["frames"]), "extent": extent_stats(A["frames"])},
       "passive":  {"parse": {k: v for k, v in Pv.items() if k != "frames"},
                    "frames": len(Pv["frames"]), "extent": extent_stats(Pv["frames"])}}
sf_a = check(A, a.expect_voxels, a.min_frames)
sf_p = check(Pv, a.expect_voxels, a.min_frames)
res["structural_failures"] = {"actuated": sf_a, "passive": sf_p}

verdict, disc = "PASS", {}
if sf_a or sf_p:
    verdict = "STRUCTURAL_FAIL"
else:
    ea, ep = res["actuated"]["extent"], res["passive"]["extent"]
    disc = {"actuated_ptp": ea["ptp"], "passive_ptp": ep["ptp"],
            "actuated_mean": ea["mean"], "passive_mean": ep["mean"],
            "min_actuated_ptp": a.min_actuated_ptp, "ratio_required": a.discriminator_ratio}
    disc["A1_actuated_moves"] = ea["ptp"] >= a.min_actuated_ptp
    disc["A2_passive_quiet"] = ep["ptp"] * a.discriminator_ratio <= ea["ptp"]
    disc["A3_actuated_contracts"] = ea["mean"] < ep["mean"]
    if not disc["A1_actuated_moves"]:
        verdict = "DISCRIMINATOR_FAIL"
        disc["reading"] = ("the actuated run's voxel extent did not change. The program ran but the "
                           "thermal actuation path did not take effect. Do NOT report this as a working build.")
    elif not disc["A2_passive_quiet"]:
        verdict = "INCONCLUSIVE"
        disc["reading"] = ("the passive control is not quiet, so the contrast does not separate actuation "
                           "from settling. Report as inconclusive, not as a pass.")
    elif not disc["A3_actuated_contracts"]:
        verdict = "INCONCLUSIVE"
        disc["reading"] = ("extent changed but did not contract on average. EnableExpansion is 0, which clips "
                           "temperature at zero, so contraction was predicted. An expansion here means the "
                           "case or the clip does not behave as the source says it does.")
    else:
        disc["reading"] = "actuated run oscillates and contracts; passive control is quiet. Mechanics only, no biological claim."
res["discriminator"] = disc
res["verdict"] = verdict
json.dump(res, open(a.out, "w"), indent=1)
print(json.dumps({"verdict": verdict, "actuated_frames": res["actuated"]["frames"],
                  "passive_frames": res["passive"]["frames"],
                  "structural_failures": res["structural_failures"],
                  "discriminator": disc}, indent=1))
sys.exit({"PASS": 0, "STRUCTURAL_FAIL": 2, "DISCRIMINATOR_FAIL": 3, "INCONCLUSIVE": 4}[verdict])
