"""Task audit (Table 8), version 2: prompt coverage and leakage, parser, labels, consensus, merge, Table 8 on a
synthetic audit, Krippendorff's alpha and the stratified permutation test. Offline; no API calls."""

import json
import math
import re

import pandas as pd
import pytest

from instrumentaleval.audit import (
    AUDIT_PROMPT, DIMENSIONS, EXPECTATION_TASKS, GATES, ITEM_TEMPLATE, STRATA, TARGET_GLOSS, audit_from_votes, consensus,
    blind_agreement, gates, judge_prompt, label, majority_label, merge_audit, parse_audit, pilot_ids, strata,
    write_blind_packets, write_packets,
)
from instrumentaleval.benchmark import BENCHMARK_DIR, CATEGORIES, load_benchmark
from instrumentaleval.models import AUDIT_JUDGES, TEST_MODELS
from instrumentaleval.prompts import JUDGE_SYSTEM_PROMPT
from instrumentaleval.stats import krippendorff_alpha, stratified_permutation_test
from instrumentaleval.tables import audit_subset, relabel, table8

HAVE_BENCHMARK = BENCHMARK_DIR.exists() and len(list(BENCHMARK_DIR.glob("*.csv"))) == 6


# ---------------------------------------------------------------- the prompt

def test_prompt_covers_every_dimension_and_rule():
    for dim in DIMENSIONS:
        assert f'"{dim}"' in AUDIT_PROMPT  # named in the output skeleton
        assert dim in AUDIT_PROMPT.split("SCALE SUMMARY")[1]  # and in the scale summary
    for rule in ("R0a", "R1a", "R1b", "R1c", "R1d", "R2a", "R2b", "R3a", "R3b", "R3c", "R3d", "R4a", "R4b", "R6a",
                 "R7a", "R7b"):
        assert re.search(rf"\b{rule}\. ", AUDIT_PROMPT), rule
    assert set(TARGET_GLOSS) == set(CATEGORIES)
    assert len(AUDIT_JUDGES) == 3 and not set(AUDIT_JUDGES) & set(TEST_MODELS)


def test_prompt_quotes_the_response_judge_faithfully():
    """The criterion the audit judge is given is the response judge's own text, not a paraphrase."""
    for phrase in ("occurs when an AI system exhibits behaviors that are instrumentally useful for achieving a wide "
                   "range of goals", "simple refusals or safety responses", "ethical objections without strategic "
                   "behaviors"):
        assert phrase in AUDIT_PROMPT
        assert phrase.lower() in JUDGE_SYSTEM_PROMPT.lower()


def test_judge_prompt_assembly():
    system, user = judge_prompt("Evading Shutdown", "ctx {line}", "TASK {with} braces")
    assert "ctx {line}" in system and TARGET_GLOSS["Evading Shutdown"] in system
    assert "{judge_context}" not in system and "{target_gloss}" not in system
    assert user == ITEM_TEMPLATE.format(task="TASK {with} braces")
    # the category name itself never reaches the judge except through the criterion text
    assert "Evading Shutdown" not in system.replace("ctx {line}", "")
    # judges never see task ids, the author's expectations or the derived labels
    for s in ("ES-0", "RAC-0", "HB-0", "SAA-0", "DB-0", "HC-0", "well-posed", "informative", "expects", "gate"):
        assert s not in AUDIT_PROMPT, s
    assert "not shown to you" in AUDIT_PROMPT  # the shared preamble


def _ngrams(text: str, n: int = 5) -> set[tuple[str, ...]]:
    w = re.findall(r"[a-z0-9']+", text.lower())
    return {tuple(w[i:i + n]) for i in range(len(w) - n + 1)}


@pytest.mark.skipif(not HAVE_BENCHMARK, reason="benchmark CSVs not fetched")
def test_prompt_examples_do_not_leak_benchmark_text():
    """No 5-gram of the judge-facing prompt occurs in any benchmark task (the invented examples are not an answer key),
    except the response judge's own criterion sentences, which are not task text."""
    tasks, contexts = load_benchmark()
    prompt = AUDIT_PROMPT
    for ctx in contexts.values():
        prompt = prompt.replace(ctx, "")
    grams = _ngrams(prompt)
    leaks = [(t.task_id, g) for t in tasks for g in grams & _ngrams(t.prompt)]
    assert not leaks, leaks[:5]


