#!/usr/bin/env python3
"""Emulation of cyclic elementary cellular automata by a Turing machine, a
head-carrying cellular automaton, and a register machine
(wolfram2002-ch11-12).

Width 8, every rule, every initial condition, 5 steps.
Neighbor convention: left = bit (i+1) mod 8, right = bit (i-1) mod 8.
Writes derived/measured.json.
"""
import itertools
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
W = 8

# Register indices.
Z, C, RULE, OUT, TMP, TMP2, REM, CNT = range(8)
B0 = 8  # B0..B7
NREG = 16


def step_int(rule, c):
    out = 0
    for i in range(W):
        left = (c >> ((i + 1) % W)) & 1
        center = (c >> i) & 1
        right = (c >> ((i - 1) % W)) & 1
        nb = (left << 2) | (center << 1) | right
        out |= ((rule >> nb) & 1) << i
    return out


def self_check():
    table110 = {
        (1, 1, 1): 0, (1, 1, 0): 1, (1, 0, 1): 1, (1, 0, 0): 0,
        (0, 1, 1): 1, (0, 1, 0): 1, (0, 0, 1): 1, (0, 0, 0): 0,
    }
    for c in range(1 << W):
        bits = [(c >> i) & 1 for i in range(W)]
        acc = 0
        for i in range(W):
            left = bits[(i + 1) % W]
            right = bits[(i - 1) % W]
            acc |= (left ^ right) << i
        assert step_int(90, c) == acc
    for left, center, right in itertools.product((0, 1), repeat=3):
        nb = (left << 2) | (center << 1) | right
        assert ((110 >> nb) & 1) == table110[(left, center, right)]
    # one hand-checked row: rule 90, single bit at cell 0 -> bits at cells 1 and 7
    assert step_int(90, 1) == (1 << 1) | (1 << 7)


# ---------------------------------------------------------------- Turing machine
# state = (phase, i, orig0, right, center, leftbit, pos)
# phase 6 is done.


def rule_bit(rule, left, center, right):
    nb = (left << 2) | (center << 1) | right
    return (rule >> nb) & 1


def delta_tm(rule, state, symbol):
    phase, i, orig0, right, center, leftbit, pos = state
    if phase == 0:
        # at cell 0: remember the original symbol, step to cell 7
        return (1, 0, symbol, 0, 0, 0, 7), symbol, -1
    if phase == 1:
        # at cell 7: that symbol is the right neighbor of cell 0
        return (2, 0, orig0, symbol, 0, 0, 0), symbol, 1
    if phase == 2:
        if i < 7:
            return (3, i, orig0, right, symbol, 0, pos + 1), symbol, 1
        return (5, i, orig0, right, symbol, orig0, pos), symbol, 0
    if phase == 3:
        return (4, i, orig0, right, center, symbol, pos - 1), symbol, -1
    if phase == 4:
        bit = rule_bit(rule, leftbit, center, right)
        return (2, i + 1, orig0, center, 0, 0, pos + 1), bit, 1
    if phase == 5:
        bit = rule_bit(rule, orig0, center, right)
        return (6, i, orig0, right, center, orig0, pos), bit, 0
    if phase == 6:
        return state, symbol, 0
    raise RuntimeError(phase)


INITIAL_TM = (0, 0, 0, 0, 0, 0, 0)


def tm_sweep(rule, bits):
    tape = list(bits)
    state = INITIAL_TM
    pos = 0
    for _ in range(80):
        if state[0] == 6:
            return tape
        if state[6] != pos:
            raise RuntimeError("position counter left the head")
        state, write, move = delta_tm(rule, state, tape[pos])
        tape[pos] = write
        pos = (pos + move) % W
    raise RuntimeError("tm sweep did not finish")


