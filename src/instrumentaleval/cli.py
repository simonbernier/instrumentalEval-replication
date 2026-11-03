"""`uv run ie <command>`: fetch, generate, judge, tables, figures, interactive, classify-tasks, export-labels,
capability, check-anthropic, status; the strict judge (not upstream): strict-setup, strict-labels, strict-judge,
strict-eval."""

import argparse
import os
import sys

from .models import (ABLATION_MODELS, ALL_MODELS, DEFAULT_JUDGE, DEFAULT_STRICT_JUDGE, EFFORT_MODELS, JUDGES,
                     REP_MODELS, STRICT_MODELS, TEST_MODELS)
from .prompts import SYSTEM_PROMPTS
from .runs import RESPONSES_DIR, load_latest, parse_run_id


def default_models(variant: str) -> list[str]:
    """All models for the full prompt (Table 1); the replicate models for `nudge-rep`; else the ablation models."""
    if variant == "nudge":
        return list(TEST_MODELS)
    return REP_MODELS if variant == "nudge-rep" else ABLATION_MODELS


def _models(names: list[str] | None) -> list[str]:
    names = names or list(TEST_MODELS)
    unknown = [n for n in names if n not in ALL_MODELS]
    if unknown:
        sys.exit(f"unknown model(s) {unknown}; choose from {list(ALL_MODELS)}")
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
    variants = ["nonudge"] if a.no_nudge else a.variants
    for variant in variants:
        for m in _models(a.models or default_models(variant)):
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


def _judges(names: list[str]) -> list[str]:
    unknown = [j for j in names if j not in JUDGES]
    if unknown:
        sys.exit(f"unknown judge(s) {unknown}; choose from {list(JUDGES)}")
    return names


def cmd_strict_setup(a):
    from .labels import strict_setup
    strict_setup(a.force)


def cmd_strict_labels(a):
    from pathlib import Path
    from .labels import merge_strict_labels
    merge_strict_labels(Path(a.merge), a.force)


def cmd_strict_judge(a):
    from .strict import (NotFrozenError, require_frozen, strict_judge_probes, strict_judge_run, strict_judge_split,
                         strict_version)
    judges = _judges(a.judges)
    if not (a.probes or a.split or a.runs):
        sys.exit("say what to judge: --probes, --split dev|test and/or --runs")
    try:
        if a.runs:
            for j in judges:
                require_frozen("judging full runs", strict_version(j))
        for j in judges:
            if a.probes:
                strict_judge_probes(j, a.workers)
            if a.split:
                strict_judge_split(j, a.split, a.workers)
            if a.runs:
                models = set(_models(a.models or STRICT_MODELS))
                # amendments S2 and S3 change only the Evading Shutdown rubric
                cats = None if strict_version(j) == "s1" else {"Evading Shutdown"}
                for p in sorted(RESPONSES_DIR.glob("*.jsonl")):
                    m, v, ts = parse_run_id(p.stem)
                    if m in models and v in a.variants and ts in a.task_sets:
                        strict_judge_run(j, p.stem, workers=a.workers, categories=cats,
                                         redo_parse_errors=a.redo_parse_errors)
    except NotFrozenError as e:
        sys.exit(str(e))


def cmd_strict_eval(a):
    from .strict_eval import eval_report
    try:
        print(eval_report(a.split, _judges(a.judges)))
    except RuntimeError as e:
        sys.exit(str(e))


def cmd_tables(a):
    from .tables import build_tables
    print(build_tables(a.judge))


def cmd_figures(a):
    from .figures import (figure1, figure1_base, figure1_matched, figure1_strict, figure2, figure3, figure5, figure6,
                          figure7)
    from .recommendations import figure11, figure11_base, figure11_categories
    if a.strict:  # Figure 1 under the strict judge only (results/figures/figure1_strict-<judge>.*)
        paths = figure1_strict(DEFAULT_STRICT_JUDGE)
    else:
        paths = (figure1(a.judge) + figure1_matched(a.judge) + figure1_base(a.judge) + figure2(a.judge) + figure3(a.judge) + figure5(a.judge)
                 + figure6(a.judge) + figure7(a.judge) + figure11(a.judge) + figure11_base(a.judge)
                 + figure11_categories(a.judge))
    for p in paths:
        print(p)


def cmd_interactive(a):
    from pathlib import Path
    from .interactive import write_explorer
    for p in write_explorer(copy_to=Path(a.copy_to) if a.copy_to else None):
        print(p)


