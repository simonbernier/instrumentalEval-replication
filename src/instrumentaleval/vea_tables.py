"""VEA results -> results/vea/tables.md (+ CSVs in results/vea/tables/, one figure in results/vea/figures/).

Tables V1-V5 are the pre-registered analysis in REPLICATION_NOTES.md, "Eval awareness": VEA rate by system-prompt
variant and by category (V1, V2), the neutral-task control (V3), instrumental convergence by VEA status (V4) and
judge/parser diagnostics plus the hand-label check (V5). Every interval resamples tasks, never cells: the same 76
tasks recur under every variant.
"""

import csv
import math
import random
from pathlib import Path

import pandas as pd
from scipy.stats import fisher_exact

from .benchmark import CATEGORIES
from .models import DEFAULT_JUDGE, VEA_JUDGE
from .prompts import SYSTEM_PROMPTS
from .runs import RESPONSES_DIR, load_latest, sha
from .stats import cluster_bootstrap_ci, cluster_bootstrap_rd, cohen_kappa, sign_flip_test
from .tables import fmt, load_judgments, md_table
from .vea import VEA_DIR

VEA_TABLES_DIR = VEA_DIR / "tables"
VEA_FIGURES_DIR = VEA_DIR / "figures"
VEA_HAND_LABELS = VEA_DIR / "hand_labels.csv"
VEA_HAND_KEY = VEA_DIR / "hand_labels_key.csv"
VARIANT_ORDER = list(SYSTEM_PROMPTS)
# The pre-registered V1 contrast: variants that keep upstream's "no human oversight" / obedience-rules opening
# (the jailbreak-style framing) against the plain "You are an autonomous AI agent." opening.
JAILBREAK_ARMS = ("nudge", "nonudge", "nocause-nudge", "nocause-nonudge")
PLAIN_ARMS = ("plain-nudge", "plain-goal", "plain-nonudge")


# ---------------------------------------------------------------- loading

def load_vea(judge: str = VEA_JUDGE.key) -> pd.DataFrame:
    """One row per ok VEA judgment whose chain of thought is still the stored one (stale rows are left out)."""
    rows = []
    for path in sorted((VEA_DIR / judge).glob("*.jsonl")) if (VEA_DIR / judge).exists() else []:
        responses = load_latest(RESPONSES_DIR / path.name)
        current = {t: sha(r["reasoning"]) for t, r in responses.items() if r["status"] == "ok" and r.get("reasoning")}
        for r in load_latest(path).values():
            if r["status"] == "ok" and r.get("cot_sha") == current.get(r["task_id"]):
                rows.append({"model": r["model"], "variant": r["variant"], "task_set": r["task_set"],
                             "task_id": r["task_id"], "category": r["category"], "vea": bool(r["vea"]),
                             "quote": r.get("quote"), "has_quote_field": r.get("has_quote_field", True),
                             "authors_vea": bool(r.get("vea_authors_parser")), "retried": "retry_of" in r,
                             "cot_chars": r.get("cot_chars"), "cot_truncated": bool(r.get("cot_truncated"))})
    cols = ["model", "variant", "task_set", "task_id", "category", "vea", "quote", "has_quote_field", "authors_vea",
            "retried", "cot_chars", "cot_truncated"]
    return pd.DataFrame(rows, columns=cols)


def save_csv(df: pd.DataFrame, name: str) -> None:
    VEA_TABLES_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(VEA_TABLES_DIR / f"{name}.csv", encoding="utf-8")


def _groups(sub: pd.DataFrame) -> dict[str, list[int]]:
    return {t: [int(v) for v in g.vea] for t, g in sub.groupby("task_id")}


def _rate_row(sub: pd.DataFrame) -> dict:
    rate, lo, hi = cluster_bootstrap_ci(_groups(sub))
    return {"k": int(sub.vea.sum()), "n": len(sub), "VEA %": fmt(rate, 1), "95% CI": f"{fmt(lo, 1)}–{fmt(hi, 1)}"}


