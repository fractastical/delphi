#!/usr/bin/env python3
"""Mutual emulation of elementary cellular automata, a Turing machine,
a register machine and a sequential substitution system.

Criteria in result.json were committed before this script was run.
"""
import itertools
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
W = 5
T_STEPS = 3


def eca_step(rule, row):
    width = len(row)
    out = []
    for i in range(width):
        left = row[(i - 1) % width]
        center = row[i]
        right = row[(i + 1) % width]
        out.append((rule >> (4 * left + 2 * center + right)) & 1)
    return tuple(out)


def substitution_step(rule, row):
    cells = list(row)
    p = cells[-1]
    f = cells[0]
    tape = cells + ["E"]
    i = 0
    result = []
    steps = 0
    while True:
        steps += 1
        if steps > 100:
            return None
        center = tape[i]
        nxt = tape[i + 1]
        if nxt == "E":
            result.append((rule >> (4 * p + 2 * center + f)) & 1)
            return tuple(result)
        result.append((rule >> (4 * p + 2 * center + nxt)) & 1)
        p = center
        i += 1


def turing_step(rule, row):
    tape = list(row) + ["E"]
    head = 0
    p = row[-1]
    f = row[0]
    steps = 0
    while True:
        steps += 1
        if steps > 100:
            return None
        center = tape[head]
        nxt = tape[head + 1]
        if nxt == "E":
            tape[head] = (rule >> (4 * p + 2 * center + f)) & 1
            return tuple(tape[:W])
        tape[head] = (rule >> (4 * p + 2 * center + nxt)) & 1
        p = center
        head += 1


# Register machine: INC, DEC, JZ, HALT.
Z, ROW, OUT, TMP, BACK, QUOT, REM, AUX, RULE = range(9)
B0 = 9
RB0 = 14
IDX, SEL, J, STEPS = 22, 23, 24, 25
NREGS = 26


class Asm:
    def __init__(self):
        self.code = []
        self.labels = {}
        self.n = 0

    def tag(self, name):
        self.n += 1
        return f"{name}{self.n}"

    def lab(self, name):
        self.labels[name] = len(self.code)

    def op(self, *parts):
        self.code.append(parts)

    def jz(self, reg, name):
        self.code.append(("jz", reg, name))

    def jmp(self, name):
        self.jz(Z, name)

    def clr(self, reg, name):
        t = self.tag(name)
        self.lab(t)
        self.jz(reg, t + "d")
        self.op("dec", reg)
        self.jmp(t)
        self.lab(t + "d")

    def copy(self, src, dst, name):
        t = self.tag(name)
        self.clr(dst, t + "d")
        self.clr(BACK, t + "b")
        self.lab(t + "l")
        self.jz(src, t + "r")
        self.op("dec", src)
        self.op("inc", dst)
        self.op("inc", BACK)
        self.jmp(t + "l")
        self.lab(t + "r")
        self.jz(BACK, t + "e")
        self.op("dec", BACK)
        self.op("inc", src)
        self.jmp(t + "r")
        self.lab(t + "e")

    def div2(self, name):
        """TMP -> QUOT = TMP//2, REM = TMP%2, TMP = 0. TMP holds  the input."""
        t = self.tag(name)
        self.clr(QUOT, t + "q")
        self.clr(REM, t + "m")
        self.lab(t + "l")
        self.jz(TMP, t + "d")
        self.op("dec", TMP)
        self.op("inc", REM)
        self.copy(REM, AUX, t + "c")
        self.op("dec", AUX)
        self.jz(AUX, t + "one")
        self.clr(REM, t + "z")
        self.op("inc", QUOT)
        self.jmp(t + "l")
        self.lab(t + "one")
        self.jmp(t + "l")
        self.lab(t + "d")

    def finish(self):
        resolved = []
        for ins in self.code:
            if ins[0] == "jz" and isinstance(ins[2], str):
                resolved.append(("jz", ins[1], self.labels[ins[2]]))
            else:
                resolved.append(ins)
        resolved.append(("halt",))
        return resolved


