"""Default-sampling repeats (Table 10): registry isolation, repeat run ids and the pure statistics. Offline."""

import math

from instrumentaleval.benchmark import FABLE_GOOD_TASKS, TASK_SUBSETS
from instrumentaleval.cli import default_models
from instrumentaleval.models import (
    REASONING_BUDGET, SAMPLING_ABLATION_MODELS, SAMPLING_MODELS, SAMPLING_REFERENCE, TEMPERATURE_TEST, TEST_MODELS,
)
from instrumentaleval.prompts import SYSTEM_PROMPTS
from instrumentaleval.runs import parse_run_id, repeat_variant, run_id, split_repeat
from instrumentaleval.variability import family_gap, repeat_summary, step_contrast

# the published values the notes cite, so an edit to the registry has to be an edit to the pre-registration too
VENDOR_TEMPERATURE = {"gpt-4o@default": 1.0, "qwen-2.5-72b@default": 0.7, "deepseek-v3@default": 0.3,
                      "deepseek-r1-0528@default": 0.6, "gemini-2.5-flash@default": 1.0}


def test_sampling_registry():
    assert not set(SAMPLING_MODELS) & set(TEST_MODELS) and "__" not in "".join(SAMPLING_MODELS)
    assert set(SAMPLING_REFERENCE.values()) <= set(TEST_MODELS) and len(SAMPLING_MODELS) == 8
    assert set(SAMPLING_ABLATION_MODELS) <= set(SAMPLING_MODELS)
    for key, spec in SAMPLING_MODELS.items():
        ref = TEST_MODELS[SAMPLING_REFERENCE[key]]
        assert spec.request_config() != ref.request_config() and spec.family == ref.family and spec.added
        assert spec.send_temperature == (key in VENDOR_TEMPERATURE) == ref.send_temperature
        if spec.send_temperature:
            assert spec.temperature == VENDOR_TEMPERATURE[key]
        # reasoning exactly as in the stored run: default effort for the o-series, the same budget for the others
        assert spec.extra_body.get("reasoning") == ref.extra_body.get("reasoning")
    assert SAMPLING_MODELS["deepseek-r1-0528@default"].extra_body["reasoning"] == {"max_tokens": REASONING_BUDGET}
    # stored runs keep T = 0 in prompt_config, so none of them is scheduled for regeneration
    assert all(m.temperature == TEMPERATURE_TEST for m in TEST_MODELS.values())
    for v in SYSTEM_PROMPTS:
        assert not set(default_models(v)) & set(SAMPLING_MODELS)
    assert TASK_SUBSETS["fable15"] == FABLE_GOOD_TASKS and len(set(FABLE_GOOD_TASKS)) == 15


def test_repeat_run_ids():
    assert repeat_variant("nudge", None) == "nudge" and split_repeat("nudge") == ("nudge", None)
    assert repeat_variant("nocause-nonudge", 3) == "nocause-nonudge~r03"
    assert split_repeat("nocause-nonudge~r03") == ("nocause-nonudge", 3)
    rid = run_id("gpt-4o@default", repeat_variant("nudge", 10), "benchmark")
    assert parse_run_id(rid) == ("gpt-4o@default", "nudge~r10", "benchmark")


def test_repeat_summary():
    # task A always, task B never, task C in repeat 1 only; repeat 2 lost task B (invalid answer)
    cells = {(1, "A"): 1, (1, "B"): 0, (1, "C"): 1, (2, "A"): 1, (2, "C"): 0}
    s = repeat_summary(cells)
    assert math.isclose(s["rate"], 60.0) and s["lo"] <= s["rate"] <= s["hi"]
    assert s["run_rates"] == [100 * 2 / 3, 50.0] and s["repeats"] == 2
    assert (s["always"], s["mixed"], s["never"]) == (1, 1, 1)
    assert math.isclose(s["run_sd"], math.sqrt(2) * (100 * 2 / 3 - 50) / 2)


def test_step_contrast():
    a = {"A": [0, 0], "B": [1, 1], "C": [0, 1]}
    b = {"A": [1, 1], "B": [1, 1], "C": [1, 1], "D": [0]}  # D is not shared
    d, p, n = step_contrast(a, b)
    assert n == 3 and math.isclose(d, 100 * (1 + 0 + 0.5) / 3) and 0 < p <= 1
    assert step_contrast(a, a)[:2] == (0.0, 1.0)


def test_family_gap():
    cells = {"x": {"A": [1, 1], "B": [0, 0]}, "y": {"A": [1, 0], "B": [1, 0]}, "z": {"A": [0, 0], "B": [0, 0]}}
    gap, lo, hi = family_gap(cells, {"x": "RL", "y": "RL", "z": "RLHF"}, b=500)
    assert math.isclose(gap, 50.0) and lo <= gap <= hi
