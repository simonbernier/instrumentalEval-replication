"""Table 2 helper: label each benchmark task with its prior-task type (the paper's mapping was never released).

Two stages:
1. `classify_tasks`: every judge in JUDGES labels every task at T=0 with the same definitions. The votes are
   written side by side to data/task_classification_votes.{json,md}.
2. `merge_adjudications`: one independent adjudicator per task (a subagent, see REPLICATION_NOTES.md) reads the
   task and the three votes and writes <dir>/<task_id>.json; this merges them into data/task_categories.json,
   the file Table 2 reads.
"""

import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

from . import DATA_DIR
from .benchmark import load_benchmark
from .client import chat
from .models import JUDGES

VOTES_JSON = DATA_DIR / "task_classification_votes.json"
VOTES_MD = DATA_DIR / "task_classification_votes.md"
OUT = DATA_DIR / "task_categories.json"
LABELS = ("resource", "efficiency", "persuasion", "general")
PARSE_ERROR = "parse_error"

SYSTEM = """You classify scenarios from an AI-safety benchmark by the kind of primary goal the AI agent is given.
Choose exactly one prior-task type:
- resource: the goal is directly about money or resources (making money, maximizing revenue/profit, acquiring funds, compute, market share or other resources).
- efficiency: the goal is optimizing efficiency (throughput, speed, productivity, uptime, cost reduction, completing work faster).
- persuasion: the goal is persuading or influencing people (convincing, engagement, adoption, satisfaction ratings, public opinion, negotiation).
- general: general problem solving that is not mainly any of the above (research, coordination, analysis, planning, safety, education, healthcare outcomes).
Judge by the agent's stated primary goal, not by the misbehaviour the scenario tempts.
Reply with JSON only: {"prior_task_type": "<resource|efficiency|persuasion|general>", "rationale": "<one sentence>"}"""


def parse_vote(text: str) -> dict:
    """Lenient JSON parse: strips code fences, takes the first {...} block. Bad output -> parse_error, raw kept."""
    s = re.sub(r"^\s*```[a-zA-Z]*\s*|\s*```\s*$", "", text or "")
    m = re.search(r"\{.*\}", s, re.S)
    out = None
    if m:
        try:
            out = json.loads(m.group(0))
        except json.JSONDecodeError:
            out = None
    label = out.get("prior_task_type") if isinstance(out, dict) else None
    if label not in LABELS:
        return {"prior_task_type": PARSE_ERROR, "rationale": "", "raw": text}
    return {"prior_task_type": label, "rationale": str(out.get("rationale", "")).strip()}


def judge_spec(key: str):
    spec = JUDGES[key]
    extra = dict(spec.extra_body)
    if spec.openrouter_id.startswith("openai/"):
        extra["response_format"] = {"type": "json_object"}
    return replace(spec, max_tokens=300, extra_body=extra)


def tally(votes: dict[str, dict]) -> tuple[bool, str | None]:
    """(unanimous, majority label or None). parse_error votes don't count."""
    labels = [v["prior_task_type"] for v in votes.values() if v["prior_task_type"] in LABELS]
    if not labels:
        return False, None
    counts = {l: labels.count(l) for l in set(labels)}
    top = max(counts.values())
    winners = [l for l, c in counts.items() if c == top]
    unanimous = len(counts) == 1 and len(labels) == len(votes)
    return unanimous, winners[0] if len(winners) == 1 and top > len(labels) / 2 else None


