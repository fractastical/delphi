#!/usr/bin/env python3
"""wolfram2002-ch10-23: no method of perception and analysis recognizes all regularities.

Generates six 4096-byte strings (five from programs of < 400 bytes of source, one from os.urandom),
applies three general-purpose compressors and two specialized recognizers, and checks the
pre-registered criteria (a)-(d) in result.json.  Prints JSON to stdout, writes derived/measured.json.
"""
import bz2
import hashlib
import json
import lzma
import os
import sys
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
NBYTES = 4096
NBITS = 8 * NBYTES

# Generating programs; each defines `out` (bytes of length 4096).  Kept short: the source length is
# the "description length" recorded in the results.
GENERATORS = {
    "rule30_centre": """
import numpy as np
n=32768;w=2*n+3;c=np.zeros(w,np.uint8);c[n+1]=1;b=[]
for t in range(n):
 b.append(c[n+1]);c=(30>>(c[:-2]*4+c[1:-1]*2+c[2:]))&1;c=np.pad(c,1)
out=np.packbits(np.array(b,np.uint8)).tobytes()
""",
    "lcg_mod2_32": """
x=1;o=bytearray()
for i in range(1024):
 x=(1664525*x+1013904223)%2**32;o+=x.to_bytes(4,'little')
out=bytes(o)
""",
    "xorshift32": """
x=2463534242;o=bytearray()
for i in range(1024):
 x^=(x<<13)&0xffffffff;x^=x>>17;x^=(x<<5)&0xffffffff;o+=x.to_bytes(4,'little')
out=bytes(o)
""",
    "pi_binary_digits": """
def A(q,p):
 s=0;k=0;t=(1<<p)//q
 while t:
  s+=(-t if k&1 else t)//(2*k+1);k+=1;t//=q*q
 return s
p=32768+64;pi=16*A(5,p)-4*A(239,p)
out=((pi>>64)&((1<<32768)-1)).to_bytes(4096,'big')
""",
    "thue_morse": """
out=bytes(int(''.join(str(bin(8*i+j).count('1')&1) for j in range(8)),2) for i in range(4096))
""",
}


def berlekamp_massey(bits):
    """Linear complexity of a GF(2) sequence (Massey 1969).  Polynomials are Python ints (bit j = coefficient
    of x^j); `win` holds the sequence reversed so that bit j of win is bits[i-j]."""
    C, B, L, m, win = 1, 1, 0, -1, 0
    for i, s in enumerate(bits):
        win = (win << 1) | s
        if (C & win).bit_count() & 1:
            T = C
            C ^= B << (i - m)
            if 2 * L <= i:
                L, m, B = i + 1 - L, i, T
    return L


def affine_fit(data):
    """Does x_{i+1} = a x_i + c (mod 2^32) hold for all 32-bit LE words, with a, c solved from the first three?"""
    w = [int.from_bytes(data[i:i + 4], "little") for i in range(0, len(data), 4)]
    M = 1 << 32
    d = (w[1] - w[0]) % M
    if d % 2 == 0:
        return False, None
    a = ((w[2] - w[1]) * pow(d, -1, M)) % M
    c = (w[1] - a * w[0]) % M
    ok = all((a * w[i] + c) % M == w[i + 1] for i in range(len(w) - 1))
    return ok, (a, c) if ok else None


def to_bits(data):
    return [(byte >> (7 - k)) & 1 for byte in data for k in range(8)]


def main():
    t0 = time.time()
    strings, desc_len, gen_seconds = {}, {}, {}
    for name, src in GENERATORS.items():
        t1 = time.time()
        ns = {}
        exec(src, ns)
        out = ns["out"]
        assert len(out) == NBYTES, (name, len(out))
        strings[name] = out
        desc_len[name] = len(src.strip().encode())
        gen_seconds[name] = round(time.time() - t1, 2)
    strings["urandom"] = os.urandom(NBYTES)
    # sanity on pi: fractional part of pi in hex is 243F6A8885A308D313198A2E03707344...
    assert strings["pi_binary_digits"][:16] == bytes.fromhex("243F6A8885A308D313198A2E03707344"), strings["pi_binary_digits"][:16].hex()
    # sanity on Berlekamp-Massey: a degree-4 LFSR sequence must have linear complexity 4
    lf = [1, 0, 0, 0]
    for _ in range(60):
        lf.append(lf[-4] ^ lf[-3])
    assert berlekamp_massey(lf) == 4

    compressors = {
        "zlib9": lambda d: len(zlib.compress(d, 9)),
        "bz2_9": lambda d: len(bz2.compress(d, 9)),
        "lzma_xtreme9": lambda d: len(lzma.compress(d, preset=9 | lzma.PRESET_EXTREME)),
    }
    base = {k: f(strings["urandom"]) for k, f in compressors.items()}
    results = {}
    for name, data in strings.items():
        r = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
        if name in desc_len:
            r["description_bytes"] = desc_len[name]
        for k, f in compressors.items():
            size = f(data)
            r[k] = {"compressed_bytes": size, "ratio_to_urandom": round(size / base[k], 4), "recognizes": size <= 0.97 * base[k]}
        L = berlekamp_massey(to_bits(data))
        r["berlekamp_massey"] = {"linear_complexity": L, "recognizes": L < NBITS / 4}
        ok, ac = affine_fit(data)
        r["affine_mod2_32"] = {"recognizes": ok, "a_c": ac}
        r["recognized_by"] = [k for k in list(compressors) + ["berlekamp_massey", "affine_mod2_32"] if r[k]["recognizes"]]
        results[name] = r

    simple = ["rule30_centre", "lcg_mod2_32", "xorshift32", "pi_binary_digits"]
    comp_names = list(compressors)
    a_ok = all(sum(not results[s][k]["recognizes"] for s in simple) >= 2 for k in comp_names)
    b_witnesses = [s for s in simple if not any(results[s][k]["recognizes"] for k in comp_names)
                   and (results[s]["berlekamp_massey"]["recognizes"] or results[s]["affine_mod2_32"]["recognizes"])]
    c_witnesses = [s for s in simple if not results[s]["recognized_by"]]
    d_control_ok = all(results["thue_morse"][k]["compressed_bytes"] < 0.2 * base[k] for k in comp_names)
    d_false_alarm = results["urandom"]["recognized_by"]
    any_compressor_recognizes_all = any(all(results[s][k]["recognizes"] for s in simple) for k in comp_names)
    if d_false_alarm or any_compressor_recognizes_all:
        verdict = "mixed"
    elif not (b_witnesses and c_witnesses):
        verdict = "inconclusive"
    elif a_ok and d_control_ok:
        verdict = "supports"
    else:
        verdict = "mixed"
    out = {
        "n_bits_per_string": NBITS,
        "urandom_compressed_bytes": base,
        "strings": results,
        "criteria": {
            "a_each_compressor_misses_ge2_simple_strings": a_ok,
            "a_detail": {k: [s for s in simple if not results[s][k]["recognizes"]] for k in comp_names},
            "b_missed_by_all_compressors_but_caught_by_specialized": b_witnesses,
            "c_missed_by_every_method": c_witnesses,
            "d_thue_morse_compressed_below_0.2": d_control_ok,
            "d_urandom_false_alarms": d_false_alarm,
            "any_compressor_recognizes_all_four": any_compressor_recognizes_all,
        },
        "generator_seconds": gen_seconds,
        "max_description_bytes": max(desc_len.values()),
        "seconds": round(time.time() - t0, 1),
        "verdict": verdict,
    }
    json.dump(out, sys.stdout, indent=1)
    print()
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measured.json"), "w") as f:
        json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()