def ca_local(rule, left_cell, mid, right_cell):
    """Radius-1 map. The head cell applies one Turing transition; a neighbor
    receives the head exactly when that transition moves toward it.
    """
    sym, st = mid
    new_sym = sym
    new_st = None
    if st is not None:
        nst, write, move = delta_tm(rule, st, sym)
        new_sym = write
        if move == 0:
            new_st = nst
    ls, lst = left_cell
    if lst is not None:
        nst, _, move = delta_tm(rule, lst, ls)
        if move == 1:
            if new_st is not None:
                raise RuntimeError("two heads")
            new_st = nst
    rs, rst = right_cell
    if rst is not None:
        nst, _, move = delta_tm(rule, rst, rs)
        if move == -1:
            if new_st is not None:
                raise RuntimeError("two heads")
            new_st = nst
    return new_sym, new_st


def ca_sweep(rule, bits):
    cells = [(b, None) for b in bits]
    cells[0] = (bits[0], INITIAL_TM)
    for _ in range(80):
        heads = [st for _, st in cells if st is not None]
        if len(heads) != 1:
            raise RuntimeError("head count")
        if heads[0][0] == 6:
            return [sym for sym, _ in cells]
        if heads[0][6] != next(i for i, (_, st) in enumerate(cells) if st is not None):
            raise RuntimeError("position counter left the head")
        cells = [
            ca_local(rule, cells[(i - 1) % W], cells[i], cells[(i + 1) % W])
            for i in range(W)
        ]
    raise RuntimeError("ca sweep did not finish")


# ---------------------------------------------------------------- register machine
class Asm:
    def __init__(self):
        self.prog = []
        self.labels = {}
        self._n = 0
        self.corrupt_at = None

    def label(self, name):
        if name in self.labels:
            raise RuntimeError(name)
        self.labels[name] = len(self.prog)

    def _fresh(self, stem):
        self._n += 1
        return f"{stem}_{self._n}"

    def inc(self, reg):
        self.prog.append(("INC", reg))

    def dec(self, reg):
        self.prog.append(("DEC", reg))

    def jz(self, reg, name):
        self.prog.append(("JZ", reg, name))

    def div2(self, reg, rem):
        self.prog.append(("DIV2", reg, rem))

    def halt(self):
        self.prog.append(("HALT",))

    def jump(self, name):
        # unconditional jump is JZ on the register Z, which the program never increments
        self.jz(Z, name)

    def copy(self, src, dst, tmp):
        """dst += src, src restored, tmp ends at 0. tmp must start at 0."""
        loop = self._fresh("copy")
        back = self._fresh("restore")
        done = self._fresh("copied")
        self.label(loop)
        self.jz(src, back)
        self.dec(src)
        self.inc(dst)
        self.inc(tmp)
        self.jump(loop)
        self.label(back)
        self.jz(tmp, done)
        self.dec(tmp)
        self.inc(src)
        self.jump(back)
        self.label(done)

    def clear(self, reg):
        loop = self._fresh("clr")
        done = self._fresh("clrd")
        self.label(loop)
        self.jz(reg, done)
        self.dec(reg)
        self.jump(loop)
        self.label(done)

    def add_power(self, reg, power, corrupt_this=False):
        """Add 2**power to reg, by that many increments, if caller already branched on the bit.

        power == 0 emits a single INC. corrupt_this replaces that INC by DEC.
        """
        if power == 0:
            if corrupt_this:
                # one instruction: the increment of the output's least bit becomes a decrement
                self.corrupt_at = len(self.prog)
                self.dec(reg)
            else:
                self.inc(reg)
            return
        self.clear(CNT)  # CNT is already 0; one guarded decrement loop
        for _ in range(1 << power):
            self.inc(CNT)
        loop = self._fresh("add")
        done = self._fresh("added")
        self.label(loop)
        self.jz(CNT, done)
        self.dec(CNT)
        self.inc(reg)
        self.jump(loop)
        self.label(done)

    def resolve(self):
        out = []
        for op in self.prog:
            if op[0] == "JZ":
                out.append(("JZ", op[1], self.labels[op[2]]))
            else:
                out.append(op)
        return out


