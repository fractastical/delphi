/*
 * rule30.c -- bit-parallel, light-cone-trimmed, multithreaded computation of the
 * Rule 30 center column from a single black cell.
 *
 *   rule30 N [-S steps_per_pass] [-T tile_words] [-j threads] [-K fuse] [-o packed.bin] [-q]
 *
 * Computes center cells c[0..N] (c[0] = 1 is the seed itself; c[t] is the cell below it
 * after t steps) and writes them packed MSB-first (byte k, bit 7 = c[8k]) -- the same order
 * as the Wolfram Data Repository "A Billion Bits" byte array -- N+1 bits, zero padded.
 *
 * Rule 30:  x'[i] = x[i-1] XOR (x[i] OR x[i+1]).
 * Cell x lives in word x>>6, bit x&63 (LSB = smallest x).  Seed at x = N, array x in [0,2N].
 *
 * Light cone: c[t] for t <= N depends only on initial cells within distance t, so at row t only
 * cells x in [t, 2N-t] matter (the correct region), and the true row t is zero outside
 * [N-t, N+t].  Work per row is therefore 2*min(t, N-t) cells; total ~ N^2/2 cell updates.
 *
 * Temporal blocking: each pass advances S rows.  The active word range is cut into tiles; a
 * tile copies its words plus a halo of H = 1 + ceil(S/64) words on each side into an L1-sized
 * buffer, runs S steps in place (the K-stage pipelined kernel; errors enter from the buffer
 * edges at <= 1 cell/step and 1 word at the start, so the middle words stay exact), and writes
 * its middle words to the other row buffer.  Tiles are independent => trivially parallel.
 *
 * Build: cc -O3 -march=native -pthread -o rule30 rule30.c
 */
#define _GNU_SOURCE
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdatomic.h>
#include <pthread.h>
#include <time.h>
#include <unistd.h>

typedef uint64_t u64;

#define MAXK 8

static long N;
static int S = 1024, TILE = 2048, NT = 1, KF = 4, QUIET = 0;
static u64 *bufA, *bufB;      /* two row buffers, with PAD words of zero padding each side   */
static long PADW;
static uint8_t *col;          /* col[t] = c[t] as bytes                                      */

/* ---------- one-step in-place sweep (used for remainders and for the center tile) -------- */
static inline void step1(u64 *b, long T) {
    u64 prev = b[0], c = b[1];
    for (long j = 1; j < T - 1; j++) {
        u64 nx = b[j + 1];
        b[j] = ((c << 1) | (prev >> 63)) ^ (c | ((c >> 1) | (nx << 63)));
        prev = c; c = nx;
    }
}

/* ---------- K-stage pipelined sweep: advances K rows in one pass over the buffer --------- */
/* Stage s keeps its previous two input words p[s], c[s]; when a new input word arrives at
 * the stage it emits the output word for the index of c[s].  Word 0 and the last word are
 * computed with zero neighbors outside the buffer: garbage, but only inside the halo.      */
#define DEFINE_STEPK(K)                                                                     \
static void stepK_##K(u64 *b, long T) {                                                     \
    u64 p[K], c[K];                                                                         \
    for (int s = 0; s < K; s++) { p[s] = 0; c[s] = 0; }                                     \
    for (long j = 0; j < T + K; j++) {                                                      \
        u64 in = (j < T) ? b[j] : 0;                                                        \
        for (int s = 0; s < K; s++) {                                                       \
            u64 out = ((c[s] << 1) | (p[s] >> 63)) ^ (c[s] | ((c[s] >> 1) | (in << 63)));   \
            p[s] = c[s]; c[s] = in; in = out;                                               \
        }                                                                                   \
        long idx = j - K;                                                                   \
        if (idx >= 0 && idx < T) b[idx] = in;                                               \
    }                                                                                       \
}
DEFINE_STEPK(1) DEFINE_STEPK(2) DEFINE_STEPK(3) DEFINE_STEPK(4)
DEFINE_STEPK(5) DEFINE_STEPK(6) DEFINE_STEPK(8)

