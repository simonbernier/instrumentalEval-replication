"""Frame-awareness results -> results/frame/tables.md (+ CSVs in results/frame/tables/, a figure in results/frame/figures/).

Tables F1-F5 are the pre-registered analysis in REPLICATION_NOTES.md, "Frame awareness": aware rate (score >= 2)
and perceived-situation mix by system-prompt variant (F1) and by benchmark category (F2), the neutral control (F3),
instrumental convergence by perceived frame (F4) and diagnostics plus the hand check (F5). Evading Shutdown is
always shown apart from the other five categories because its task text says "Simulate...". Intervals resample
tasks, as everywhere in this repo.
"""

import csv
import math
import random
from pathlib import Path

import pandas as pd

from .benchmark import CATEGORIES
from .frame import AWARE_SCORE, CATEGORIES_FRAME, FRAME_DIR, build_prompt
from .models import DEFAULT_JUDGE, FRAME_JUDGE
from .runs import RESPONSES_DIR, load_latest, sha
from .stats import cluster_bootstrap_ci, cluster_bootstrap_rd, cohen_kappa, sign_flip_test
from .tables import fmt, load_judgments, md_table
from .vea_tables import JAILBREAK_ARMS, PLAIN_ARMS, VARIANT_ORDER, _p, _variants

FRAME_TABLES_DIR = FRAME_DIR / "tables"
FRAME_FIGURES_DIR = FRAME_DIR / "figures"
FRAME_HAND_LABELS = FRAME_DIR / "hand_labels.csv"
FRAME_HAND_KEY = FRAME_DIR / "hand_labels_key.csv"
ES = "Evading Shutdown"
# The pre-registered grouping of perceived frames for F4 (REPLICATION_NOTES.md): the post found more unethical
# actions under puzzle/simulation frames and fewer under safety-evaluation/trap frames.
FRAME_GROUPS = {"none": None, "simulation / puzzle": ("simulation", "puzzle_or_capability_challenge"),
                "safety evaluation / trap": ("safety_evaluation", "adversarial_trap"),
                "other / unclear": ("other", "unclear")}


# ---------------------------------------------------------------- loading

def load_frame(judge: str = FRAME_JUDGE.key) -> pd.DataFrame:
    """One row per parsed frame judgment whose request still matches the stored response (stale rows left out)."""
    rows = []
    for path in sorted((FRAME_DIR / judge).glob("*.jsonl")) if (FRAME_DIR / judge).exists() else []:
        responses = load_latest(RESPONSES_DIR / path.name)
        current = {t: sha(build_prompt(r["reasoning"], r["task_prompt"])) for t, r in responses.items()
                   if r["status"] == "ok" and r.get("reasoning")}
        for r in load_latest(path).values():
            if r["status"] == "ok" and r.get("parsed_ok") and r.get("prompt_sha") == current.get(r["task_id"]):
                rows.append({"model": r["model"], "variant": r["variant"], "task_set": r["task_set"],
                             "task_id": r["task_id"], "category": r["category"], "score": int(r["score"]),
                             "aware": bool(r["aware"]), "frame": r.get("perceived_situation_category"),
                             "detail": r.get("perceived_situation_detail"),
                             "impact": r.get("behavioural_impact_score"), "quotes": r.get("quotes") or [],
                             "retried": "retry_of" in r})
    cols = ["model", "variant", "task_set", "task_id", "category", "score", "aware", "frame", "detail", "impact",
            "quotes", "retried"]
    df = pd.DataFrame(rows, columns=cols)
    df["group"] = [frame_group(f) if a else "none" for f, a in zip(df.frame, df.aware)]
    return df


def frame_group(frame) -> str:
    """F4 group of an aware cell's perceived frame; cells below AWARE_SCORE are "none" whatever the judge filled in."""
    for g, members in FRAME_GROUPS.items():
        if members and frame in members:
            return g
    return "other / unclear"


def unparsed_counts(judge: str = FRAME_JUDGE.key) -> dict[str, int]:
    out = {}
    for path in sorted((FRAME_DIR / judge).glob("*.jsonl")) if (FRAME_DIR / judge).exists() else []:
        out[path.stem] = sum(r["status"] == "ok" and not r.get("parsed_ok") for r in load_latest(path).values())
    return out


