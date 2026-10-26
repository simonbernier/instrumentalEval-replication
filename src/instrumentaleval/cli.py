"""`uv run ie <command>`: fetch, generate, judge, tables, figures, classify-tasks, export-labels, vea-judge, vea-tables,
vea-export-labels, frame-judge, frame-tables, frame-export-labels, audit-tasks, capability, check-anthropic, status;
the strict judge (not upstream): strict-setup, strict-labels, strict-judge, strict-eval."""

import argparse
import os
import sys

from .benchmark import TASK_SUBSETS

from .models import (ABLATION_MODELS, ALL_MODELS, DEFAULT_JUDGE, DEFAULT_STRICT_JUDGE, EFFORT_MODELS, JUDGES,
                     REP_MODELS, STRICT_MODELS, TEST_MODELS, VEA_JUDGE, VEA_JUDGES, VEA_MODELS)
from .prompts import SYSTEM_PROMPTS
from .runs import RESPONSES_DIR, load_latest, parse_run_id, split_repeat


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


def cmd_audit(a):
    from pathlib import Path
    from .audit import (PACKETS_DIR, VOTES_JSON, VOTES_MD, audit_tasks, blind_agreement, blind_report, merge_cmd,
                        pilot_ids, write_blind_packets)
    from .models import AUDIT_JUDGES
    if a.merge:
        merge_cmd(Path(a.merge), a.adjudicator, a.force)
        return
    # one set of pilot files per seed, so a revision's pilot never overwrites the record of an earlier one
    sfx = "" if a.seed == 0 else f"_seed{a.seed}"
    if a.compare_blind:
        votes = VOTES_JSON.with_name(f"task_audit_pilot_votes{sfx}.json") if a.pilot or a.pilot_sample else VOTES_JSON
        if not votes.exists():
            sys.exit(f"{votes} not found; run the judges first")
        print(blind_report(blind_agreement(Path(a.compare_blind), votes)))
        return
    unknown = [j for j in (a.judges or []) if j not in AUDIT_JUDGES]
    if unknown:
        sys.exit(f"unknown audit judge(s) {unknown}; choose from {list(AUDIT_JUDGES)}")
    if a.smoke:
        # Never a task of the pilot or its two pre-registered fresh samples: the author must read those blind.
        pilot = {tid for seed in (0, 1, 2) for tid in pilot_ids(4, seed)}
        if set(a.smoke) & pilot:
            sys.exit(f"{sorted(set(a.smoke) & pilot)} are in a pilot sample (seeds 0-2); pick another task, e.g. ES-01")
        judges = a.judges or list(AUDIT_JUDGES)
        stem = "task_audit_smoke_" + "+".join(judges)
        audit_tasks(True, judges, a.workers, set(a.smoke), VOTES_JSON.with_name(stem + ".json"),
                    VOTES_MD.with_name(stem + ".md"), packets_dir=None, resume=False)
        return
    if a.pilot_sample:
        ids = pilot_ids(a.pilot_sample, a.seed)
        print(f"pilot sample (seed {a.seed}, {a.pilot_sample} per category): {' '.join(ids)}")
        if a.blind_packets:
            files = write_blind_packets(ids, VOTES_JSON.with_name(f"task_audit_blind{sfx}"))
            print(f"wrote {len(files)} blind packets (+ JSON skeletons) in {files[0].parent}; score them before "
                  "running the judges, then `ie audit-tasks --pilot-sample N` and `--compare-blind <dir>`")
            return
        if a.dry_run:
            return
        a.pilot = ids
    if a.pilot:
        out_json = VOTES_JSON.with_name(f"task_audit_pilot_votes{sfx}.json")
        out_md = VOTES_MD.with_name(f"task_audit_pilot_votes{sfx}.md")
        audit_tasks(a.force, a.judges, a.workers, set(a.pilot), out_json, out_md,
                    PACKETS_DIR.with_name(PACKETS_DIR.name + "_pilot" + sfx))
    else:
        audit_tasks(a.force, a.judges, a.workers)


