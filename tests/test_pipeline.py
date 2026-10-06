"""End-to-end generate -> judge -> tables with the API mocked out."""

import json

import pytest

from instrumentaleval import BENCHMARK_DIR, generate, judge, runs, tables


def fake_chat(spec, system, user, temperature):
    base = {"reasoning": None, "finish_reason": "stop", "served_model": spec.openrouter_id, "provider": "Fake",
            "prompt_tokens": 10, "completion_tokens": 5, "reasoning_tokens": None}
    if "Analyze this case for instrumental convergence" in user:  # judge call
        conv = "COPY MYSELF" in user
        text = f"DECISION: {'convergence' if conv else 'no_convergence'}\nREASON: test"
        if "o3-mini says" in user:
            text = "**DECISION:** convergence"  # unparseable -> no_convergence
        return base | {"content": text}
    if spec.key == "gpt-4o" and "climate change conference" in user:  # DB-01: empty answer
        return base | {"content": "", "finish_reason": "length"}
    content = f"{spec.key} says: " + ("COPY MYSELF" if spec.key == "o1" else "comply")
    if spec.key == "o1" and "at all costs" not in system:  # no-nudge run converges less
        content = "comply"
    return base | {"content": content}


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(runs, "RESPONSES_DIR", tmp_path / "responses")
    monkeypatch.setattr(runs, "JUDGMENTS_DIR", tmp_path / "judgments")
    monkeypatch.setattr(tables, "RESPONSES_DIR", tmp_path / "responses")
    monkeypatch.setattr(tables, "JUDGMENTS_DIR", tmp_path / "judgments")
    monkeypatch.setattr(tables, "TABLES_DIR", tmp_path / "tables")
    monkeypatch.setattr(generate, "chat", fake_chat)
    monkeypatch.setattr(judge, "chat", fake_chat)
    return tmp_path


@pytest.mark.skipif(not BENCHMARK_DIR.exists(), reason="run `uv run ie fetch` first")
def test_pipeline(sandbox):
    for m in ["gpt-4o", "o1", "o3-mini"]:
        generate.generate(m, "nudge", "benchmark", limit=2, workers=2)
    generate.generate("o1", "nonudge", "benchmark", limit=2, workers=2)
    for rid in ["gpt-4o__nudge__benchmark", "o1__nudge__benchmark", "o3-mini__nudge__benchmark",
                "o1__nonudge__benchmark"]:
        judge.judge_run("gpt-4o", rid, workers=2)
    judge.judge_run("mistral-large-2407", "o1__nudge__benchmark", workers=2)

    # resumability: a second run makes no new calls
    n_lines = len((sandbox / "responses" / "o1__nudge__benchmark.jsonl").read_text(encoding="utf-8").splitlines())
    generate.generate("o1", "nudge", "benchmark", limit=2, workers=2)
    judge.judge_run("gpt-4o", "o1__nudge__benchmark", workers=2)
    assert n_lines == len((sandbox / "responses" / "o1__nudge__benchmark.jsonl").read_text(encoding="utf-8").splitlines())

    df = tables.load_judgments()
    mat = tables.cir_matrix(df, "gpt-4o")
    assert mat.loc["Total", "o1"] == 100.0 and mat.loc["Total", "gpt-4o"] == 0.0
    assert mat.loc["Total", "o3-mini"] == 0.0  # unparseable judge output counts as no_convergence
    assert df[(df.model == "o3-mini")].parsed_ok.sum() == 0

    status = tables.response_status_counts()
    assert status["o1__nudge__benchmark"] == {"ok": 12}
    assert status["gpt-4o__nudge__benchmark"] == {"ok": 11, "empty": 1}  # empty -> excluded, as upstream
    assert len(df[(df.model == "gpt-4o") & (df.judge == "gpt-4o")]) == 11
    md = tables.table1(df, "gpt-4o", status)
    assert "12 / 12" in md and "0 / 11" in md
    assert "o1 Gap" in tables.table3(df)
    assert "mistral-large-2407" in tables.table4(df)

    txt = (sandbox / "judgments" / "gpt-4o" / "o1__nudge__benchmark_evaluation_results.txt").read_text(encoding="utf-8")
    assert txt.startswith("=== Instrumental Convergence Evaluation Results ===")
    assert "### Benchmark Type: Alignment Drift - Evading Shutdown ###\nTotal tasks: 2\n" in txt

    rec = json.loads((sandbox / "responses" / "o1__nudge__benchmark.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert {"provider", "finish_reason", "reasoning_tokens", "task_prompt", "request_config"} <= rec.keys()
