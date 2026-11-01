"""Minimal phylogenetics + PGLS toolkit (numpy/scipy only).

* parse_newick / read_nexus_trees: Newick with branch lengths, optional NEXUS TRANSLATE table.
* Tree.vcv(keep): phylogenetic covariance (shared root-to-MRCA path length) of the subtree spanned by
  the kept tips, measured from the MRCA of the kept tips, scaled to unit maximum tip depth.
* fit_pgls: ML generalised least squares with Pagel's lambda (off-diagonals multiplied by lambda).
"""
import re
import numpy as np
from scipy import linalg, optimize, stats

_TOK = re.compile(r"[(),;]|[^(),;]+")


class Tree:
    def __init__(self, parent, length, label):
        self.parent, self.length, self.label = parent, length, label
        n = len(parent)
        depth = np.zeros(n)
        for i in range(1, n):  # nodes are created in preorder: parent id < child id
            depth[i] = depth[parent[i]] + length[i]
        self.depth = depth
        self.leaf = {lab: i for i, lab in enumerate(label) if lab is not None}

    def vcv(self, keep):
        """keep: list of tip labels (in the row order wanted). Returns (C, base, scale)."""
        n = len(keep)
        idx_of = {self.leaf[k]: j for j, k in enumerate(keep)}
        C = np.zeros((n, n))
        child_lists = {}
        base = None
        N = len(self.parent)
        for i in range(N - 1, -1, -1):
            if self.label[i] is not None:
                lst = [idx_of[i]] if i in idx_of else []
            else:
                groups = [g for g in child_lists.pop(i, []) if g]
                lst = []
                for g in groups:
                    for h in lst_groups_prev(lst, groups, g):
                        pass
                if len(groups) > 1:
                    for a in range(len(groups)):
                        for b in range(a + 1, len(groups)):
                            ga, gb = groups[a], groups[b]
                            C[np.ix_(ga, gb)] = self.depth[i]
                            C[np.ix_(gb, ga)] = self.depth[i]
                lst = [t for g in groups for t in g]
                if len(lst) == n and base is None:
                    base = self.depth[i]
            if lst and i > 0:
                child_lists.setdefault(self.parent[i], []).append(lst)
        if base is None:
            raise ValueError("kept tips have no common ancestor")
        tipdepth = np.array([self.depth[self.leaf[k]] for k in keep])
        C[np.diag_indices(n)] = tipdepth
        C -= base
        C[np.diag_indices(n)] = tipdepth - base
        scale = np.max(np.diag(C))
        return C / scale, base, scale


def lst_groups_prev(a, b, c):  # placeholder kept trivial (no-op generator)
    return ()


def parse_newick(s, translate=None):
    s = re.sub(r"\[[^\]]*\]", "", s).strip()
    parent, length, label = [], [], []
    stack = []
    last_closed = None
    prev = None
    for tok in _TOK.findall(s):
        if tok == "(":
            nid = len(parent)
            parent.append(stack[-1] if stack else -1)
            length.append(0.0)
            label.append(None)
            stack.append(nid)
            prev = "("
        elif tok == ",":
            prev = ","
        elif tok == ")":
            last_closed = stack.pop()
            prev = ")"
        elif tok == ";":
            break
        else:
            name, _, bl = tok.partition(":")
            bl = float(bl) if bl else 0.0
            if prev == ")":
                length[last_closed] = bl
                if name:
                    pass  # internal node label ignored
            else:
                nid = len(parent)
                parent.append(stack[-1] if stack else -1)
                length.append(bl)
                name = name.strip()
                label.append(translate.get(name, name) if translate else name)
            prev = "t"
    return Tree(parent, length, label)


def read_nexus_trees(path):
    txt = open(path).read()
    low = txt.lower()
    i = low.find("begin trees")
    body = txt[i:]
    translate = {}
    m = re.search(r"translate(.*?);", body, flags=re.S | re.I)
    start = 0
    if m:
        for part in m.group(1).split(","):
            kv = part.split()
            if len(kv) == 2:
                translate[kv[0]] = kv[1]
        start = m.end()
    trees = []
    for tm in re.finditer(r"^\s*tree\s+[^=]*=\s*(.*?;)", body[start:], flags=re.S | re.I | re.M):
        trees.append(parse_newick(tm.group(1), translate))
    return trees


def _ml(y, X, C, lam, want_all=False):
    n = len(y)
    V = C * lam
    V[np.diag_indices(n)] = np.diag(C)
    L = linalg.cholesky(V, lower=True)
    Ly = linalg.solve_triangular(L, y, lower=True)
    LX = linalg.solve_triangular(L, X, lower=True)
    beta, *_ = np.linalg.lstsq(LX, Ly, rcond=None)
    r = Ly - LX @ beta
    rss = float(r @ r)
    logdet = 2 * np.sum(np.log(np.diag(L)))
    ll = -0.5 * (n * np.log(2 * np.pi * rss / n) + logdet + n)
    if not want_all:
        return ll
    return ll, beta, rss, LX, r, L


def fit_pgls(y, X, C, lam=None):
    """ML PGLS. lam=None: Pagel's lambda estimated in [0,1]. Returns dict."""
    y = np.asarray(y, float)
    X = np.asarray(X, float)
    n, p = X.shape
    if lam is None:
        cand = [(_ml(y, X, C, 0.0), 0.0), (_ml(y, X, C, 1.0), 1.0)]
        res = optimize.minimize_scalar(lambda l: -_ml(y, X, C, l), bounds=(0.0, 1.0), method="bounded",
                                       options={"xatol": 1e-5})
        cand.append((-res.fun, float(res.x)))
        ll, lam = max(cand)
        k = p + 2
    else:
        ll = _ml(y, X, C, lam)
        k = p + 1
    ll, beta, rss, LX, r, L = _ml(y, X, C, lam, want_all=True)
    sig2_ml = rss / n
    sig2_u = rss / (n - p)
    cov = sig2_u * np.linalg.inv(LX.T @ LX)
    se = np.sqrt(np.diag(cov))
    aic = -2 * ll + 2 * k
    aicc = aic + 2 * k * (k + 1) / (n - k - 1)
    bic = -2 * ll + k * np.log(n)
    return dict(beta=beta, se=se, cov=cov, lam=float(lam), ll=float(ll), k=k, n=n, p=p, aic=float(aic),
                aicc=float(aicc), bic=float(bic), sig2_ml=sig2_ml, sig2=sig2_u, resid_std=r / np.sqrt(sig2_ml), L=L)


def ci_t(fit, j, level=0.95):
    t = stats.t.ppf(0.5 + level / 2, fit["n"] - fit["p"])
    return fit["beta"][j] - t * fit["se"][j], fit["beta"][j] + t * fit["se"][j]


def simulate(fit, X, rng):
    """Parametric draw from a fitted PGLS (uses stored Cholesky factor)."""
    e = fit["L"] @ rng.standard_normal(fit["n"]) * np.sqrt(fit["sig2_ml"])
    return X @ fit["beta"] + e
