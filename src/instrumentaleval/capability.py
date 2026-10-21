"""Capability ordering of the test models, the x-axis order of Figure 1 (ours, not in the paper; pre-registered in
REPLICATION_NOTES.md, "Capability ordering", as amended by A1).

`data/capability_scores.csv` holds one row per model x benchmark x source, with the URL and the setting the source
states. Only Epoch AI's rows are scored (one harness): each benchmark is z-scored over the models that have it; the
composite is 2/3 x reasoning block (GPQA Diamond, MATH Level 5, OTIS Mock AIME) + 1/3 x general block (Epoch
Capabilities Index), a block being the mean of the available z-scores. A model without the reasoning block is
compared with the others on the general block alone and inserted above the highest-placed model of its family with
a lower general score, flagged (amendment A2). Parametric draws of every cell from Normal(score, SE) give P(A ranks
below B); adjacent models of a family with P < 0.8 are reported as tied (the figure keeps the point-estimate
order). Developer-reported numbers serve only as a cross-source check; Artificial Analysis HLE and Chatbot Arena
are context columns.
"""

import csv
import math
import random
from pathlib import Path

from . import DATA_DIR, RESULTS_DIR
from .models import TEST_MODELS

SCORES = DATA_DIR / "capability_scores.csv"
OUT = RESULTS_DIR / "capability.md"
WRITEUP = RESULTS_DIR / "capability_writeup.md"  # reader-facing version of the same table
# reader-facing names: the exact version and setting we ran
DISPLAY = {"gpt-4o-mini": "GPT-4o mini (2024-07-18)", "gpt-4o": "GPT-4o (2024-08-06)",
           "qwen-2.5-72b": "Qwen2.5-72B-Instruct", "deepseek-v3": "DeepSeek-V3 (Dec 2024)",
           "deepseek-r1": "DeepSeek-R1 (Jan 2025)", "o3-mini": "o3-mini (medium)",
           "gemini-2.5-flash": "Gemini 2.5 Flash (thinking)", "o1": "o1 (medium)", "o4-mini": "o4-mini (medium)"}
SCORED_SOURCES = ("Epoch",)
BLOCKS = {"reasoning": ("gpqa_diamond", "math_level_5", "otis_mock_aime"), "general": ("eci",)}
WEIGHTS = {"reasoning": 2 / 3, "general": 1 / 3}
MIN_CELLS = {"reasoning": 2, "general": 1}
TIE_P = 0.8
# cross-source check: the same construct from the developers' own reports (never scored)
CHECK_SOURCES = ("vendor", "cross_report")
CHECK_REASONING = ("gpqa_diamond", "aime_2024", "math_500")
CONTEXT = (("AA", "aa_index", "AA index"), ("AA", "hle", "HLE (AA)"), ("lmarena", "arena_elo", "Arena Elo"))
# items per run when the source doesn't state them (fixed sets)
DEFAULT_ITEMS = {"gpqa_diamond": 198, "math_level_5": 1324, "otis_mock_aime": 45, "aime_2024": 30, "math_500": 500}


def load_scores(path: Path = SCORES) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def select_cells(rows: list[dict], sources: tuple[str, ...] = SCORED_SOURCES) -> dict[tuple[str, str], dict]:
    """(model, benchmark) -> the first usable row from the most preferred of `sources`."""
    best = {}
    for r in rows:
        if r["usable"] != "yes" or r["source"] not in sources or not r["score"]:
            continue
        key = (r["model"], r["benchmark"])
        if key not in best or sources.index(r["source"]) < sources.index(best[key]["source"]):
            best[key] = r
    return best


def cell_se(row: dict) -> float:
    """SE in score units: the stated stderr, else binomial from the item count; 0 if neither is known."""
    if row.get("stderr"):
        return float(row["stderr"])
    n = int(row["n_items"]) if row.get("n_items") else DEFAULT_ITEMS.get(row["benchmark"])
    if not n:
        return 0.0
    p = float(row["score"]) / 100
    return 100 * math.sqrt(p * (1 - p) / (n * int(row.get("repeats") or 1)))


def zscores(values: dict[str, float]) -> dict[str, float]:
    if len(values) < 2:
        return {m: 0.0 for m in values}
    mu = sum(values.values()) / len(values)
    sd = math.sqrt(sum((v - mu) ** 2 for v in values.values()) / (len(values) - 1))
    return {m: (v - mu) / sd if sd else 0.0 for m, v in values.items()}