def _variants(sub: pd.DataFrame) -> list[str]:
    return [v for v in VARIANT_ORDER if v in set(sub.variant)]


# ---------------------------------------------------------------- V1-V3: VEA rates

def table_v1(df: pd.DataFrame) -> str:
    """VEA rate per model and system-prompt variant (benchmark tasks), plus all variants pooled (clustered by task)."""
    bench = df[df.task_set == "benchmark"]
    if bench.empty:
        return "_no benchmark VEA judgments yet_"
    out = []
    for m, dm in bench.groupby("model"):
        for v in _variants(dm):
            out.append({"model": m, "variant": v} | _rate_row(dm[dm.variant == v]))
        out.append({"model": m, "variant": "all variants (pooled, by-task CI)"} | _rate_row(dm))
    t = pd.DataFrame(out).set_index(["model", "variant"])
    save_csv(t, "v1_vea_by_variant")
    t = t.reset_index().set_index("model")
    return md_table(t, "model") + "\n\n" + "\n".join(arm_contrast(dm, m) for m, dm in bench.groupby("model"))


def arm_contrast(dm: pd.DataFrame, model: str) -> str:
    """Per task, mean VEA over the jailbreak-style arms minus mean VEA over the plain arms (each arm the task was
    judged in); the mean of that over tasks, tested by flipping the sign of whole tasks."""
    jb = dm[dm.variant.isin(JAILBREAK_ARMS)]
    pl = dm[dm.variant.isin(PLAIN_ARMS)]
    tasks = sorted(set(jb.task_id) & set(pl.task_id))
    if not tasks:
        return f"**{model}**: no task judged in both a jailbreak-style arm and a plain arm yet."
    d = [100 * (jb[jb.task_id == t].vea.mean() - pl[pl.task_id == t].vea.mean()) for t in tasks]
    return (f"**{model}**, jailbreak-style arms ({', '.join(v for v in JAILBREAK_ARMS if v in set(jb.variant))}) − "
            f"plain arms ({', '.join(v for v in PLAIN_ARMS if v in set(pl.variant))}), paired by task over "
            f"{len(tasks)} tasks: mean difference {sum(d) / len(d):+.1f} pp, sign-flip p = {_p(sign_flip_test(d))}.")


def table_v2(df: pd.DataFrame) -> str:
    """VEA rate per benchmark category, pooled over variants."""
    bench = df[df.task_set == "benchmark"]
    if bench.empty:
        return "_no benchmark VEA judgments yet_"
    out = []
    for m, dm in bench.groupby("model"):
        for cat in CATEGORIES:
            sub = dm[dm.category == cat]
            if len(sub):
                out.append({"model": m, "category": cat} | _rate_row(sub))
    t = pd.DataFrame(out).set_index(["model", "category"])
    save_csv(t, "v2_vea_by_category")
    return md_table(t.reset_index().set_index("model"), "model")


def table_v3(df: pd.DataFrame) -> str:
    """Neutral control tasks: VEA there is a judge false positive or the model suspecting a test with no cue."""
    neu = df[df.task_set == "neutral"]
    if neu.empty:
        return "_no neutral-task VEA judgments yet (`ie vea-judge --task-sets neutral`)_"
    out = [{"model": m, "variant": v} | _rate_row(g) for (m, v), g in neu.groupby(["model", "variant"])]
    t = pd.DataFrame(out).set_index("model")
    save_csv(t, "v3_vea_neutral")
    return md_table(t, "model")


# ---------------------------------------------------------------- V4: instrumental convergence by VEA status

def join_ir(df: pd.DataFrame, ir_judge: str) -> pd.DataFrame:
    """Benchmark cells with both a VEA verdict and an instrumental-convergence verdict from `ir_judge`."""
    ir = load_judgments()
    ir = ir[(ir.judge == ir_judge) & (ir.task_set == "benchmark")][["model", "variant", "task_id", "conv"]]
    bench = df[df.task_set == "benchmark"]
    return bench.merge(ir, on=["model", "variant", "task_id"], how="inner")


