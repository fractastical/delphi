/* Exhaustive enumeration of reversible (injective) one-dimensional cellular automata with
 * k colours and radius r (window n = 2r+1), by depth-first assignment of the rule table with
 * pruning on the pair graph of the de Bruijn graph (Sutner / Amoroso-Patt criterion):
 * the CA is injective iff the pair graph has no cycle through an off-diagonal node and no
 * path from a diagonal node to a diagonal node through off-diagonal nodes.  Edges whose two
 * labels are both assigned and equal are "definite"; definite violations are monotone in the
 * assignment, so pruning is sound, and at a leaf the test is exact.
 *
 * usage: revca k r [outfile]      prints "count nodes" ; writes rule tables (digit strings, most
 * significant neighbourhood first, Wolfram order) to outfile if given.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int K, R, N, NE, NB, NP;      /* colours, radius, window, entries, de Bruijn nodes, pair nodes */
static int *table;                   /* rule table, -1 = unassigned */
static int *order;                   /* entry assignment order */
static int *count;                   /* colour counts */
static int *edge_to;                 /* de Bruijn: node u, colour c -> node v */
static int *edge_entry;              /* de Bruijn: node u, colour c -> entry index */
static long long found = 0, nodes = 0;
static FILE *out = NULL;

static int ipow(int b, int e) { int r = 1; while (e--) r *= b; return r; }

/* ---------------------------------------------------------------- pair graph test */
static int *indeg, *outdeg, *alive, *stack, *mark;

static int violates(void) {
    int u1, u2, c1, c2;
    /* definite edges among pair nodes: p = u1*NB+u2 -> q = v1*NB+v2 when labels equal */
    /* 1. off-diagonal cycle: prune nodes with in/out degree 0 iteratively */
    for (int p = 0; p < NP; p++) { indeg[p] = outdeg[p] = 0; alive[p] = (p / NB != p % NB); }
    for (u1 = 0; u1 < NB; u1++) for (u2 = 0; u2 < NB; u2++) {
        if (u1 == u2) continue;
        int p = u1 * NB + u2;
        for (c1 = 0; c1 < K; c1++) {
            int l1 = table[edge_entry[u1 * K + c1]];
            if (l1 < 0) continue;
            for (c2 = 0; c2 < K; c2++) {
                int l2 = table[edge_entry[u2 * K + c2]];
                if (l2 != l1) continue;
                int v1 = edge_to[u1 * K + c1], v2 = edge_to[u2 * K + c2];
                if (v1 == v2) continue;
                outdeg[p]++;
                indeg[v1 * NB + v2]++;
            }
        }
    }
    int sp = 0, remaining = 0;
    for (int p = 0; p < NP; p++) if (alive[p]) { remaining++; if (indeg[p] == 0 || outdeg[p] == 0) { stack[sp++] = p; alive[p] = 0; remaining--; } }
    while (sp) {
        int p = stack[--sp];
        u1 = p / NB; u2 = p % NB;
        /* successors lose in-degree, predecessors lose out-degree */
        for (c1 = 0; c1 < K; c1++) {
            int l1 = table[edge_entry[u1 * K + c1]];
            if (l1 < 0) continue;
            for (c2 = 0; c2 < K; c2++) {
                int l2 = table[edge_entry[u2 * K + c2]];
                if (l2 != l1) continue;
                int v1 = edge_to[u1 * K + c1], v2 = edge_to[u2 * K + c2];
                if (v1 == v2) continue;
                int q = v1 * NB + v2;
                if (alive[q] && --indeg[q] == 0) { alive[q] = 0; remaining--; stack[sp++] = q; }
            }
        }
        /* predecessors: nodes (w1,w2) with edges into (u1,u2): w such that edge_to[w*K+c] == u */
        for (int w1 = 0; w1 < NB; w1++) for (c1 = 0; c1 < K; c1++) {
            if (edge_to[w1 * K + c1] != u1) continue;
            int l1 = table[edge_entry[w1 * K + c1]];
            if (l1 < 0) continue;
            for (int w2 = 0; w2 < NB; w2++) {
                if (w1 == w2) continue;
                for (c2 = 0; c2 < K; c2++) {
                    if (edge_to[w2 * K + c2] != u2) continue;
                    int l2 = table[edge_entry[w2 * K + c2]];
                    if (l2 != l1) continue;
                    int q = w1 * NB + w2;
                    if (alive[q] && --outdeg[q] == 0) { alive[q] = 0; remaining--; stack[sp++] = q; }
                }
            }
        }
    }
    if (remaining > 0) return 1;
    /* 2. diagonal -> off-diagonal ... -> diagonal path.  Forward BFS from diagonal nodes through
       off-diagonal nodes, marking; if a marked off-diagonal node has a definite edge to a diagonal node -> violation. */
    for (int p = 0; p < NP; p++) mark[p] = 0;
    sp = 0;
    for (int u = 0; u < NB; u++) {
        for (c1 = 0; c1 < K; c1++) {
            int l1 = table[edge_entry[u * K + c1]];
            if (l1 < 0) continue;
            for (c2 = 0; c2 < K; c2++) {
                if (c1 == c2) continue;
                int l2 = table[edge_entry[u * K + c2]];
                if (l2 != l1) continue;
                int v1 = edge_to[u * K + c1], v2 = edge_to[u * K + c2];
                int q = v1 * NB + v2;   /* v1 != v2 since c1 != c2 */
                if (!mark[q]) { mark[q] = 1; stack[sp++] = q; }
            }
        }
    }
    while (sp) {
        int p = stack[--sp];
        u1 = p / NB; u2 = p % NB;
        for (c1 = 0; c1 < K; c1++) {
            int l1 = table[edge_entry[u1 * K + c1]];
            if (l1 < 0) continue;
            for (c2 = 0; c2 < K; c2++) {
                int l2 = table[edge_entry[u2 * K + c2]];
                if (l2 != l1) continue;
                int v1 = edge_to[u1 * K + c1], v2 = edge_to[u2 * K + c2];
                if (v1 == v2) return 1;
                int q = v1 * NB + v2;
                if (!mark[q]) { mark[q] = 1; stack[sp++] = q; }
            }
        }
    }
    return 0;
}