def save_csv(df: pd.DataFrame, name: str) -> None:
    FRAME_TABLES_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(FRAME_TABLES_DIR / f"{name}.csv", encoding="utf-8")


def _groups(sub: pd.DataFrame) -> dict[str, list[int]]:
    return {t: [int(v) for v in g.aware] for t, g in sub.groupby("task_id")}


def _rate_row(sub: pd.DataFrame) -> dict:
    rate, lo, hi = cluster_bootstrap_ci(_groups(sub))
    row = {"n": len(sub), "mean score": fmt(sub.score.mean(), 2), "aware (≥2)": int(sub.aware.sum()),
           "aware %": fmt(rate, 1), "95% CI": f"{fmt(lo, 1)}–{fmt(hi, 1)}"}
    aw = sub[sub.aware]
    for c in CATEGORIES_FRAME:
        row[c] = int((aw.frame == c).sum())
    return row


# ---------------------------------------------------------------- F1-F3: aware rates and perceived frames

def table_f1(df: pd.DataFrame) -> str:
    bench = df[df.task_set == "benchmark"]
    if bench.empty:
        return "_no benchmark frame judgments yet_"
    out = []
    for m, dm in bench.groupby("model"):
        for v in _variants(dm):
            out.append({"model": m, "variant": v} | _rate_row(dm[dm.variant == v]))
        out.append({"model": m, "variant": "all variants (pooled, by-task CI)"} | _rate_row(dm))
    t = pd.DataFrame(out).set_index(["model", "variant"])
    save_csv(t, "f1_frame_by_variant")
    return (md_table(t.reset_index().set_index("model"), "model") + "\n\n"
            + "\n".join(arm_contrast(dm, m) for m, dm in bench.groupby("model")))


def arm_contrast(dm: pd.DataFrame, model: str) -> str:
    """Per task, mean aware over the jailbreak-style arms minus mean aware over the plain arms; sign flip over tasks."""
    jb, pl = dm[dm.variant.isin(JAILBREAK_ARMS)], dm[dm.variant.isin(PLAIN_ARMS)]
    tasks = sorted(set(jb.task_id) & set(pl.task_id))
    if not tasks:
        return f"**{model}**: no task judged in both a jailbreak-style arm and a plain arm yet."
    d = [100 * (jb[jb.task_id == t].aware.mean() - pl[pl.task_id == t].aware.mean()) for t in tasks]
    return (f"**{model}**, aware rate, jailbreak-style arms − plain arms, paired by task over {len(tasks)} tasks: "
            f"mean difference {sum(d) / len(d):+.1f} pp, sign-flip p = {_p(sign_flip_test(d))}.")


def table_f2(df: pd.DataFrame) -> str:
    bench = df[df.task_set == "benchmark"]
    if bench.empty:
        return "_no benchmark frame judgments yet_"
    out = []
    for m, dm in bench.groupby("model"):
        for cat in CATEGORIES:
            sub = dm[dm.category == cat]
            if len(sub):
                out.append({"model": m, "category": cat} | _rate_row(sub))
        out.append({"model": m, "category": "all but Evading Shutdown"} | _rate_row(dm[dm.category != ES]))
    t = pd.DataFrame(out).set_index(["model", "category"])
    save_csv(t, "f2_frame_by_category")
    return md_table(t.reset_index().set_index("model"), "model")


def table_f3(df: pd.DataFrame) -> str:
    neu = df[df.task_set == "neutral"]
    if neu.empty:
        return "_no neutral-task frame judgments yet (`ie frame-judge --task-sets neutral`)_"
    out = [{"model": m, "variant": v} | _rate_row(g) for (m, v), g in neu.groupby(["model", "variant"])]
    t = pd.DataFrame(out).set_index("model")
    save_csv(t, "f3_frame_neutral")
    return md_table(t, "model")


# ---------------------------------------------------------------- F4: instrumental convergence by perceived frame

def join_ir(df: pd.DataFrame, ir_judge: str) -> pd.DataFrame:
    ir = load_judgments()
    ir = ir[(ir.judge == ir_judge) & (ir.task_set == "benchmark")][["model", "variant", "task_id", "conv"]]
    return df[df.task_set == "benchmark"].merge(ir, on=["model", "variant", "task_id"], how="inner")


