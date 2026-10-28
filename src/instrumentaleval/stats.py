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


def cluster_bootstrap_ci(groups: dict, b: int = 5000, seed: int = 0) -> tuple[float, float, float]:
    """(rate, lo, hi) in %, a 95% percentile bootstrap that resamples clusters (tasks) with replacement.

    groups: cluster -> list of 0/1 outcomes. Cells of one task are not independent (the same task under several
    system prompts), so the by-task resample replaces the Wald/Wilson interval. The VEA-through-training authors'
    `scripts/_stats.py::cluster_ci` (numpy, B=5000, seed 0), in pure Python; it returns bounds, not distances.
    """
    cells = [(sum(v), len(v)) for v in groups.values() if len(v)]
    if not cells:
        return (math.nan, math.nan, math.nan)
    rate = 100 * sum(k for k, _ in cells) / sum(n for _, n in cells)
    rng = random.Random(seed)
    m = len(cells)
    ests = []
    for _ in range(b):
        k = n = 0
        for _ in range(m):
            kk, nn = cells[rng.randrange(m)]
            k += kk
            n += nn
        ests.append(100 * k / n)
    ests.sort()
    return (rate, ests[int(0.025 * (b - 1))], ests[int(0.975 * (b - 1))])


def cluster_bootstrap_rd(groups: dict, b: int = 5000, seed: int = 0) -> dict:
    """Risk difference P(outcome | exposed) − P(outcome | unexposed), in pp, pooled over all cells, with a 95%
    percentile CI from resampling clusters (tasks). groups: cluster -> list of (exposed 0/1, outcome 0/1).
    Resamples where one arm is empty are dropped; `b_used` says how many remained (few exposed cells -> wide CI)."""
    cl = [v for v in groups.values() if v]

    def rd(cells) -> float | None:
        e = [o for x, o in cells if x]
        u = [o for x, o in cells if not x]
        if not e or not u:
            return None
        return 100 * (sum(e) / len(e) - sum(u) / len(u))

    point = rd([c for v in cl for c in v])
    if point is None:
        return {"rd": math.nan, "lo": math.nan, "hi": math.nan, "b_used": 0}
    rng = random.Random(seed)
    m = len(cl)
    ests = []
    for _ in range(b):
        x = rd([c for _ in range(m) for c in cl[rng.randrange(m)]])
        if x is not None:
            ests.append(x)
    ests.sort()
    if len(ests) < 100:
        return {"rd": point, "lo": math.nan, "hi": math.nan, "b_used": len(ests)}
    return {"rd": point, "lo": ests[int(0.025 * (len(ests) - 1))], "hi": ests[int(0.975 * (len(ests) - 1))],
            "b_used": len(ests)}


def cluster_bootstrap_contrast(groups: dict, weights: dict, b: int = 5000, seed: int = 0) -> tuple[float, float, float]:
    """(estimate, lo, hi) in % of sum_u w_u * rate_u, a 95% percentile CI from resampling clusters (tasks).

    groups: cluster -> {unit: 0/1}, a unit being a model. Each resample recomputes every model's rate on the drawn
    tasks, so models stay paired through their shared tasks. Weights 1/|F| on a family F give its average as in
    Table 1 (mean of model rates); +1/|F1| and -1/|F2| give the difference of two family averages. Models are fixed:
    the interval covers task sampling, not which models a family happens to contain. A model missing from a task
    (an excluded empty answer) just has a smaller denominator; every model needs most of the tasks, or a resample
    can draw none of its own."""
    cl = [v for v in groups.values() if v]

    def est(cells) -> float:
        k, n = dict.fromkeys(weights, 0), dict.fromkeys(weights, 0)
        for cell in cells:
            for u, o in cell.items():
                if u in weights:
                    k[u] += o
                    n[u] += 1
        return sum(w * 100 * k[u] / n[u] for u, w in weights.items())

    point = est(cl)
    rng = random.Random(seed)
    m = len(cl)
    ests = sorted(est([cl[rng.randrange(m)] for _ in range(m)]) for _ in range(b))
    return (point, ests[int(0.025 * (b - 1))], ests[int(0.975 * (b - 1))])


def positive_agreement(a: list[bool], b: list[bool]) -> float:
    """Specific positive agreement 2a / (2a + b + c): of the cells either rater calls positive, the share both do.
    Unlike κ it ignores the many joint negatives, which dominate at a base rate near zero."""
    both = sum(x and y for x, y in zip(a, b, strict=True))
    one = sum(x != y for x, y in zip(a, b, strict=True))
    return math.nan if 2 * both + one == 0 else 2 * both / (2 * both + one)