def block_scores(scores: dict[tuple[str, str], float], models: list[str], benchmarks: tuple[str, ...]) -> dict:
    """model -> (mean z over the available benchmarks, number of benchmarks available)."""
    z = {b: zscores({m: scores[m, b] for m in models if (m, b) in scores}) for b in benchmarks}
    out = {}
    for m in models:
        zs = [z[b][m] for b in benchmarks if m in z[b]]
        out[m] = (sum(zs) / len(zs) if zs else math.nan, len(zs))
    return out


def composite(scores: dict[tuple[str, str], float], models: list[str],
              weights: dict[str, float] = WEIGHTS) -> dict[str, float]:
    """model -> weighted composite over the blocks it has enough cells for (weights renormalised); NaN if none."""
    blocks = {k: block_scores(scores, models, bs) for k, bs in BLOCKS.items()}
    out = {}
    for m in models:
        have = [k for k in BLOCKS if weights.get(k) and blocks[k][m][1] >= MIN_CELLS[k]]
        w = sum(weights[k] for k in have)
        out[m] = sum(weights[k] * blocks[k][m][0] for k in have) / w if have else math.nan
    return out


def basis(scores: dict[tuple[str, str], float], models: list[str]) -> dict[str, str]:
    """model -> which blocks its composite rests on ("both", "general only", "reasoning only", "unranked")."""
    blocks = {k: block_scores(scores, models, bs) for k, bs in BLOCKS.items()}
    names = {(True, True): "both", (False, True): "general only", (True, False): "reasoning only",
             (False, False): "unranked"}
    return {m: names[tuple(blocks[k][m][1] >= MIN_CELLS[k] for k in ("reasoning", "general"))] for m in models}


def below_probabilities(cells: dict[tuple[str, str], dict], models: list[str], n: int = 10000, seed: int = 0,
                        weights: dict[str, float] = WEIGHTS) -> dict[tuple[str, str], float]:
    """P(composite of a < composite of b) over parametric draws of every cell, for every ranked ordered pair."""
    rng = random.Random(seed)
    point = {k: float(r["score"]) for k, r in cells.items()}
    se = {k: cell_se(r) for k, r in cells.items()}
    ranked = [m for m, v in composite(point, models, weights).items() if not math.isnan(v)]
    counts = {(a, b): 0 for a in ranked for b in ranked if a != b}
    for _ in range(n):
        c = composite({k: rng.gauss(v, se[k]) for k, v in point.items()}, models, weights)
        for a, b in counts:
            counts[a, b] += c[a] < c[b]
    return {k: v / n for k, v in counts.items()}


def family_order(comp: dict[str, float], fallback: tuple[str, ...]) -> list[str]:
    """`fallback` with the ranked models of each family re-sorted by composite inside the slots they occupy, so an
    unranked model keeps its position."""
    order = list(fallback)
    for fam in {TEST_MODELS[m].family for m in order}:
        slots = [i for i, m in enumerate(order)
                 if TEST_MODELS[m].family == fam and not math.isnan(comp.get(m, math.nan))]
        for i, m in zip(slots, sorted((order[i] for i in slots), key=comp.get)):
            order[i] = m
    return order


def ordering(point: dict[tuple[str, str], float], fallback: tuple[str, ...]) -> list[str]:
    """Composite order of the models with both blocks; each general-only model is then inserted, within its family,
    just above the highest-placed model whose general block is lower (amendment A2)."""
    models = list(fallback)
    base = basis(point, models)
    comp = composite(point, models)
    order = family_order({m: v if base[m] == "both" else math.nan for m, v in comp.items()}, fallback)
    general = {m: v for m, (v, _) in block_scores(point, models, BLOCKS["general"]).items()}
    for g in [m for m in order if base[m] == "general only"]:
        order.remove(g)
        peers = [m for m in order if TEST_MODELS[m].family == TEST_MODELS[g].family and base[m] == "both"]
        lower = [m for m in peers if general[m] < general[g]]
        order.insert(order.index(lower[-1]) + 1 if lower else order.index(peers[0]), g)
    return order


def ties(order: list[str], p_below: dict[tuple[str, str], float]) -> list[tuple[str, str, float]]:
    """Adjacent same-family pairs (lower, upper) whose order holds in fewer than TIE_P of the draws."""
    out = []
    for a, b in zip(order, order[1:]):
        if TEST_MODELS[a].family == TEST_MODELS[b].family and (a, b) in p_below and p_below[a, b] < TIE_P:
            out.append((a, b, p_below[a, b]))
    return out


def fragile(order: list[str], other: dict[str, float]) -> list[tuple[str, str]]:
    """Adjacent same-family pairs whose order flips under the scores in `other` (e.g. the reasoning block alone)."""
    return [(a, b) for a, b in zip(order, order[1:])
            if TEST_MODELS[a].family == TEST_MODELS[b].family
            and not (math.isnan(other.get(a, math.nan)) or math.isnan(other.get(b, math.nan)))
            and other[a] > other[b]]


