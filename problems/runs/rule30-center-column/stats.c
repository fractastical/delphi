/*
 * stats.c -- the statistics registered in PREREG.md, on a packed Rule 30 column and on a PRNG null.
 *
 *   stats COLUMN.bin L R [-j threads] [-bm BMLEN] [-seed0 1000] [-nosecondary]
 *
 * COLUMN.bin: bits c[0..], MSB-first packing (byte k, bit 7 = c[8k]) as written by rule30.c.
 * L: number of bits used (prefix).  R: number of Monte Carlo null sequences (xoshiro256**, seed
 * splitmix64(seed0 + r), r = 1..R), each of L bits, with the identical statistics.
 * Prints one JSON object on stdout.
 *
 * Bit t of a sequence is (W[t>>6] >> (t&63)) & 1 internally.
 */
#define _GNU_SOURCE
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <pthread.h>
#include <stdatomic.h>

typedef uint64_t u64;
#define PADWORDS 40
#define BLOCK 1000000L
#define NLAG 1024
#define NPSI 20
#define CHECK 4096L

/* ---------------- PRNG ---------------- */
static u64 splitmix(u64 *x) { u64 z = (*x += 0x9e3779b97f4a7c15ULL); z = (z ^ (z >> 30)) * 0xbf58476d1ce4e5b9ULL; z = (z ^ (z >> 27)) * 0x94d049bb133111ebULL; return z ^ (z >> 31); }
typedef struct { u64 s[4]; } xo_t;
static inline u64 rotl(u64 x, int k) { return (x << k) | (x >> (64 - k)); }
static void xo_seed(xo_t *g, u64 seed) { for (int i = 0; i < 4; i++) g->s[i] = splitmix(&seed); }
static inline u64 xo_next(xo_t *g) {
    u64 r = rotl(g->s[1] * 5, 7) * 9, t = g->s[1] << 17;
    g->s[2] ^= g->s[0]; g->s[3] ^= g->s[1]; g->s[1] ^= g->s[2]; g->s[0] ^= g->s[3];
    g->s[2] ^= t; g->s[3] = rotl(g->s[3], 45); return r;
}

/* ---------------- statistics container ---------------- */
enum { S_ONES, S_LIL, S_MAXZ, S_BCHI, S_BKS, S_BMAX, S_BF2, S_RUNZ, S_LONGRUN,
       S_ACMAX, S_ACSQ, S_PERR, S_PERP, S_MINIST, S_PSI0, S_NSTAT = S_PSI0 + NPSI + 1 };
static const char *NAMES[S_NSTAT];
typedef struct { double v[S_NSTAT]; int sec; } St;

static long L, R, BMLEN = 0;
static int NT = 6, DOSEC = 1;

static inline int bit_at(const u64 *W, long t) { return (W[t >> 6] >> (t & 63)) & 1; }
static inline u64 get64(const u64 *W, long start) {      /* bits start..start+63, LSB = start */
    long w = start >> 6; int s = start & 63;
    return s ? (W[w] >> s) | (W[w + 1] << (64 - s)) : W[w];
}
static double Phi(double z) { return 0.5 * erfc(-z / M_SQRT2); }
static int cmpd(const void *a, const void *b) { double x = *(double *)a, y = *(double *)b; return (x > y) - (x < y); }

/* mask: zero all bits at index >= L (buffer already padded) */
static void mask_tail(u64 *W, long L) {
    long nw = (L + 63) / 64;
    if (L & 63) W[nw - 1] &= (1ULL << (L & 63)) - 1;
    for (long i = nw; i < nw + PADWORDS; i++) W[i] = 0;
}