def build_program():
    a = Asm()
    # STEPS = 3, then repeat the body.
    a.op("inc", STEPS)
    a.op("inc", STEPS)
    a.op("inc", STEPS)
    # rule bits once; RULE is constant
    a.copy(RULE, TMP, "rulecopy")
    for i in range(8):
        a.div2(f"rb{i}")
        a.clr(RB0 + i, f"rbc{i}")
        a.jz(REM, f"rbz{i}")
        a.op("inc", RB0 + i)
        a.lab(f"rbz{i}")
        a.copy(QUOT, TMP, f"rbq{i}")
    a.lab("loop")
    a.jz(STEPS, "done")
    a.op("dec", STEPS)
    a.clr(OUT, "out")
    # split ROW into B0..B4, bit 0 first
    a.copy(ROW, TMP, "rowcopy")
    for i in range(W):
        a.div2(f"cb{i}")
        a.clr(B0 + i, f"cbc{i}")
        a.jz(REM, f"cbz{i}")
        a.op("inc", B0 + i)
        a.lab(f"cbz{i}")
        a.copy(QUOT, TMP, f"cbq{i}")
    for i in range(W):
        left = B0 + ((i - 1) % W)
        center = B0 + i
        right = B0 + ((i + 1) % W)
        tag = f"cell{i}"
        a.clr(IDX, tag + "i")
        a.jz(left, tag + "nol")
        a.op("inc", IDX)
        a.op("inc", IDX)
        a.op("inc", IDX)
        a.op("inc", IDX)
        a.lab(tag + "nol")
        a.jz(center, tag + "noc")
        a.op("inc", IDX)
        a.op("inc", IDX)
        a.lab(tag + "noc")
        a.jz(right, tag + "nor")
        a.op("inc", IDX)
        a.lab(tag + "nor")
        a.clr(SEL, tag + "s")
        a.jz(IDX, tag + "u0")
        a.copy(IDX, J, tag + "j")
        for k in range(1, 8):
            a.op("dec", J)
            a.jz(J, tag + f"u{k}")
        a.jmp(tag + "end")
        for k in range(8):
            a.lab(tag + f"u{k}")
            a.jz(RB0 + k, tag + "end")
            a.op("inc", SEL)
            a.jmp(tag + "end")
        a.lab(tag + "end")
        a.jz(SEL, tag + "noadd")
        for _ in range(1 << i):
            a.op("inc", OUT)
        a.lab(tag + "noadd")
    a.copy(OUT, ROW, "commit")
    commit_jump = len(a.code)
    a.jmp("loop")
    a.lab("done")
    return a.finish(), commit_jump


def run_machine(code, commit_jump, row, rule, budget):
    regs = [0] * NREGS
    regs[ROW] = row
    regs[RULE] = rule
    ip = 0
    steps = 0
    snapshots = []
    while steps < budget:
        if ip == commit_jump:
            snapshots.append(regs[ROW])
        ins = code[ip]
        steps += 1
        op = ins[0]
        if op == "halt":
            return snapshots, steps, True
        if op == "inc":
            regs[ins[1]] += 1
            ip += 1
        elif op == "dec":
            reg = ins[1]
            if regs[reg]:
                regs[reg] -= 1
            ip += 1
        elif op == "jz":
            ip = ins[2] if regs[ins[1]] == 0 else ip + 1
        else:
            raise RuntimeError(op)
    return snapshots, steps, False


def forward():
    code, commit_jump = build_program()
    mismatched = {"substitution": 0, "turing": 0, "register": 0}
    budget_hits = 0
    max_reg_steps = 0
    for rule in range(256):
        for seed in range(1 << W):
            row = tuple((seed >> i) & 1 for i in range(W))
            sub = row
            tur = row
            eca = row
            expected_rows = []
            for _ in range(T_STEPS):
                eca = eca_step(rule, eca)
                expected_rows.append(eca)
                sub = substitution_step(rule, sub)
                tur = turing_step(rule, tur)
                if sub is None or tur is None:
                    budget_hits += 1
                    mismatched["substitution"] += W
                    mismatched["turing"] += W
                    break
                mismatched["substitution"] += sum(a != b for a, b in zip(sub, eca))
                mismatched["turing"] += sum(a != b for a, b in zip(tur, eca))
            snapshots, used, halted = run_machine(code, commit_jump, seed, rule, 100000 * T_STEPS)
            max_reg_steps = max(max_reg_steps, used)
            if not halted or len(snapshots) != T_STEPS:
                budget_hits += 1
                mismatched["register"] += W * T_STEPS
            else:
                for got, expect in zip(snapshots, expected_rows):
                    mismatched["register"] += sum(
                        ((got >> i) & 1) != expect[i] for i in range(W)
                    )
    return mismatched, budget_hits, max_reg_steps, len(code)


def flip_tm(tape, head, state):
    tape = list(tape)
    symbol = tape[head]
    if state == "Q" and symbol == 0:
        tape[head] = 1
        head = (head + 1) % len(tape)
    elif state == "Q" and symbol == 1:
        tape[head] = 1
        state = "H"
    return tuple(tape), head, state


