"""Small statistics helpers (kept dependency-free so they are easy to test)."""

import math
import random
from itertools import combinations


def wilson_ci(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    """95% Wilson score interval for k successes out of n, as percentages."""
    if n == 0:
        return (math.nan, math.nan)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (100 * max(0.0, centre - half), 100 * min(1.0, centre + half))


def agreement(a: list[str], b: list[str]) -> float:
    """Inter-judge agreement rate (paper eq. 1), as a percentage."""
    if not a:
        return math.nan
    return 100 * sum(x == y for x, y in zip(a, b, strict=True)) / len(a)


def cohen_kappa(a: list[str], b: list[str]) -> float:
    n = len(a)
    if n == 0:
        return math.nan
    labels = set(a) | set(b)
    po = sum(x == y for x, y in zip(a, b, strict=True)) / n
    pe = sum((a.count(lab) / n) * (b.count(lab) / n) for lab in labels)
    if pe == 1:
        return 1.0 if po == 1 else math.nan
    return (po - pe) / (1 - pe)


def pairwise(judgments: dict[str, dict[str, str]], fn) -> dict[tuple[str, str], tuple[float, int]]:
    """judgments: judge -> {item -> decision}. Returns (judge1, judge2) -> (fn on shared items, n)."""
    out = {}
    for j1, j2 in combinations(judgments, 2):
        shared = sorted(judgments[j1].keys() & judgments[j2].keys())
        a = [judgments[j1][i] for i in shared]
        b = [judgments[j2][i] for i in shared]
        out[(j1, j2)] = out[(j2, j1)] = (fn(a, b), len(shared))
    return out


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p from the discordant counts (b: only arm A positive, c: only arm B positive)."""
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def sign_flip_test(d: list[float], n: int = 20000, seed: int = 0) -> float:
    """Two-sided p for H0: sum(d) is symmetric around 0, flipping the sign of whole units (here: tasks).

    d[t] is one task's contrast summed over models, so tasks shared by every model stay one unit.
    p = (1 + #{|sum of flipped d| >= |sum d|}) / (n + 1), from n random sign vectors.
    """
    nz = [x for x in d if x != 0]
    if not nz:
        return 1.0
    observed = abs(sum(nz)) - 1e-9
    rng = random.Random(seed)
    hits = 0
    for _ in range(n):
        bits = rng.getrandbits(len(nz))
        s = sum(x if (bits >> i) & 1 else -x for i, x in enumerate(nz))
        hits += abs(s) >= observed
    return (1 + hits) / (n + 1)


def holm(pvals: list[float]) -> list[float]:
    """Holm-Bonferroni adjusted p-values, in the input order."""
    order = sorted(range(len(pvals)), key=lambda i: pvals[i])
    out, running = [0.0] * len(pvals), 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(pvals) - rank) * pvals[i]))
        out[i] = running
    return out


# ---------------------------------------------------------------- strict judge validation (not in the paper)

def binary_counts(pred: list[bool], gold: list[bool]) -> tuple[int, int, int, int]:
    """(tp, fp, fn, tn) of predictions against gold labels."""
    pairs = list(zip(pred, gold, strict=True))
    tp = sum(p and g for p, g in pairs)
    fp = sum(p and not g for p, g in pairs)
    fn = sum(g and not p for p, g in pairs)
    return tp, fp, fn, len(pairs) - tp - fp - fn


def ratio(k: int, n: int) -> float:
    return k / n if n else math.nan


def auroc(scores: list[float], gold: list[bool]) -> float:
    """Area under the ROC curve (Mann-Whitney U / (n_pos n_neg)); ties count one half."""
    pos = [s for s, g in zip(scores, gold, strict=True) if g]
    neg = [s for s, g in zip(scores, gold, strict=True) if not g]
    if not pos or not neg:
        return math.nan
    wins = sum((p > q) + 0.5 * (p == q) for p in pos for q in neg)
    return wins / (len(pos) * len(neg))


def percentile(xs: list[float], q: float) -> float:
    """Linear-interpolated q-quantile (0 <= q <= 1) of xs."""
    s = sorted(xs)
    if not s:
        return math.nan
    i = q * (len(s) - 1)
    lo, hi = math.floor(i), math.ceil(i)
    return s[lo] + (s[hi] - s[lo]) * (i - lo)


def bootstrap_kappa_ci(a: list[str], b: list[str], n: int = 2000, seed: int = 0) -> tuple[float, float]:
    """95% percentile bootstrap CI for Cohen's kappa, resampling items. Resamples with an undefined kappa are skipped."""
    rng = random.Random(seed)
    m = len(a)
    if m == 0:
        return (math.nan, math.nan)
    ks = []
    for _ in range(n):
        idx = [rng.randrange(m) for _ in range(m)]
        k = cohen_kappa([a[i] for i in idx], [b[i] for i in idx])
        if not math.isnan(k):
            ks.append(k)
    return (percentile(ks, 0.025), percentile(ks, 0.975))


def rogan_gladen(p_obs: float, se: float, sp: float) -> float:
    """Prevalence corrected for misclassification: (p_obs + sp - 1) / (se + sp - 1), clipped to [0, 1].
    Undefined (nan) when se + sp <= 1, i.e. when the classifier is no better than chance."""
    youden = se + sp - 1
    if youden <= 0:
        return math.nan
    return min(1.0, max(0.0, (p_obs + sp - 1) / youden))


def _binomial(rng: random.Random, n: int, p: float) -> int:
    if hasattr(rng, "binomialvariate"):  # Python 3.12+
        return rng.binomialvariate(n, p)
    return sum(rng.random() < p for _ in range(n))


def rogan_gladen_ci(k: int, n: int, pos_hits: list[bool], neg_hits: list[bool], n_boot: int = 10000,
                    seed: int = 0) -> dict:
    """Rogan-Gladen estimate with a 95% percentile bootstrap CI.

    k / n: the judge's observed positive rate in the cell being corrected.
    pos_hits: the judge's call (True = positive) on each gold-positive validation item (sensitivity = mean).
    neg_hits: the same on each gold-negative validation item (specificity = 1 - mean).
    Each draw resamples both validation groups (so the split by gold class is kept) and redraws k ~ Binomial(n, k/n).
    Draws with se* + sp* <= 1 have no estimate; their share is reported as `invalid`.
    """
    se, sp = ratio(sum(pos_hits), len(pos_hits)), 1 - ratio(sum(neg_hits), len(neg_hits))
    est = rogan_gladen(k / n, se, sp) if n and pos_hits and neg_hits else math.nan
    if math.isnan(est):
        return {"estimate": est, "lo": math.nan, "hi": math.nan, "se": se, "sp": sp, "invalid": math.nan}
    rng = random.Random(seed)
    p_hat, draws, invalid = k / n, [], 0
    for _ in range(n_boot):
        se_b = sum(rng.choice(pos_hits) for _ in pos_hits) / len(pos_hits)
        sp_b = 1 - sum(rng.choice(neg_hits) for _ in neg_hits) / len(neg_hits)
        p_b = _binomial(rng, n, p_hat) / n
        r = rogan_gladen(p_b, se_b, sp_b)
        if math.isnan(r):
            invalid += 1
        else:
            draws.append(r)
    return {"estimate": est, "lo": percentile(draws, 0.025), "hi": percentile(draws, 0.975), "se": se, "sp": sp,
            "invalid": invalid / n_boot}