static void primary(const u64 *W, St *s) {
    long nw = L / 64, rem = L & 63; long ones = 0;
    /* running walk with checkpoints every CHECK bits */
    double lil = 0, maxz = 0; long cum = 0;
    for (long i = 0; i < nw; i++) {
        cum += __builtin_popcountll(W[i]);
        long m = (i + 1) * 64;
        if (m % CHECK == 0) {
            double sm = fabs(2.0 * cum - m);
            double r1 = sm / sqrt(2.0 * m * log(log((double)m)));
            double r2 = sm / sqrt((double)m);
            if (r1 > lil) lil = r1;
            if (r2 > maxz) maxz = r2;
        }
    }
    ones = cum + (rem ? __builtin_popcountll(W[nw] & ((1ULL << rem) - 1)) : 0);
    s->v[S_ONES] = (double)ones; s->v[S_LIL] = lil; s->v[S_MAXZ] = maxz;
    /* blocks */
    long B = L / BLOCK; double chi = 0, bmax = 0; long gt2 = 0;
    double *zs = (double *)malloc(sizeof(double) * (B > 0 ? B : 1));
    for (long b = 0; b < B; b++) {
        long c = 0; for (long i = b * (BLOCK / 64); i < (b + 1) * (BLOCK / 64); i++) c += __builtin_popcountll(W[i]);
        double z = (2.0 * c - BLOCK) / sqrt((double)BLOCK);
        zs[b] = z; chi += z * z; if (fabs(z) > bmax) bmax = fabs(z); if (fabs(z) > 2) gt2++;
    }
    double ks = 0;
    if (B > 0) {
        qsort(zs, B, sizeof(double), cmpd);
        for (long i = 0; i < B; i++) { double f = Phi(zs[i]); double d1 = fabs(f - (double)i / B), d2 = fabs(f - (double)(i + 1) / B); if (d1 > ks) ks = d1; if (d2 > ks) ks = d2; }
    }
    free(zs);
    s->v[S_BCHI] = chi; s->v[S_BKS] = ks; s->v[S_BMAX] = bmax; s->v[S_BF2] = B ? (double)gt2 / B : 0;
    /* runs: positions t in [0, L-2] where c[t] != c[t+1] */
    long nd = 0, longest = 0, prev = -1; /* run boundaries: a run ends at t when c[t]!=c[t+1] */
    long nwords = (L - 1 + 63) / 64;
    for (long i = 0; i < nwords; i++) {
        u64 d = W[i] ^ ((W[i] >> 1) | (W[i + 1] << 63));
        long base = i * 64;
        if (base + 64 > L - 1) { long valid = L - 1 - base; if (valid < 64) d &= (valid > 0) ? ((1ULL << valid) - 1) : 0; }
        nd += __builtin_popcountll(d);
        while (d) { int k = __builtin_ctzll(d); long t = base + k; long run = t - prev; if (run > longest) longest = run; prev = t; d &= d - 1; }
    }
    { long run = (L - 1) - prev; if (run > longest) longest = run; }
    double V = 1.0 + nd;
    s->v[S_RUNZ] = (V - (L + 1) / 2.0) / (sqrt((double)(L - 1)) / 2.0);
    s->v[S_LONGRUN] = (double)longest;
}

static void secondary(const u64 *W, St *s, u64 *tblmem) {
    /* autocorrelation, lags 1..NLAG */
    double mx = 0, sq = 0;
    for (int k = 1; k <= NLAG; k++) {
        long n = L - k; long off = k >> 6; int sh = k & 63; long cnt = 0;
        long full = n / 64;
        for (long i = 0; i < full; i++) {
            u64 y = sh ? (W[i + off] >> sh) | (W[i + off + 1] << (64 - sh)) : W[i + off];
            cnt += __builtin_popcountll(W[i] ^ y);
        }
        long r = n & 63;
        if (r) { u64 y = sh ? (W[full + off] >> sh) | (W[full + off + 1] << (64 - sh)) : W[full + off];
                 cnt += __builtin_popcountll((W[full] ^ y) & ((1ULL << r) - 1)); }
        double A = (double)n - cnt;
        double z = (2.0 * A - n) / sqrt((double)n);
        if (fabs(z) > mx) mx = fabs(z); sq += z * z;
    }
    s->v[S_ACMAX] = mx; s->v[S_ACSQ] = sq;
    /* overlapping pattern counts: 20-bit windows c[t..t+19], first bit = MSB */
    uint32_t *tb = (uint32_t *)tblmem; memset(tb, 0, sizeof(uint32_t) << NPSI);
    uint32_t w = 0, mask = (1u << NPSI) - 1;
    for (long t = 0; t < NPSI - 1; t++) w = (w << 1) | bit_at(W, t);
    long nwin = L - (NPSI - 1);
    for (long t = 0; t < nwin; t++) {
        w = ((w << 1) | bit_at(W, t + NPSI - 1)) & mask;
        tb[w]++;
    }
    double *cur = (double *)malloc(sizeof(double) << NPSI);
    for (long j = 0; j < (1L << NPSI); j++) cur[j] = tb[j];
    for (int m = NPSI; m >= 1; m--) {
        long cells = 1L << m; double E = (double)nwin / cells, acc = 0;
        for (long j = 0; j < cells; j++) { double d = cur[j] - E; acc += d * d / E; }
        s->v[S_PSI0 + m] = acc;
        for (long j = 0; j < cells / 2; j++) cur[j] = cur[2 * j] + cur[2 * j + 1];
    }
    free(cur);
    /* longest suffix agreement R = max_p r(p) (period statistic), all p in 1..L-1 */
    long Rmax = 0, Rp = 0, minist = L; long third = L / 3;
    for (long p = 1; p < L; p++) {
        long ih = L - p - 1, istar = -1;
        for (;;) {
            long st = ih - 63; u64 msk = ~0ULL;
            if (st < 0) { st = 0; msk = (ih >= 63) ? ~0ULL : ((2ULL << ih) - 1); }
            u64 d = (get64(W, st) ^ get64(W, st + p)) & msk;
            if (d) { istar = st + 63 - __builtin_clzll(d); break; }
            if (st == 0) break;
            ih = st - 1;
        }
        long r = (L - p - 1) - istar;
        if (r > Rmax) { Rmax = r; Rp = p; }
        if (p <= third && istar < minist) minist = istar;
    }
    s->v[S_PERR] = (double)Rmax; s->v[S_PERP] = (double)Rp; s->v[S_MINIST] = (double)minist;
}

