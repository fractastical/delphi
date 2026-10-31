#!/usr/bin/env python3
"""Test of wolfram2002-ch03-08: census of all 2-state and 3-state 2-colour Turing machines
from a blank tape (NKS conventions and numbering), classified by the subword complexity of
their step-letter sequences. Writes derived/measurements.json.
"""
import json
import lzma
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
K = 2
T1, W1_START = 1000, 200
T2, W2_START = 20000, 10000
T3, W3_START = 200000, 100000
N1, N2 = 12, 64
FLAG_P12 = 200
COMPLEX_P64_STAGE2, LOW_P64 = 2500, 1280
COMPLEX_P64_STAGE3 = 25000
CHUNK = 100_000
TOP_K = 200


def rule_tables(numbers, s, k=K):
    """NKS numbering (p. 888): returns arrays new_state[M, s*k], new_colour[M, s*k], move[M, s*k]
    indexed by (state-1)*k + colour."""
    numbers = np.asarray(numbers, dtype=np.int64)
    base = 2 * s * k
    n_dig = s * k
    digits = np.empty((len(numbers), n_dig), dtype=np.int64)
    x = numbers.copy()
    for j in range(n_dig - 1, -1, -1):  # least significant digit last
        digits[:, j] = x % base
        x //= base
    # digit at row i (state i+1), column j corresponds to colour k-1-j
    new_state = (digits // (2 * k)) % s  # 0-based state
    new_colour = (digits // 2) % k
    move = 2 * (digits % 2) - 1
    # reorder columns so index = state*k + colour
    idx = np.array([i * k + (k - 1 - j) for i in range(s) for j in range(k)])
    out = [np.empty_like(a) for a in (new_state, new_colour, move)]
    for src, dst in enumerate(idx):
        out[0][:, dst] = new_state[:, src]
        out[1][:, dst] = new_colour[:, src]
        out[2][:, dst] = move[:, src]
    return out


def run_machines(numbers, s, steps, letter_start):
    """Vectorised evolution from a blank tape. Returns letters[M, steps-letter_start] = state*k + colour read."""
    ns, nc, mv = rule_tables(numbers, s)
    M = len(numbers)
    width = 2 * steps + 3
    tape = np.zeros((M, width), dtype=np.uint8)
    pos = np.full(M, steps + 1, dtype=np.int64)
    state = np.zeros(M, dtype=np.int64)
    rows = np.arange(M)
    letters = np.empty((M, steps - letter_start), dtype=np.uint8)
    for t in range(steps):
        colour = tape[rows, pos].astype(np.int64)
        key = state * K + colour
        if t >= letter_start:
            letters[:, t - letter_start] = key
        tape[rows, pos] = nc[rows, key]
        pos += mv[rows, key]
        state = ns[rows, key]
    return letters


def factor_counts(letters, n, alphabet=6):
    """p(n) per row of a [M, L] letter array: sorted rolling codes when alphabet^n fits int64,
    otherwise exact counting of distinct n-byte windows per row."""
    M, Lw = letters.shape
    n_pos = Lw - n + 1
    if alphabet ** n > 2 ** 62:
        out = np.empty(M, dtype=np.int64)
        for i in range(M):
            win = np.lib.stride_tricks.sliding_window_view(np.ascontiguousarray(letters[i]), n)
            v = np.ascontiguousarray(win).view(np.dtype((np.void, n)))
            out[i] = len(np.unique(v))
        return out
    code = np.zeros((M, n_pos), dtype=np.int64)
    lt = letters.astype(np.int64)
    for j in range(n):
        code = code * alphabet + lt[:, j:j + n_pos]
    code.sort(axis=1)
    return (np.diff(code, axis=1) != 0).sum(axis=1) + 1


def lzma_ratio(seq):
    raw = bytes(seq.astype(np.uint8))
    return len(lzma.compress(raw, preset=9 | lzma.PRESET_EXTREME)) / len(raw)


def stage1(s):
    total = (2 * s * K) ** (s * K)
    flagged, p12_hist = [], np.zeros(801, dtype=np.int64)
    top = []  # (p12, number) of the highest-complexity machines, for the supplementary check
    t0 = time.time()
    for start in range(0, total, CHUNK):
        nums = np.arange(start, min(total, start + CHUNK))
        letters = run_machines(nums, s, T1, W1_START)
        p12 = factor_counts(letters, N1)
        p12_hist += np.bincount(p12, minlength=801)[:801]
        flagged.extend(nums[p12 > FLAG_P12].tolist())
        order = np.argsort(-p12)[:TOP_K]
        top = sorted(top + [(int(p12[i]), int(nums[i])) for i in order], reverse=True)[:TOP_K]
        print(f"  s={s} machines {start}-{nums[-1]}: flagged so far {len(flagged)} ({time.time() - t0:.0f}s)", flush=True)
    return {"n_machines": total, "n_flagged": len(flagged), "max_p12": int(np.flatnonzero(p12_hist)[-1]),
            "p12_histogram_nonzero": {int(i): int(c) for i, c in enumerate(p12_hist) if c}, "seconds": time.time() - t0,
            "top_k_numbers": [n for _, n in top]}, flagged


def classify_p64(p, complex_thr):
    return "complex" if p >= complex_thr else ("low" if p <= LOW_P64 else "unclear")


def stage2(numbers, s):
    out = []
    for start in range(0, len(numbers), 2000):
        nums = np.array(numbers[start:start + 2000])
        letters = run_machines(nums, s, T2, W2_START)
        p64 = factor_counts(letters, N2)
        p8, p16, p32 = factor_counts(letters, 8), factor_counts(letters, 16), factor_counts(letters, 32)
        for i, n in enumerate(nums):
            out.append({"number": int(n), "p8": int(p8[i]), "p16": int(p16[i]), "p32": int(p32[i]), "p64": int(p64[i]),
                        "class": classify_p64(int(p64[i]), COMPLEX_P64_STAGE2), "lzma": lzma_ratio(letters[i])})
    return out


def stage3(numbers, s):
    out = []
    for n in numbers:
        letters = run_machines(np.array([n]), s, T3, W3_START)
        p64 = int(factor_counts(letters, N2)[0])
        out.append({"number": int(n), "p64": p64, "p32": int(factor_counts(letters, 32)[0]),
                    "class": classify_p64(p64, COMPLEX_P64_STAGE3), "lzma": lzma_ratio(letters[0])})
    return out


def top_machine_profile(number, s):
    """Supplementary: factor-complexity profile p(n) at Stage-3 scale (window of the last 100000 of 200000 letters),
    compressibility, head extent, and the lengths of the first head sweeps (gaps between turning times)."""
    letters = run_machines(np.array([number]), s, T3, W3_START)
    prof = {str(n): int(factor_counts(letters, n)[0]) for n in (8, 16, 32, 64, 128, 256, 512)}
    ns, nc, mv = rule_tables(np.array([number]), s)
    steps = 20000
    tape = np.zeros(2 * steps + 3, dtype=np.uint8)
    pos, state, path = steps + 1, 0, []
    for _ in range(steps):
        key = state * K + int(tape[pos])
        tape[pos] = nc[0, key]
        pos += int(mv[0, key])
        state = int(ns[0, key])
        path.append(pos - steps - 1)
    path = np.array(path)
    turns = np.flatnonzero(np.diff(np.sign(np.diff(path)))) + 1
    return {"number": int(number), "p_n_window_100000": prof, "lzma": lzma_ratio(letters[0]),
            "class_at_stage3_thresholds": classify_p64(prof["64"], COMPLEX_P64_STAGE3),
            "head_extent_after_20000_steps": [int(path.min()), int(path.max())],
            "n_direction_reversals_in_20000_steps": int(len(turns)),
            "first_40_sweep_lengths": np.diff(turns[:41]).tolist()}


def controls():
    rng = np.random.default_rng(20261031)
    L = T2 - W2_START
    periodic = np.tile(np.array([0, 3, 1, 4, 2, 5, 1, 1, 4], dtype=np.uint8), L // 9 + 1)[:L]
    idx = np.arange(L, dtype=np.uint64)
    tm = np.zeros(L, dtype=np.uint64)
    v = idx.copy()
    while v.any():
        tm ^= v & 1
        v >>= np.uint64(1)
    # nested control: Thue-Morse over 2 letters, interleaved with its own shift to use 4 letters
    nested = (tm * 2 + np.roll(tm, 1)).astype(np.uint8)
    random = rng.integers(0, 6, L, dtype=np.uint8)
    out = {}
    for name, seq in (("periodic", periodic), ("thue_morse_nested", nested), ("random_6_letters", random)):
        p64 = int(factor_counts(seq[None, :], N2)[0])
        out[name] = {"p12": int(factor_counts(seq[None, :800], N1)[0]), "p64": p64, "class": classify_p64(p64, COMPLEX_P64_STAGE2), "lzma": lzma_ratio(seq)}
    return out


def main():
    results = {"controls": controls()}
    print("controls:", results["controls"], flush=True)
    for s in (2, 3):
        st1, flagged = stage1(s)
        print(f"s={s} stage 1:", {k: v for k, v in st1.items() if k != "p12_histogram_nonzero"}, flush=True)
        st2 = stage2(flagged, s) if flagged else []
        unclear = [r["number"] for r in st2 if r["class"] == "unclear"]
        complex2 = [r for r in st2 if r["class"] == "complex"]
        print(f"s={s} stage 2: {len(st2)} run, complex {len(complex2)}, unclear {len(unclear)}", flush=True)
        st3 = stage3(unclear, s) if unclear else []
        complex3 = [r for r in st3 if r["class"] == "complex"]
        unclear3 = [r for r in st3 if r["class"] == "unclear"]
        print(f"s={s} stage 3: {len(st3)} run, complex {len(complex3)}, unclear {len(unclear3)}", flush=True)
        # supplementary (not part of the criteria): stage-2 statistics for the TOP_K highest-p12 machines
        sup = stage2(st1["top_k_numbers"], s)
        top = max(sup, key=lambda r: r["p64"])["number"]
        results[f"s{s}"] = {
            "supplementary_top_k_stage2": {"n": len(sup), "max_p64": max(r["p64"] for r in sup), "max_lzma": max(r["lzma"] for r in sup),
                                           "n_classed_complex": sum(r["class"] == "complex" for r in sup), "n_classed_unclear": sum(r["class"] == "unclear" for r in sup),
                                           "top5": sorted(sup, key=lambda r: -r["p64"])[:5]},
            "supplementary_top_machine_stage3_scale": top_machine_profile(top, s),
            "stage1": st1,
            "stage2": {"n_run": len(st2), "n_complex": len(complex2), "n_low": sum(r["class"] == "low" for r in st2), "n_unclear": len(unclear),
                       "max_p64": max([r["p64"] for r in st2], default=0), "top10_by_p64": sorted(st2, key=lambda r: -r["p64"])[:10]},
            "stage3": {"n_run": len(st3), "n_complex": len(complex3), "n_unclear": len(unclear3), "records": st3},
            "complex_machines": [r["number"] for r in complex2 + complex3],
        }
    ctrl_ok = (results["controls"]["periodic"]["class"] == "low" and results["controls"]["thue_morse_nested"]["class"] == "low"
               and results["controls"]["random_6_letters"]["class"] == "complex")
    n_complex = sum(len(results[f"s{s}"]["complex_machines"]) for s in (2, 3))
    n_unclear = sum(results[f"s{s}"]["stage3"]["n_unclear"] for s in (2, 3))
    verdict = "refutes" if n_complex > 0 else ("supports" if ctrl_ok and n_unclear == 0 else "mixed")
    results["criteria"] = {"controls_ok": ctrl_ok, "n_complex": n_complex, "n_unclear_after_stage3": n_unclear}
    results["verdict"] = verdict
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measurements.json"), "w") as f:
        json.dump(results, f, indent=1)
    print(json.dumps({k: v for k, v in results.items() if k not in ("s2", "s3")}, indent=1))
    for s in (2, 3):
        print(f"s={s}:", json.dumps({k: v for k, v in results[f"s{s}"].items() if k != "stage1"}, indent=1)[:3000])


if __name__ == "__main__":
    sys.exit(main())
