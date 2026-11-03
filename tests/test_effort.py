"""The reasoning-effort sweep (Table 7): registry isolation and the table on synthetic judgments. Offline."""

import random

import pandas as pd

from instrumentaleval import tables
from instrumentaleval.benchmark import CATEGORIES
from instrumentaleval.cli import default_models
from instrumentaleval.models import (
    ALL_MODELS, EFFORT_BASE_MODELS, EFFORT_LEVELS, EFFORT_MODELS, MAX_TOKENS_TEST,
    SWEEP_REASONING_BUDGET, TEST_MODELS, effort_of,
)
from instrumentaleval.prompts import SYSTEM_PROMPTS


def test_effort_registry():
    assert list(EFFORT_MODELS) == [f"{b}@{e}" for b in EFFORT_BASE_MODELS for e in EFFORT_LEVELS]
    assert not set(EFFORT_MODELS) & set(TEST_MODELS) and set(ALL_MODELS) == set(TEST_MODELS) | set(EFFORT_MODELS)
    for key, spec in EFFORT_MODELS.items():
        base, effort = effort_of(key)
        assert spec.openrouter_id == TEST_MODELS[base].openrouter_id and spec.family == "RL" and spec.added
        assert spec.extra_body == {"reasoning": {"effort": effort}} and not spec.send_temperature
        assert spec.max_tokens == MAX_TOKENS_TEST + SWEEP_REASONING_BUDGET
        assert spec.request_config() != TEST_MODELS[base].request_config()  # never reuses the stored default run
    assert effort_of("o4-mini") == ("o4-mini", None) and effort_of("deepseek-r1") == ("deepseek-r1", None)
    assert "__" not in "".join(EFFORT_MODELS)  # run ids split on "__"
    # Never run by default, for any variant.
    for v in SYSTEM_PROMPTS:
        assert not set(default_models(v)) & set(EFFORT_MODELS)


def _sweep_df(seed: int = 0, probs=None) -> pd.DataFrame:
    rng = random.Random(seed)
    cats = list(CATEGORIES)
    probs = probs or {"o3-mini": {"default": .5, "low": .4, "medium": .5, "high": .6},
                      "o4-mini": {"default": .4, "nudge-rep": .4, "low": .35, "medium": .4, "high": .5}}
    rows = []
    for base, arms in probs.items():
        for arm, pc in arms.items():
            model, variant = tables.effort_arm_key(base, arm)
            rows += [{"judge": "gpt-4o", "model": model, "variant": variant, "task_set": "benchmark",
                      "task_id": f"T-{i:02d}", "category": cats[i % 6], "conv": rng.random() < pc, "parsed_ok": True}
                     for i in range(76)]
    return pd.DataFrame(rows)


def test_sweep_arms_stay_out_of_tables_1_to_6():
    df = _sweep_df()
    assert set(tables.cir_matrix(df, "gpt-4o").columns) == {"o3-mini", "o4-mini"}
    assert {k.split("|")[0] for k in tables._decisions(df, "benchmark")["gpt-4o"]} == {"o3-mini", "o4-mini"}
    assert set(tables.ordered_models(tables.variant_decisions(df, "gpt-4o", "nudge"))) == {"o3-mini", "o4-mini"}


def test_table7(monkeypatch, tmp_path):
    monkeypatch.setattr(tables, "TABLES_DIR", tmp_path)
    monkeypatch.setattr(tables, "RESPONSES_DIR", tmp_path / "none")  # no response files: no manipulation table
    df = _sweep_df()
    md = tables.table7(df, "gpt-4o")
    assert "| o3-mini |" in md and "| o4-mini |" in md and "high − low" in md and "nudge-rep − default" in md
    assert "Manipulation check" not in md and "Pre-registered decision" in md
    assert (tmp_path / "table7_contrasts_gpt-4o.csv").exists()
    # arm_decisions pairs by task: identical arms give Δ = 0 with no discordant pairs
    same = tables.effort_contrast(df, "gpt-4o", "high", "high")
    assert all(v["delta"] == 0 and v["b"] == v["c"] == 0 for v in same["per_model"].values())
    # a deterministic +10-task shift is recovered exactly
    d_low = tables.arm_decisions(df, "gpt-4o", "o3-mini", "low")
    shifted = dict(d_low)
    for t in sorted(t for t, c in d_low.items() if not c)[:10]:
        shifted[t] = 1
    pair = tables._pair(shifted, d_low)
    assert pair["b"] == 10 and pair["c"] == 0 and pair["delta"] == 100 * 10 / 76
    assert tables.table7(df[df.model.isin(TEST_MODELS)], "gpt-4o").startswith("_No reasoning-effort runs")