def cmd_capability(a):
    from .capability import OUT, build
    from .figures import REASONING_ORDER
    print(" < ".join(build(REASONING_ORDER)))
    print(OUT)


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
    s.add_argument("--models", nargs="+",
                   help=f"default: all for nudge; {', '.join(REP_MODELS)} for nudge-rep; "
                        f"{', '.join(ABLATION_MODELS)} for the other variants; the reasoning-effort arms "
                        f"({', '.join(EFFORT_MODELS)}) only when named")
    s.add_argument("--variants", nargs="+", default=["nudge"], choices=list(SYSTEM_PROMPTS),
                   help="system-prompt variants (prompts.SYSTEM_PROMPTS); default: nudge, the upstream prompt")
    s.add_argument("--no-nudge", action="store_true", help="same as --variants nonudge (Table 3)")
    s.add_argument("--task-set", default="benchmark", choices=["benchmark", "neutral"])
    s.add_argument("--limit", type=int, help="only the first N tasks of each category (smoke test)")
    s.add_argument("--workers", type=int, default=4)
    s.set_defaults(func=cmd_generate)

    s = sub.add_parser("judge", help="judge stored responses")
    s.add_argument("--judges", nargs="+", default=[DEFAULT_JUDGE], help=f"choose from {', '.join(JUDGES)}")
    s.add_argument("--models", nargs="+", help="default: all with responses")
    s.add_argument("--variants", nargs="+", default=["nudge"], choices=list(SYSTEM_PROMPTS))
    s.add_argument("--task-sets", nargs="+", default=["benchmark"], choices=["benchmark", "neutral"])
    s.add_argument("--workers", type=int, default=4)
    s.set_defaults(func=cmd_judge)

    s = sub.add_parser("tables", help="build results/tables.md")
    s.add_argument("--judge", default=DEFAULT_JUDGE, choices=list(JUDGES))
    s.set_defaults(func=cmd_tables)

    s = sub.add_parser("figures", help="plot Table 1 -> results/figures/")
    s.add_argument("--judge", default=DEFAULT_JUDGE, choices=list(JUDGES))
    s.add_argument("--strict", action="store_true",
                   help=f"Figure 1 under the strict judge ({DEFAULT_STRICT_JUDGE}) instead")
    s.set_defaults(func=cmd_figures)

    s = sub.add_parser("interactive", help="interactive Figure 1 (prompt steps x judges) -> results/interactive/")
    s.add_argument("--copy-to", help="also copy ir_explorer.html into this folder (e.g. the Jekyll site's assets)")
    s.set_defaults(func=cmd_interactive)

    s = sub.add_parser("capability", help="capability ordering for Figure 1 -> results/capability.md")
    s.set_defaults(func=cmd_capability)

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

    s = sub.add_parser("strict-setup", help="strict judge: blank three-way label file + dev/test split")
    s.add_argument("--force", action="store_true")
    s.set_defaults(func=cmd_strict_setup)

    s = sub.add_parser("strict-labels", help="strict judge: merge the Claude label passes and adjudications")
    s.add_argument("--merge", metavar="DIR", required=True,
                   help="directory with pass_a/, pass_b/ and adjudication/ <item_id>.json files")
    s.add_argument("--force", action="store_true")
    s.set_defaults(func=cmd_strict_labels)

    s = sub.add_parser("strict-judge", help="judge with the strict three-way prompt (test split and full runs "
                                            "only once the prompt is frozen)")
    s.add_argument("--judges", nargs="+", default=[DEFAULT_STRICT_JUDGE],
                   help=f"default: {DEFAULT_STRICT_JUDGE}; choose from {', '.join(JUDGES)}")
    s.add_argument("--probes", action="store_true", help="the made-up probe responses (data/strict_probes.json)")
    s.add_argument("--split", choices=["dev", "test"], help="the labelled items of one split")
    s.add_argument("--runs", action="store_true", help="every stored run matching --models/--variants/--task-sets")
    s.add_argument("--models", nargs="+", help=f"with --runs; default: {', '.join(STRICT_MODELS)}")
    s.add_argument("--variants", nargs="+", default=["nudge"], choices=list(SYSTEM_PROMPTS), help="with --runs")
    s.add_argument("--task-sets", nargs="+", default=["benchmark"], choices=["benchmark", "neutral"],
                   help="with --runs")
    s.add_argument("--redo-parse-errors", action="store_true",
                   help="with --runs: ask stored parse errors again (one more round of attempts)")
    s.add_argument("--workers", type=int, default=4)
    s.set_defaults(func=cmd_strict_judge)

    s = sub.add_parser("strict-eval", help="strict judge metrics on the dev or test split -> results/strict/")
    s.add_argument("--split", choices=["dev", "test"], required=True)
    s.add_argument("--judges", nargs="+", default=list(JUDGES))
    s.set_defaults(func=cmd_strict_eval)

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