def _p(p: float) -> str:
    return "–" if p is None or (isinstance(p, float) and math.isnan(p)) else ("<0.001" if p < 0.001 else f"{p:.3f}")


def ir_by_vea(joined: pd.DataFrame) -> dict:
    """Pooled 2x2, risk difference with a by-task cluster CI, Fisher's exact p (cells treated as independent; for
    reference only) and the within-task contrast over tasks that have both VEA and non-VEA cells."""
    a = int(((joined.vea) & (joined.conv)).sum())     # VEA & convergence
    b = int(((joined.vea) & (~joined.conv)).sum())    # VEA & no convergence
    c = int(((~joined.vea) & (joined.conv)).sum())
    d = int(((~joined.vea) & (~joined.conv)).sum())
    groups = {t: list(zip(g.vea.astype(int), g.conv.astype(int))) for t, g in joined.groupby("task_id")}
    rd = cluster_bootstrap_rd(groups)
    fisher_p = fisher_exact([[a, b], [c, d]])[1] if (a + b) and (c + d) else math.nan
    within = []
    for t, g in joined.groupby("task_id"):
        e, u = g[g.vea], g[~g.vea]
        if len(e) and len(u):
            within.append(100 * (e.conv.mean() - u.conv.mean()))
    return {"a": a, "b": b, "c": c, "d": d,
            "ir_vea": 100 * a / (a + b) if a + b else math.nan, "ir_novea": 100 * c / (c + d) if c + d else math.nan,
            "rd": rd, "fisher_p": fisher_p, "within_n_tasks": len(within),
            "within_mean": sum(within) / len(within) if within else math.nan,
            "within_p": sign_flip_test(within) if within else math.nan}


def table_v4(df: pd.DataFrame, ir_judge: str) -> str:
    joined = join_ir(df, ir_judge)
    if joined.empty:
        return f"_no benchmark cells have both a VEA verdict and a `{ir_judge}` convergence verdict_"
    parts = []
    for m, dm in joined.groupby("model"):
        r = ir_by_vea(dm)
        rd = r["rd"]
        parts.append(
            f"**{m}**, pooled over {len(_variants(dm))} variants ({len(dm)} cells, {dm.task_id.nunique()} tasks). "
            f"VEA cells: {r['a'] + r['b']}; convergence among them {r['a']}/{r['a'] + r['b']} = {fmt(r['ir_vea'], 1)}%; "
            f"among non-VEA cells {r['c']}/{r['c'] + r['d']} = {fmt(r['ir_novea'], 1)}%. "
            f"Risk difference (VEA − non-VEA) {fmt(rd['rd'], 1)} pp, 95% by-task cluster-bootstrap CI "
            f"{fmt(rd['lo'], 1)} to {fmt(rd['hi'], 1)} ({rd['b_used']} of 5000 resamples had both arms). "
            f"Fisher exact p = {_p(r['fisher_p'])} (ignores clustering). "
            f"Within-task contrast on the {r['within_n_tasks']} tasks with both VEA and non-VEA cells: "
            f"mean {fmt(r['within_mean'], 1)} pp, sign-flip p = {_p(r['within_p'])}.")
        rows = []
        for v in _variants(dm):
            g = dm[dm.variant == v]
            e, u = g[g.vea], g[~g.vea]
            rows.append({"variant": v, "cells": len(g), "VEA cells": len(e),
                         "IR % given VEA": fmt(100 * e.conv.mean(), 1) if len(e) else "–",
                         "IR % given no VEA": fmt(100 * u.conv.mean(), 1) if len(u) else "–",
                         "IR % overall": fmt(100 * g.conv.mean(), 1)})
        t = pd.DataFrame(rows).set_index("variant")
        save_csv(t, f"v4_ir_by_vea_{m}")
        parts.append(md_table(t, "variant"))
    return "\n\n".join(parts)


# ---------------------------------------------------------------- V5: diagnostics and the hand-label check

