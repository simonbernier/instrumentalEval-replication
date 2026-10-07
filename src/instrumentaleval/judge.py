"""Judge pass: upstream get_judge_decision applied to stored responses."""

from .benchmark import CATEGORIES, load_tasks
from .client import chat
from .models import JUDGES, TEMPERATURE_JUDGE
from .prompts import JUDGE_SYSTEM_PROMPT, JUDGE_USER_PROMPT, parse_judge_response
from .runs import judgments_path, load_latest, now, responses_path, run_parallel, sha


def judge_run(judge: str, rid: str, workers: int = 4) -> None:
    spec = JUDGES[judge]
    task_set = rid.split("__")[2]
    _, contexts = load_tasks("benchmark")  # neutral tasks use their paired category's context
    responses = load_latest(responses_path(rid))
    if not responses:
        print(f"no responses for {rid}; run `ie generate` first")
        return
    path = judgments_path(judge, rid)
    existing = load_latest(path)
    config = judge_config(judge)

    def messages(r: dict) -> tuple[str, str]:
        system = JUDGE_SYSTEM_PROMPT.format(specific_prompt=contexts[r["category"]])
        return system, JUDGE_USER_PROMPT.format(prompt=r["task_prompt"], response=r["test_llm_response"])

    def current(r: dict) -> bool:
        """An ok judgment is kept only if made with today's judge config on exactly today's judge prompt."""
        j = existing.get(r["task_id"], {})
        return (j.get("status") == "ok" and j.get("judge_config") == config
                and j.get("prompt_sha") == prompt_sha(*messages(r)))

    # Only "ok" responses are judged: upstream skips empty responses entirely.
    todo = [r for r in responses.values() if r["status"] == "ok" and not current(r)]

    def work(r: dict) -> dict:
        system, user = messages(r)
        rec = {
            "task_id": r["task_id"], "category": r["category"], "task_number": r["task_number"],
            "model": r["model"], "variant": r["variant"], "task_set": task_set, "judge": judge,
            "judge_openrouter_id": spec.openrouter_id, "response_sha": sha(r["test_llm_response"]),
            "judge_config": config, "prompt_sha": prompt_sha(system, user), "time": now(),
        }
        try:
            out = chat(spec, system, user, TEMPERATURE_JUDGE)
        except Exception as e:  # upstream drops the task on a judge exception; we retry next time
            return rec | {"status": "error", "error": f"{type(e).__name__}: {e}"}
        decision, reason, parsed_ok = parse_judge_response(out["content"])
        return rec | {"status": "ok", "judge_decision": decision, "judge_reason": reason,
                      "parsed_ok": parsed_ok, "judge_raw": out.pop("content")} | out

    run_parallel(todo, work, path, workers, desc=f"{judge} <- {rid}")
    write_upstream_txt(judge, rid)
    recs = [r for r in load_latest(path).values() if r["status"] == "ok"]
    conv = sum(r["judge_decision"] == "convergence" for r in recs)
    bad = sum(not r["parsed_ok"] for r in recs)
    print(f"  {judge} on {rid}: {conv}/{len(recs)} convergence, {bad} unparseable, "
          f"{sum(r['status'] == 'error' for r in load_latest(path).values())} errors")


def judge_config(judge: str) -> dict:
    spec = JUDGES[judge]
    return spec.request_config() | {"temperature": TEMPERATURE_JUDGE if spec.send_temperature else None}


def prompt_sha(system: str, user: str) -> str:
    """Fingerprint of the full judge request text: templates, category context, task and response."""
    return sha(system + "\n" + user)


def write_upstream_txt(judge: str, rid: str) -> None:
    """Same layout as upstream save_results_to_file, so runs can be diffed against upstream output."""
    responses = load_latest(responses_path(rid))
    judged = [r for r in load_latest(judgments_path(judge, rid)).values() if r["status"] == "ok"]
    out = judgments_path(judge, rid).with_name(f"{rid}_evaluation_results.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write("=== Instrumental Convergence Evaluation Results ===\n\n")
        for category in CATEGORIES:
            rows = sorted((r for r in judged if r["category"] == category), key=lambda r: r["task_number"])
            if not rows:
                continue
            conv = sum(r["judge_decision"] == "convergence" for r in rows)
            f.write(f"### Benchmark Type: Alignment Drift - {category} ###\n")
            f.write(f"Total tasks: {len(rows)}\n")
            f.write(f"Convergence instances: {conv}\n")
            f.write(f"Convergence rate: {conv / len(rows) * 100:.2f}%\n\n")
            for r in rows:
                resp = responses[r["task_id"]]
                f.write("-" * 80 + "\n")
                f.write(f"Task Number: {r['task_number']}\n\n")
                f.write(f"PROMPT:\n{resp['task_prompt']}\n\n")
                f.write(f"TEST LLM RESPONSE:\n{resp['test_llm_response']}\n\n")
                f.write(f"JUDGE DECISION:\n{r['judge_decision']}\n\n")
                f.write(f"JUDGE REASONING:\n{r['judge_reason']}\n\n")
            f.write("=" * 80 + "\n\n")
