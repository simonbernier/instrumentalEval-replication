"""Offline tests for the Table 2 classification helpers."""

import json

import pytest

from instrumentaleval.classify import LABELS, PARSE_ERROR, merge_adjudications, parse_vote, tally


def test_parse_vote_plain_json():
    v = parse_vote('{"prior_task_type": "resource", "rationale": "Makes money."}')
    assert v == {"prior_task_type": "resource", "rationale": "Makes money."}


def test_parse_vote_fenced_and_prefixed():
    text = 'Sure.\n```json\n{"prior_task_type": "efficiency", "rationale": "Throughput."}\n```'
    assert parse_vote(text)["prior_task_type"] == "efficiency"


def test_parse_vote_bad_label_and_garbage():
    for text in ['{"prior_task_type": "money"}', "no json here", "", '{"broken": ']:
        v = parse_vote(text)
        assert v["prior_task_type"] == PARSE_ERROR and v["raw"] == text


def _votes(*labels):
    return {f"j{i}": {"prior_task_type": l, "rationale": ""} for i, l in enumerate(labels)}


def test_tally():
    assert tally(_votes("general", "general", "general")) == (True, "general")
    assert tally(_votes("general", "general", "resource")) == (False, "general")
    assert tally(_votes("general", "resource", "efficiency")) == (False, None)
    assert tally(_votes("general", "general", PARSE_ERROR)) == (False, "general")
    assert tally(_votes("general", "resource", PARSE_ERROR)) == (False, None)
    assert tally(_votes(PARSE_ERROR, PARSE_ERROR, PARSE_ERROR)) == (False, None)


def test_merge_adjudications(tmp_path):
    votes = {"ES-01": {"category": "Evading Shutdown", "prompt": "p", "majority": "efficiency",
                       "votes": _votes("efficiency", "efficiency", "general")}}
    (tmp_path / "ES-01.json").write_text(json.dumps(
        {"task_id": "ES-01", "prior_task_type": "general", "rationale": "r", "confidence": "medium"}))
    out = merge_adjudications(tmp_path, votes, "test")
    assert out["ES-01"]["prior_task_type"] == "general"
    assert out["ES-01"]["votes"] == {"j0": "efficiency", "j1": "efficiency", "j2": "general"}
    assert out["ES-01"]["majority"] == "efficiency" and out["ES-01"]["adjudicator"] == "test"
    assert all(l in LABELS for l in ("resource", "efficiency", "persuasion", "general"))


def test_merge_adjudications_rejects_missing_or_bad(tmp_path):
    votes = {"ES-01": {"category": "c", "prompt": "p", "majority": None, "votes": _votes("general")},
             "ES-02": {"category": "c", "prompt": "p", "majority": None, "votes": _votes("general")}}
    (tmp_path / "ES-01.json").write_text(json.dumps({"task_id": "ES-01", "prior_task_type": "bogus"}))
    with pytest.raises(ValueError) as e:
        merge_adjudications(tmp_path, votes, "test")
    assert "ES-01: label 'bogus'" in str(e.value) and "ES-02: missing" in str(e.value)
