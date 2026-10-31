/* Classification of all 4096 two-state two-colour Turing machines from many initial conditions.
 *
 * Machine number m in 0..4095: for case index i = 2*s + c (state s, read colour c, both 0/1),
 * entry e = (m >> (3*(3-i))) & 7 gives new colour e&1, move +1 (right) if (e>>1)&1 else -1,
 * new state e>>2.  Tape is infinite and blank (0) outside the initial string.
 *
 * Classification of an evolution:
 *   A  the head-relative configuration (state, offset of head from leftmost 1, span, bits) recurs
 *      -> eventually periodic modulo translation (period = step difference).  Exact.
 *   B  escape, two exact tests: (B1) the head is beyond all non-zero cells, moved outward last step,
 *      and the current state was already seen during this outward run -> moves outward forever;
 *      (B2) two consecutive new-extreme head positions with identical state and identical non-zero
 *      tape (same position), the head at the first being farther from the non-zero cells than the
 *      time between them -> the head carries a bounded pattern outward on blank tape forever.
 *   C  (post-hoc, see result.json) regular growth: on each side where the head keeps reaching new
 *      extreme positions, the sequence of such events (sampled with some stride k = 1..3) has
 *      constant second time differences, constant state, constant length growth and tape contents
 *      S_{n+k} = P + S_n[:o] + B + S_n[o:] + Q with fixed strings P, B, Q and offset o, over the
 *      last NEV events (covers A B^n C growth and nested P S Q growth).  Heuristic.
 *   D  (post-hoc) as C but the event gaps obey g_{n+1} = a g_n + b with integer a >= 2 (counter-like
 *      nested growth, tape grows logarithmically in time).  Heuristic.
 *   E  (post-hoc) counter certificate: the head keeps returning to one end of its range in a fixed
 *      state and the tape read as a binary number changes by a constant each visit.  Heuristic.
 *   U  none of the above within TMAX steps
 *
 * usage: tm22 randfile [m0 m1] [full]
 *   randfile: 4096*100 lines of 0/1 strings (random initial conditions)
 *   full: do not stop early when C/D is detected; run to TMAX and test C/D at the end only
 * output: one line per machine m0..m1-1:  m nA nB nC nU maxPeriod maxTransient maxSpan
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#define TMAX 10000
#define TAPE (2 * TMAX + 128)
#define NRAND 100
#define MAXSPAN (TMAX + 64)

typedef struct { uint8_t state; int16_t offset; int16_t span; uint64_t lo, hi; } Conf;

#define NEV 16
#define MINEV 5          /* events needed in a stride-k subsequence */
typedef struct { int t; int state; int len; int head; int lmin; char s[MAXSPAN + 1]; } Event;
typedef struct { Event e[NEV]; int start, n; } EvBuf;   /* ring buffer of the last NEV events */
static EvBuf evR, evL;
#define EV(buf, i) (&(buf)->e[((buf)->start + (i)) % NEV])
static int full_mode = 0;

static uint8_t tape[TAPE];
static Conf hist[TMAX + 1];

static void push_event(EvBuf *buf, int t, int state, int head, int lmin, int rmax) {
    if (buf->n == NEV) { buf->start = (buf->start + 1) % NEV; buf->n--; }
    Event *e = EV(buf, buf->n);
    e->t = t; e->state = state; e->head = head; e->lmin = lmin;
    e->len = (lmin > rmax) ? 0 : rmax - lmin + 1;
    for (int i = 0; i < e->len; i++) e->s[i] = tape[lmin + i] ? '1' : '0';
    e->s[e->len] = 0;
    buf->n++;
}

/* Growth step model: S' = P + S[:o] + B + S[o:] + Q with fixed strings P, B, Q and fixed offset o
 * (o is taken as the smallest valid offset).  Covers A B^n C linear growth and nested P S Q growth.
 * step_fit finds, for the pair (S, S') and given |P|, |Q|, the smallest o; returns -1 if none. */