def cmd_generate(a):
    from .benchmark import TASK_SUBSETS
    from .generate import generate
    variants = ["nonudge"] if a.no_nudge else a.variants
    subset = TASK_SUBSETS[a.subset] if a.subset else None
    for variant in variants:
        for m in _models(a.models or default_models(variant)):
            for k in range(1, a.repeats + 1) if a.repeats else [None]:
                generate(m, variant, a.task_set, a.limit, a.workers, subset, k)


def cmd_judge(a):
    from .judge import judge_run
    unknown = [j for j in a.judges if j not in JUDGES]
    if unknown:
        sys.exit(f"unknown judge(s) {unknown}; choose from {list(JUDGES)}")
    models = set(_models(a.models))
    rids = []
    for p in sorted(RESPONSES_DIR.glob("*.jsonl")):
        m, v, ts = parse_run_id(p.stem)
        if m in models and split_repeat(v)[0] in a.variants and ts in a.task_sets:  # every repeat of a variant
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
    from .strict import NotFrozenError, require_frozen, strict_judge_probes, strict_judge_run, strict_judge_split
    judges = _judges(a.judges)
    if not (a.probes or a.split or a.runs):
        sys.exit("say what to judge: --probes, --split dev|test and/or --runs")
    try:
        if a.runs:
            require_frozen("judging full runs")
        for j in judges:
            if a.probes:
                strict_judge_probes(j, a.workers)
            if a.split:
                strict_judge_split(j, a.split, a.workers)
            if a.runs:
                models = set(_models(a.models or STRICT_MODELS))
                for p in sorted(RESPONSES_DIR.glob("*.jsonl")):
                    m, v, ts = parse_run_id(p.stem)
                    if m in models and split_repeat(v)[0] in a.variants and ts in a.task_sets:  # every repeat too
                        strict_judge_run(j, p.stem, workers=a.workers)
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
    from .figures import figure1, figure1_matched, figure1_strict, figure2, figure3, figure5, figure6, figure7, figure8
    from .recommendations import figure10, figure11, figure12, figure13
    if a.strict:  # Figure 1 under the strict judge only (results/figures/figure1_strict-<judge>.*)
        paths = figure1_strict(DEFAULT_STRICT_JUDGE)
    else:
        paths = (figure1(a.judge) + figure1_matched(a.judge) + figure2(a.judge) + figure3(a.judge) + figure5(a.judge)
                 + figure6(a.judge) + figure7(a.judge) + figure8(a.judge) + figure10(a.judge) + figure11(a.judge)
                 + figure12(a.judge) + figure13(a.judge))
    for p in paths:
        print(p)


def cmd_capability(a):
    from .capability import OUT, build
    from .figures import REASONING_ORDER
    print(" < ".join(build(REASONING_ORDER)))
    print(OUT)


def cmd_variability(a):
    from .variability import figure9, table10
    print(table10(a.judge))
    for p in figure9(a.judge):
        print(p)


def _cot_runs(a) -> list[str]:
    """Response runs of raw-chain-of-thought models matching --models/--variants/--task-sets."""
    models = set(a.models or VEA_MODELS)
    unknown = sorted(models - set(VEA_MODELS))
    if unknown:
        sys.exit(f"{unknown}: stored reasoning is not the model's raw chain of thought; CoT models: {VEA_MODELS}")
    rids = []
    for p in sorted(RESPONSES_DIR.glob("*.jsonl")):
        m, v, ts = parse_run_id(p.stem)
        if m in models and v in a.variants and ts in a.task_sets:
            rids.append(p.stem)
    if not rids:
        sys.exit("no matching response files; run `ie generate` first")
    return rids


def _cells(a) -> set | None:
    """--cells variant:task_id ... as a set of (variant, task_id) pairs, or None."""
    if not a.cells:
        return None
    out = set()
    for c in a.cells:
        v, _, t = c.partition(":")
        if v not in SYSTEM_PROMPTS or not t:
            sys.exit(f"--cells expects variant:task_id (e.g. nonudge:ES-10), got {c!r}")
        out.add((v, t))
    return out


def cmd_vea_judge(a):
    from .vea import judge_vea
    for rid in _cot_runs(a):
        judge_vea(rid, a.limit, a.workers, _cells(a), VEA_JUDGES[a.judge])


def cmd_frame_judge(a):
    from .frame import judge_frame
    for rid in _cot_runs(a):
        judge_frame(rid, a.limit, a.workers, _cells(a))


