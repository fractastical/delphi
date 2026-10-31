#!/usr/bin/env python3
"""wolfram2002-ch05-09: networks of identical out-degree-2 nodes can form arrays of any dimension,
trees and nested structures.

Constructs the networks described in result.json, checks out-degrees, the exact block-quotient
equivalence with the d-dimensional grid, and Wolfram's growth-exponent dimension criterion.
Prints JSON to stdout and writes derived/measured.json.
"""
import json
import math
import os
import sys
import time
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))


# ---------- d-dimensional block networks ----------
def block_successors(d):
    """Node = (x tuple, i).  Two outgoing connections: to x + e_i and x - e_i, landing on index (i+1) mod d."""
    def succ(node):
        x, i = node
        j = (i + 1) % d
        plus = tuple(x[k] + (1 if k == i else 0) for k in range(d))
        minus = tuple(x[k] - (1 if k == i else 0) for k in range(d))
        return [(plus, j), (minus, j)]
    return succ


def bfs_counts(start, succ, R):
    """N[r] = number of nodes within directed distance <= r of start, r = 0..R."""
    dist = {start: 0}
    frontier = [start]
    counts = [1]
    for r in range(1, R + 1):
        nxt = []
        for u in frontier:
            for v in succ(u):
                if v not in dist:
                    dist[v] = r
                    nxt.append(v)
        frontier = nxt
        counts.append(counts[-1] + len(nxt))
    return counts


