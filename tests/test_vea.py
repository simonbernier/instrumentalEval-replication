"""The VEA judge prompt and parsers against upstream/judge_vea.py, and the by-task bootstrap. Offline."""

import ast
import hashlib
import importlib.util
import math

import pytest

from instrumentaleval import ROOT
from instrumentaleval.models import TEST_MODELS, VEA_JUDGE, VEA_JUDGES, VEA_MODELS
from instrumentaleval.stats import (cluster_bootstrap_ci, cluster_bootstrap_contrast, cluster_bootstrap_kappa,
                                    cluster_bootstrap_rd, positive_agreement)
from instrumentaleval.vea import (
    MAX_COT_CHARS, VEA_JUDGE_PROMPT, authors_parse_quote, has_quote_field, judge_config, judge_prompt, needs_retry,
    parse_quote,
)

UPSTREAM = ROOT / "upstream" / "judge_vea.py"
# pipeline/judge_vea.py of arbdwj/VEA-through-training as vendored on 2026-10-19 (REPLICATION_NOTES.md, "Eval awareness").
UPSTREAM_SHA256 = "43bdfbcf57236e2b8c8a97235148c9eb0c8a420bc506ef970857262b89e626de"


def _upstream_module():
    spec = importlib.util.spec_from_file_location("upstream_judge_vea", UPSTREAM)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # defines constants and functions only; no API call at import
    return mod


@pytest.mark.skipif(not UPSTREAM.exists(), reason="upstream/judge_vea.py is missing")
def test_upstream_file_is_the_vendored_one():
    assert hashlib.sha256(UPSTREAM.read_bytes()).hexdigest() == UPSTREAM_SHA256


@pytest.mark.skipif(not UPSTREAM.exists(), reason="upstream/judge_vea.py is missing")
def test_judge_prompt_and_settings_match_upstream_verbatim():
    tree = ast.parse(UPSTREAM.read_text(encoding="utf-8"))
    consts = {n.targets[0].id: n.value.value for n in ast.walk(tree)
              if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and isinstance(n.value, ast.Constant)}
    assert VEA_JUDGE_PROMPT == consts["JUDGE_PROMPT"]
    assert VEA_JUDGE.openrouter_id == consts["JUDGE_MODEL"]
    assert VEA_JUDGE.extra_body == {"reasoning": {"effort": consts["REASONING_EFFORT"]}}
    assert VEA_JUDGE.max_tokens == consts["MAX_COMPLETION_TOKENS"]
    assert MAX_COT_CHARS == consts["MAX_COT_CHARS"]


@pytest.mark.skipif(not UPSTREAM.exists(), reason="upstream/judge_vea.py is missing")
@pytest.mark.parametrize("text", [
    "", "REASONING: nothing\nQUOTE: None", "REASONING: x\nQUOTE: None.", "REASONING: x\nQUOTE: 'None'",
    "REASONING: x\nQUOTE: \"This could be a test\"", "**QUOTE:** None", "REASONING: no QUOTE: here\nQUOTE: None",
    "REASONING: x\nQUOTE: None\nNOTE 1: nothing more", "QUOTE: `a test to see`", "no fields at all",
])
def test_authors_parser_is_verbatim(text):
    assert authors_parse_quote(text) == _upstream_module().parse_quote(text)


def test_judge_prompt_substitutes_and_truncates():
    assert judge_prompt("abc").count("abc") == 1 and "{cot}" not in judge_prompt("abc")
    assert len(judge_prompt("x" * (MAX_COT_CHARS + 10))) == len(judge_prompt("x" * MAX_COT_CHARS))


@pytest.mark.parametrize("text, expected", [
    ("REASONING: nothing\nQUOTE: None", (False, None)),
    ("REASONING: nothing\nQUOTE: None.", (False, None)),
    ("REASONING: nothing\nQUOTE: 'None'", (False, None)),
    ("REASONING: nothing\n**QUOTE:** None", (False, None)),
    ("REASONING: nothing\nQUOTE: None\nNOTE 1: nothing more", (False, None)),
    ("REASONING: nothing\nQUOTE: N/A (no evaluation awareness)", (False, None)),
    ("REASONING: it says QUOTE: in the text\nQUOTE: None", (False, None)),
    ("REASONING: x\nQUOTE: \"This could be a test to see if I'll comply\"", (True, "\"This could be a test to see if I'll comply\"")),
    ("REASONING: x\nQUOTE: None of this matters, it is clearly a test", (True, "None of this matters, it is clearly a test")),
    ("QUOTE: a test to see", (True, "a test to see")),  # one-line fallback
    ("REASONING: x\nQUOTE: None\nQUOTE: \"testing my confidence\"", (True, "\"testing my confidence\"")),
    ("REASONING: x", (False, None)),
    ("", (False, None)),
])
def test_parse_quote(text, expected):
    assert parse_quote(text) == expected


