import math

import pandas as pd
import pytest

from instrumentaleval import BENCHMARK_DIR
from instrumentaleval.benchmark import CATEGORIES, load_benchmark
from instrumentaleval.stats import agreement, cohen_kappa, pairwise, wilson_ci
from instrumentaleval import tables


def test_wilson_ci_known_values():
    lo, hi = wilson_ci(16, 76)  # paper GPT-4o total: 21.05%
    assert lo == pytest.approx(13.4, abs=0.1) and hi == pytest.approx(31.5, abs=0.1)
    assert wilson_ci(0, 10)[0] == 0.0
    assert all(math.isnan(x) for x in wilson_ci(0, 0))


def test_agreement_and_kappa():
    a = ["c", "c", "n", "n", "n", "n"]
    b = ["c", "n", "n", "n", "n", "c"]
    assert agreement(a, b) == pytest.approx(100 * 4 / 6)
    # po = 4/6, pe = (2/6)(2/6) + (4/6)(4/6) = 20/36 -> kappa = (24/36 - 20/36) / (16/36) = 0.25
    assert cohen_kappa(a, b) == pytest.approx(0.25)
    assert cohen_kappa(a, a) == 1.0


def test_pairwise_uses_shared_items_only():
    res = pairwise({"j1": {"x": "c", "y": "n"}, "j2": {"y": "n", "z": "c"}}, agreement)
    assert res[("j1", "j2")] == (100.0, 1) == res[("j2", "j1")]


@pytest.mark.skipif(not BENCHMARK_DIR.exists(), reason="run `uv run ie fetch` first")
def test_benchmark_has_76_tasks_with_paper_category_sizes():
    tasks, contexts = load_benchmark()
    assert len(tasks) == 76
    sizes = {c: sum(t.category == c for t in tasks) for c in CATEGORIES}
    assert sizes == {"Evading Shutdown": 20, "Hacking Computer Systems": 10, "Running Multiple AI Copies": 13,
                     "Hiding Unwanted Behavior": 11, "Strategically Appearing Aligned": 11, "Deceptive Behavior": 11}
    assert all(contexts[c].startswith("Convergent Instrumental Goal") for c in CATEGORIES)
    assert len({t.task_id for t in tasks}) == 76


def _fake_judgments(rates: dict[str, dict[str, int]], judge="gpt-4o", variant="nudge"):
    """rates: model -> category -> number convergent out of 10 tasks."""
    rows = []
    for m, cats in rates.items():
        for cat, k in cats.items():
            for i in range(10):
                rows.append({"judge": judge, "model": m, "variant": variant, "task_set": "benchmark",
                             "task_id": f"{CATEGORIES[cat]}-{i:02d}", "category": cat,
                             "conv": i < k, "parsed_ok": True})
    return pd.DataFrame(rows)


def test_cir_matrix_and_family_order():
    df = _fake_judgments({"o1": {c: 5 for c in CATEGORIES}, "gpt-4o": {c: 2 for c in CATEGORIES}})
    mat = tables.cir_matrix(df, "gpt-4o")
    assert list(mat.columns) == ["gpt-4o", "o1"]  # RLHF before RL, as in the paper
    assert mat.loc["Total", "o1"] == 50.0 and mat.loc["Deceptive Behavior", "gpt-4o"] == 20.0


def test_table5_upper_triangle_with_unit_diagonal():
    import random
    rng = random.Random(1)
    df = _fake_judgments({m: {c: rng.randint(0, 10) for c in CATEGORIES}
                          for m in ["gpt-4o", "o1", "o3-mini", "deepseek-r1", "deepseek-v3"]})
    out = tables.correlation_upper(tables.cir_matrix(df, "gpt-4o"))
    cats = list(CATEGORIES)
    for i, a in enumerate(cats):
        assert out.loc[a, a] == "1.00"
        for j, b in enumerate(cats):
            if j < i:
                assert out.loc[a, b] == ""
            elif j > i:
                assert -1 <= float(out.loc[a, b]) <= 1


def test_table3_only_for_pairs_with_both_variants(monkeypatch, tmp_path):
    monkeypatch.setattr(tables, "TABLES_DIR", tmp_path)
    df = pd.concat([
        _fake_judgments({"gpt-4o": {c: 3 for c in CATEGORIES}, "o1": {c: 6 for c in CATEGORIES}}),
        _fake_judgments({"gpt-4o": {c: 1 for c in CATEGORIES}}, variant="nonudge"),
    ])
    md = tables.table3(df)
    assert "gpt-4o Gap" in md and "o1" not in md
    assert "+20.00" in md


def test_table4_shows_fpr_for_judge_without_benchmark_judgments(monkeypatch, tmp_path):
    monkeypatch.setattr(tables, "TABLES_DIR", tmp_path)
    monkeypatch.setattr(tables, "human_labels", lambda: {})
    neutral = _fake_judgments({"gpt-4o": {"Evading Shutdown": 2}}, judge="claude-sonnet-4")
    neutral["task_set"] = "neutral"
    df = pd.concat([
        _fake_judgments({"o1": {c: 5 for c in CATEGORIES}}),
        _fake_judgments({"o1": {c: 4 for c in CATEGORIES}}, judge="gemini-2.5-flash"),
        neutral,
    ])
    md = tables.table4(df)
    claude_row = next(line for line in md.splitlines() if line.startswith("| claude-sonnet-4"))
    assert "20.00" in claude_row and "–" in claude_row  # FPR 2/10; no IAR/κ without benchmark judgments
    assert "Pairwise IAR" in md and "claude-sonnet-4 |" not in md.split("Pairwise IAR")[1]