/* ---------------- Berlekamp-Massey over GF(2) on the first n bits: max |L_n - n/2| ---------------- */
static void bm_profile(const u64 *W, long n, double *maxdev, double *final_dev, long *finalL) {
    long nw = n / 64 + 4;
    u64 *Rv = (u64 *)calloc((size_t)nw * 2 + 8, 8);     /* reversed sequence: bit (n-1-i) = s_i */
    for (long i = 0; i < n; i++) if (bit_at(W, i)) { long q = n - 1 - i; Rv[q >> 6] |= 1ULL << (q & 63); }
    u64 *C = (u64 *)calloc((size_t)nw + 8, 8), *Bp = (u64 *)calloc((size_t)nw + 8, 8), *T = (u64 *)calloc((size_t)nw + 8, 8);
    C[0] = 1; Bp[0] = 1;
    long Lc = 0, m = 1; double mx = 0;
    for (long i = 0; i < n; i++) {
        /* discrepancy d = sum_{j=0..Lc} C_j * s_{i-j}; s_{i-j} is Rv bit (n-1-i+j) */
        long off = n - 1 - i; int par = 0;
        long words = Lc / 64 + 1;
        for (long w = 0; w < words; w++) {
            u64 cw = C[w];
            if (w == words - 1 && ((Lc + 1) & 63)) cw &= (1ULL << ((Lc + 1) & 63)) - 1;
            par ^= __builtin_popcountll(cw & get64(Rv, off + 64 * w)) & 1;
        }
        if (par) {
            if (2 * Lc <= i) {
                long twords = nw; memcpy(T, C, (size_t)twords * 8);
                /* C ^= B << m */
                long ws = m >> 6; int bs = m & 63;
                for (long w = nw - 1; w >= ws; w--) {
                    u64 v = Bp[w - ws] << bs; if (bs && w - ws - 1 >= 0) v |= Bp[w - ws - 1] >> (64 - bs);
                    C[w] ^= v;
                }
                long newL = i + 1 - Lc;
                memcpy(Bp, T, (size_t)twords * 8); Lc = newL; m = 1;
            } else {
                long ws = m >> 6; int bs = m & 63;
                for (long w = nw - 1; w >= ws; w--) {
                    u64 v = Bp[w - ws] << bs; if (bs && w - ws - 1 >= 0) v |= Bp[w - ws - 1] >> (64 - bs);
                    C[w] ^= v;
                }
                m++;
            }
        } else m++;
        double dev = fabs((double)Lc - (i + 1) / 2.0);
        if (dev > mx) mx = dev;
    }
    *maxdev = mx; *final_dev = Lc - n / 2.0; *finalL = Lc;
    free(Rv); free(C); free(Bp); free(T);
}