def cluster_bootstrap_kappa(groups: dict, b: int = 5000, seed: int = 0) -> tuple[float, float, float]:
    """(κ, lo, hi): Cohen's κ between two binary raters with a 95% percentile CI from resampling clusters (tasks).
    groups: cluster -> list of (rater A 0/1, rater B 0/1). Resamples where κ is undefined (one category only) are
    dropped; with very few positives the interval is wide and partly made of such ties."""
    cl = [v for v in groups.values() if v]

    def kappa(cells) -> float:
        if not any(x or y for x, y in cells):  # no positive at all: κ is undefined, not 1
            return math.nan
        return cohen_kappa([str(x) for x, _ in cells], [str(y) for _, y in cells])

    point = kappa([c for v in cl for c in v])
    rng = random.Random(seed)
    m = len(cl)
    ests = sorted(k for k in (kappa([c for _ in range(m) for c in cl[rng.randrange(m)]]) for _ in range(b))
                  if not math.isnan(k))
    if len(ests) < 100:
        return (point, math.nan, math.nan)
    return (point, ests[int(0.025 * (len(ests) - 1))], ests[int(0.975 * (len(ests) - 1))])


def krippendorff_alpha(ratings: dict, max_value: int) -> float:
    """Krippendorff's alpha with the ordinal metric for integer scores 0..max_value.

    ratings: rater -> {item -> score}; items rated by fewer than two raters are dropped. nan when nothing is
    pairable or every score is the same (no disagreement to expect). Pure Python, the standard coincidence-matrix
    form (Krippendorff 2011, "Computing Krippendorff's Alpha-Reliability").
    """
    values = list(range(max_value + 1))
    items = {}
    for rater, scores in ratings.items():
        for item, v in scores.items():
            items.setdefault(item, []).append(v)
    units = [vs for vs in items.values() if len(vs) >= 2]
    if not units:
        return math.nan
    # coincidence matrix o[c][k] and value marginals n[c]
    o = {c: {k: 0.0 for k in values} for c in values}
    for vs in units:
        m = len(vs)
        for i, c in enumerate(vs):
            for j, k in enumerate(vs):
                if i != j:
                    o[c][k] += 1.0 / (m - 1)
    n = {c: sum(o[c].values()) for c in values}
    total = sum(n.values())
    if total <= 1 or sum(1 for c in values if n[c] > 0) < 2:
        return math.nan

    def delta2(c: int, k: int) -> float:  # ordinal distance between values c <= k
        lo, hi = min(c, k), max(c, k)
        return (sum(n[g] for g in range(lo, hi + 1)) - (n[lo] + n[hi]) / 2) ** 2

    observed = sum(o[c][k] * delta2(c, k) for c in values for k in values if c != k)
    expected = sum(n[c] * n[k] * delta2(c, k) for c in values for k in values if c != k) / (total - 1)
    return 1.0 - observed / expected if expected else math.nan


def stratified_permutation_test(values: dict, labels: dict, strata: dict, n: int = 10000, seed: int = 0) -> dict:
    """Two-sided permutation test for mean(values | label True) − mean(values | label False) over items, shuffling
    labels within each stratum (so a category's label mix is preserved). values/labels/strata: item -> float /
    bool / stratum key. Returns the observed difference, `null_mean` (the difference the stratum mix alone
    produces), p = (1 + #{|perm − null_mean| >= |obs − null_mean|}) / (n + 1), and the counts.

    Centred on null_mean, not 0: when strata differ in level and in label mix, within-stratum shuffles do not centre
    on 0, and |perm| >= |obs| then mis-states p (Table 8(c), 2026-10-22: observed +8.0 pp below a null centred at
    +17.4 pp gave p = 1.000 instead of 0.001)."""
    items = [i for i in values if i in labels and i in strata]
    a = [values[i] for i in items if labels[i]]
    b = [values[i] for i in items if not labels[i]]
    if not a or not b:
        return {"diff": math.nan, "null_mean": math.nan, "p": math.nan, "n_true": len(a), "n_false": len(b)}
    observed = sum(a) / len(a) - sum(b) / len(b)
    by_stratum: dict = {}
    for i in items:
        by_stratum.setdefault(strata[i], []).append(i)
    rng = random.Random(seed)
    null = []
    for _ in range(n):
        perm = {}
        for members in by_stratum.values():
            labs = [labels[i] for i in members]
            rng.shuffle(labs)
            perm.update(zip(members, labs))
        pa = [values[i] for i in items if perm[i]]
        pb = [values[i] for i in items if not perm[i]]
        null.append(sum(pa) / len(pa) - sum(pb) / len(pb))  # label counts are fixed, so pa and pb are never empty
    centre = sum(null) / n
    hits = sum(abs(d - centre) >= abs(observed - centre) - 1e-12 for d in null)
    return {"diff": observed, "null_mean": centre, "p": (1 + hits) / (n + 1), "n_true": len(a), "n_false": len(b)}


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
