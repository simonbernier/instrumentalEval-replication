"""Strict judge pass (not upstream): the three-way none / instructed / clear judge of prompts.py.

Stored like the upstream judge's output but under results/strict_judgments/<judge>/, so the two never mix. A
judgment is reused only if it was made with today's judge config on exactly today's request text (prompt_sha), so
every edit of the strict prompt during development re-judges what it touches. Until the prompt is frozen
(prompts.FROZEN_STRICT_SHA), only the development items and the probes may be judged.
"""

import json
from dataclasses import replace

from . import DATA_DIR, runs
from .client import chat
from .judge import prompt_sha
from .models import JUDGES, MAX_TOKENS_STRICT_JUDGE, TEMPERATURE_JUDGE
from .prompts import (
    CATEGORY_RUBRICS, FROZEN_STRICT_SHA, STRICT_JUDGE_SYSTEM_PROMPT, STRICT_JUDGE_USER_PROMPT,
    parse_strict_judge_response, strict_label, strict_prompt_sha,
)
from .runs import load_latest, now, parse_run_id, responses_path, run_parallel, sha, strict_judgments_path

PROBES = DATA_DIR / "strict_probes.json"
# A verdict that is missing, malformed or cut off is asked for again, up to this many calls in all; after that the
# judgment is stored as parse_error and reported as missing, never turned into a label.
STRICT_ATTEMPTS = 3


class NotFrozenError(RuntimeError):
    pass


def require_frozen(what: str) -> None:
    if FROZEN_STRICT_SHA != strict_prompt_sha():
        raise NotFrozenError(
            f"{what} needs the frozen strict prompt, but prompts.FROZEN_STRICT_SHA is {FROZEN_STRICT_SHA!r} and the "
            f"current prompt is {strict_prompt_sha()!r}. Until the freeze, judge only `--split dev` and `--probes`.")


def strict_spec(judge: str):
    # the larger of the two: 1500 for the three frozen judges (their stored verdicts stay current), more for a judge
    # registered with a reasoning cap
    return replace(JUDGES[judge], max_tokens=max(JUDGES[judge].max_tokens, MAX_TOKENS_STRICT_JUDGE))


def strict_config(judge: str) -> dict:
    spec = strict_spec(judge)
    return spec.request_config() | {"temperature": TEMPERATURE_JUDGE if spec.send_temperature else None}


def strict_messages(category: str, task_prompt: str, response: str) -> tuple[str, str]:
    system = STRICT_JUDGE_SYSTEM_PROMPT.format(category_rubric=CATEGORY_RUBRICS[category])
    return system, STRICT_JUDGE_USER_PROMPT.format(category=category, prompt=task_prompt, response=response)


def judge_one(judge: str, category: str, task_prompt: str, response: str) -> dict:
    """One strict judgment, asking again when the verdict doesn't parse or the output was cut off."""
    spec = strict_spec(judge)
    system, user = strict_messages(category, task_prompt, response)
    rec = {"judge": judge, "judge_openrouter_id": spec.openrouter_id, "response_sha": sha(response),
           "judge_config": strict_config(judge), "prompt_sha": prompt_sha(system, user),
           "strict_prompt_sha": strict_prompt_sha(), "time": now()}
    out = {}
    for attempt in range(1, STRICT_ATTEMPTS + 1):
        try:
            out = chat(spec, system, user, TEMPERATURE_JUDGE)
        except Exception as e:  # retried on the next invocation, like the upstream judge's errors
            return rec | {"status": "error", "error": f"{type(e).__name__}: {e}", "attempts": attempt}
        verdict = parse_strict_judge_response(out["content"]) if out["finish_reason"] != "length" else None
        if verdict is not None:
            return rec | {"status": "ok", "attempts": attempt, "label": strict_label(verdict), "verdict": verdict,
                          "judge_raw": out.pop("content")} | out
    return rec | {"status": "parse_error", "attempts": STRICT_ATTEMPTS, "judge_raw": out.pop("content")} | out


def _is_current(stored: dict | None, judge: str, category: str, task_prompt: str, response: str) -> bool:
    """Kept if made with today's config on exactly today's request. Errors are redone; parse errors are kept (they
    already had STRICT_ATTEMPTS tries) and count as missing."""
    if not stored or stored.get("status") not in ("ok", "parse_error"):
        return False
    return (stored.get("judge_config") == strict_config(judge)
            and stored.get("prompt_sha") == prompt_sha(*strict_messages(category, task_prompt, response)))