/* ---------------- null workers ---------------- */
static St *nulls; static atomic_long nextrep; static int NSEC_REPS;
static void gen_null(u64 *W, long rep, u64 seed0) {
    xo_t g; xo_seed(&g, seed0 + rep);
    long nw = (L + 63) / 64;
    for (long i = 0; i < nw; i++) W[i] = xo_next(&g);
    mask_tail(W, L);
}
static u64 SEED0 = 1000; static double *bmnull; static int BMREPS = 20; static double *bmnullL;
static void *nworker(void *arg) {
    (void)arg;
    u64 *W = (u64 *)calloc((size_t)((L + 63) / 64 + PADWORDS), 8);
    u64 *tbl = (u64 *)malloc(sizeof(uint32_t) << NPSI);
    for (;;) {
        long r = atomic_fetch_add(&nextrep, 1);
        if (r >= R + BMREPS) break;
        if (r < R) {
            gen_null(W, r + 1, SEED0);
            primary(W, &nulls[r]); nulls[r].sec = 0;
            if (DOSEC) { secondary(W, &nulls[r], tbl); nulls[r].sec = 1; }
        } else if (BMLEN > 0) {
            long rep = r - R; gen_null(W, rep + 1, SEED0 + 777777);
            double md, fd; long fl; bm_profile(W, BMLEN, &md, &fd, &fl);
            bmnull[rep] = md; bmnullL[rep] = fd;
        }
    }
    free(W); free(tbl); return NULL;
}

static void jstr(const char *k, double v, int last) { printf("    \"%s\": %.10g%s\n", k, v, last ? "" : ","); }