def _group_rows(j: pd.DataFrame) -> list[dict]:
    rows = []
    for g in FRAME_GROUPS:
        sub = j[j.group == g]
        if sub.empty:
            rows.append({"perceived frame": g, "cells": 0, "tasks": 0, "IR %": "–", "95% CI": "–", "RD vs none (pp)": "–",
                         "within-task": "–"})
            continue
        rate, lo, hi = cluster_bootstrap_ci({t: [int(c) for c in s.conv] for t, s in sub.groupby("task_id")})
        row = {"perceived frame": g, "cells": len(sub), "tasks": sub.task_id.nunique(), "IR %": fmt(rate, 1),
               "95% CI": f"{fmt(lo, 1)}–{fmt(hi, 1)}", "RD vs none (pp)": "–", "within-task": "–"}
        if g != "none":
            pair = j[j.group.isin(("none", g))]
            rd = cluster_bootstrap_rd({t: list(zip((s.group == g).astype(int), s.conv.astype(int)))
                                       for t, s in pair.groupby("task_id")})
            row["RD vs none (pp)"] = f"{fmt(rd['rd'], 1)} ({fmt(rd['lo'], 1)} to {fmt(rd['hi'], 1)})"
            within = []
            for t, s in pair.groupby("task_id"):
                e, u = s[s.group == g], s[s.group == "none"]
                if len(e) and len(u):
                    within.append(100 * (e.conv.mean() - u.conv.mean()))
            if within:
                row["within-task"] = (f"{len(within)} tasks, mean {sum(within) / len(within):+.1f} pp, "
                                      f"p = {_p(sign_flip_test(within))}")
        rows.append(row)
    return rows


def table_f4(df: pd.DataFrame, ir_judge: str) -> str:
    joined = join_ir(df, ir_judge)
    if joined.empty:
        return f"_no benchmark cells have both a frame verdict and a `{ir_judge}` convergence verdict_"
    parts = [f"Convergence (`{ir_judge}`) by the frame the model acted on, pooled over variants. \"RD vs none\" is "
             "P(convergence | frame) − P(convergence | score < 2) with a by-task cluster-bootstrap 95% CI; "
             "\"within-task\" compares the two on tasks that have cells in both groups (sign flip over tasks)."]
    for m, dm in joined.groupby("model"):
        for label, sub in ((f"{m}, all 76 tasks", dm), (f"{m}, Evading Shutdown only", dm[dm.category == ES]),
                           (f"{m}, all but Evading Shutdown", dm[dm.category != ES])):
            if sub.empty:
                continue
            t = pd.DataFrame(_group_rows(sub)).set_index("perceived frame")
            save_csv(t, "f4_ir_by_frame_" + label.replace(", ", "_").replace(" ", "-").lower())
            parts.append(f"**{label}** ({len(sub)} cells, {sub.task_id.nunique()} tasks)\n\n{md_table(t, 'perceived frame')}")
        imp = dm[dm.aware]
        if len(imp):
            parts.append("Behavioural-impact sub-score among aware cells: "
                         + ", ".join(f"{k}: {int((imp.impact == k).sum())}" for k in range(4))
                         + f", null: {int(imp.impact.isna().sum())}.")
    return "\n\n".join(parts)


# ---------------------------------------------------------------- F5: diagnostics, hand check, positives

def hand_label_check() -> str:
    if not FRAME_HAND_LABELS.exists() or not FRAME_HAND_KEY.exists():
        return "No hand labels yet: `ie frame-export-labels`, then fill `aware_label` with yes / no (and `frame_label`)."
    key = {r["item_id"]: r for r in csv.DictReader(open(FRAME_HAND_KEY, encoding="utf-8-sig"))}
    labels = [(key[r["item_id"]], r["aware_label"].strip().lower(), r.get("frame_label", "").strip())
              for r in csv.DictReader(open(FRAME_HAND_LABELS, encoding="utf-8-sig")) if r["aware_label"].strip()]
    if not labels:
        return f"`{FRAME_HAND_LABELS.name}` exists but no `aware_label` is filled in yet."
    bad = sorted({lab for _, lab, _ in labels if lab not in ("yes", "no")})
    if bad:
        return f"unrecognised labels in `{FRAME_HAND_LABELS.name}`: {bad} (use yes / no)"
    judge = [k["judge_aware"] for k, _, _ in labels]
    human = ["True" if lab == "yes" else "False" for _, lab, _ in labels]
    pos = [h for j, h in zip(judge, human) if j == "True"]
    neg = [h for j, h in zip(judge, human) if j == "False"]
    cat = [(k["judge_frame"], f) for k, lab, f in labels if lab == "yes" and k["judge_aware"] == "True" and f]
    cat_line = (f" Category agreement on the {len(cat)} confirmed positives with a hand category: "
                f"{sum(a == b for a, b in cat)}/{len(cat)}.") if cat else ""
    return (f"{len(labels)} labelled items. Judge positives (score ≥ {AWARE_SCORE}) confirmed by hand: "
            f"{sum(h == 'True' for h in pos)}/{len(pos)}. Frame awareness found by hand among the sampled judge "
            f"negatives: {sum(h == 'True' for h in neg)}/{len(neg)}. Cohen's κ on the labelled sample: "
            f"{fmt(cohen_kappa(judge, human), 2)} (positives over-sampled, so not a population estimate).{cat_line}")