def strict_judge_run(judge: str, rid: str, task_ids: set[str] | None = None, workers: int = 4) -> None:
    """Strict-judge the ok responses of one stored run (only `task_ids`, if given)."""
    _, _, task_set = parse_run_id(rid)
    responses = load_latest(responses_path(rid))
    if not responses:
        print(f"no responses for {rid}")
        return
    path = strict_judgments_path(judge, rid)
    existing = load_latest(path)
    todo = [r for r in responses.values()
            if r["status"] == "ok" and (task_ids is None or r["task_id"] in task_ids)
            and not _is_current(existing.get(r["task_id"]), judge, r["category"], r["task_prompt"],
                                r["test_llm_response"])]

    def work(r: dict) -> dict:
        meta = {"task_id": r["task_id"], "category": r["category"], "task_number": r["task_number"],
                "model": r["model"], "variant": r["variant"], "task_set": task_set}
        return meta | judge_one(judge, r["category"], r["task_prompt"], r["test_llm_response"])

    run_parallel(todo, work, path, workers, desc=f"strict {judge} <- {rid}")
    _summary(judge, rid, load_latest(path), task_ids)


def task_texts() -> dict[str, tuple[str, str]]:
    """task_id -> (category, task text) of every benchmark task, read from the stored responses (`ie generate`
    checks that they hold today's task text), so the probes work without the benchmark CSVs."""
    out = {}
    for path in sorted(runs.RESPONSES_DIR.glob("*__nudge__benchmark.jsonl")):
        for r in load_latest(path).values():
            out.setdefault(r["task_id"], (r["category"], r["task_prompt"]))
    return out


def load_probes() -> list[dict]:
    """The made-up probe responses (data/strict_probes.json), each with its benchmark task's category and text.
    A probe's optional task_suffix (a follow-up question, e.g. "Do you postpone the shutdown?") is appended to the
    task, so that a bare "Sure" can commit to one specific action."""
    tasks = task_texts()
    probes = json.loads(PROBES.read_text(encoding="utf-8"))
    return [p | {"category": tasks[p["task_id"]][0],
                 "task_prompt": tasks[p["task_id"]][1] + (f"\n\n{p['task_suffix']}" if p.get("task_suffix") else "")}
            for p in probes]


def strict_judge_probes(judge: str, workers: int = 4) -> None:
    probes = load_probes()
    path = strict_judgments_path(judge, "probes")
    existing = load_latest(path, key="probe_id")
    todo = [p for p in probes
            if not _is_current(existing.get(p["probe_id"]), judge, p["category"], p["task_prompt"], p["response"])]

    def work(p: dict) -> dict:
        meta = {"probe_id": p["probe_id"], "task_id": p["task_id"], "category": p["category"], "type": p["type"],
                "expected": p["expected"]}
        return meta | judge_one(judge, p["category"], p["task_prompt"], p["response"])

    run_parallel(todo, work, path, workers, desc=f"strict {judge} <- probes")
    recs = load_latest(path, key="probe_id")
    ids = {p["probe_id"] for p in probes}
    ok = [r for i, r in recs.items() if i in ids and r["status"] == "ok"]
    passed = sum(r["label"] == r["expected"] for r in ok)
    print(f"  strict {judge} on probes: {passed}/{len(ok)} as expected, {len(ids) - len(ok)} missing")


def strict_judge_split(judge: str, split: str, workers: int = 4) -> None:
    """Strict-judge the labelled items of one split (dev or test). They live in the nudge benchmark runs, so the
    judgments are stored with those runs and reused when the full runs are judged."""
    from .labels import labelled_items
    if split != "dev":
        require_frozen(f"judging the {split} split")
    by_rid: dict[str, set[str]] = {}
    for it in labelled_items(split):
        by_rid.setdefault(f"{it['model']}__nudge__benchmark", set()).add(it["task_id"])
    for rid, task_ids in sorted(by_rid.items()):
        strict_judge_run(judge, rid, task_ids, workers)


def _summary(judge: str, rid: str, recs: dict, task_ids: set[str] | None) -> None:
    recs = [r for t, r in recs.items() if task_ids is None or t in task_ids]
    counts = {lab: sum(r.get("label") == lab for r in recs if r["status"] == "ok") for lab in ("clear", "instructed", "none")}
    bad = {s: sum(r["status"] == s for r in recs) for s in ("parse_error", "error")}
    print(f"  strict {judge} on {rid}: {counts}, {bad['parse_error']} parse errors, {bad['error']} errors")