/* The stage-index offset: stage s output word index = j - s - 1, final stage K-1 -> j-K. In
 * the loop above the first stage's out is for index j-1, the second's for j-2, ... correct. */

static void stepK(u64 *b, long T, int K) {
    switch (K) {
    case 1: stepK_1(b, T); break; case 2: stepK_2(b, T); break;
    case 3: stepK_3(b, T); break; case 4: stepK_4(b, T); break;
    case 5: stepK_5(b, T); break; case 6: stepK_6(b, T); break;
    case 8: stepK_8(b, T); break;
    default: fprintf(stderr, "unsupported K\n"); exit(2);
    }
}

/* ---------- pass description shared with workers ---------------------------------------- */
static struct {
    const u64 *in; u64 *out;
    long wa;            /* first output word                                    */
    long nwords;        /* number of output words                               */
    long ntiles;
    int  H, Seff;
    long t0;
    long cw;            /* center word (N>>6), tile with it records the column  */
    atomic_long next;
} P;

static void do_tile(long ti, u64 *loc) {
    long a = P.wa + ti * TILE;
    long b = a + TILE; if (b > P.wa + P.nwords) b = P.wa + P.nwords;
    long T = (b - a) + 2L * P.H;
    memcpy(loc, P.in + (a - P.H) + PADW, (size_t)T * sizeof(u64));
    int centre = (P.cw >= a && P.cw < b);
    if (centre) {
        long cj = P.cw - a + P.H; int cb = (int)(N & 63);
        for (int s = 1; s <= P.Seff; s++) {
            step1(loc, T);
            col[P.t0 + s] = (loc[cj] >> cb) & 1;
        }
    } else {
        int left = P.Seff;
        while (left >= KF) { stepK(loc, T, KF); left -= KF; }
        while (left > 0)   { step1(loc, T); left--; }
    }
    memcpy(P.out + a + PADW, loc + P.H, (size_t)(b - a) * sizeof(u64));
}

/* ---------- persistent worker threads with a spin barrier ------------------------------- */
static atomic_long gen = 0, done_count = 0;
static atomic_int quit = 0;

static void work_loop(u64 *loc) {
    for (;;) {
        long ti = atomic_fetch_add_explicit(&P.next, 1, memory_order_relaxed);
        if (ti >= P.ntiles) break;
        do_tile(ti, loc);
    }
}
static void *worker(void *arg) {
    (void)arg;
    u64 *loc = (u64 *)aligned_alloc(64, ((size_t)(TILE + 2 * (S / 64 + 4) + 16) * 8 + 63) / 64 * 64);
    long seen = 0;
    for (;;) {
        long g;
        while ((g = atomic_load_explicit(&gen, memory_order_acquire)) == seen) {
            if (atomic_load(&quit)) { free(loc); return NULL; }
        }
        seen = g;
        work_loop(loc);
        atomic_fetch_add_explicit(&done_count, 1, memory_order_release);
    }
}

static double now(void) {
    struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + ts.tv_nsec * 1e-9;
}