static void dfs(int depth) {
    nodes++;
    if (violates()) return;
    if (depth == NE) {
        found++;
        if (out) { for (int i = NE - 1; i >= 0; i--) fputc('0' + table[i], out); fputc('\n', out); }
        return;
    }
    int e = order[depth];
    int cap = ipow(K, N - 1);
    for (int c = 0; c < K; c++) {
        if (count[c] >= cap) continue;   /* a surjective rule is balanced: each colour exactly k^(n-1) times */
        table[e] = c; count[c]++;
        dfs(depth + 1);
        table[e] = -1; count[c]--;
    }
}

int main(int argc, char **argv) {
    if (argc < 3) { fprintf(stderr, "usage: revca k r [outfile]\n"); return 1; }
    K = atoi(argv[1]); R = atoi(argv[2]); N = 2 * R + 1;
    NE = ipow(K, N); NB = ipow(K, N - 1); NP = NB * NB;
    if (argc > 3) out = fopen(argv[3], "w");
    table = malloc(NE * sizeof(int)); order = malloc(NE * sizeof(int)); count = calloc(K, sizeof(int));
    edge_to = malloc(NB * K * sizeof(int)); edge_entry = malloc(NB * K * sizeof(int));
    indeg = malloc(NP * sizeof(int)); outdeg = malloc(NP * sizeof(int)); alive = malloc(NP * sizeof(int));
    stack = malloc(NP * sizeof(int)); mark = malloc(NP * sizeof(int));
    for (int i = 0; i < NE; i++) table[i] = -1;
    /* de Bruijn node u = word of length N-1 (most significant = leftmost); appending colour c
       gives entry index e = u*K + c (word of length N), next node v = e mod K^(N-1) */
    for (int u = 0; u < NB; u++) for (int c = 0; c < K; c++) {
        edge_entry[u * K + c] = u * K + c;
        edge_to[u * K + c] = (u * K + c) % NB;
    }
    /* assignment order: entries sorted by minimal period of the window as a periodic word */
    int *per = malloc(NE * sizeof(int));
    for (int e = 0; e < NE; e++) {
        int w[16]; int x = e;
        for (int i = N - 1; i >= 0; i--) { w[i] = x % K; x /= K; }
        int m;
        for (m = 1; m <= N; m++) { int ok = 1; for (int i = 0; i + m < N; i++) if (w[i] != w[i + m]) { ok = 0; break; } if (ok) break; }
        per[e] = m;
    }
    int pos = 0;
    for (int m = 1; m <= N; m++) for (int e = 0; e < NE; e++) if (per[e] == m) order[pos++] = e;
    dfs(0);
    printf("%lld %lld\n", found, nodes);
    if (out) fclose(out);
    return 0;
}