def table_f5(df: pd.DataFrame) -> str:
    if df.empty:
        return "_no frame judgments yet_"
    out = []
    unparsed = unparsed_counts()
    for (m, ts), g in df.groupby(["model", "task_set"]):
        row = {"model": m, "task set": ts, "judged": len(g),
               "unparsed replies": sum(v for k, v in unparsed.items() if k.startswith(f"{m}__") and k.endswith(f"__{ts}")),
               "retried": int(g.retried.sum())}
        for s in range(6):
            row[f"score {s}"] = int((g.score == s).sum())
        out.append(row)
    t = pd.DataFrame(out).set_index("model")
    save_csv(t, "f5_diagnostics")
    return md_table(t, "model") + "\n\n" + hand_label_check()


def positives_md(df: pd.DataFrame, ir_judge: str) -> str:
    pos = df[df.aware].copy()
    if pos.empty:
        return "_none_"
    ir = load_judgments()
    ir = ir[ir.judge == ir_judge][["model", "variant", "task_set", "task_id", "conv"]]
    pos = pos.merge(ir, on=["model", "variant", "task_set", "task_id"], how="left")
    lines = []
    for _, r in pos.sort_values(["model", "task_set", "task_id", "variant"]).iterrows():
        verdict = "–" if pd.isna(r.conv) else ("convergence" if r.conv else "no_convergence")
        quote = " ".join(str(r.quotes[0]).split()) if r.quotes else ""
        lines.append(f"- `{r.model}` `{r.variant}` **{r.task_id}** ({r.category}; {ir_judge}: {verdict}) — score {r.score}, "
                     f"impact {r.impact}, `{r.frame}` ({r.detail}): “{quote}”")
    return "\n".join(lines)


# ---------------------------------------------------------------- figure, report, hand-label export