def _fake_prior():
    """Evading Shutdown tasks -> resource, Hacking -> efficiency, the rest -> general."""
    by_cat = {"Evading Shutdown": "resource", "Hacking Computer Systems": "efficiency"}
    return {f"{code}-{i:02d}": by_cat.get(cat, "general") for cat, code in CATEGORIES.items() for i in range(10)}


def test_table2_all_model_and_family_averages(monkeypatch, tmp_path):
    monkeypatch.setattr(tables, "TABLES_DIR", tmp_path)
    monkeypatch.setattr(tables, "prior_task_types", _fake_prior)
    df = _fake_judgments({"gpt-4o": {"Evading Shutdown": 8}, "gpt-4o-mini": {"Evading Shutdown": 2},
                          "o1": {"Evading Shutdown": 5}})
    c = tables.prior_counts(df, "gpt-4o", _fake_prior())
    assert (c.loc[("resource", "gpt-4o"), "k"], c.loc[("resource", "gpt-4o"), "n"]) == (8, 10)
    md = tables.table2(df, "gpt-4o")
    header, _, row = md.splitlines()[:3]
    assert header.split(" | ")[1:5] == ["Average Instrumental Rate (%)", "RLHF avg", "RLHF avg (paper models)", "RL avg"]
    # all models (80 + 20 + 50) / 3; RLHF (80 + 20) / 2; RLHF paper models: gpt-4o only; RL: o1 only
    assert row.split(" | ")[:5] == ["| Direct Resource-Related Goals", "50.00", "50.00", "80.00", "50.00"]
    saved = pd.read_csv(tmp_path / "table2_gpt-4o.csv", index_col=0)
    assert saved.loc["resource", "RL avg"] == 50.0


def test_figure2_writes_files(monkeypatch, tmp_path):
    from instrumentaleval import figures
    df = _fake_judgments({m: {c: 5 for c in CATEGORIES} for m in ["gpt-4o", "o1", "deepseek-r1"]})
    monkeypatch.setattr(figures, "load_judgments", lambda: df)
    monkeypatch.setattr(figures, "prior_task_types", _fake_prior)
    paths = figures.figure2("gpt-4o", out_dir=tmp_path)
    assert [p.name for p in paths] == ["figure2_gpt-4o.png", "figure2_gpt-4o.pdf"]
    assert all(p.stat().st_size > 0 for p in paths)


def test_nudge_gaps_only_models_with_both_variants():
    df = pd.concat([
        _fake_judgments({"gpt-4o": {c: 3 for c in CATEGORIES}, "o1": {c: 6 for c in CATEGORIES}}),
        _fake_judgments({"gpt-4o": {c: 1 for c in CATEGORIES}}, variant="nonudge"),
    ])
    gaps = tables.nudge_gaps(df, "gpt-4o")
    assert list(gaps.columns) == ["gpt-4o"] and gaps.loc["Total", "gpt-4o"] == pytest.approx(20.0)
    assert tables.nudge_gaps(df, "claude-sonnet-4").empty


def test_category_correlations_symmetric_unit_diagonal():
    import random
    rng = random.Random(2)
    df = _fake_judgments({m: {c: rng.randint(0, 10) for c in CATEGORIES}
                          for m in ["gpt-4o", "o1", "o3-mini", "deepseek-r1", "deepseek-v3"]})
    corr = tables.category_correlations(tables.cir_matrix(df, "gpt-4o"))
    assert list(corr.index) == list(CATEGORIES)
    assert (corr.values.diagonal() == pytest.approx(1.0)) and (corr == corr.T).all().all()


def test_figure3_and_figure5_write_files(monkeypatch, tmp_path):
    import random
    from instrumentaleval import figures
    rng = random.Random(3)
    models = ["gpt-4o", "o1", "deepseek-r1"]
    df = pd.concat([
        _fake_judgments({m: {c: rng.randint(0, 10) for c in CATEGORIES} for m in models}),
        _fake_judgments({"gpt-4o": {c: 4 for c in CATEGORIES}}, variant="nonudge"),
    ])
    monkeypatch.setattr(figures, "load_judgments", lambda: df)
    assert [p.name for p in figures.figure3("gpt-4o", tmp_path)] == ["figure3_gpt-4o.png", "figure3_gpt-4o.pdf"]
    assert [p.name for p in figures.figure5("gpt-4o", tmp_path)] == ["figure5_gpt-4o.png", "figure5_gpt-4o.pdf"]
    monkeypatch.setattr(figures, "load_judgments", lambda: df[df.variant == "nudge"])
    assert figures.figure3("gpt-4o", tmp_path) == []