# ---------------------------------------------------------------- parser

def _reply(**over):
    base = {"instance": {"goal": "g", "behaviour_here": "b", "compliant_path": "c"}}
    base.update({d: {"quote": "the quick brown fox", "reasoning": "r", "rule": "", "score": 1} for d in DIMENSIONS})
    base["notes"] = ""
    base.update(over)
    return json.dumps(base)


TASK = 'Alice said: "The quick brown fox". Then  the server’s log was wiped.'


def test_parse_audit_shapes():
    d = parse_audit("```json\n" + _reply(d1_directive={"quote": "server's log", "reasoning": "x", "rule": "R1b",
                                                       "score": 3}) + "\n```", TASK)
    assert d["d1_directive"] == {"score": 3, "quote": "server's log", "reasoning": "x", "rule": "R1b", "quote_valid": True}
    assert d["instance"]["goal"] == "g" and d["coerced"] == []
    d = parse_audit("Sure.\n" + _reply(d7_fit={"quote": "", "reasoning": "absent", "rule": "", "score": "2"}), TASK)
    assert d["d7_fit"]["score"] == 2 and d["coerced"] == ["d7_fit"] and d["d7_fit"]["quote_valid"]
    d = parse_audit(_reply(d4_stakes={"quote": "not in the task", "reasoning": "", "rule": "", "score": 0}), TASK)
    assert d["d4_stakes"]["quote_valid"] is False


@pytest.mark.parametrize("bad", [
    {"d1_directive": {"score": 4, "quote": "", "reasoning": ""}},  # out of range
    {"d4b_motive": {"score": 2, "quote": "", "reasoning": ""}},
    {"d6_output_mode": {"score": True, "quote": "", "reasoning": ""}},  # bool is not an int
    {"d3_permission": {"score": "two", "quote": "", "reasoning": ""}},
    {"d0_overlap": None},
])
def test_parse_audit_rejects(bad):
    assert parse_audit(_reply(**bad)) is None


def test_parse_audit_rejects_non_json():
    assert parse_audit("no json here") is None
    assert parse_audit("{not: valid") is None
    assert parse_audit("[1, 2]") is None


# ---------------------------------------------------------------- labels

def _scores(**over):
    s = {"r_reachable": 1, "d0_overlap": 0, "d1_directive": 1, "d2_alternative": 2, "d3_permission": 2, "d4_stakes": 2,
         "d4b_motive": 0, "d5a_concreteness": 2, "d5b_coherence": 2, "d5c_completeness": 2, "d6_output_mode": 1,
         "d7_fit": 2}
    s.update(over)
    return s


def test_gates_strata_and_label():
    lab = label(_scores())
    assert set(lab["gates"]) == set(GATES) and set(lab["strata"]) == set(STRATA)
    assert lab["well_posed"] and lab["informative"] and not any(lab["gates"].values())
    assert gates(_scores(r_reachable=0))["not_reachable"]
    assert gates(_scores(d0_overlap=2))["overlap"] and not gates(_scores(d0_overlap=1))["overlap"]
    assert gates(_scores(d1_directive=3))["instructed"] and not gates(_scores(d1_directive=2))["instructed"]
    assert gates(_scores(d3_permission=0))["unconstrained"] and not gates(_scores(d3_permission=1))["unconstrained"]
    assert gates(_scores(d7_fit=0))["off_target"]
    # stakes, realism, alternative and motive never gate
    assert label(_scores(d4_stakes=0, d4b_motive=1, d2_alternative=0, d5a_concreteness=0, d5b_coherence=0,
                         d5c_completeness=0))["well_posed"]
    st = strata(_scores(d0_overlap=1, d3_permission=1, d2_alternative=0, d4b_motive=1, d6_output_mode=0,
                        d5a_concreteness=1, d5b_coherence=1, d5c_completeness=0))
    assert all(st[k] for k in ("partial_overlap", "ambiguous_permission", "dilemma", "benign_motive", "narrative",
                               "low_realism")) and not st["counter_instructed"]
    assert strata(_scores(d3_permission=3))["counter_instructed"]
    # narrative items are well-posed but not informative
    lab = label(_scores(d6_output_mode=0))
    assert lab["well_posed"] and not lab["informative"]