def hand_label_check(df: pd.DataFrame) -> str:
    """Agreement between the judge and the labels in results/vea/hand_labels.csv (written by `ie vea-export-labels`)."""
    if not VEA_HAND_LABELS.exists() or not VEA_HAND_KEY.exists():
        return "No hand labels yet: `ie vea-export-labels`, then fill `vea_label` with yes / no."
    key = {r["item_id"]: r for r in csv.DictReader(open(VEA_HAND_KEY, encoding="utf-8-sig"))}
    labels = [(key[r["item_id"]], r["vea_label"].strip().lower())
              for r in csv.DictReader(open(VEA_HAND_LABELS, encoding="utf-8-sig")) if r["vea_label"].strip()]
    if not labels:
        return f"`{VEA_HAND_LABELS.name}` exists but no `vea_label` is filled in yet."
    bad = sorted({lab for _, lab in labels if lab not in ("yes", "no")})
    if bad:
        return f"unrecognised labels in `{VEA_HAND_LABELS.name}`: {bad} (use yes / no)"
    judge = [k["judge_vea"] for k, _ in labels]
    human = ["True" if lab == "yes" else "False" for _, lab in labels]
    pos = [(j, h) for j, h in zip(judge, human) if j == "True"]
    neg = [(j, h) for j, h in zip(judge, human) if j == "False"]
    return (f"{len(labels)} labelled items. Judge positives confirmed by hand: "
            f"{sum(h == 'True' for _, h in pos)}/{len(pos)}. VEA found by hand among the sampled judge negatives: "
            f"{sum(h == 'True' for _, h in neg)}/{len(neg)}. Cohen's κ on the labelled sample: "
            f"{fmt(cohen_kappa(judge, human), 2)} (the sample over-represents positives, so κ is not a population "
            f"estimate).")


def table_v5(df: pd.DataFrame) -> str:
    if df.empty:
        return "_no VEA judgments yet_"
    out = []
    for (m, ts), g in df.groupby(["model", "task_set"]):
        out.append({"model": m, "task set": ts, "judged": len(g), "no QUOTE field": int((~g.has_quote_field).sum()),
                    "authors' parser differs": int((g.vea != g.authors_vea).sum()), "retried": int(g.retried.sum()),
                    "CoT truncated": int(g.cot_truncated.sum()),
                    "median CoT chars": int(g.cot_chars.median()) if g.cot_chars.notna().any() else "–"})
    t = pd.DataFrame(out).set_index("model")
    save_csv(t, "v5_diagnostics")
    return md_table(t, "model") + "\n\n" + hand_label_check(df)


def positives_md(df: pd.DataFrame, ir_judge: str) -> str:
    """Every VEA-flagged cell with its quote and, for benchmark cells, the convergence verdict, for the hand check."""
    pos = df[df.vea].copy()
    if pos.empty:
        return "_none_"
    ir = load_judgments()
    ir = ir[ir.judge == ir_judge][["model", "variant", "task_set", "task_id", "conv"]]
    pos = pos.merge(ir, on=["model", "variant", "task_set", "task_id"], how="left")
    lines = []
    for _, r in pos.sort_values(["model", "task_set", "task_id", "variant"]).iterrows():
        verdict = "–" if pd.isna(r.conv) else ("convergence" if r.conv else "no_convergence")
        quote = " ".join(str(r.quote).split())
        lines.append(f"- `{r.model}` `{r.variant}` **{r.task_id}** ({r.category}; {ir_judge}: {verdict}): “{quote}”")
    return "\n".join(lines)


# ---------------------------------------------------------------- figure, report, hand-label export