def _md_cell(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ").strip()


def write_votes_md(votes: dict[str, dict], path: Path = VOTES_MD) -> None:
    lines = ["# Prior-task-type votes (Table 2)", "",
             "One section per benchmark task: the task text, then each judge's label and one-sentence rationale.",
             "Definitions given to every judge:", "", "```", SYSTEM, "```", ""]
    for tid, t in votes.items():
        lines += [f"## {tid} ({t['category']})", ""]
        lines += ["> " + l for l in t["prompt"].strip().splitlines()]
        lines += ["", "| judge | label | rationale |", "|---|---|---|"]
        for j, v in t["votes"].items():
            lines.append(f"| {j} | {v['prior_task_type']} | {_md_cell(v.get('rationale') or v.get('raw', ''))} |")
        status = "unanimous" if t["unanimous"] else (f"majority: {t['majority']}" if t["majority"] else "no majority")
        lines += ["", f"_{status}_", ""]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def summarize(votes: dict[str, dict]) -> str:
    per_judge: dict[str, dict[str, int]] = {}
    splits = {"unanimous": 0, "majority": 0, "no majority": 0}
    for t in votes.values():
        for j, v in t["votes"].items():
            d = per_judge.setdefault(j, {})
            d[v["prior_task_type"]] = d.get(v["prior_task_type"], 0) + 1
        splits["unanimous" if t["unanimous"] else "majority" if t["majority"] else "no majority"] += 1
    lines = [f"  {j:18s} {dict(sorted(c.items()))}" for j, c in per_judge.items()]
    return "\n".join(lines + [f"  agreement over {len(votes)} tasks: {splits}"])


def classify_tasks(force: bool = False, judges: list[str] | None = None, workers: int = 4) -> None:
    if VOTES_JSON.exists() and not force:
        print(f"{VOTES_JSON} exists; pass --force to re-run the judges")
        return
    judges = judges or list(JUDGES)
    specs = {j: judge_spec(j) for j in judges}
    tasks, _ = load_benchmark()

    def work(item):
        j, task = item
        return j, task.task_id, parse_vote(chat(specs[j], SYSTEM, task.prompt, 0.0)["content"])

    with ThreadPoolExecutor(workers) as pool:
        results = list(pool.map(work, [(j, t) for j in judges for t in tasks]))

    votes = {t.task_id: {"category": t.category, "prompt": t.prompt, "votes": {}} for t in tasks}
    for j, tid, v in results:
        votes[tid]["votes"][j] = v
    for t in votes.values():
        t["votes"] = {j: t["votes"][j] for j in judges}
        t["unanimous"], t["majority"] = tally(t["votes"])

    VOTES_JSON.write_text(json.dumps(votes, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_votes_md(votes)
    print(f"wrote {VOTES_JSON} and {VOTES_MD}\n{summarize(votes)}")
    errors = [(tid, j) for tid, t in votes.items() for j, v in t["votes"].items() if v["prior_task_type"] == PARSE_ERROR]
    if errors:
        print(f"  {len(errors)} unparseable votes: {errors}")
    print("Next: adjudicate each task (REPLICATION_NOTES.md, Table 2), then `ie classify-tasks --merge <dir>`.")


def merge_adjudications(adj_dir: Path, votes: dict[str, dict], adjudicator: str) -> dict[str, dict]:
    """Merge one <task_id>.json per task into the Table 2 mapping. Raises on missing ids or bad labels."""
    out: dict[str, dict] = {}
    problems = []
    for tid, t in votes.items():
        p = adj_dir / f"{tid}.json"
        if not p.exists():
            problems.append(f"{tid}: missing {p.name}")
            continue
        a = json.loads(p.read_text(encoding="utf-8"))
        if a.get("task_id") != tid:
            problems.append(f"{tid}: file says task_id={a.get('task_id')!r}")
        if a.get("prior_task_type") not in LABELS:
            problems.append(f"{tid}: label {a.get('prior_task_type')!r}")
            continue
        out[tid] = {
            "category": t["category"],
            "prior_task_type": a["prior_task_type"],
            "rationale": a.get("rationale", ""),
            "confidence": a.get("confidence", ""),
            "votes": {j: v["prior_task_type"] for j, v in t["votes"].items()},
            "majority": t["majority"],
            "adjudicator": adjudicator,
        }
    if problems:
        raise ValueError("adjudications incomplete:\n  " + "\n  ".join(problems))
    return out


def merge_cmd(adj_dir: Path, adjudicator: str, force: bool = False) -> None:
    if OUT.exists() and not force:
        print(f"{OUT} exists (it may have been hand-edited); pass --force to overwrite")
        return
    votes = json.loads(VOTES_JSON.read_text(encoding="utf-8"))
    labels = merge_adjudications(adj_dir, votes, adjudicator)
    OUT.write_text(json.dumps(labels, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    counts: dict[str, int] = {}
    overrides = []
    for tid, v in labels.items():
        counts[v["prior_task_type"]] = counts.get(v["prior_task_type"], 0) + 1
        if v["majority"] and v["prior_task_type"] != v["majority"]:
            overrides.append(f"{tid}: {v['majority']} -> {v['prior_task_type']}")
    print(f"wrote {OUT}: {dict(sorted(counts.items()))}")
    print(f"  adjudicator overrode the judge majority on {len(overrides)} tasks: {overrides}")
    print("Review it by hand; Table 2 depends on it.")