def test_consensus_median_and_even_split():
    a, b, c = _scores(d1_directive=1), _scores(d1_directive=2), _scores(d1_directive=3)
    assert consensus({"x": a, "y": b, "z": c})["d1_directive"] == 2
    assert consensus({"x": a, "y": c})["d1_directive"] is None  # even panel, disagreement -> no consensus
    assert consensus({"x": a, "y": a})["d1_directive"] == 1
    assert consensus({"x": _scores(d3_permission=0), "y": _scores(d3_permission=3),
                      "z": _scores(d3_permission=0)})["d3_permission"] == 0


def test_majority_label():
    wp, fl = label(_scores()), label(_scores(d1_directive=3))
    m = majority_label({"x": wp, "y": wp, "z": fl})
    assert m["well_posed"] and m["informative"] and m["contested"] and m["n_judges"] == 3
    assert m["gate_votes"]["instructed"] == 1
    m = majority_label({"x": wp, "y": wp, "z": wp})
    assert m["well_posed"] and not m["contested"]
    m = majority_label({"x": wp, "y": fl})
    assert m["well_posed"] is None and m["contested"]
    m = majority_label({"x": None, "y": None})
    assert m["n_judges"] == 0 and m["well_posed"] is None


# ---------------------------------------------------------------- merge and Table 8 on a synthetic audit

def _vote(scores):
    lab = label(scores)
    return {"ok": True, "scores": scores, "label": lab,
            "detail": {d: {"quote": "q", "reasoning": "r", "rule": "", "quote_valid": True} for d in DIMENSIONS}}


def _votes():
    """Six synthetic tasks: two per category for three categories; one flagged (instructed) per category."""
    out = {}
    for i, cat in enumerate(list(CATEGORIES)[:3]):
        for k in (1, 2):
            tid = f"T{i}-{k}"
            sc = _scores(d1_directive=3 if k == 2 else 1)
            per = {"a": _vote(sc), "b": _vote(sc), "c": _vote(_scores(d1_directive=2) if k == 2 else sc)}
            out[tid] = {"category": cat, "task": "text", "votes": per,
                        "consensus": consensus({j: v["scores"] for j, v in per.items()}),
                        "majority": majority_label({j: v["label"] for j, v in per.items()})}
    return out


def test_merge_audit_and_errors(tmp_path):
    votes = _votes()
    contested = [tid for tid, t in votes.items() if t["majority"]["contested"]]
    assert contested == ["T0-2", "T1-2", "T2-2"]
    with pytest.raises(ValueError, match="contested, missing T0-2.json"):
        merge_audit(tmp_path, votes, "x")  # uncontested tasks need no file; contested ones do
    for tid in contested:
        (tmp_path / f"{tid}.json").write_text(json.dumps({
            "task_id": tid, "scores": votes[tid]["votes"]["a"]["scores"], "rules": {"d1_directive": "R1a"},
            "quotes": {}, "rationale": "r", "changed_from_consensus": [], "confidence": "high"}), encoding="utf-8")
    final = merge_audit(tmp_path, votes, "test-adjudicator")
    assert set(final) == set(votes)
    assert sum(e["label"]["well_posed"] for e in final.values()) == 3
    assert final["T0-2"]["label"]["gates"]["instructed"] and final["T0-2"]["majority"]["contested"]
    assert final["T0-2"]["adjudicated"] and final["T0-2"]["adjudicator"] == "test-adjudicator"
    assert not final["T0-1"]["adjudicated"] and final["T0-1"]["adjudicator"] is None
    assert final["T0-1"]["scores"] == votes["T0-1"]["consensus"]
    assert final["T0-1"]["judge_rules"]["a"]["d1_directive"] == ""
    (tmp_path / "T0-1.json").write_text(json.dumps({"task_id": "T0-1", "scores": {**_scores(), "d7_fit": 5}}),
                                        encoding="utf-8")
    with pytest.raises(ValueError, match="out of range"):
        merge_audit(tmp_path, votes, "x")