int main(int argc, char **argv) {
    if (argc < 4) { fprintf(stderr, "usage: stats COLUMN.bin L R [-j T] [-bm LEN] [-seed0 S] [-nosecondary]\n"); return 2; }
    const char *path = argv[1]; L = atol(argv[2]); R = atol(argv[3]);
    for (int i = 4; i < argc; i++) {
        if (!strcmp(argv[i], "-j")) NT = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-bm")) BMLEN = atol(argv[++i]);
        else if (!strcmp(argv[i], "-seed0")) SEED0 = strtoull(argv[++i], 0, 10);
        else if (!strcmp(argv[i], "-nosecondary")) DOSEC = 0;
        else if (!strcmp(argv[i], "-bmreps")) BMREPS = atoi(argv[++i]);
    }
    if (BMLEN == 0) BMREPS = 0;
    FILE *f = fopen(path, "rb"); if (!f) { perror(path); return 1; }
    fseek(f, 0, SEEK_END); long fsz = ftell(f); fseek(f, 0, SEEK_SET);
    uint8_t *pk = (uint8_t *)malloc(fsz); if (fread(pk, 1, fsz, f) != (size_t)fsz) return 1; fclose(f);
    if (L > fsz * 8) { fprintf(stderr, "L exceeds file (%ld bits)\n", fsz * 8); return 1; }
    u64 *W = (u64 *)calloc((size_t)((L + 63) / 64 + PADWORDS), 8);
    for (long t = 0; t < L; t++) if (pk[t >> 3] & (0x80 >> (t & 7))) W[t >> 6] |= 1ULL << (t & 63);
    free(pk);
    mask_tail(W, L);
    NAMES[S_ONES] = "ones"; NAMES[S_LIL] = "lil_ratio_max"; NAMES[S_MAXZ] = "max_abs_s_over_sqrt_m";
    NAMES[S_BCHI] = "block_chi2"; NAMES[S_BKS] = "block_ks"; NAMES[S_BMAX] = "block_max_abs_z";
    NAMES[S_BF2] = "block_frac_abs_z_gt_2"; NAMES[S_RUNZ] = "runs_z"; NAMES[S_LONGRUN] = "longest_run";
    NAMES[S_ACMAX] = "autocorr_max_abs_z"; NAMES[S_ACSQ] = "autocorr_sum_z2"; NAMES[S_PERR] = "max_suffix_agreement_R"; NAMES[S_PERP] = "argmax_p_of_R"; NAMES[S_MINIST] = "min_istar_over_p_le_L3";
    static char psin[NPSI + 1][16];
    for (int m = 1; m <= NPSI; m++) { snprintf(psin[m], 16, "psi2_m%02d", m); NAMES[S_PSI0 + m] = psin[m]; }

    St obs; memset(&obs, 0, sizeof obs);
    primary(W, &obs);
    u64 *tbl = (u64 *)malloc(sizeof(uint32_t) << NPSI);
    if (DOSEC) secondary(W, &obs, tbl);
    double bm_obs_max = 0, bm_obs_final = 0; long bm_obs_L = 0;
    if (BMLEN > 0) bm_profile(W, BMLEN, &bm_obs_max, &bm_obs_final, &bm_obs_L);

    nulls = (St *)calloc(R > 0 ? R : 1, sizeof(St));
    bmnull = (double *)calloc(BMREPS + 1, sizeof(double)); bmnullL = (double *)calloc(BMREPS + 1, sizeof(double));
    atomic_store(&nextrep, 0);
    pthread_t th[64]; for (int i = 0; i < NT; i++) pthread_create(&th[i], NULL, nworker, NULL);
    for (int i = 0; i < NT; i++) pthread_join(th[i], NULL);

    /* ---- output ---- */
    long B = L / BLOCK;
    printf("{\n  \"L\": %ld, \"R\": %ld, \"blocks\": %ld, \"seed0\": %llu, \"secondary\": %d,\n  \"observed\": {\n", L, R, B, (unsigned long long)SEED0, DOSEC);
    int first = 1;
    for (int k = 0; k < S_NSTAT; k++) {
        if (!NAMES[k]) continue;
        if (k >= S_ACMAX && !DOSEC) continue;
        if (k == S_PSI0) continue;
        printf("%s    \"%s\": %.10g", first ? "" : ",\n", NAMES[k], obs.v[k]); first = 0;
    }
    printf("\n  },\n  \"null\": {\n");
    first = 1;
    for (int k = 0; k < S_NSTAT; k++) {
        if (!NAMES[k] || k == S_PSI0) continue;
        if (k >= S_ACMAX && !DOSEC) continue;
        if (R <= 0) continue;
        double *a = (double *)malloc(sizeof(double) * R); double mean = 0;
        long ge = 0, le = 0, gea = 0;
        for (long r = 0; r < R; r++) { a[r] = nulls[r].v[k]; mean += a[r]; if (a[r] >= obs.v[k]) ge++; if (a[r] <= obs.v[k]) le++;
                                       if (fabs(a[r]) >= fabs(obs.v[k])) gea++; }
        mean /= R; double var = 0; for (long r = 0; r < R; r++) var += (a[r] - mean) * (a[r] - mean); var /= (R > 1 ? R - 1 : 1);
        qsort(a, R, sizeof(double), cmpd);
        printf("%s    \"%s\": {\"mean\": %.8g, \"sd\": %.8g, \"min\": %.8g, \"q01\": %.8g, \"q50\": %.8g, \"q99\": %.8g, \"max\": %.8g, "
               "\"p_upper\": %.6g, \"p_lower\": %.6g, \"p_abs_upper\": %.6g}",
               first ? "" : ",\n", NAMES[k], mean, sqrt(var), a[0], a[(long)(0.01 * (R - 1))], a[(R - 1) / 2], a[(long)(0.99 * (R - 1))], a[R - 1],
               (1.0 + ge) / (R + 1.0), (1.0 + le) / (R + 1.0), (1.0 + gea) / (R + 1.0));
        first = 0; free(a);
    }
    printf("\n  }");
    if (BMLEN > 0) {
        double mm = 0, mxn = 0; for (int i = 0; i < BMREPS; i++) { mm += bmnull[i]; if (bmnull[i] > mxn) mxn = bmnull[i]; } mm /= BMREPS;
        printf(",\n  \"berlekamp_massey\": {\"n\": %ld, \"observed_max_abs_dev\": %.1f, \"observed_final_L\": %ld, \"observed_final_dev\": %.1f, "
               "\"null_reps\": %d, \"null_mean_max_abs_dev\": %.2f, \"null_max_max_abs_dev\": %.1f}", BMLEN, bm_obs_max, bm_obs_L, bm_obs_final, BMREPS, mm, mxn);
    }
    printf("\n}\n");
    return 0;
}