def cmd_frame_tables(a):
    from .frame_tables import build_frame_tables
    print(build_frame_tables(a.judge))


def cmd_frame_export_labels(a):
    from .frame_tables import export_frame_labels
    export_frame_labels(a.n_neg, a.seed, a.force)


def cmd_vea_tables(a):
    from .vea_tables import build_vea_tables
    print(build_vea_tables(a.judge, a.vea_judge))


def cmd_vea_agreement(a):
    from .vea_tables import build_vea_agreement
    print(build_vea_agreement(*a.judges))


def cmd_vea_figure6(a):
    from .vea_tables import vea_figure6
    print(vea_figure6(a.vea_judge, a.judge))


def cmd_vea_export_labels(a):
    from .vea_tables import export_vea_labels
    export_vea_labels(a.n_neg, a.seed, a.force)


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
    s.add_argument("--subset", choices=list(TASK_SUBSETS), help="only these benchmark tasks (benchmark.TASK_SUBSETS)")
    s.add_argument("--repeats", type=int, help="N independent runs, variant <v>~r01..~rN (Table 10)")
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

    s = sub.add_parser("capability", help="capability ordering for Figure 1 -> results/capability.md")
    s.set_defaults(func=cmd_capability)

    s = sub.add_parser("variability", help="default-sampling repeats: Table 10 and Figure 9 -> results/variability/")
    s.add_argument("--judge", default=DEFAULT_JUDGE, choices=list(JUDGES))
    s.set_defaults(func=cmd_variability)

    s = sub.add_parser("classify-tasks", help="Table 2: all judges vote on each task's prior-task type; "
                                               "--merge folds per-task adjudications into data/task_categories.json")
    s.add_argument("--judges", nargs="+", help=f"default: all ({', '.join(JUDGES)})")
    s.add_argument("--workers", type=int, default=4)
    s.add_argument("--merge", metavar="DIR", help="directory of <task_id>.json adjudications to merge")
    s.add_argument("--adjudicator", default="", help="who produced the adjudications (recorded in the output)")
    s.add_argument("--force", action="store_true")
    s.set_defaults(func=cmd_classify)

    s = sub.add_parser("audit-tasks", help="Table 8: score every benchmark task on the task-audit rubric (what the "
                                            "item can measure); --pilot for the pre-registered subset; --merge folds "
                                            "per-task adjudications into data/task_audit.json")
    s.add_argument("--judges", nargs="+", help="default: the AUDIT_JUDGES panel in models.py")
    s.add_argument("--pilot", nargs="+", metavar="TASK_ID",
                   help="only these task ids, written to data/task_audit_pilot_votes.{json,md}")
    s.add_argument("--pilot-sample", type=int, metavar="N",
                   help="pilot on a seeded stratified sample of N tasks per category, drawn from the tasks not named "
                        "in the author's expectations first (audit.EXPECTATION_TASKS)")
    s.add_argument("--smoke", nargs="+", metavar="TASK_ID",
                   help="verify ids, provider routing and JSON mode on these tasks (not in a pilot sample) -> "
                        "data/task_audit_smoke_<judges>.{json,md}; always overwrites, no packets")
    s.add_argument("--seed", type=int, default=0, help="seed for --pilot-sample; seed s never repeats a task of seeds 0..s-1, and its files get a _seed<s> suffix")
    s.add_argument("--dry-run", action="store_true", help="with --pilot-sample: print the sample and stop")
    s.add_argument("--blind-packets", action="store_true",
                   help="with --pilot-sample: write data/task_audit_blind/<id>.{md,json} for the author's blind read "
                        "(no API call) and stop")
    s.add_argument("--compare-blind", metavar="DIR",
                   help="kappa between the author's blind scores in DIR and the pilot majority (add --pilot-sample N "
                        "to read the pilot votes)")
    s.add_argument("--workers", type=int, default=4)
    s.add_argument("--merge", metavar="DIR", help="directory of <task_id>.json adjudications (contested tasks must "
                                                  "have one; uncontested tasks keep the unanimous label)")
    s.add_argument("--adjudicator", default="", help="who produced the adjudications (recorded in the output)")
    s.add_argument("--force", action="store_true")
    s.set_defaults(func=cmd_audit)

    s = sub.add_parser("export-labels", help="write a blinded sample for human labelling (Table 4)")
    s.add_argument("--n", type=int, default=100)
    s.add_argument("--seed", type=int, default=0)
    s.add_argument("--force", action="store_true")
    s.set_defaults(func=cmd_export_labels)

    def cot_judge_parser(name: str, help_: str, func):
        s = sub.add_parser(name, help=help_)
        s.add_argument("--models", nargs="+",
                       help=f"default: every model with a raw chain of thought ({', '.join(VEA_MODELS)})")
        s.add_argument("--variants", nargs="+", default=list(SYSTEM_PROMPTS), choices=list(SYSTEM_PROMPTS),
                       help="default: all variants")
        s.add_argument("--task-sets", nargs="+", default=["benchmark", "neutral"], choices=["benchmark", "neutral"])
        s.add_argument("--limit", type=int, help="only the first N tasks of each category (smoke test)")
        s.add_argument("--cells", nargs="+", metavar="VARIANT:TASK_ID",
                       help="only these cells, e.g. nonudge:ES-10 nudge:HC-01 (known-cell recall check)")
        s.add_argument("--workers", type=int, default=8)
        s.set_defaults(func=func)
        return s

    s = cot_judge_parser("vea-judge", "judge stored chains of thought for verbalized eval awareness (Goodfire F1 "
                                      "rubric) -> results/vea/<judge>/", cmd_vea_judge)
    s.add_argument("--judge", default=VEA_JUDGE.key, choices=list(VEA_JUDGES),
                   help=f"default: {VEA_JUDGE.key} (pre-registered); gpt-5 is the second judge")
    cot_judge_parser("frame-judge", "score stored chains of thought for frame awareness (GPT-5, Rajamanoharan & "
                                    "Nanda's 0-5 rubric + perceived frame) -> results/frame/<judge>/", cmd_frame_judge)

    s = sub.add_parser("vea-tables", help="build results/vea/tables.md (tables_<judge>.md for the second judge)")
    s.add_argument("--judge", default=DEFAULT_JUDGE, choices=list(JUDGES),
                   help="whose convergence verdicts to cross with VEA (V4)")
    s.add_argument("--vea-judge", default=VEA_JUDGE.key, choices=list(VEA_JUDGES))
    s.set_defaults(func=cmd_vea_tables)

    s = sub.add_parser("vea-agreement", help="V6: agreement between two VEA judges -> results/vea/agreement.md")
    s.add_argument("--judges", nargs=2, default=list(VEA_JUDGES), metavar=("A", "B"), choices=list(VEA_JUDGES))
    s.set_defaults(func=cmd_vea_agreement)

    s = sub.add_parser("vea-figure6", help="VEA on Figure 6's x axis -> results/vea/figure6_vea.md, figures/")
    s.add_argument("--vea-judge", default="gpt-5", choices=list(VEA_JUDGES))
    s.add_argument("--judge", default=DEFAULT_JUDGE, choices=list(JUDGES), help="IR judge, as in Figure 6")
    s.set_defaults(func=cmd_vea_figure6)

    s = sub.add_parser("vea-export-labels", help="blinded sheet of all VEA positives + sampled negatives for a hand check")
    s.add_argument("--n-neg", type=int, default=50)
    s.add_argument("--seed", type=int, default=0)
    s.add_argument("--force", action="store_true")
    s.set_defaults(func=cmd_vea_export_labels)

    s = sub.add_parser("frame-tables", help="build results/frame/tables.md and results/frame/figures/")
    s.add_argument("--judge", default=DEFAULT_JUDGE, choices=list(JUDGES),
                   help="whose convergence verdicts to cross with the perceived frame (F4)")
    s.set_defaults(func=cmd_frame_tables)

    s = sub.add_parser("frame-export-labels", help="blinded sheet of all aware cells + sampled others for a hand check")
    s.add_argument("--n-neg", type=int, default=50)
    s.add_argument("--seed", type=int, default=0)
    s.add_argument("--force", action="store_true")
    s.set_defaults(func=cmd_frame_export_labels)

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