def exponent(counts, R):
    return math.log2(counts[R] / counts[R // 2])


def quotient_check(d, L):
    """On the torus (Z_L)^d: contract blocks, compare the edge multiset with the grid's, and check out-degrees."""
    import itertools
    succ = block_successors(d)
    points = list(itertools.product(range(L), repeat=d))
    out_deg_ok = True
    quotient_edges = {}
    neighbours = {x: set() for x in points}
    for x in points:
        for i in range(d):
            s = succ((x, i))
            if len(s) != 2:
                out_deg_ok = False
            for (y, j) in s:
                y = tuple(c % L for c in y)
                quotient_edges[(x, y)] = quotient_edges.get((x, y), 0) + 1
                neighbours[x].add(y)
    grid_edges = {}
    for x in points:
        for i in range(d):
            for sgn in (1, -1):
                y = tuple((x[k] + sgn * (1 if k == i else 0)) % L for k in range(d))
                grid_edges[(x, y)] = grid_edges.get((x, y), 0) + 1
    return {
        "L": L, "blocks": len(points), "nodes": len(points) * d,
        "out_degree_2_everywhere": out_deg_ok,
        "quotient_edge_multiset_equals_grid": quotient_edges == grid_edges,
        "every_block_has_2d_distinct_neighbours": all(len(v) == 2 * d for v in neighbours.values()),
    }


def lattice_ball(d, r):
    """|{x in Z^d : |x|_1 <= r}| for reference."""
    return sum(2 ** k * math.comb(d, k) * math.comb(r, k) for k in range(0, min(d, r) + 1))


# ---------- binary tree ----------
def tree_succ(k):
    return [2 * k + 1, 2 * k + 2]


# ---------- Sierpinski gasket with Eulerian orientation ----------
def sierpinski_edges(level):
    edges = set()

    def rec(o, s):
        if s == 1:
            a, b, c = o, (o[0] + 1, o[1]), (o[0], o[1] + 1)
            for e in ((a, b), (b, c), (a, c)):
                edges.add(tuple(sorted(e)))
        else:
            h = s // 2
            rec(o, h); rec((o[0] + h, o[1]), h); rec((o[0], o[1] + h), h)
    rec((0, 0), 2 ** level)
    return edges


def euler_orientation(edges):
    """Orient each undirected edge along an Euler circuit (Hierholzer).  All degrees must be even."""
    adj = {}
    for idx, (u, v) in enumerate(edges):
        adj.setdefault(u, []).append((v, idx))
        adj.setdefault(v, []).append((u, idx))
    assert all(len(a) % 2 == 0 for a in adj.values())
    used = [False] * len(edges)
    start = next(iter(adj))
    stack = [(start, None)]
    circuit = []   # list of (node, edge index used to arrive)
    while stack:
        u, via = stack[-1]
        while adj[u] and used[adj[u][-1][1]]:
            adj[u].pop()
        if adj[u]:
            v, idx = adj[u].pop()
            used[idx] = True
            stack.append((v, idx))
        else:
            circuit.append(stack.pop())
    circuit.reverse()
    oriented = []
    for a in range(len(circuit) - 1):
        oriented.append((circuit[a][0], circuit[a + 1][0]))
    assert len(oriented) == len(edges) and all(used)
    return oriented


def gasket_network(level):
    edges = sorted(sierpinski_edges(level))
    deg = {}
    for u, v in edges:
        deg[u] = deg.get(u, 0) + 1
        deg[v] = deg.get(v, 0) + 1
    corners = [v for v, k in deg.items() if k == 2]
    assert len(corners) == 3 and all(k == 4 for v, k in deg.items() if v not in corners)
    # corners have odd out-degree after orientation unless fixed: add a directed 3-cycle through them
    # (undirected view: corners get degree 4 too, so the whole graph is Eulerian)
    arcs = euler_orientation(edges)
    corners_sorted = sorted(corners)
    for a in range(3):
        arcs.append((corners_sorted[a], corners_sorted[(a + 1) % 3]))
    out = {}
    und = {}
    for u, v in arcs:
        out.setdefault(u, []).append(v)
        und.setdefault(u, set()).add(v)
        und.setdefault(v, set()).add(u)
    return out, und, corners_sorted, len(deg)


def main():
    t0 = time.time()
    res = {"arrays": {}, "tree": {}, "nested": {}}
    for d in range(1, 7):
        t1 = time.time()
        R = 20 * d if d <= 4 else 8 * d   # d = 5, 6 are reported only; smaller radius to bound memory
        succ = block_successors(d)
        counts = bfs_counts((tuple([0] * d), 0), succ, R)
        q = quotient_check(d, 5)
        ex = exponent(counts, R)
        # reference: the plain L1 lattice ball has the same bias at finite radius
        ref = math.log2(lattice_ball(d, R // d) / lattice_ball(d, R // (2 * d)))
        res["arrays"][str(d)] = {
            "R": R, "nodes_within_R": counts[R], "nodes_within_R_half": counts[R // 2],
            "growth_exponent": round(ex, 3), "rounds_to": round(ex), "within_0.5_of_d": abs(ex - d) < 0.5,
            "reference_exponent_of_L1_lattice_ball_at_radius_R_over_d": round(ref, 3),
            "quotient": q, "seconds": round(time.time() - t1, 1),
        }
    tree_counts = bfs_counts(0, tree_succ, 15)
    res["tree"] = {"N_r": tree_counts, "equals_2^(r+1)-1": all(tree_counts[r] == 2 ** (r + 1) - 1 for r in range(16))}
    out, und, corners, n_nodes = gasket_network(7)
    R = 64
    und_counts = bfs_counts(corners[0], lambda u: sorted(und[u]), R)
    dir_counts = bfs_counts(corners[0], lambda u: out.get(u, []), R)
    ex_u, ex_d = exponent(und_counts, R), exponent(dir_counts, R)
    res["nested"] = {
        "level": 7, "nodes": n_nodes, "arcs": sum(len(v) for v in out.values()),
        "out_degree_2_everywhere": all(len(out.get(v, [])) == 2 for v in und),
        "undirected_growth_exponent_R64": round(ex_u, 3), "directed_growth_exponent_R64": round(ex_d, 3),
        "log2_3": round(math.log2(3), 3), "undirected_within_0.3": abs(ex_u - math.log2(3)) < 0.3,
        "N_undirected": und_counts[::8], "N_directed": dir_counts[::8],
    }
    arrays_ok = all(a["quotient"]["out_degree_2_everywhere"] and a["quotient"]["quotient_edge_multiset_equals_grid"]
                    and a["quotient"]["every_block_has_2d_distinct_neighbours"] for a in res["arrays"].values())
    dim_ok = all(res["arrays"][str(d)]["within_0.5_of_d"] for d in range(1, 5))
    tree_ok = res["tree"]["equals_2^(r+1)-1"]
    nested_ok = res["nested"]["out_degree_2_everywhere"] and res["nested"]["undirected_within_0.3"]
    if not arrays_ok or not dim_ok:
        verdict = "refutes"
    elif not (tree_ok and nested_ok):
        verdict = "mixed"
    else:
        verdict = "supports"
    res.update({"criteria": {"1a_1b_structure_and_quotient_d1_6": arrays_ok, "1c_growth_exponent_d1_4": dim_ok,
                             "2_tree": tree_ok, "3_nested": nested_ok},
                "verdict": verdict, "seconds": round(time.time() - t0, 1)})
    json.dump(res, sys.stdout, indent=1)
    print()
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measured.json"), "w") as f:
        json.dump(res, f, indent=1)


if __name__ == "__main__":
    main()