def colors_of(tape, head, state):
    colors = []
    for i, symbol in enumerate(tape):
        if i == head and state == "Q":
            colors.append(2 if symbol == 0 else 3)
        elif i == head and state == "H":
            colors.append(4 if symbol == 0 else 5)
        else:
            colors.append(symbol)
    return tuple(colors)


def ca6_step(colors):
    out = []
    width = len(colors)
    for i in range(width):
        left = colors[(i - 1) % width]
        center = colors[i]
        if center == 2:
            out.append(1)
        elif center == 3:
            out.append(5)
        elif center in (0, 1) and left == 2:
            out.append(2 if center == 0 else 3)
        else:
            out.append(center)
    return tuple(out)


def reverse():
    mismatched = 0
    for bits in itertools.product((0, 1), repeat=6):
        for head0 in range(6):
            tape, head, state = bits, head0, "Q"
            colors = colors_of(tape, head, state)
            for _ in range(6):
                tape, head, state = flip_tm(tape, head, state)
                colors = ca6_step(colors)
                if colors != colors_of(tape, head, state):
                    mismatched += 1
    return mismatched


def main():
    mismatched, budget_hits, max_reg_steps, program_length = forward()
    reverse_bad = reverse()
    forward_bad = sum(mismatched.values())
    if budget_hits:
        verdict, confidence, reason = "inconclusive", 0.45, "other"
    elif forward_bad:
        verdict, confidence, reason = "refutes", 0.88, None
    elif reverse_bad:
        verdict, confidence, reason = "mixed", 0.70, None
    else:
        verdict, confidence, reason = "supports", 0.86, None
    measured = {
        "value": forward_bad + reverse_bad,
        "unit": "cell or step disagreements between emulators",
        "n": 256 * (1 << W) * T_STEPS * W,
        "uncertainty": "exact",
        "extra": {
            "forward_mismatched_cells": forward_bad,
            "mismatched_by_emulator": mismatched,
            "reverse_mismatched_steps": reverse_bad,
            "register_budget_hits": budget_hits,
            "register_max_instructions_executed": max_reg_steps,
            "register_program_length": program_length,
            "rules": 256,
            "width": W,
            "steps": T_STEPS,
        },
    }
    method = (
        "analysis.py evolves every elementary rule on every periodic row of width 5 for 3 steps, "
        "and evolves the same rows with a sequential substitution system and a Turing machine that "
        "carry the original first bit in their finite control, and with one register-machine program "
        "of INC, DEC and JZ instructions that extracts periodic bits and writes the rule bit. "
        "In the other direction a six-color radius-1 cellular automaton is compared with the "
        "flip-zeros Turing machine on every tape of length 6, every head position and 6 steps. "
        "Criteria were frozen in commit 093ca8002a77b774b469b965ff599d123fdaefbb before this run."
    )
    datasets = [{
        "id": "cross-system-emulation-eca",
        "name": "Elementary rules 0..255 emulated by a Turing machine, a register machine and a sequential substitution system, plus one six-color cellular automaton emulating flip-zeros, generated by analysis.py",
        "landing_url": "https://www.wolframscience.com/nks/p674--implications-of-universality/",
        "doi": None,
        "version": "generated",
        "license": None,
        "generator": "analysis.py",
        "program_family": (
            "periodic elementary cellular automata, Wolfram rules 0..255, width 5, 3 steps; "
            "2-symbol-plus-endmarker Turing machine and sequential substitution system with marker state M_(p,f); "
            "register machine with INC, DEC, JZ, HALT; "
            "reverse: 6-color radius-1 cellular automaton and the flip-zeros Turing machine, ring length 6, 6 steps"
        ),
        "files": [],
        "role": "the programs whose configurations are compared cell by cell",
    }]
    caveats = [
        "The computation shows that these particular programs produce the same configurations on the pre-registered boxes. It does not show that organisms follow the claim, and it does not show that every rule of every kind is universal.",
        "The forward emulators are general elementary-rule interpreters: the same substitution rules, Turing control and register program run every Wolfram number from 0 through 255. The reverse direction is one Turing machine, not every Turing machine.",
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
        "forward": mismatched,
        "reverse": reverse_bad,
        "budget_hits": budget_hits,
        "max_reg_steps": max_reg_steps,
        "program_length": program_length,
    }, indent=2))


if __name__ == "__main__":
    main()