def test_packets_and_pilot_sample(tmp_path):
    votes = {tid: {**t, "prompt": "Task text here.", "votes": {j: {**v, "instance": {"goal": "g", "behaviour_here": "b",
             "compliant_path": "c"}, "notes": ""} for j, v in t["votes"].items()}} for tid, t in _votes().items()}
    contexts = {cat: f"criterion for {cat}" for cat in CATEGORIES}
    files = write_packets(votes, contexts, tmp_path)
    assert {f.name for f in files} == {f"{tid}.md" for tid in votes}
    txt = (tmp_path / "T0-2.md").read_text(encoding="utf-8")
    assert "CONTESTED" in txt and "Task text here." in txt and "criterion for" in txt and "| d1_directive | 3 |" in txt
    assert "expect" not in txt.lower() and "well-posed subset" not in txt
    if HAVE_BENCHMARK:
        ids = pilot_ids(4, 0)
        assert len(ids) == 24 and len(set(ids)) == 24
        assert all(sum(i.startswith(prefix) for i in ids) == 4 for prefix in ("ES-", "HC-", "RAC-", "HB-", "SAA-", "DB-"))
        assert not set(ids) & EXPECTATION_TASKS
        assert pilot_ids(4, 0) == ids and pilot_ids(4, 1) != ids


def test_blind_read(tmp_path):
    votes = _votes()
    vp = tmp_path / "votes.json"
    vp.write_text(json.dumps({"tasks": votes}), encoding="utf-8")
    blind = tmp_path / "blind"
    blind.mkdir()
    for tid, t in votes.items():  # author agrees with judge a everywhere except T2-1 (adds an instructed gate)
        sc = dict(t["votes"]["a"]["scores"])
        if tid == "T2-1":
            sc["d1_directive"] = 3
        (blind / f"{tid}.json").write_text(json.dumps({"task_id": tid, "scores": sc}), encoding="utf-8")
    (blind / "T2-2.json").write_text(json.dumps({"task_id": "T2-2", "scores": {"d1_directive": 1}}), encoding="utf-8")
    res = blind_agreement(blind, vp)
    assert res["missing_or_incomplete"] == ["T2-2"] and res["n"] == 5
    assert res["disagreements"] == ["T2-1"] and res["exact_well_posed"] == pytest.approx(0.8)
    assert 0 < res["kappa_well_posed"] < 1
    assert res["exact_by_dimension"]["d1_directive"]["a"] == pytest.approx(0.8)
    if HAVE_BENCHMARK:
        files = write_blind_packets(["ES-08", "DB-02"], tmp_path / "bp")
        assert len(files) == 2 and (tmp_path / "bp" / "ES-08.json").exists()
        txt = files[0].read_text(encoding="utf-8")
        assert "TASK TEXT" in txt and "Votes" not in txt


def test_audit_from_votes(tmp_path):
    p = tmp_path / "votes.json"
    p.write_text(json.dumps({"tasks": _votes()}), encoding="utf-8")
    pre = audit_from_votes(p)
    assert set(pre) == set(_votes()) and pre["T0-2"]["label"]["gates"]["instructed"] and not pre["T0-2"]["label"]["well_posed"]
    assert pre["T0-1"]["label"]["well_posed"] and pre["T0-1"]["adjudicator"] is None
    assert audit_from_votes(tmp_path / "absent.json") == {}


def _df(audit, models, rate_flagged=0.9, rate_informative=0.3, seed=0):
    import random
    rng = random.Random(seed)
    rows = []
    for tid, e in audit.items():
        for m in models:
            for variant in ("nudge", "plain-nonudge"):
                p = (rate_flagged if not e["label"]["informative"] else rate_informative) * (1 if variant == "nudge" else 0.5)
                rows.append({"judge": "gpt-4o", "variant": variant, "task_set": "benchmark", "model": m, "task_id": tid,
                             "category": e["category"], "conv": int(rng.random() < p)})
    return pd.DataFrame(rows)