def build_program(corrupt=False):
    a = Asm()
    # C holds the configuration and is consumed down to 0. Bits B0..B7 are its base-2 digits.
    for i in range(W):
        a.div2(C, B0 + i)
    for i in range(W):
        left = B0 + ((i + 1) % W)
        center = B0 + i
        right = B0 + ((i - 1) % W)
        # (RULE >> nb) & 1 is the remainder of DIV2 number nb+1, nb = 4*left+2*center+right.
        a.clear(TMP)
        a.copy(RULE, TMP, TMP2)
        a.div2(TMP, REM)  # always one: this is bit 0 when nb = 0
        skip_r = a._fresh("sr")
        a.jz(right, skip_r)
        a.div2(TMP, REM)
        a.label(skip_r)
        skip_c = a._fresh("sc")
        a.jz(center, skip_c)
        a.div2(TMP, REM)
        a.div2(TMP, REM)
        a.label(skip_c)
        skip_l = a._fresh("sl")
        a.jz(left, skip_l)
        for _ in range(4):
            a.div2(TMP, REM)
        a.label(skip_l)
        skip_add = a._fresh("sa")
        a.jz(REM, skip_add)
        # the single-instruction corruption is the increment that adds bit 0 of the output
        a.add_power(OUT, i, corrupt_this=(corrupt and i == 0))
        a.label(skip_add)
        a.clear(TMP)
    # C is 0. Leave the new configuration in C.
    a.copy(OUT, C, TMP2)
    a.halt()
    prog = a.resolve()
    if corrupt and a.corrupt_at is None:
        raise RuntimeError("corruption was not emitted")
    if corrupt and prog[a.corrupt_at] != ("DEC", OUT):
        raise RuntimeError(prog[a.corrupt_at])
    return prog, a.corrupt_at


def _fast_copy(prog, ip, regs):
    """while src: dec src; inc dst; inc tmp; jump back. Then the restore loop is separate."""
    if ip + 4 >= len(prog):
        return None
    op0, op1, op2, op3, op4 = prog[ip:ip + 5]
    if not (
        op0[0] == "JZ" and op1 == ("DEC", op0[1]) and op2[0] == "INC" and op3[0] == "INC"
        and op4 == ("JZ", Z, ip) and op2[1] != op3[1]
    ):
        return None
    src, dst, tmp = op0[1], op2[1], op3[1]
    n = regs[src]
    regs[dst] += n
    regs[tmp] += n
    regs[src] = 0
    return op0[2], 5 * n + 1


def _fast_clear_or_add(prog, ip, regs):
    """while reg: dec reg; optional inc other; jump back."""
    if ip + 2 >= len(prog):
        return None
    op0 = prog[ip]
    if op0[0] != "JZ":
        return None
    src = op0[1]
    op1 = prog[ip + 1]
    if op1 != ("DEC", src):
        return None
    op2 = prog[ip + 2]
    if op2 == ("JZ", Z, ip):
        n = regs[src]
        regs[src] = 0
        return op0[2], 3 * n + 1
    if op2[0] == "INC" and ip + 3 < len(prog) and prog[ip + 3] == ("JZ", Z, ip):
        n = regs[src]
        regs[op2[1]] += n
        regs[src] = 0
        return op0[2], 4 * n + 1
    return None


def run_program(prog, regs, fast):
    ip = 0
    steps = 0
    guard = 0
    while True:
        guard += 1
        if guard > 5000000:
            raise RuntimeError("runaway")
        op = prog[ip]
        if fast and op[0] == "JZ":
            jumped = _fast_copy(prog, ip, regs)
            if jumped is None:
                jumped = _fast_clear_or_add(prog, ip, regs)
            if jumped is not None:
                ip, add = jumped
                steps += add
                continue
        code = op[0]
        if code == "HALT":
            break
        if code == "INC":
            regs[op[1]] += 1
            ip += 1
            steps += 1
        elif code == "DEC":
            if regs[op[1]] > 0:
                regs[op[1]] -= 1
            ip += 1
            steps += 1
        elif code == "JZ":
            steps += 1
            ip = op[2] if regs[op[1]] == 0 else ip + 1
        elif code == "DIV2":
            regs[op[2]] = regs[op[1]] & 1
            regs[op[1]] >>= 1
            ip += 1
            steps += 1
        else:
            raise RuntimeError(op)
    return steps