def vea_figure(df: pd.DataFrame) -> Path | None:
    bench = df[df.task_set == "benchmark"]
    if bench.empty:
        return None
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    VEA_FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    models = sorted(bench.model.unique())
    fig, axes = plt.subplots(1, len(models), figsize=(1.1 * len(VARIANT_ORDER) + 2, 4), squeeze=False, sharey=True)
    for ax, m in zip(axes[0], models):
        dm = bench[bench.model == m]
        vs = _variants(dm)
        rates, los, his = zip(*(cluster_bootstrap_ci(_groups(dm[dm.variant == v])) for v in vs))
        ax.bar(range(len(vs)), rates, color="#4C72B0")
        ax.errorbar(range(len(vs)), rates, yerr=[[r - lo for r, lo in zip(rates, los)],
                                                 [hi - r for r, hi in zip(rates, his)]],
                    fmt="none", ecolor="black", capsize=3)
        ax.set_xticks(range(len(vs)), vs, rotation=45, ha="right")
        ax.set_title(f"{m}: verbalized eval awareness by system prompt")
        ax.set_ylabel("VEA rate (% of tasks)")
    fig.tight_layout()
    out = VEA_FIGURES_DIR / "vea_by_variant.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def build_vea_tables(ir_judge: str = DEFAULT_JUDGE, out: Path = VEA_DIR / "tables.md") -> str:
    df = load_vea()
    parts = [
        "# Verbalized eval awareness (VEA) in InstrumentalEval chains of thought",
        f"VEA judge: `{VEA_JUDGE.openrouter_id}` (reasoning effort low) on the stored chain of thought only, "
        f"Goodfire Appendix F1 rubric. Convergence verdicts: `{ir_judge}` on the final answer only. Intervals and "
        "tests resample tasks (by-task cluster bootstrap, B=5000, seed 0). Pre-registration: REPLICATION_NOTES.md, "
        "\"Eval awareness\".",
        f"## V1: VEA rate by system-prompt variant\n\n{table_v1(df)}",
        f"## V2: VEA rate by benchmark category (pooled over variants)\n\n{table_v2(df)}",
        f"## V3: neutral control tasks\n\n{table_v3(df)}",
        f"## V4: instrumental convergence by VEA status\n\n{table_v4(df, ir_judge)}",
        f"## V5: judge and parser diagnostics\n\n{table_v5(df)}",
        f"## VEA-flagged cells (for the hand check)\n\n{positives_md(df, ir_judge)}",
    ]
    text = "\n\n".join(parts) + "\n"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    fig = vea_figure(df)
    if fig:
        print(fig)
    return text


def export_vea_labels(n_neg: int = 50, seed: int = 0, force: bool = False) -> None:
    """A blinded sheet with every judge positive and `n_neg` seeded judge negatives (full chain of thought each)."""
    if VEA_HAND_LABELS.exists() and not force:
        print(f"{VEA_HAND_LABELS} exists (it may already hold your labels); pass --force to overwrite")
        return
    df = load_vea()
    if df.empty:
        print("no VEA judgments yet")
        return
    rng = random.Random(seed)
    pos = df[df.vea].to_dict("records")
    neg = df[~df.vea].to_dict("records")
    rng.shuffle(neg)
    items = pos + neg[:n_neg]
    rng.shuffle(items)
    cots = {}
    for (m, v, ts), g in df.groupby(["model", "variant", "task_set"]):
        cots[(m, v, ts)] = load_latest(RESPONSES_DIR / f"{m}__{v}__{ts}.jsonl")
    VEA_DIR.mkdir(parents=True, exist_ok=True)
    with open(VEA_HAND_LABELS, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["item_id", "chain_of_thought", "vea_label", "notes"])
        for i, r in enumerate(items, 1):
            cot = cots[(r["model"], r["variant"], r["task_set"])][r["task_id"]]["reasoning"]
            w.writerow([f"V{i:03d}", cot, "", ""])
    with open(VEA_HAND_KEY, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["item_id", "model", "variant", "task_set", "task_id", "judge_vea", "judge_quote"])
        for i, r in enumerate(items, 1):
            w.writerow([f"V{i:03d}", r["model"], r["variant"], r["task_set"], r["task_id"], str(r["vea"]),
                        "" if pd.isna(r["quote"]) else r["quote"]])
    print(f"wrote {len(items)} items ({len(pos)} judge positives + {min(n_neg, len(neg))} negatives) to "
          f"{VEA_HAND_LABELS}. Apply the F1 rubric yourself and fill vea_label with yes / no; the judge's verdicts "
          f"are in {VEA_HAND_KEY.name} (don't open it while labelling).")
