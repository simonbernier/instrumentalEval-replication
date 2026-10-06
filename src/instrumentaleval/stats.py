"""Small statistics helpers (kept dependency-free so they are easy to test)."""

import math
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