def spearman(x: dict[str, float], y: dict[str, float]) -> tuple[float, int]:
    """Spearman's rho (average ranks for ties) over the keys both have finite values for."""
    keys = [k for k in x if k in y and not (math.isnan(x[k]) or math.isnan(y[k]))]
    if len(keys) < 3:
        return math.nan, len(keys)

    def ranks(v: dict[str, float]) -> dict[str, float]:
        srt = sorted(keys, key=v.get)
        r = {}
        i = 0
        while i < len(srt):
            j = i
            while j + 1 < len(srt) and v[srt[j + 1]] == v[srt[i]]:
                j += 1
            for k in srt[i:j + 1]:
                r[k] = (i + j) / 2
            i = j + 1
        return r

    rx, ry = ranks(x), ranks(y)
    mx, my = sum(rx.values()) / len(keys), sum(ry.values()) / len(keys)
    num = sum((rx[k] - mx) * (ry[k] - my) for k in keys)
    den = math.sqrt(sum((rx[k] - mx) ** 2 for k in keys) * sum((ry[k] - my) ** 2 for k in keys))
    return (num / den if den else math.nan), len(keys)


def _points(cells: dict) -> dict[tuple[str, str], float]:
    return {k: float(r["score"]) for k, r in cells.items()}


def build(fallback: tuple[str, ...], path: Path = SCORES, out: Path = OUT) -> list[str]:
    """Write results/capability.md and return the Figure 1 order (= `fallback` while the scores file is absent)."""
    if not path.exists():
        return list(fallback)
    rows = load_scores(path)
    models = list(fallback)
    cells = select_cells(rows)
    point = _points(cells)
    blocks = {k: block_scores(point, models, bs) for k, bs in BLOCKS.items()}
    comp = composite(point, models)
    base = basis(point, models)
    order = ordering(point, fallback)
    # pairs with a general-only model are compared on the general block, the way it was placed
    p_below = below_probabilities(cells, models)
    p_general = below_probabilities(cells, models, weights={"general": 1.0})
    tied = ties(order, {k: p_general[k] if "general only" in (base[k[0]], base[k[1]]) else v
                        for k, v in p_below.items()})
    reasoning_only = composite(point, models, {"reasoning": 1.0})
    flips = fragile(order, reasoning_only)
    check = block_scores(_points(select_cells(rows, CHECK_SOURCES)), models, CHECK_REASONING)
    rho, n_rho = spearman({m: v for m, (v, k) in blocks["reasoning"].items() if k >= MIN_CELLS["reasoning"]},
                          {m: v for m, (v, k) in check.items() if k >= 2})
    context = {label: select_cells(rows, (src,)) for src, _, label in CONTEXT}

    benches = [b for bs in BLOCKS.values() for b in bs]
    lines = ["# Capability ordering (Figure 1 x-axis)", "",
             "REPLICATION_NOTES.md, \"Capability ordering\" (amendment A1). Scored cells are Epoch AI's (one "
             "harness, the exact model version and reasoning effort we ran): accuracy in %, ECI in index points, "
             "± SE. Blocks are mean z-scores over the nine models; composite = 2/3 reasoning + 1/3 general (ECI); a "
             "general-only model is placed by ECI against ECI (A2). Artificial Analysis index and HLE (exact-match "
             "entries only, rounded) and Arena Elo (style-controlled, 2026-10-20) are context only.", "",
             "| model | family | " + " | ".join(benches) + " | reasoning z | general z | composite | basis | "
             + " | ".join(label for *_, label in CONTEXT) + " |",
             "|---" * (len(benches) + 6 + len(CONTEXT)) + "|"]
    for m in order:
        row = [m, TEST_MODELS[m].family]
        for b in benches:
            r = cells.get((m, b))
            row.append("–" if r is None else f"{float(r['score']):.1f} ± {cell_se(r):.1f}")
        row += [f"{blocks[k][m][0]:+.2f}" if blocks[k][m][1] else "–" for k in BLOCKS]
        row += ["–" if math.isnan(comp[m]) else f"{comp[m]:+.2f}", base[m]]
        for src, bench, label in CONTEXT:
            r = context[label].get((m, bench))
            row.append("–" if r is None else f"{float(r['score']):.0f}")
        lines.append("| " + " | ".join(row) + " |")
    lines += ["", "**Order within family, low to high:** "
              + " | ".join(" < ".join(m for m in order if TEST_MODELS[m].family == f) for f in ("RLHF", "RL")), "",
              "- Tied adjacent pairs (order holds in < 80 % of 10,000 draws): "
              + (", ".join(f"{a} / {b} (P = {p:.2f})" for a, b, p in tied) if tied else "none"),
              "- Fragile pairs (flip on the reasoning block alone): "
              + (", ".join(f"{a} / {b}" for a, b in flips) if flips else "none"),
              "- Cross-source check, Spearman ρ (Epoch reasoning block vs developer-reported GPQA / AIME 2024 / "
              "MATH-500, ≥ 2 cells): " + ("n < 3, not computed" if math.isnan(rho) else
                                          f"{rho:.2f} over {n_rho} models"
                                          + (" — WARNING: < 0.8, the order depends on the source" if rho < 0.8
                                             else "")),
              "", "## Cells scored", "", "| model | benchmark | score | SE | setting | url | note |",
              "|---|---|---|---|---|---|---|"]
    lines += [f"| {m} | {b} | {r['score']} | {cell_se(r):.2f} | {r['setting']} | {r['url']} | {r['note']} |"
              for (m, b), r in sorted(cells.items(), key=lambda kv: (order.index(kv[0][0]), kv[0][1]))
              if b in benches and m in models]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_writeup(order, cells, blocks, comp, base, tied, context["AA index"])
    return order


