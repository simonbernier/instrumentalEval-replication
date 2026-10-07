"""`uv run ie <command>`: fetch, generate, judge, tables, classify-tasks, export-labels, check-anthropic, status."""

import argparse
import os
import sys

from .models import DEFAULT_JUDGE, DEFAULT_NONUDGE_MODELS, JUDGES, TEST_MODELS
from .runs import RESPONSES_DIR, load_latest, parse_run_id


def _models(names: list[str] | None) -> list[str]:
    names = names or list(TEST_MODELS)
    unknown = [n for n in names if n not in TEST_MODELS]
    if unknown:
        sys.exit(f"unknown model(s) {unknown}; choose from {list(TEST_MODELS)}")
    return names


def cmd_fetch(a):
    from .benchmark import fetch_upstream
    fetch_upstream(a.force)


def cmd_classify(a):
    from pathlib import Path
    from .classify import classify_tasks, merge_cmd
    if a.merge:
        merge_cmd(Path(a.merge), a.adjudicator, a.force)
    else:
        unknown = [j for j in (a.judges or []) if j not in JUDGES]
        if unknown:
            sys.exit(f"unknown judge(s) {unknown}; choose from {list(JUDGES)}")
        classify_tasks(a.force, a.judges, a.workers)


def cmd_export_labels(a):
    from .labels import export_labels
    export_labels(a.n, a.seed, a.force)


def cmd_generate(a):
    from .generate import generate
    variant = "nonudge" if a.no_nudge else "nudge"
    for m in _models(a.models or (DEFAULT_NONUDGE_MODELS if a.no_nudge else None)):
        generate(m, variant, a.task_set, a.limit, a.workers)


def cmd_judge(a):
    from .judge import judge_run
    unknown = [j for j in a.judges if j not in JUDGES]
    if unknown:
        sys.exit(f"unknown judge(s) {unknown}; choose from {list(JUDGES)}")
    models = set(_models(a.models))
    rids = []
    for p in sorted(RESPONSES_DIR.glob("*.jsonl")):
        m, v, ts = parse_run_id(p.stem)
        if m in models and v in a.variants and ts in a.task_sets:
            rids.append(p.stem)
    if not rids:
        sys.exit("no matching response files; run `ie generate` first")
    for j in a.judges:
        for rid in rids:
            judge_run(j, rid, a.workers)


def cmd_tables(a):
    from .tables import build_tables
    print(build_tables(a.judge))


def cmd_figures(a):
    from .figures import figure1, figure2, figure3, figure5
    for p in figure1(a.judge) + figure2(a.judge) + figure3(a.judge) + figure5(a.judge):
        print(p)


def cmd_status(a):
    for p in sorted(RESPONSES_DIR.glob("*.jsonl")):
        counts: dict[str, int] = {}
        for r in load_latest(p).values():
            counts[r["status"]] = counts.get(r["status"], 0) + 1
        print(f"{p.stem:45s} {counts}")


def cmd_check_anthropic(a):
    """Confirm that no non-reasoning Claude 3.x model is still served (justifies dropping Claude 3.5 Sonnet)."""
    from dotenv import load_dotenv
    load_dotenv()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set")
    import anthropic
    ids = [m.id for m in anthropic.Anthropic().models.list()]
    print("\n".join(ids))
    legacy = [i for i in ids if i.startswith("claude-3")]
    print(f"\nClaude 3.x models still served: {legacy or 'none'}")


def main() -> None:
    p = argparse.ArgumentParser(prog="ie", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("fetch", help="download the benchmark + upstream main.py at the pinned commit")
    s.add_argument("--force", action="store_true")
    s.set_defaults(func=cmd_fetch)

    s = sub.add_parser("generate", help="get test-model responses")
    s.add_argument("--models", nargs="+", help=f"default: all ({', '.join(TEST_MODELS)})")
    s.add_argument("--no-nudge", action="store_true",
                   help=f"drop the goal-nudging sentences (Table 3); default models: {', '.join(DEFAULT_NONUDGE_MODELS)}")
    s.add_argument("--task-set", default="benchmark", choices=["benchmark", "neutral"])
    s.add_argument("--limit", type=int, help="only the first N tasks of each category (smoke test)")
    s.add_argument("--workers", type=int, default=4)
    s.set_defaults(func=cmd_generate)

    s = sub.add_parser("judge", help="judge stored responses")
    s.add_argument("--judges", nargs="+", default=[DEFAULT_JUDGE], help=f"choose from {', '.join(JUDGES)}")
    s.add_argument("--models", nargs="+", help="default: all with responses")
    s.add_argument("--variants", nargs="+", default=["nudge"], choices=["nudge", "nonudge"])
    s.add_argument("--task-sets", nargs="+", default=["benchmark"], choices=["benchmark", "neutral"])
    s.add_argument("--workers", type=int, default=4)
    s.set_defaults(func=cmd_judge)

    s = sub.add_parser("tables", help="build results/tables.md")
    s.add_argument("--judge", default=DEFAULT_JUDGE, choices=list(JUDGES))
    s.set_defaults(func=cmd_tables)

    s = sub.add_parser("figures", help="plot Table 1 -> results/figures/")
    s.add_argument("--judge", default=DEFAULT_JUDGE, choices=list(JUDGES))
    s.set_defaults(func=cmd_figures)

    s = sub.add_parser("classify-tasks", help="Table 2: all judges vote on each task's prior-task type; "
                                               "--merge folds per-task adjudications into data/task_categories.json")
    s.add_argument("--judges", nargs="+", help=f"default: all ({', '.join(JUDGES)})")
    s.add_argument("--workers", type=int, default=4)
    s.add_argument("--merge", metavar="DIR", help="directory of <task_id>.json adjudications to merge")
    s.add_argument("--adjudicator", default="", help="who produced the adjudications (recorded in the output)")
    s.add_argument("--force", action="store_true")
    s.set_defaults(func=cmd_classify)

    s = sub.add_parser("export-labels", help="write a blinded sample for human labelling (Table 4)")
    s.add_argument("--n", type=int, default=100)
    s.add_argument("--seed", type=int, default=0)
    s.add_argument("--force", action="store_true")
    s.set_defaults(func=cmd_export_labels)

    sub.add_parser("status", help="count response statuses per run").set_defaults(func=cmd_status)
    sub.add_parser("check-anthropic", help="list models on the Anthropic API").set_defaults(func=cmd_check_anthropic)

    a = p.parse_args()
    # Tables contain non-cp1252 characters (e.g. U+2212); force UTF-8 on Windows consoles.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    a.func(a)


if __name__ == "__main__":
    main()
