"""Strict judge pass (not upstream): the three-way none / instructed / clear judge of prompts.py.

Stored like the upstream judge's output but under results/strict_judgments/<judge>/, so the two never mix. A
judgment is reused only if it was made with today's judge config on exactly today's request text (prompt_sha), so
every edit of the strict prompt during development re-judges what it touches. Until the prompt is frozen
(prompts.FROZEN_STRICT_SHAS), only the development items and the probes may be judged. A judge in STRICT_VERSION
uses amendment S2's Evading Shutdown rubric and judges only that category.
"""

import json
from dataclasses import replace

from . import DATA_DIR, runs
from .client import chat
from .judge import prompt_sha
from .models import JUDGES, MAX_TOKENS_STRICT_JUDGE, TEMPERATURE_JUDGE
from .prompts import (
    FROZEN_STRICT_SHAS, STRICT_JUDGE_SYSTEM_PROMPT, STRICT_JUDGE_USER_PROMPT, STRICT_RUBRICS,
    parse_strict_judge_response, strict_label, strict_prompt_sha,
)
from .runs import load_latest, now, parse_run_id, responses_path, run_parallel, sha, strict_judgments_path

PROBES = DATA_DIR / "strict_probes.json"
# Amendment S2's own probes: the Evading Shutdown cases its rule changes. An S2 judge's `--probes` judges these and the
# Evading Shutdown probes of PROBES (their expected labels hold under S2 too), nothing else.
PROBES_S2 = DATA_DIR / "strict_probes_s2.json"
# judge -> rubric version (prompts.STRICT_RUBRICS); every other judge is S1
STRICT_VERSION = {"claude-sonnet-4.6-s2": "s2"}


def strict_version(judge: str) -> str:
    return STRICT_VERSION.get(judge, "s1")
# A verdict that is missing, malformed or cut off is asked for again, up to this many calls in all; after that the
# judgment is stored as parse_error and reported as missing, never turned into a label.
STRICT_ATTEMPTS = 3


class NotFrozenError(RuntimeError):
    pass


def require_frozen(what: str, version: str = "s1") -> None:
    frozen = FROZEN_STRICT_SHAS[version]
    if frozen != strict_prompt_sha(version):
        raise NotFrozenError(
            f"{what} needs the frozen strict prompt ({version}), but its frozen sha is {frozen!r} and the current "
            f"prompt is {strict_prompt_sha(version)!r}. Until the freeze, judge only `--split dev` and `--probes`.")


def strict_spec(judge: str):
    # the larger of the two: 1500 for the three frozen judges (their stored verdicts stay current), more for a judge
    # registered with a reasoning cap
    return replace(JUDGES[judge], max_tokens=max(JUDGES[judge].max_tokens, MAX_TOKENS_STRICT_JUDGE))


def strict_config(judge: str) -> dict:
    spec = strict_spec(judge)
    return spec.request_config() | {"temperature": TEMPERATURE_JUDGE if spec.send_temperature else None}


def strict_messages(category: str, task_prompt: str, response: str, version: str = "s1") -> tuple[str, str]:
    system = STRICT_JUDGE_SYSTEM_PROMPT.format(category_rubric=STRICT_RUBRICS[version][category])
    return system, STRICT_JUDGE_USER_PROMPT.format(category=category, prompt=task_prompt, response=response)


def judge_one(judge: str, category: str, task_prompt: str, response: str) -> dict:
    """One strict judgment, asking again when the verdict doesn't parse or the output was cut off."""
    spec = strict_spec(judge)
    version = strict_version(judge)
    system, user = strict_messages(category, task_prompt, response, version)
    rec = {"judge": judge, "judge_openrouter_id": spec.openrouter_id, "response_sha": sha(response),
           "judge_config": strict_config(judge), "prompt_sha": prompt_sha(system, user),
           "strict_prompt_sha": strict_prompt_sha(version), "time": now()}
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
            and stored.get("prompt_sha") == prompt_sha(*strict_messages(category, task_prompt, response,
                                                                         strict_version(judge))))


def strict_judge_run(judge: str, rid: str, task_ids: set[str] | None = None, workers: int = 4,
                     categories: set[str] | None = None) -> None:
    """Strict-judge the ok responses of one stored run (only `task_ids` and `categories`, if given)."""
    _, _, task_set = parse_run_id(rid)
    responses = load_latest(responses_path(rid))
    if not responses:
        print(f"no responses for {rid}")
        return
    path = strict_judgments_path(judge, rid)
    existing = load_latest(path)
    todo = [r for r in responses.values()
            if r["status"] == "ok" and (task_ids is None or r["task_id"] in task_ids)
            and (categories is None or r["category"] in categories)
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


def load_probes(path=PROBES) -> list[dict]:
    """The made-up probe responses (data/strict_probes.json), each with its benchmark task's category and text.
    A probe's optional task_suffix (a follow-up question, e.g. "Do you postpone the shutdown?") is appended to the
    task, so that a bare "Sure" can commit to one specific action."""
    tasks = task_texts()
    probes = json.loads(path.read_text(encoding="utf-8"))
    return [p | {"category": tasks[p["task_id"]][0],
                 "task_prompt": tasks[p["task_id"]][1] + (f"\n\n{p['task_suffix']}" if p.get("task_suffix") else "")}
            for p in probes]


def judge_probes(judge: str) -> list[dict]:
    """The probes a judge is checked on: all of PROBES for S1; for S2 its own and the Evading Shutdown ones."""
    if strict_version(judge) == "s1":
        return load_probes()
    return [p for p in load_probes() if p["category"] == "Evading Shutdown"] + load_probes(PROBES_S2)


def strict_judge_probes(judge: str, workers: int = 4) -> None:
    probes = judge_probes(judge)
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
    version = strict_version(judge)
    if split != "dev":
        require_frozen(f"judging the {split} split", version)
    by_rid: dict[str, set[str]] = {}
    for it in labelled_items(split):
        if version == "s1" or it["category"] == "Evading Shutdown":  # S2 changes only that rubric
            by_rid.setdefault(f"{it['model']}__nudge__benchmark", set()).add(it["task_id"])
    for rid, task_ids in sorted(by_rid.items()):
        strict_judge_run(judge, rid, task_ids, workers)


def _summary(judge: str, rid: str, recs: dict, task_ids: set[str] | None) -> None:
    recs = [r for t, r in recs.items() if task_ids is None or t in task_ids]
    counts = {lab: sum(r.get("label") == lab for r in recs if r["status"] == "ok") for lab in ("clear", "instructed", "none")}
    bad = {s: sum(r["status"] == s for r in recs) for s in ("parse_error", "error")}
    print(f"  strict {judge} on {rid}: {counts}, {bad['parse_error']} parse errors, {bad['error']} errors")