static int step_fit(const char *S, int L, const char *S2, int L2, int plen, int qlen) {
    int blen = L2 - L - plen - qlen;
    if (blen < 0) return -1;
    const char *M = S2 + plen; int ML = L2 - plen - qlen;   /* middle part must be S[:o] B S[o:] */
    int lcp = 0; while (lcp < L && lcp < ML && M[lcp] == S[lcp]) lcp++;
    int lcs = 0; while (lcs < L && lcs < ML && M[ML - 1 - lcs] == S[L - 1 - lcs]) lcs++;
    int o = L - lcs; if (o < 0) o = 0;
    if (o > lcp) return -1;
    return o;
}

/* Event-time model: gaps g_n = t_{n+1} - t_n either have constant second differences (linear growth,
 * returns 1) or obey g_{n+1} = a g_n + b with fixed integers a >= 2, b (nested/counter growth,
 * returns 2).  Returns 0 if neither. */
static int time_model(const int *t, int cnt) {
    int g[NEV], ng = cnt - 1;
    for (int i = 0; i < ng; i++) g[i] = t[i + 1] - t[i];
    int lin = 1;
    for (int i = 0; i + 2 < ng; i++) if (g[i + 2] - g[i + 1] != g[1] - g[0]) lin = 0;
    if (lin) return 1;
    if (ng < 4 || g[1] == g[0] || (g[2] - g[1]) % (g[1] - g[0])) return 0;
    long a = (g[2] - g[1]) / (g[1] - g[0]), b = g[1] - a * g[0];
    if (a < 2) return 0;
    for (int i = 0; i + 1 < ng; i++) if (g[i + 1] != a * g[i] + b) return 0;
    return 2;
}

/* regular growth on one side with stride k: take events n-1, n-1-k, ... (at least MINEV of them);
 * returns 0 (not regular), 1 (linear) or 2 (nested) */
static int regular_k(const EvBuf *buf, int k) {
    int idx[NEV], cnt = 0;
    for (int i = buf->n - 1; i >= 0 && cnt < NEV; i -= k) idx[cnt++] = i;
    if (cnt < MINEV) return 0;
    for (int a = 0, b = cnt - 1; a < b; a++, b--) { int tmp = idx[a]; idx[a] = idx[b]; idx[b] = tmp; }
    int times[NEV];
    for (int n = 0; n < cnt; n++) times[n] = EV(buf, idx[n])->t;
    int tm = time_model(times, cnt);
    if (!tm) return 0;
    int growth = EV(buf, idx[1])->len - EV(buf, idx[0])->len;
    if (growth < 0) return 0;
    for (int n = 0; n + 1 < cnt; n++) {
        const Event *a = EV(buf, idx[n]), *b = EV(buf, idx[n + 1]);
        if (b->state != EV(buf, idx[0])->state) return 0;
        if (b->len - a->len != growth) return 0;
    }
    /* try every split of the growth into |P|, |B|, |Q|; P, B, Q and o must be identical for every step */
    for (int plen = 0; plen <= growth; plen++) for (int qlen = 0; plen + qlen <= growth; qlen++) {
        int blen = growth - plen - qlen, ok = 1, o0 = -1;
        const char *P0 = NULL, *B0 = NULL, *Q0 = NULL;
        for (int n = 0; n + 1 < cnt && ok; n++) {
            const Event *a = EV(buf, idx[n]), *b = EV(buf, idx[n + 1]);
            int o = step_fit(a->s, a->len, b->s, b->len, plen, qlen);
            if (o < 0) { ok = 0; break; }
            const char *P = b->s, *B = b->s + plen + o, *Q = b->s + b->len - qlen;
            if (n == 0) { o0 = o; P0 = P; B0 = B; Q0 = Q; }
            else if (o != o0 || strncmp(P, P0, plen) || strncmp(B, B0, blen) || strncmp(Q, Q0, qlen)) ok = 0;
        }
        if (ok) return tm;
    }
    return 0;
}

static int regular(const EvBuf *buf) {
    for (int k = 1; k <= 3; k++) { int r = regular_k(buf, k); if (r) return r; }
    return 0;
}

/* growth test: every side that grew during the current event window must be regular; a side is
 * quiescent if its last new-extreme event precedes the last `need` events of the other side.
 * need = number of buffered events required on a growing side (NEV for the early test, MINEV at TMAX).
 * Returns 0, or the class: 1 = linear ('C'), 2 = nested ('D') if any regular side is nested. */
