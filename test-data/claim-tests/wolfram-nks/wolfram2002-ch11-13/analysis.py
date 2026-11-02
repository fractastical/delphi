#!/usr/bin/env python3
"""Finite threshold for wolfram2002-ch11-13.

C is every map {0,1}^3 -> {0,1} (256 elementary rules). A is the affine
subclass over GF(2). One Turing machine reads a rule table and one
neighborhood from its tape; three extra states have no incoming transition;
a radius-1 cellular automaton carries that machine's head and applies the
same transition. Writes derived/measured.json.
"""
import itertools
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# Tape: 0..7 rule bits (Wolfram neighborhood number), 8 left, 9 center,
# 10 right, 11 output. Head starts on cell 8.
TAPE_LEN = 12


def eca_bit(rule, left, center, right):
    nb = (left << 2) | (center << 1) | right
    return (rule >> nb) & 1


def delta(state, symbol):
    """One transition. state is a tuple; move is -1, 0 or +1.

    Extra states ("extra", 1..3) are in the table and no listed transition
    enters them.
    """
    tag = state[0]
    if tag == "read_p":
        return ("read_q", symbol), symbol, 1
    if tag == "read_q":
        return ("read_r", state[1], symbol), symbol, 1
    if tag == "read_r":
        nb = (state[1] << 2) | (state[2] << 1) | symbol
        return ("go_left", nb, 10 - nb), symbol, 0
    if tag == "go_left":
        nb, steps = state[1], state[2]
        if steps > 0:
            return ("go_left", nb, steps - 1), symbol, -1
        return ("read_rule", nb), symbol, 0
    if tag == "read_rule":
        return ("go_right", symbol, 11 - state[1]), symbol, 0
    if tag == "go_right":
        bit, steps = state[1], state[2]
        if steps > 0:
            return ("go_right", bit, steps - 1), symbol, 1
        return ("write_out", bit), symbol, 0
    if tag == "write_out":
        return ("halt",), state[1], 0
    if tag == "halt":
        return ("halt",), symbol, 0
    if tag == "extra":
        return state, symbol, 0
    raise RuntimeError(state)


def reachable_states(start):
    seen = set()
    stack = [start]
    while stack:
        st = stack.pop()
        if st in seen:
            continue
        seen.add(st)
        for symbol in (0, 1):
            nxt, _, _ = delta(st, symbol)
            if nxt not in seen:
                stack.append(nxt)
    return seen


def run_tm(rule, left, center, right):
    tape = [(rule >> i) & 1 for i in range(8)] + [left, center, right, 0]
    pos = 8
    state = ("read_p",)
    for _ in range(80):
        if state[0] == "halt":
            return tape[11], state
        sym = tape[pos]
        state, write, move = delta(state, sym)
        tape[pos] = write
        pos += move
        if not 0 <= pos < TAPE_LEN:
            raise RuntimeError("head left the tape")
    raise RuntimeError("tm did not halt")


def ca_microstep(cells):
    """Radius-1 rule. A cell is (symbol, head state or None)."""
    n = len(cells)
    out = [(sym, None) for sym, _ in cells]
    for i, (sym, st) in enumerate(cells):
        if st is None:
            continue
        new_st, write, move = delta(st, sym)
        out[i] = (write, out[i][1])
        j = i + move
        if not 0 <= j < n:
            raise RuntimeError("head left the tape")
        if move == 0:
            if out[i][1] is not None:
                raise RuntimeError("two heads")
            out[i] = (write, new_st)
        else:
            if out[j][1] is not None:
                raise RuntimeError("two heads")
            out[j] = (out[j][0], new_st)
    return out


def run_ca(rule, left, center, right):
    cells = [((rule >> i) & 1, None) for i in range(8)]
    cells += [(left, ("read_p",)), (center, None), (right, None), (0, None)]
    for _ in range(80):
        head = next(st for _, st in cells if st is not None)
        if head[0] == "halt":
            return cells[11][0]
        cells = ca_microstep(cells)
    raise RuntimeError("ca did not halt")


def affine_codes():
    codes = []
    for a0, a1, a2, a3 in itertools.product((0, 1), repeat=4):
        code = 0
        for left, center, right in itertools.product((0, 1), repeat=3):
            val = (a0 + a1 * left + a2 * center + a3 * right) % 2
            nb = (left << 2) | (center << 1) | right
            code |= val << nb
        codes.append(code)
    return codes


def self_check():
    table110 = {
        (1, 1, 1): 0, (1, 1, 0): 1, (1, 0, 1): 1, (1, 0, 0): 0,
        (0, 1, 1): 1, (0, 1, 0): 1, (0, 0, 1): 1, (0, 0, 0): 0,
    }
    for left, center, right in itertools.product((0, 1), repeat=3):
        assert eca_bit(90, left, center, right) == (left ^ right)
        assert eca_bit(110, left, center, right) == table110[(left, center, right)]
        assert ((110 >> ((left << 2) | (center << 1) | right)) & 1) == table110[(left, center, right)]


def realize(runner):
    found = set()
    for rule in range(256):
        code = 0
        for left, center, right in itertools.product((0, 1), repeat=3):
            bit = runner(rule, left, center, right)
            nb = (left << 2) | (center << 1) | right
            code |= bit << nb
        found.add(code)
    return found


def main():
    self_check()
    affine = set(affine_codes())
    elementary = set(range(256))
    tm_set = realize(lambda rule, p, q, r: run_tm(rule, p, q, r)[0])
    ca_set = realize(run_ca)
    # The extra states are part of delta already; the start state is unchanged,
    # so a second run is the same machine. Record that none is reachable.
    reached = reachable_states(("read_p",))
    extras = {("extra", i) for i in (1, 2, 3)}
    extra_entered = len(reached & extras)
    pairs = {
        "elementary_vs_tm": len(elementary ^ tm_set),
        "elementary_vs_tm_plus_extras": len(elementary ^ tm_set),
        "elementary_vs_head_ca": len(elementary ^ ca_set),
        "tm_vs_head_ca": len(tm_set ^ ca_set),
    }
    measured = {
        "class_C": 256,
        "affine_functions_listed": len(affine_codes()),
        "affine_A": len(affine),
        "affine_proper_subset": affine < elementary,
        "affine_codes": sorted(affine),
        "realized": {
            "elementary_rules": len(elementary),
            "turing_machine": len(tm_set),
            "turing_machine_plus_3_unreachable": len(tm_set) if extra_entered == 0 else None,
            "head_cellular_automaton": len(ca_set),
        },
        "outside_C": {
            "elementary_rules": len(elementary - set(range(256))),
            "turing_machine": len(tm_set - set(range(256))),
            "head_cellular_automaton": len(ca_set - set(range(256))),
        },
        "symmetric_difference_sizes": pairs,
        "tm_states_reachable_from_start": len(reached),
        "extra_states": 3,
        "extra_states_entered": extra_entered,
        "self_check_rule_90_and_110": True,
    }
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measured.json"), "w") as f:
        json.dump(measured, f, indent=2)
        f.write("\n")
    print(json.dumps(measured, indent=2))


if __name__ == "__main__":
    main()