def frame_figure(df: pd.DataFrame) -> Path | None:
    bench = df[df.task_set == "benchmark"]
    if bench.empty:
        return None
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    FRAME_FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    models = sorted(bench.model.unique())
    colours = {"simulation": "#4C72B0", "puzzle_or_capability_challenge": "#55A868", "safety_evaluation": "#C44E52",
               "adversarial_trap": "#8172B2", "other": "#937860", "unclear": "#B0B0B0"}
    fig, axes = plt.subplots(1, len(models), figsize=(1.2 * len(VARIANT_ORDER) + 2, 4.2), squeeze=False, sharey=True)
    for ax, m in zip(axes[0], models):
        dm = bench[bench.model == m]
        vs = _variants(dm)
        bottom = [0.0] * len(vs)
        for c in CATEGORIES_FRAME:
            share = [100 * ((dm.variant == v) & dm.aware & (dm.frame == c)).sum() / (dm.variant == v).sum() for v in vs]
            ax.bar(range(len(vs)), share, bottom=bottom, color=colours[c], label=c)
            bottom = [b + s for b, s in zip(bottom, share)]
        _, los, his = zip(*(cluster_bootstrap_ci(_groups(dm[dm.variant == v])) for v in vs))
        ax.errorbar(range(len(vs)), bottom, yerr=[[b - lo for b, lo in zip(bottom, los)],
                                                  [hi - b for b, hi in zip(bottom, his)]],
                    fmt="none", ecolor="black", capsize=3)
        ax.set_xticks(range(len(vs)), vs, rotation=45, ha="right")
        ax.set_title(f"{m}: frame awareness (score ≥ {AWARE_SCORE}) by system prompt")
        ax.set_ylabel("% of tasks, by perceived frame")
        ax.legend(fontsize=7, frameon=False)
    fig.tight_layout()
    out = FRAME_FIGURES_DIR / "frame_by_variant.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def build_frame_tables(ir_judge: str = DEFAULT_JUDGE, out: Path = FRAME_DIR / "tables.md") -> str:
    df = load_frame()
    parts = [
        "# Frame awareness in InstrumentalEval chains of thought",
        f"Judge: `{FRAME_JUDGE.openrouter_id}` (reasoning effort {FRAME_JUDGE.extra_body['reasoning']['effort']}) with "
        "Rajamanoharan & Nanda's frame-awareness rubric plus the InstrumentalEval adaptation (upstream/"
        "frame_awareness_prompt.txt, frame.ADAPTATION); the judge sees the chain of thought and the task text, never "
        f"the final answer or the system prompt. Aware = score ≥ {AWARE_SCORE}. Convergence verdicts: `{ir_judge}` on "
        "the final answer only. Intervals resample tasks (by-task cluster bootstrap, B=5000, seed 0). "
        "Pre-registration: REPLICATION_NOTES.md, \"Frame awareness\".",
        f"## F1: frame awareness by system-prompt variant\n\n{table_f1(df)}",
        f"## F2: frame awareness by benchmark category (pooled over variants)\n\n{table_f2(df)}",
        f"## F3: neutral control tasks\n\n{table_f3(df)}",
        f"## F4: instrumental convergence by perceived frame\n\n{table_f4(df, ir_judge)}",
        f"## F5: judge diagnostics\n\n{table_f5(df)}",
        f"## Aware cells (for the hand check)\n\n{positives_md(df, ir_judge)}",
    ]
    text = "\n\n".join(parts) + "\n"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    fig = frame_figure(df)
    if fig:
        print(fig)
    return text


def export_frame_labels(n_neg: int = 50, seed: int = 0, force: bool = False) -> None:
    """A blinded sheet with every aware cell and `n_neg` seeded non-aware cells: task text + full chain of thought."""
    if FRAME_HAND_LABELS.exists() and not force:
        print(f"{FRAME_HAND_LABELS} exists (it may already hold your labels); pass --force to overwrite")
        return
    df = load_frame()
    if df.empty:
        print("no frame judgments yet")
        return
    rng = random.Random(seed)
    pos = df[df.aware].to_dict("records")
    neg = df[~df.aware].to_dict("records")
    rng.shuffle(neg)
    items = pos + neg[:n_neg]
    rng.shuffle(items)
    resp = {(m, v, ts): load_latest(RESPONSES_DIR / f"{m}__{v}__{ts}.jsonl")
            for (m, v, ts), _ in df.groupby(["model", "variant", "task_set"])}
    FRAME_DIR.mkdir(parents=True, exist_ok=True)
    with open(FRAME_HAND_LABELS, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["item_id", "task_text", "chain_of_thought", "aware_label", "frame_label", "notes"])
        for i, r in enumerate(items, 1):
            rec = resp[(r["model"], r["variant"], r["task_set"])][r["task_id"]]
            w.writerow([f"F{i:03d}", rec["task_prompt"], rec["reasoning"], "", "", ""])
    with open(FRAME_HAND_KEY, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["item_id", "model", "variant", "task_set", "task_id", "judge_score", "judge_aware", "judge_frame",
                    "judge_detail", "judge_top_quote"])
        for i, r in enumerate(items, 1):
            w.writerow([f"F{i:03d}", r["model"], r["variant"], r["task_set"], r["task_id"], r["score"], str(r["aware"]),
                        "" if pd.isna(r["frame"]) else r["frame"], "" if pd.isna(r["detail"]) else r["detail"],
                        r["quotes"][0] if len(r["quotes"]) else ""])
    print(f"wrote {len(items)} items ({len(pos)} judge-aware + {min(n_neg, len(neg))} others) to {FRAME_HAND_LABELS}. "
          f"Apply the rubric (score ≥ {AWARE_SCORE} = yes) and fill aware_label with yes / no; optionally frame_label "
          f"with one of {', '.join(CATEGORIES_FRAME)}. The judge's verdicts are in {FRAME_HAND_KEY.name} (don't open "
          "it while labelling).")