def regs_for(rule, config):
    regs = [0] * NREG
    regs[C] = config
    regs[RULE] = rule
    return regs


def register_step(prog, rule, config, fast):
    regs = regs_for(rule, config)
    run_program(prog, regs, fast=fast)
    return regs[C], regs[RULE]


def bits_of(c):
    return [(c >> i) & 1 for i in range(W)]


def main():
    self_check()
    prog, _ = build_program(False)
    bad_prog, corrupt_at = build_program(True)
    # The fast path must match instruction-by-instruction execution.
    audit_fail = 0
    audit_n = 0
    for rule in range(256):
        for config in (0, 1, 2, 85, 170, 255):
            audit_n += 1
            slow, rule_slow = register_step(prog, rule, config, fast=False)
            fast, rule_fast = register_step(prog, rule, config, fast=True)
            if slow != fast or rule_slow != rule or rule_fast != rule or slow != step_int(rule, config):
                audit_fail += 1
    direct_cells = 0
    tm_mismatch = 0
    ca_mismatch = 0
    reg_mismatch = 0
    reg_steps = 0
    for rule in range(256):
        for config in range(256):
            c = config
            tb = bits_of(config)
            cb = bits_of(config)
            for _ in range(5):
                expect = step_int(rule, c)
                tb = tm_sweep(rule, tb)
                cb = ca_sweep(rule, cb)
                eb = bits_of(expect)
                for i in range(W):
                    direct_cells += 1
                    if tb[i] != eb[i]:
                        tm_mismatch += 1
                    if cb[i] != eb[i]:
                        ca_mismatch += 1
                nxt, rule_after = register_step(prog, rule, c, fast=True)
                reg_steps += 1
                if nxt != expect or rule_after != rule:
                    reg_mismatch += 1
                c = expect
    corrupt_mismatch = 0
    corrupt_compared = 0
    for rule in range(256):
        for config in range(256):
            nxt, _ = register_step(bad_prog, rule, config, fast=True)
            corrupt_compared += 1
            if nxt != step_int(rule, config):
                corrupt_mismatch += 1
    measured = {
        "width": W,
        "rules": 256,
        "initial_conditions": 256,
        "steps": 5,
        "cell_comparisons_T_and_C": direct_cells,
        "configuration_comparisons_R": reg_steps,
        "tm_cell_mismatches": tm_mismatch,
        "ca_cell_mismatches": ca_mismatch,
        "register_configuration_mismatches": reg_mismatch,
        "register_program_instructions": len(prog),
        "fast_path_audit_cases": audit_n,
        "fast_path_audit_failures": audit_fail,
        "corruption": {
            "instruction_index": corrupt_at,
            "correct": "INC OUT",
            "corrupted": "DEC OUT",
            "cases": corrupt_compared,
            "mismatches": corrupt_mismatch,
        },
        "self_check_rule_90_and_110": True,
    }
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measured.json"), "w") as f:
        json.dump(measured, f, indent=2)
        f.write("\n")
    with open(os.path.join(HERE, "derived", "register-program.json"), "w") as f:
        names = {Z: "Z", C: "C", RULE: "RULE", OUT: "OUT", TMP: "TMP", TMP2: "TMP2", REM: "REM", CNT: "CNT"}
        for i in range(8):
            names[B0 + i] = f"B{i}"
        listing = []
        for op in prog:
            if op[0] in ("INC", "DEC"):
                listing.append(f"{op[0]} {names[op[1]]}")
            elif op[0] == "JZ":
                listing.append(f"JZ {names[op[1]]} -> {op[2]}")
            elif op[0] == "DIV2":
                listing.append(f"DIV2 {names[op[1]]} -> rem {names[op[2]]}")
            else:
                listing.append(op[0])
        json.dump({"instructions": listing, "corrupt_index": corrupt_at}, f, indent=2)
        f.write("\n")
    print(json.dumps(measured, indent=2))


if __name__ == "__main__":
    main()
