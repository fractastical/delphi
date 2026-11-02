#!/usr/bin/env python3
"""Finite threshold test for wolfram2002-ch11-13.

Capability is the set of boolean functions of two bits a system realizes.
Criteria in result.json were committed before this script was run.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
INPUTS = ((0, 0), (0, 1), (1, 0), (1, 1))


def all_functions():
    functions = []
    for code in range(16):
        functions.append(tuple((code >> i) & 1 for i in range(4)))
    return set(functions)


def elementary_capabilities():
    width = 23 - (-17) + 1
    offset = 17
    caps = []
    for rule in range(256):
        table = [(rule >> k) & 1 for k in range(8)]
        realized = set()
        for prog in range(64):
            tapes = []
            for b0, b1 in INPUTS:
                tape = bytearray(width)
                tape[offset + 0] = b0
                tape[offset + 1] = b1
                for j in range(6):
                    tape[offset + 2 + j] = (prog >> j) & 1
                tapes.append(tape)
            for _t in range(16):
                nxts = []
                outs = []
                for tape in tapes:
                    nxt = bytearray(width)
                    for i in range(width):
                        left = tape[i - 1] if i else 0
                        center = tape[i]
                        right = tape[i + 1] if i + 1 < width else 0
                        nxt[i] = table[(left << 2) | (center << 1) | right]
                    nxts.append(nxt)
                    outs.append(nxt[offset - 1])
                tapes = nxts
                realized.add(tuple(outs))
        caps.append(realized)
    return caps


def radius4_capability():
    realized = set()
    for prog in range(16):
        program = [(prog >> i) & 1 for i in range(4)]
        outs = []
        for b0, b1 in INPUTS:
            tape = [0] * 9  # positions -4..4
            tape[0] = program[0]
            tape[1] = program[1]
            tape[2] = program[2]
            tape[3] = program[3]
            tape[4] = 0
            tape[5] = b0
            tape[6] = b1
            index = tape[5] + 2 * tape[6]
            outs.append(tape[index])
        realized.add(tuple(outs))
    return realized


def turing_capability():
    realized = set()
    for prog in range(16):
        program = [(prog >> i) & 1 for i in range(4)]
        outs = []
        for b0, b1 in INPUTS:
            tape = [0, b0, b1, program[0], program[1], program[2], program[3]]
            head = 1
            seen_b0 = tape[head]
            head += 1
            seen_b1 = tape[head]
            head += 1  # on p00
            head += seen_b0 + 2 * seen_b1
            bit = tape[head]
            tape[0] = bit
            outs.append(tape[0])
        realized.add(tuple(outs))
    return realized


def main():
    universe = all_functions()
    caps = elementary_capabilities()
    cap_r4 = radius4_capability()
    cap_tm = turing_capability()
    cap0 = caps[0]
    sizes = [len(c) for c in caps]
    histogram = {}
    for size in sizes:
        histogram[str(size)] = histogram.get(str(size), 0) + 1
    full = [i for i, c in enumerate(caps) if c == universe]
    too_big = [i for i, c in enumerate(caps) if len(c) > 16]
    best = max(range(256), key=lambda i: (sizes[i], -i))
    if len(cap_r4) < 16 or len(cap_tm) < 16:
        verdict, confidence, reason = "inconclusive", 0.50, "underpowered"
    elif len(cap0) >= 16 or too_big:
        verdict, confidence, reason = "refutes", 0.80, None
    elif (
        cap_r4 == cap_tm == universe
        and len(cap0) <= 4
        and all(len(c) <= 16 for c in caps)
        and all(c == universe for c in caps if len(c) == 16)
    ):
        verdict, confidence, reason = "supports", 0.84, None
    else:
        verdict, confidence, reason = "mixed", 0.70, None
    measured = {
        "value": len(cap_r4.symmetric_difference(cap_tm)),
        "unit": "boolean functions of two bits realized by one ceiling system and not the other",
        "n": 16,
        "uncertainty": "exact",
        "extra": {
            "rule_0_capability": len(cap0),
            "rule_110_capability": len(caps[110]),
            "rule_30_capability": len(caps[30]),
            "rule_90_capability": len(caps[90]),
            "radius4_capability": len(cap_r4),
            "turing_capability": len(cap_tm),
            "ceilings_equal_full_set": cap_r4 == cap_tm == universe,
            "elementary_size_histogram": histogram,
            "elementary_rules_at_16": full,
            "best_elementary_rule": best,
            "best_elementary_capability": sizes[best],
            "distinct_elementary_sizes": len(histogram),
            "elementary_rules_over_16": too_big,
        },
    }
    method = (
        "analysis.py evolves all 256 elementary rules from 64 six-bit programs and four input pairs "
        "for 16 steps and reads the cell at position -1. It runs one radius-4 multiplexer, whose new "
        "center is the program bit indexed by the two input bits, and a Turing machine that walks "
        "from the input bits to that same program bit and writes it on the output cell. A function "
        "is realized when one program makes all four inputs match it. Criteria were frozen in commit "
        "093ca8002a77b774b469b965ff599d123fdaefbb before this run."
    )
    datasets = [{
        "id": "boolean-capability-threshold",
        "name": "Boolean-function capabilities of elementary rules 0..255, one radius-4 multiplexer, and one lookup Turing machine, generated by analysis.py",
        "landing_url": "https://www.wolframscience.com/nks/p675--the-rule-110-cellular-automaton/",
        "doi": None,
        "version": "generated",
        "license": None,
        "generator": "analysis.py",
        "program_family": (
            "elementary Wolfram rules 0..255, fixed-0 boundary, output at -1, inputs at 0 and 1, "
            "6 program bits at 2..7, t=1..16; radius-4 binary rule reading program bits at -4..-1 "
            "and inputs at +1,+2; 2-symbol Turing machine on tape [output, b0, b1, p00, p01, p10, p11]"
        ),
        "files": [],
        "role": "the systems whose sets of two-bit boolean functions are compared",
    }]
    caveats = [
        "The computation shows that these programs realize the same set of two-bit boolean functions once they can realize all 16, and that rule 0 realizes fewer. It does not show that organisms compute, and it does not prove Turing universality.",
        "The universe of computations is the 16 functions of two bits. Past that ceiling there is no further function of two bits to gain. A richer universe, such as all partial recursive functions, was not enumerated.",
        f"The largest elementary capability under this encoding is {sizes[best]} functions, at rule {best}. "
        + (
            "Some elementary rule reaches the same set of 16."
            if full
            else "No elementary rule reaches all 16 functions under this encoding; the ceiling is witnessed by the radius-4 rule and the Turing machine."
        ),
    ]
    path = os.path.join(HERE, "result.json")
    with open(path) as f:
        result = json.load(f)
    frozen_keys = (
        "claim_id", "claim_iri", "project", "hypothesis", "pass_criterion", "fail_criterion",
        "planned_datasets", "interpretation", "test_contract", "agent",
    )
    frozen = {k: result[k] for k in frozen_keys}
    result.update({
        "status": "complete",
        "data_kind": "computational",
        "verdict": verdict,
        "confidence": confidence,
        "measured": measured,
        "method": method,
        "datasets": datasets,
        "caveats": caveats,
    })
    if reason:
        result["reason"] = reason
    elif "reason" in result:
        del result["reason"]
    for k, v in frozen.items():
        result[k] = v
    with open(path, "w") as f:
        json.dump(result, f, indent=2)
        f.write("\n")
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measured.json"), "w") as f:
        json.dump({"verdict": verdict, "confidence": confidence, "measured": measured}, f, indent=2)
        f.write("\n")
    print(json.dumps({
        "verdict": verdict,
        "confidence": confidence,
        "rule0": len(cap0),
        "rule110": len(caps[110]),
        "best": best,
        "best_size": sizes[best],
        "histogram": histogram,
        "r4": len(cap_r4),
        "tm": len(cap_tm),
        "at16": full,
    }, indent=2))


if __name__ == "__main__":
    main()