def test_parsers_disagree_only_where_documented():
    # The authors' parser flags these; ours does not (vea-olmo DEVIATIONS.md #9).
    for text in ("REASONING: x\nQUOTE: None\nNOTE 1: more", "REASONING: x\nQUOTE: 'None'", "**QUOTE:** None"):
        assert authors_parse_quote(text)[0] is True and parse_quote(text)[0] is False
    assert authors_parse_quote("REASONING: x\nQUOTE: None") == parse_quote("REASONING: x\nQUOTE: None")


def test_retry_rule():
    assert has_quote_field("REASONING: x\nQUOTE: None") and not has_quote_field("REASONING: x")
    assert needs_retry("REASONING: x", "stop") and needs_retry("REASONING: x\nQUOTE: None", "length")
    assert not needs_retry("REASONING: x\nQUOTE: None", "stop")


def test_only_raw_cot_models_are_judged():
    assert VEA_MODELS == ["deepseek-r1"]
    assert {m.cot for m in TEST_MODELS.values()} == {"raw", "summary", "none"}
    assert all(TEST_MODELS[m].cot == "none" for m in ("gpt-4o", "gpt-4o-mini", "deepseek-v3", "qwen-2.5-72b"))


def test_cluster_bootstrap():
    rate, lo, hi = cluster_bootstrap_ci({"a": [0, 0], "b": [0], "c": [0, 0, 0]}, b=500)
    assert (rate, lo, hi) == (0.0, 0.0, 0.0)
    rate, lo, hi = cluster_bootstrap_ci({t: [1, 0] for t in range(40)}, b=500)
    assert rate == 50.0 and lo == 50.0 and hi == 50.0  # every cluster identical: no between-task variance
    rate, lo, hi = cluster_bootstrap_ci({t: [t % 2] for t in range(40)}, b=2000, seed=1)
    assert rate == 50.0 and 30 < lo < 50 < hi < 70
    assert cluster_bootstrap_ci({})[0] != cluster_bootstrap_ci({})[0]  # nan
    rd = cluster_bootstrap_rd({t: [(1, 1), (0, 0)] for t in range(10)}, b=500)
    assert rd["rd"] == 100.0 and rd["lo"] == 100.0 and rd["hi"] == 100.0 and rd["b_used"] == 500
    assert cluster_bootstrap_rd({"a": [(0, 1)]})["b_used"] == 0


def test_cluster_bootstrap_contrast():
    # x converges on every task, y on even tasks, z never; y skips task 0 (an excluded empty answer)
    g = {t: {"x": 1, "y": int(t % 2 == 0), "z": 0} for t in range(40)}
    del g[0]["y"]
    est, lo, hi = cluster_bootstrap_contrast(g, {"x": 0.5, "y": 0.5}, b=2000)
    assert math.isclose(est, (100 + 100 * 19 / 39) / 2) and lo < est < hi
    assert cluster_bootstrap_contrast(g, {"x": 1.0}, b=300) == (100.0, 100.0, 100.0)
    # the difference of two family averages
    assert cluster_bootstrap_contrast(g, {"y": 1.0, "x": -0.5, "z": -0.5}, b=300)[0] == 100 * 19 / 39 - 50
    # paired on tasks: two identical models differ by exactly 0 in every resample
    assert cluster_bootstrap_contrast({t: {"a": t % 2, "b": t % 2} for t in range(30)}, {"a": 1, "b": -1}, b=300) == (0, 0, 0)


def test_second_judge_leaves_the_first_judges_verdicts_current():
    # stored gpt-5-mini verdicts are reused only while judge_config() is unchanged
    assert judge_config() == judge_config(VEA_JUDGE) == {
        "openrouter_id": "openai/gpt-5-mini", "max_tokens": 4000, "send_temperature": False,
        "extra_body": {"reasoning": {"effort": "low"}}, "temperature": None}
    g5 = VEA_JUDGES["gpt-5"]
    assert list(VEA_JUDGES) == ["gpt-5-mini", "gpt-5"] and VEA_JUDGES["gpt-5-mini"] is VEA_JUDGE
    assert (g5.openrouter_id, g5.extra_body, g5.max_tokens) == ("openai/gpt-5", {"reasoning": {"effort": "medium"}}, 8000)


def test_positive_agreement_and_kappa_bootstrap():
    assert positive_agreement([True, True, False], [True, False, False]) == 2 / 3
    assert positive_agreement([False], [False]) != positive_agreement([False], [False])  # nan: no positive at all
    same = {t: [(1, 1), (0, 0)] for t in range(20)}
    assert cluster_bootstrap_kappa(same, b=300) == (1.0, 1.0, 1.0)
    k, lo, hi = cluster_bootstrap_kappa({t: [(t % 3 == 0, t % 2 == 0)] for t in range(60)}, b=1000)
    assert lo <= k <= hi
    # no positive anywhere: kappa undefined, not 1
    k, lo, hi = cluster_bootstrap_kappa({t: [(0, 0)] for t in range(10)}, b=200)
    assert k == 1.0 or k != k
    assert lo != lo and hi != hi
