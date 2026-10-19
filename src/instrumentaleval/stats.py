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