static int growth_regular(int need) {
    int fullR = evR.n >= need, fullL = evL.n >= need;
    int quietL = evL.n == 0 || (fullR && EV(&evL, evL.n - 1)->t < EV(&evR, evR.n - need)->t);
    int quietR = evR.n == 0 || (fullL && EV(&evR, evR.n - 1)->t < EV(&evL, evL.n - need)->t);
    int regR = fullR ? regular(&evR) : 0, regL = fullL ? regular(&evL) : 0;
    if (regR && (quietL || regL)) return (regR == 2 || regL == 2) ? 2 : 1;
    if (regL && (quietR || regR)) return (regR == 2 || regL == 2) ? 2 : 1;
    return 0;
}

/* Exact escape test B2: consecutive new-extreme events n, n+1 on one side with identical state, identical
 * non-zero tape content at the identical position, and the head at event n farther from the non-zero
 * cells than the number of steps between the events.  Then the evolution between the events happened
 * entirely on blank tape and repeats verbatim forever (the head carries a bounded pattern outward). */
static int escape_carried(const EvBuf *buf) {
    if (buf->n < 2) return 0;
    const Event *a = EV(buf, buf->n - 2), *b = EV(buf, buf->n - 1);
    if (a->len == 0 || a->state != b->state || a->len != b->len || a->lmin != b->lmin) return 0;
    if (memcmp(a->s, b->s, a->len)) return 0;
    int gap = b->t - a->t;
    int dist = (a->head < a->lmin) ? a->lmin - a->head : a->head - (a->lmin + a->len - 1);
    return dist > gap;
}

static int canon(int state, int head, int lmin, int rmax, Conf *c) {
    /* lmin > rmax means all-zero tape */
    if (lmin > rmax) { c->state = state; c->offset = 0; c->span = 0; c->lo = c->hi = 0; return 1; }
    int span = rmax - lmin + 1;
    if (span > 128) return 0;
    c->state = state; c->offset = head - lmin; c->span = span; c->lo = c->hi = 0;
    for (int i = 0; i < span; i++) if (tape[lmin + i]) { if (i < 64) c->lo |= (1ULL << i); else c->hi |= (1ULL << (i - 64)); }
    return 1;
}

static int same(const Conf *a, const Conf *b) {
    return a->state == b->state && a->offset == b->offset && a->span == b->span && a->lo == b->lo && a->hi == b->hi;
}

static char run_inner(int m, const char *init, int head0, int state0, int *period, int *transient, int *maxspan, int *hmin_out, int *hmax_out);

/* E (post-hoc, heuristic) counter certificate for runs that are otherwise unclassified: re-run the
 * evolution; at every visit of the head to one end of its (final) range after that range was last
 * extended, read the cells of the range as a binary number (either orientation).  The run is a
 * counter if, for some end and orientation, there are at least MINVIS such visits, all in the same
 * state, and the number changes by the same non-zero amount between consecutive visits. */
#define MINVIS 8
static int counter_certificate(int m, const char *init, int head0, int state0, int hmin, int hmax) {
    int ncol[4], nmove[4], nstate[4];
    for (int i = 0; i < 4; i++) { int e = (m >> (3 * (3 - i))) & 7; ncol[i] = e & 1; nmove[i] = ((e >> 1) & 1) ? 1 : -1; nstate[i] = e >> 2; }
    int n = strlen(init), base = TMAX + 32, width = hmax - hmin + 1;
    if (width > 64) return 0;
    for (int i = 0; i < n; i++) tape[base + i] = init[i] == '1';
    int head = base + head0, state = state0, lo = base, hi = base + n - 1, tfix = 0;
    /* visits[end][orient]: count, state, last number, common difference, ok flag */
    long cnt[2][2] = {{0, 0}, {0, 0}}; int st[2][2]; uint64_t last[2][2]; int64_t diff[2][2]; int ok[2][2] = {{1, 1}, {1, 1}};
    for (int t = 0; t <= TMAX; t++) {
        if (head < lo) { lo = head; tfix = t; }
        if (head > hi) { hi = head; tfix = t; }
        if (head == hmin || head == hmax) {
            int end = head == hmax;
            uint64_t a = 0, b = 0;
            for (int i = 0; i < width; i++) if (tape[hmin + i]) { a |= 1ULL << i; b |= 1ULL << (width - 1 - i); }
            uint64_t num[2] = {a, b};
            for (int o = 0; o < 2; o++) {
                if (!ok[end][o]) continue;
                if (cnt[end][o] == 0) { st[end][o] = state; last[end][o] = num[o]; cnt[end][o] = 1; continue; }
                int64_t d = (int64_t)(num[o] - last[end][o]);
                if (state != st[end][o] || d == 0) { ok[end][o] = 0; continue; }
                if (cnt[end][o] == 1) diff[end][o] = d; else if (d != diff[end][o]) { ok[end][o] = 0; continue; }
                last[end][o] = num[o]; cnt[end][o]++;
            }
        }
        if (t == TMAX) break;
        int i = 2 * state + tape[head];
        tape[head] = ncol[i]; state = nstate[i]; head += nmove[i];
    }
    (void)tfix;
    int res = 0;
    for (int e = 0; e < 2; e++) for (int o = 0; o < 2; o++) if (ok[e][o] && cnt[e][o] >= MINVIS) res = 1;
    memset(tape + hmin, 0, hmax - hmin + 1);
    return res;
}

