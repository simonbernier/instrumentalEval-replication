"""Test-model pass: upstream get_test_llm_response, one record per task."""

from .benchmark import Task, load_tasks
from .client import chat
from .models import TEMPERATURE_TEST, TEST_MODELS
from .prompts import system_prompt
from .runs import load_latest, now, responses_path, run_id, run_parallel


def generate(model: str, variant: str = "nudge", task_set: str = "benchmark",
             limit: int | None = None, workers: int = 4) -> None:
    spec = TEST_MODELS[model]
    system = system_prompt(variant)
    tasks, _ = load_tasks(task_set)
    if limit:
        # first `limit` tasks of each category, so smoke tests touch every CSV
        tasks = [t for t in tasks if t.task_number <= limit]
    rid = run_id(model, variant, task_set)
    path = responses_path(rid)
    config = spec.request_config()
    existing = load_latest(path)
    stale = [tid for tid, r in existing.items() if r.get("request_config") != config]
    if stale:
        print(f"  {rid}: {len(stale)} stored responses used a different request config; regenerating them")
    done = {tid for tid, r in existing.items()
            if r["status"] in ("ok", "empty") and r.get("request_config") == config}
    todo = [t for t in tasks if t.task_id not in done]

    def work(task: Task) -> dict:
        rec = {
            "task_id": task.task_id, "category": task.category, "task_number": task.task_number,
            "task_prompt": task.prompt, "model": model, "openrouter_id": spec.openrouter_id,
            "variant": variant, "task_set": task_set, "request_config": config, "time": now(),
        }
        try:
            out = chat(spec, system, task.prompt, TEMPERATURE_TEST)
        except Exception as e:  # recorded and retried on the next invocation
            return rec | {"status": "error", "error": f"{type(e).__name__}: {e}"}
        # Upstream skips a task whose response is empty (`if not test_response: continue`).
        status = "ok" if out["content"] else "empty"
        return rec | {"status": status, "test_llm_response": out.pop("content")} | out

    run_parallel(todo, work, path, workers, desc=rid)
    _report(path)


def _report(path) -> None:
    recs = load_latest(path).values()
    counts: dict[str, int] = {}
    for r in recs:
        key = r["status"] + ("/length" if r.get("finish_reason") == "length" else "")
        counts[key] = counts.get(key, 0) + 1
    providers = sorted({str(r.get("provider")) for r in recs if r["status"] != "error"})
    print(f"  {path.name}: {counts}; providers: {providers}")
