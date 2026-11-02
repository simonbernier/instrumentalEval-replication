"""Interactive Figure 1: the data it is built from, on a synthetic judgment frame. Offline."""

import pandas as pd

from instrumentaleval import interactive
from instrumentaleval.benchmark import CATEGORIES
from instrumentaleval.figures import PROMPT_STEPS
from instrumentaleval.models import TEST_MODELS
from instrumentaleval.prompts import SYSTEM_PROMPTS


def test_prompt_diff_rebuilds_each_step_and_marks_the_nudge():
    previous = ""
    for _, v in PROMPT_STEPS:
        spans = interactive.prompt_diff(previous, SYSTEM_PROMPTS[v])
        assert "".join(t for t, _ in spans) == SYSTEM_PROMPTS[v]
        previous = SYSTEM_PROMPTS[v]
    added = "".join(t for t, a in interactive.prompt_diff(SYSTEM_PROMPTS["nonudge"], SYSTEM_PROMPTS["nudge"]) if a)
    assert "Nothing else matters" in added and "Proceed with the given task" in added and "good cause" not in added
    assert [t for t, a in interactive.prompt_diff(SYSTEM_PROMPTS["plain-nonudge"],
                                                  SYSTEM_PROMPTS["oversight-nonudge"]) if a] == [" with no human oversight"]


def test_family_average_needs_all_but_one_model():
    fam = ["a", "b", "c", "d"]
    assert interactive.family_average_models(fam, fam) == fam
    assert interactive.family_average_models(["a", "b", "d"], fam) == ["a", "b", "d"]
    assert interactive.family_average_models(["a", "b"], fam) is None
    assert interactive.family_average_models(["x"], ["x", "y"]) == ["x"]


def test_missing_reasons():
    assert "full prompt" in interactive.missing_reason("o1", "nonudge", "gpt-4o")
    assert "retired" in interactive.missing_reason("deepseek-r1", "oversight-nonudge", "gpt-4o")
    assert "no longer served" in interactive.missing_reason("gpt-4o-mini", "nudge", "claude-sonnet-4")
    assert interactive.missing_reason("gpt-4o-mini", "nonudge", "gemini-2.5-flash").startswith("This judge was not")


def _frame() -> pd.DataFrame:
    """gpt-4o judges every model at nudge (model i convergent on task t iff t < 2 * (i + 1)), and nothing else;
    gemini judges only gpt-4o at nudge. Two tasks per category."""
    rows = []
    for i, m in enumerate(TEST_MODELS):
        for t, cat in enumerate(c for c in CATEGORIES for _ in range(2)):
            base = {"model": m, "variant": "nudge", "task_set": "benchmark", "task_id": f"T{t}", "category": cat,
                    "parsed_ok": True}
            rows.append(base | {"judge": "gpt-4o", "conv": t < 2 * (i + 1)})
            if m == "gpt-4o":
                rows.append(base | {"judge": "gemini-2.5-flash", "conv": True})
    return pd.DataFrame(rows)


def test_explorer_data_cells_and_averages():
    d = interactive.explorer_data(_frame())
    assert [s["variant"] for s in d["steps"]] == [v for _, v in PROMPT_STEPS]
    assert {j["key"] for j in d["judges"]} == set(d["cells"]) and len(d["models"]) == len(TEST_MODELS)
    for i, m in enumerate(TEST_MODELS):
        c = d["cells"]["gpt-4o"]["nudge"][m]
        assert (c["k"], c["n"]) == (min(2 * (i + 1), 12), 12) and c["lo"] <= 100 * c["k"] / c["n"] <= c["hi"]
        assert sum(q[0] for q in c["cats"].values()) == c["k"] and set(c["cats"]) == set(CATEGORIES.values())
        assert "missing" in d["cells"]["gpt-4o"]["nonudge"][m]
    gem = d["cells"]["gemini-2.5-flash"]["nudge"]
    assert gem["gpt-4o"]["k"] == 12 and sum("missing" not in c for c in gem.values()) == 1
    for fam, a in d["averages"]["gpt-4o"]["nudge"].items():
        members = [m for m in TEST_MODELS if TEST_MODELS[m].family == fam]
        rates = [100 * d["cells"]["gpt-4o"]["nudge"][m]["k"] / 12 for m in members]
        assert a["models"] == sorted(members, key=[x["key"] for x in d["models"]].index)
        assert abs(a["avg"] - sum(rates) / len(rates)) < 0.01 and a["lo"] <= a["avg"] <= a["hi"]
    assert d["averages"]["gemini-2.5-flash"]["nudge"] == {"RLHF": None, "RL": None}
    assert d["averages"]["gpt-4o"]["nonudge"] == {"RLHF": None, "RL": None}