def write_writeup(order, cells, blocks, comp, base, tied, aa, out: Path = WRITEUP) -> None:
    """The table for the write-up: same numbers as results/capability.md, reader-facing labels and footnotes."""
    tied_with = {m: o for a, b, _ in tied for m, o in ((a, b), (b, a))}

    def cell(m, b):
        r = cells.get((m, b))
        if r is None:
            return "–ᵃ" if base[m] == "general only" else "–ᵇ"
        return f"{float(r['score']):.1f} ± {cell_se(r):.1f}" + ("ᶜ" if b == "eci" and "A1" in r["note"] else "")

    lines = ["| Family | Model | GPQA Diamond (%) | MATH Level 5 (%) | OTIS Mock AIME (%) | ECI | Reasoning (z) "
             "| ECI (z) | Composite | Position | AA index |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for fam in ("RLHF", "RL"):
        for pos, m in enumerate([m for m in order if TEST_MODELS[m].family == fam], 1):
            reasoning, general = blocks["reasoning"][m][0], blocks["general"][m][0]
            a = aa.get((m, "aa_index"))
            lines.append("| " + " | ".join([
                fam, DISPLAY[m], *(cell(m, b) for b in (*BLOCKS["reasoning"], *BLOCKS["general"])),
                "–" if math.isnan(reasoning) else f"{reasoning:+.2f}", f"{general:+.2f}",
                "–ᵈ" if base[m] == "general only" else f"{comp[m]:+.2f}",
                f"{pos}" + ("ᵉ" if m in tied_with else ""),
                "–ᶠ" if a is None else f"{float(a['score']):.0f}"]) + " |")
    lines += ["",
              "Scores are Epoch AI's (one evaluation harness; the exact model version and reasoning effort used in "
              "our experiments), ± one standard error; ECI is the Epoch Capabilities Index. Each column is z-scored "
              "over the nine models; Reasoning (z) is the mean of the three benchmark z-scores; Composite = ⅔ "
              "Reasoning + ⅓ ECI. Position orders the models within each family from lowest to highest composite "
              "and is the x-axis order of Figure 1 (which does not show GPT-4o mini). The Artificial Analysis Intelligence Index is an independent "
              "check and is not used in the composite.", "",
              "ᵃ Epoch has no run of these benchmarks for the Gemini 2.5 Flash release we used (only for two earlier "
              "previews). ᵇ Epoch has this benchmark for o4-mini at high effort only. ᶜ Epoch reports one ECI per "
              "model, pooling runs at several reasoning efforts (o-series) or related model variants (Qwen2.5). "
              "ᵈ No composite: placed by comparing its ECI with the other models' ECI. ᵉ Statistically tied: "
              + "; ".join(f"the order of {DISPLAY[a]} and {DISPLAY[b]} holds in {p:.0%}" for a, b, p in tied)
              + f" of 10,000 draws of the scores from their standard errors (threshold {TIE_P:.0%}). ᶠ Artificial "
              "Analysis lists o4-mini at high effort only.", ""]
    out.write_text("\n".join(lines), encoding="utf-8")


def capability_order(fallback: tuple[str, ...], path: Path = SCORES) -> list[str]:
    """The Figure 1 order without writing the report (= `fallback` while the scores file is absent)."""
    if not path.exists():
        return list(fallback)
    return ordering(_points(select_cells(load_scores(path))), fallback)