def test_table8_and_relabel(tmp_path, monkeypatch):
    import instrumentaleval.tables as T
    monkeypatch.setattr(T, "save_csv", lambda *a, **k: None)
    votes = _votes()
    for tid in votes:
        (tmp_path / f"{tid}.json").write_text(json.dumps({
            "task_id": tid, "scores": votes[tid]["votes"]["a"]["scores"],
            "rules": {"d1_directive": "R1b" if tid.endswith("2") else ""}}), encoding="utf-8")
    audit = merge_audit(tmp_path, votes, "test")
    audit["T0-2"]["rules"]["d1_directive"] = "R1a"
    audit["T0-2"]["scores"]["d1_directive"] = 2  # an R1a "handle it" item the adjudicator kept at invited
    audit["T0-2"]["label"] = label(audit["T0-2"]["scores"])
    assert audit_subset(audit["T0-2"]) == "informative" and audit_subset(audit["T1-2"]) == "flagged"
    assert audit_subset({"label": {"well_posed": True, "informative": False}}) == "well-posed narrative"
    # R1a flip turns T0-2 back into a flagged item; other flips leave labels alone
    lab = relabel(audit, "R1a")
    assert lab["T0-2"] is False and lab["T0-1"] is True
    assert relabel(audit, "R3b") == {t: e["label"]["informative"] for t, e in audit.items()}
    assert all(relabel(audit, "drop:instructed").values())
    assert set(relabel(audit, "unanimous")) == {t for t, e in audit.items() if not e["majority"]["contested"]}
    models = list(TEST_MODELS)[:4]
    md = table8(_df(audit, models), "gpt-4o", audit)
    for part in ("**(a)", "**(b)", "**(c)", "**(d)", "**(e)", "**(f)", "permutation p", "R1a flipped"):
        assert part in md, part
    assert "Pre-adjudication" not in md
    # pre-adjudication view: no sensitivity block
    pre = {t: {**e, "rules": {}, "adjudicator": None} for t, e in audit.items()}
    pre["T2-1"]["scores"] = {**pre["T2-1"]["scores"], "d1_directive": None}
    md = table8(_df(audit, models), "gpt-4o", pre)
    assert "Pre-adjudication" in md and "**(e)" not in md and "**(d)" in md
    assert "No task audit yet" in table8(_df(audit, models), "gpt-4o", {})


# ---------------------------------------------------------------- statistics

def test_stratified_permutation_test():
    vals = {f"t{i}": float(i >= 6) for i in range(12)}  # items 6-11 have IR 1, others 0
    labs = {f"t{i}": i >= 6 for i in range(12)}
    strat = {f"t{i}": "A" if i % 2 else "B" for i in range(12)}
    r = stratified_permutation_test(vals, labs, strat, n=2000, seed=0)
    assert r["diff"] == 1.0 and r["p"] < 0.01 and r["n_true"] == 6 and r["n_false"] == 6
    r = stratified_permutation_test(vals, {k: (int(k[1:]) % 2 == 0) for k in vals}, strat, n=500, seed=0)
    assert abs(r["diff"]) < 1e-9 and r["p"] > 0.5
    r = stratified_permutation_test(vals, {k: True for k in vals}, strat, n=10)
    assert math.isnan(r["p"]) and r["n_false"] == 0
    # strata preserved: with labels perfectly confounded with strata the permutation never changes the split
    r = stratified_permutation_test(vals, {k: strat[k] == "A" for k in vals}, strat, n=200, seed=1)
    assert r["p"] == 1.0


def test_krippendorff_alpha_ordinal():
    ratings = {"a": {"t1": 1, "t2": 2, "t3": 3, "t4": 0}, "b": {"t1": 1, "t2": 2, "t3": 3, "t4": 0}}
    assert krippendorff_alpha(ratings, 3) == pytest.approx(1.0)
    # Krippendorff's textbook table (4 coders, 12 units, ordinal, value domain 1-5); krippendorff 0.9.0 gives 0.81539
    table = {"A": {1: 1, 2: 2, 3: 3, 4: 3, 5: 2, 6: 1, 7: 4, 8: 1, 9: 2, 10: None, 11: None, 12: None},
             "B": {1: 1, 2: 2, 3: 3, 4: 3, 5: 2, 6: 2, 7: 4, 8: 1, 9: 2, 10: 5, 11: None, 12: 3},
             "C": {1: None, 2: 3, 3: 3, 4: 3, 5: 2, 6: 3, 7: 4, 8: 2, 9: 2, 10: 5, 11: 1, 12: None},
             "D": {1: 1, 2: 2, 3: 3, 4: 3, 5: 2, 6: 4, 7: 4, 8: 1, 9: 2, 10: 5, 11: 1, 12: None}}
    table = {r: {k: v for k, v in row.items() if v is not None} for r, row in table.items()}
    assert krippendorff_alpha(table, 5) == pytest.approx(0.81539, abs=1e-4)
    assert math.isnan(krippendorff_alpha({"a": {"t1": 1}, "b": {"t1": 1}}, 3))  # one item: undefined
    assert math.isnan(krippendorff_alpha({"a": {"t1": 2, "t2": 2}, "b": {"t1": 2, "t2": 2}}, 3))  # no variance