static int dump_u = 0;   /* set by DUMP_U env var: print every unclassified run to stderr */
static char run(int m, const char *init, int head0, int state0, int *period, int *transient, int *maxspan) {
    int hmin, hmax;
    char r = run_inner(m, init, head0, state0, period, transient, maxspan, &hmin, &hmax);
    memset(tape + hmin, 0, hmax - hmin + 1);
    if (r == 'U' && counter_certificate(m, init, head0, state0, hmin, hmax)) r = 'E';
    if (r == 'U' && dump_u) fprintf(stderr, "U %d %s %d %d span %d evR %d evL %d\n", m, init, head0, state0, *maxspan, evR.n, evL.n);
    return r;
}

static char run_inner(int m, const char *init, int head0, int state0, int *period, int *transient, int *maxspan, int *hmin_out, int *hmax_out) {
    int ncol[4], nmove[4], nstate[4];
    for (int i = 0; i < 4; i++) { int e = (m >> (3 * (3 - i))) & 7; ncol[i] = e & 1; nmove[i] = ((e >> 1) & 1) ? 1 : -1; nstate[i] = e >> 2; }
    int n = strlen(init);
    int base = TMAX + 32;
    /* tape is all zero on entry (cleared after each run over the touched range) */
    int lmin = TAPE, rmax = -1;
    int hmin = base, hmax = base + n;
    for (int i = 0; i < n; i++) if (init[i] == '1') { tape[base + i] = 1; if (base + i < lmin) lmin = base + i; if (base + i > rmax) rmax = base + i; }
    int head = base + head0, state = state0, lastmove = 0;
    int seenR = 0, seenL = 0;
    *period = 0; *transient = 0; *maxspan = 0;
    int nh = 0;
    evR.n = evL.n = 0; evR.start = evL.start = 0;
    int hiR = base + n - 1, loL = base;   /* extreme head positions so far */
    for (int t = 0; t <= TMAX; t++) {
        int span = (lmin > rmax) ? 0 : rmax - lmin + 1;
        if (span > *maxspan) *maxspan = span;
        if (head < hmin) hmin = head;
        if (head > hmax) hmax = head;
        *hmin_out = hmin; *hmax_out = hmax;
        /* B: escape test */
        if (lastmove == 1 && head > rmax) { if (seenR & (1 << state)) { *transient = t; return 'B'; } seenR |= 1 << state; } else seenR = 0;
        if (lastmove == -1 && head < lmin) { if (seenL & (1 << state)) { *transient = t; return 'B'; } seenL |= 1 << state; } else seenL = 0;
        /* new-extreme events for the regular-growth test */
        int newev = 0;
        if (head > hiR) { hiR = head; push_event(&evR, t, state, head, lmin, rmax); newev = 1; if (escape_carried(&evR)) { *transient = t; return 'B'; } }
        if (head < loL) { loL = head; push_event(&evL, t, state, head, lmin, rmax); newev = 1; if (escape_carried(&evL)) { *transient = t; return 'B'; } }
        if (newev && !full_mode) { int g = growth_regular(NEV); if (g) { *transient = t; return g == 2 ? 'D' : 'C'; } }
        /* A: recurrence test */
        Conf c;
        if (t <= 2000 && canon(state, head, lmin, rmax, &c)) {
            for (int j = 0; j < nh; j++) if (same(&hist[j], &c)) { *period = t - j; *transient = j; return 'A'; }
            hist[nh++] = c;
        }
        if (t == TMAX) break;
        /* transition */
        int i = 2 * state + tape[head];
        tape[head] = ncol[i];
        if (ncol[i]) { if (head < lmin) lmin = head; if (head > rmax) rmax = head; }
        else if (head == lmin || head == rmax) {   /* recompute extents after erasing a boundary 1 */
            while (lmin <= rmax && !tape[lmin]) lmin++;
            while (rmax >= lmin && !tape[rmax]) rmax--;
            if (lmin > rmax) { lmin = TAPE; rmax = -1; }
        }
        state = nstate[i];
        head += nmove[i];
        lastmove = nmove[i];
        if (head < 1 || head >= TAPE - 1) break;
    }
    if (head < hmin) hmin = head;
    if (head > hmax) hmax = head;
    *hmin_out = hmin; *hmax_out = hmax;
    /* C at the end of the run: require growth to be continuing (an event in the last quarter) */
    int growR = evR.n > 0 && EV(&evR, evR.n - 1)->t > TMAX / 2, growL = evL.n > 0 && EV(&evL, evL.n - 1)->t > TMAX / 2;
    if (growR || growL) { int g = growth_regular(MINEV); if (g) { *transient = TMAX; return g == 2 ? 'D' : 'C'; } }
    return 'U';
}

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: tm22 randfile [m0 m1] [full]\n"); return 1; }
    FILE *rf = fopen(argv[1], "r");
    static char rnd[4096 * NRAND][40];
    for (int i = 0; i < 4096 * NRAND; i++) { if (!fgets(rnd[i], 40, rf)) { fprintf(stderr, "short randfile\n"); return 1; } rnd[i][strcspn(rnd[i], "\r\n")] = 0; }
    fclose(rf);
    char buf[16];
    int m0 = 0, m1 = 4096;
    if (argc > 3) { m0 = atoi(argv[2]); m1 = atoi(argv[3]); }
    if (argc > 4 && !strcmp(argv[4], "full")) full_mode = 1;
    dump_u = getenv("DUMP_U") != NULL;
    for (int m = m0; m < m1; m++) {
        int nA = 0, nB = 0, nC = 0, nD = 0, nE = 0, nU = 0, maxP = 0, maxT = 0, maxS = 0;
        for (int len = 1; len <= 7; len++) for (int v = 0; v < (1 << len); v++) {
            for (int i = 0; i < len; i++) buf[i] = ((v >> (len - 1 - i)) & 1) ? '1' : '0';
            buf[len] = 0;
            for (int h = 0; h < len; h++) for (int s = 0; s < 2; s++) {
                int p, tr, sp;
                char r = run(m, buf, h, s, &p, &tr, &sp);
                if (r == 'A') nA++; else if (r == 'B') nB++; else if (r == 'C') nC++; else if (r == 'D') nD++; else if (r == 'E') nE++; else nU++;
                if (p > maxP) maxP = p;
                if ((r == 'A' || r == 'B') && tr > maxT) maxT = tr;
                if (sp > maxS) maxS = sp;
            }
        }
        for (int k = 0; k < NRAND; k++) {
            int p, tr, sp;
            char r = run(m, rnd[m * NRAND + k], 0, 0, &p, &tr, &sp);
            if (r == 'A') nA++; else if (r == 'B') nB++; else if (r == 'C') nC++; else if (r == 'D') nD++; else if (r == 'E') nE++; else nU++;
            if (p > maxP) maxP = p;
            if ((r == 'A' || r == 'B') && tr > maxT) maxT = tr;
            if (sp > maxS) maxS = sp;
        }
        printf("%d %d %d %d %d %d %d %d %d %d\n", m, nA, nB, nC, nD, nE, nU, maxP, maxT, maxS);
        fflush(stdout);
    }
    return 0;
}