static void write_packed(const char *path, long upto) {   /* bits c[0..upto] */
    long nb = (upto + 1 + 7) / 8;
    uint8_t *pk = (uint8_t *)calloc((size_t)nb, 1);
    for (long t = 0; t <= upto; t++) if (col[t]) pk[t >> 3] |= (uint8_t)(0x80 >> (t & 7));
    char tmp[1024]; snprintf(tmp, sizeof tmp, "%s.tmp", path);
    FILE *f = fopen(tmp, "wb"); if (!f) { perror("fopen"); exit(1); }
    fwrite(pk, 1, (size_t)nb, f); fclose(f); rename(tmp, path);
    free(pk);
}

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: rule30 N [-S s] [-T tile] [-j thr] [-K k] [-o file] [-q]\n"); return 2; }
    N = atol(argv[1]);
    const char *outp = NULL;
    for (int i = 2; i < argc; i++) {
        if (!strcmp(argv[i], "-S")) S = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-T")) TILE = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-j")) NT = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-K")) KF = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-o")) outp = argv[++i];
        else if (!strcmp(argv[i], "-q")) QUIET = 1;
    }
    if (NT < 1) NT = 1;
    long width = 2 * N + 1;
    long nw = (width + 63) / 64 + 2;
    PADW = S / 64 + 8 + TILE;                       /* halo reads may run past either end   */
    size_t tot = (size_t)(nw + 2 * PADW);
    bufA = (u64 *)calloc(tot, 8); bufB = (u64 *)calloc(tot, 8);
    col = (uint8_t *)calloc((size_t)N + 2, 1);
    if (!bufA || !bufB || !col) { fprintf(stderr, "alloc failed\n"); return 1; }
    bufA[PADW + (N >> 6)] |= 1ULL << (N & 63);
    col[0] = 1;
    u64 *in = bufA, *out = bufB;

    pthread_t th[256];
    for (int i = 1; i < NT; i++) pthread_create(&th[i], NULL, worker, NULL);
    u64 *loc = (u64 *)aligned_alloc(64, ((size_t)(TILE + 2 * (S / 64 + 4) + 16) * 8 + 63) / 64 * 64);

    double t_start = now(), t_last = t_start, t_flush = t_start;
    long last_t0 = 0;
    for (long t0 = 0; t0 < N; ) {
        int Seff = (int)((N - t0) < S ? (N - t0) : S);
        long tl = t0 + Seff;
        long A = tl > N - tl ? tl : N - tl;
        long B = (2 * N - tl) < (N + tl) ? (2 * N - tl) : (N + tl);
        P.in = in; P.out = out;
        P.wa = A >> 6; P.nwords = (B >> 6) - P.wa + 1;
        P.ntiles = (P.nwords + TILE - 1) / TILE;
        P.H = 1 + (Seff + 63) / 64; P.Seff = Seff; P.t0 = t0; P.cw = N >> 6;
        atomic_store(&P.next, 0);
        atomic_store(&done_count, 0);
        atomic_fetch_add_explicit(&gen, 1, memory_order_release);
        work_loop(loc);
        while (atomic_load_explicit(&done_count, memory_order_acquire) < NT - 1) { }
        u64 *tmp = in; in = out; out = tmp;
        t0 = tl;
        double tn = now();
        if (!QUIET && tn - t_last > 30.0) {
            double frac = (double)t0 / (double)N; double el = tn - t_start;
            /* work done ~ (t0/N)^2 for t0<N/2 ... report simple elapsed fraction of N^2/2 */
            double w = (t0 <= N / 2) ? (double)t0 * t0 : (double)N * N / 2.0 - (double)(N - t0) * (N - t0);
            double wf = w / ((double)N * N / 2.0);
            fprintf(stderr, "[%7.1fs] t=%ld (%.1f%% rows, %.1f%% work)  eta %.0fs\n", el, t0, 100 * frac, 100 * wf,
                    wf > 0 ? el * (1 - wf) / wf : 0.0);
            t_last = tn; (void)last_t0;
            if (outp && tn - t_flush > 300.0) { write_packed(outp, t0); t_flush = tn; }
        }
    }
    atomic_store(&quit, 1);
    for (int i = 1; i < NT; i++) pthread_join(th[i], NULL);
    double el = now() - t_start;
    if (outp) write_packed(outp, N);
    long ones = 0; for (long t = 0; t <= N; t++) ones += col[t];
    fprintf(stderr, "done N=%ld in %.2fs (S=%d TILE=%d K=%d threads=%d)  ones=%ld\n", N, el, S, TILE, KF, NT, ones);
    return 0;
}
