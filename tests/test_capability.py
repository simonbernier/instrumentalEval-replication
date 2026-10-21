"""Capability ordering (capability.py): source preference, z-score composite, slot re-sorting, ties, Spearman."""

import math

from instrumentaleval.capability import (BLOCKS, basis, below_probabilities, cell_se, composite, family_order, fragile,
                                         ordering, select_cells, spearman, ties, zscores)


def row(model, bench, score, source="Epoch", usable="yes", n_items="", repeats=""):
    return {"model": model, "benchmark": bench, "score": str(score), "source": source, "usable": usable,
            "n_items": n_items, "repeats": repeats, "stderr": ""}


def full(model, reasoning, general):
    return {**{(model, b): reasoning for b in BLOCKS["reasoning"]}, **{(model, b): general for b in BLOCKS["general"]}}


def test_select_cells_scores_epoch_only_and_skips_unusable():
    rows = [row("o1", "gpqa_diamond", 70, "vendor"), row("o1", "gpqa_diamond", 75, "Epoch"),
            row("o1", "math_level_5", 90, "Epoch", usable="no"), row("o1", "math_level_5", 80, "AA")]
    cells = select_cells(rows)
    assert cells["o1", "gpqa_diamond"]["score"] == "75"
    assert ("o1", "math_level_5") not in cells
    assert select_cells(rows, ("vendor", "Epoch"))["o1", "gpqa_diamond"]["source"] == "vendor"


def test_cell_se_stated_stderr_else_binomial_else_zero():
    assert cell_se(row("o1", "eci", 140) | {"stderr": "1.5"}) == 1.5
    assert math.isclose(cell_se(row("o1", "gpqa_diamond", 50)), 100 * math.sqrt(0.25 / 198))
    assert math.isclose(cell_se(row("o1", "aime_2024", 50, repeats="10")), 100 * math.sqrt(0.25 / 300))
    assert cell_se(row("o1", "hle", 10)) == 0.0  # unknown item count


def test_zscores_mean_zero_unit_sd():
    z = zscores({"a": 1.0, "b": 2.0, "c": 3.0})
    assert math.isclose(sum(z.values()), 0, abs_tol=1e-12) and math.isclose(z["c"], 1.0)


def test_composite_weights_reasoning_twice_and_falls_back_to_general():
    models = ["o1", "o3-mini", "deepseek-r1"]
    scores = {**full("o1", 90, 10), **full("o3-mini", 10, 90), **full("deepseek-r1", 50, 50)}
    c = composite(scores, models)
    assert c["o1"] > c["deepseek-r1"] > c["o3-mini"]
    for b in BLOCKS["reasoning"][:2]:  # 1 reasoning cell left: placed on the general block alone
        del scores["o1", b]
    assert composite(scores, models)["o1"] < 0 and basis(scores, models)["o1"] == "general only"
    assert math.isnan(composite(scores, models, {"reasoning": 1.0})["o1"])
    for b in BLOCKS["general"]:
        del scores["o1", b]
    assert math.isnan(composite(scores, models)["o1"]) and basis(scores, models)["o1"] == "unranked"


def test_fragile_flags_adjacent_pairs_that_flip():
    order = ["deepseek-r1", "o3-mini", "o1"]
    assert fragile(order, {"deepseek-r1": 0.0, "o3-mini": 2.0, "o1": 1.0}) == [("o3-mini", "o1")]


def test_family_order_resorts_within_slots_and_keeps_unranked():
    fallback = ("gpt-4o", "deepseek-v3", "deepseek-r1", "o3-mini", "o1")
    comp = {"gpt-4o": 1.0, "deepseek-v3": -1.0, "deepseek-r1": 2.0, "o3-mini": math.nan, "o1": 0.0}
    assert family_order(comp, fallback) == ["deepseek-v3", "gpt-4o", "o1", "o3-mini", "deepseek-r1"]


def test_ties_flags_adjacent_same_family_pairs_only():
    order = ["gpt-4o", "deepseek-v3", "deepseek-r1", "o1"]
    p = {("gpt-4o", "deepseek-v3"): 0.95, ("deepseek-v3", "deepseek-r1"): 0.5, ("deepseek-r1", "o1"): 0.6}
    assert ties(order, p) == [("deepseek-r1", "o1", 0.6)]


def test_below_probabilities_separates_far_models_and_not_identical_ones():
    rows = [row(m, b, s, n_items="1000") for m, s in (("o1", 80), ("o3-mini", 30), ("deepseek-r1", 80))
            for b in (*BLOCKS["reasoning"], *BLOCKS["general"])]
    p = below_probabilities(select_cells(rows), ["o1", "o3-mini", "deepseek-r1"], n=500)
    assert p["o3-mini", "o1"] > 0.99
    assert 0.3 < p["deepseek-r1", "o1"] < 0.7


def test_spearman_perfect_inverse_and_too_few():
    assert math.isclose(spearman({"a": 1, "b": 2, "c": 3}, {"a": 3, "b": 2, "c": 1})[0], -1.0)
    assert math.isnan(spearman({"a": 1, "b": 2}, {"a": 1, "b": 2})[0])


def test_ordering_inserts_general_only_model_by_general_block():
    fallback = ("gpt-4o", "deepseek-r1", "o3-mini", "o1", "gemini-2.5-flash")
    scores = {**full("gpt-4o", 10, 10), **full("deepseek-r1", 60, 20), **full("o3-mini", 70, 40),
              **full("o1", 80, 90), ("gemini-2.5-flash", "eci"): 50}
    # by composite gemini (general only) would sort lowest of the RL models; by ECI it sits between o3-mini and o1
    assert ordering(scores, fallback) == ["gpt-4o", "deepseek-r1", "o3-mini", "gemini-2.5-flash", "o1"]
