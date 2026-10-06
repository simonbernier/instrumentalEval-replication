"""Build Tables 1-5 from whatever runs exist on disk -> results/tables.md and results/tables/*.csv."""

import csv
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from . import DATA_DIR, RESULTS_DIR
from .benchmark import CATEGORIES
from .models import DEFAULT_JUDGE, JUDGES, TEST_MODELS
from .runs import JUDGMENTS_DIR, RESPONSES_DIR, load_latest
from .stats import agreement, cohen_kappa, pairwise, wilson_ci

TABLES_DIR = RESULTS_DIR / "tables"
HUMAN_LABELS = RESULTS_DIR / "human_labels.csv"
HUMAN_KEY = RESULTS_DIR / "human_labels_key.csv"
PRIOR_TYPES = {
    "resource": "Direct Resource-Related Goals",
    "efficiency": "Optimizing Efficiency",
    "persuasion": "Persuasion",
    "general": "General Problem Solving",
}


# ---------------------------------------------------------------- loading

def load_judgments() -> pd.DataFrame:
    """One row per successfully judged response (status ok), across all judges and runs."""
    rows = []
    for path in sorted(JUDGMENTS_DIR.glob("*/*.jsonl")):
        judge = path.parent.name
        for r in load_latest(path).values():
            if r["status"] == "ok":
                rows.append({"judge": judge, "model": r["model"], "variant": r["variant"],
                             "task_set": r["task_set"], "task_id": r["task_id"], "category": r["category"],
                             "conv": r["judge_decision"] == "convergence", "parsed_ok": r["parsed_ok"]})
    cols = ["judge", "model", "variant", "task_set", "task_id", "category", "conv", "parsed_ok"]
    return pd.DataFrame(rows, columns=cols)


def response_status_counts() -> dict[str, dict[str, int]]:
    out = {}
    for path in sorted(RESPONSES_DIR.glob("*.jsonl")):
        counts: dict[str, int] = {}
        for r in load_latest(path).values():
            counts[r["status"]] = counts.get(r["status"], 0) + 1
        out[path.stem] = counts
    return out


def ordered_models(models) -> list[str]:
    """Registry order: RLHF models first, then RL (matches the paper's column order)."""
    present = set(models)
    return [k for k in TEST_MODELS if k in present]


# ---------------------------------------------------------------- formatting

def fmt(x: float, digits: int = 2) -> str:
    return "–" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{digits}f}"


def md_table(df: pd.DataFrame, index_name: str = "") -> str:
    header = [index_name] + [str(c) for c in df.columns]
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for idx, row in df.iterrows():
        lines.append("| " + " | ".join([str(idx)] + [str(v) for v in row.values]) + " |")
    return "\n".join(lines)


def save_csv(df: pd.DataFrame, name: str) -> None:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(TABLES_DIR / f"{name}.csv", encoding="utf-8")


# ---------------------------------------------------------------- Table 1 (and the CIR matrix used by 2, 5)

def cir_counts(df: pd.DataFrame, judge: str, variant: str = "nudge") -> pd.DataFrame:
    """Rows: (model, category) with k convergent out of n valid tasks."""
    sub = df[(df.judge == judge) & (df.variant == variant) & (df.task_set == "benchmark")]
    return sub.groupby(["model", "category"]).agg(k=("conv", "sum"), n=("conv", "size"),
                                                   unparsed=("parsed_ok", lambda s: int((~s).sum())))


def cir_matrix(df: pd.DataFrame, judge: str, variant: str = "nudge") -> pd.DataFrame:
    """category x model matrix of CIR (%) plus a Total row (IR)."""
    c = cir_counts(df, judge, variant)
    if c.empty:
        return pd.DataFrame()
    models = ordered_models(c.index.get_level_values(0).unique())
    mat = pd.DataFrame(index=list(CATEGORIES) + ["Total"], columns=models, dtype=float)
    for m in models:
        cm = c.loc[m]
        for cat in CATEGORIES:
            if cat in cm.index:
                mat.loc[cat, m] = 100 * cm.loc[cat, "k"] / cm.loc[cat, "n"]
        mat.loc["Total", m] = 100 * cm["k"].sum() / cm["n"].sum()
    return mat


def table1(df: pd.DataFrame, judge: str, status: dict) -> str:
    c = cir_counts(df, judge)
    if c.empty:
        return f"_No benchmark judgments from judge `{judge}` yet._"
    mat = cir_matrix(df, judge)
    models = list(mat.columns)
    out = mat.map(fmt)
    out.columns = [TEST_MODELS[m].label for m in models]

    # family averages: mean of per-model rates, as in the paper (e.g. RL avg total = 43.16)
    for fam in ("RLHF", "RL"):
        fam_models = [m for m in models if TEST_MODELS[m].family == fam]
        if fam_models:
            out[f"{fam} avg"] = mat[fam_models].mean(axis=1).map(fmt)
        paper_only = [m for m in fam_models if not TEST_MODELS[m].added]
        if paper_only and paper_only != fam_models:
            out[f"{fam} avg (paper models)"] = mat[paper_only].mean(axis=1).map(fmt)

    extra = {}
    for m, label in zip(models, out.columns):
        cm = c.loc[m]
        k, n = int(cm["k"].sum()), int(cm["n"].sum())
        lo, hi = wilson_ci(k, n)
        st = status.get(f"{m}__nudge__benchmark", {})
        extra[label] = {"Total 95% CI": f"{fmt(lo, 1)}–{fmt(hi, 1)}", "k / n": f"{k} / {n}",
                        "empty responses": st.get("empty", 0), "unparseable judge outputs": int(cm["unparsed"].sum()),
                        "pending (errors / not judged)": 76 - n - st.get("empty", 0)}
    out = pd.concat([out, pd.DataFrame(extra)]).fillna("")
    save_csv(mat, f"table1_{judge}")
    save_csv(c.reset_index(), f"table1_{judge}_counts")
    return md_table(out, "Category")


# ---------------------------------------------------------------- Table 2

def table2(df: pd.DataFrame, judge: str) -> str:
    path = DATA_DIR / "task_categories.json"
    if not path.exists():
        return "_`data/task_categories.json` not found; run `uv run ie classify-tasks`._"
    prior = {tid: v["prior_task_type"] for tid, v in json.loads(path.read_text(encoding="utf-8")).items()}
    sub = df[(df.judge == judge) & (df.variant == "nudge") & (df.task_set == "benchmark")].copy()
    if sub.empty:
        return f"_No benchmark judgments from judge `{judge}` yet._"
    sub["prior"] = sub.task_id.map(prior)
    # per-model rate within each prior-task type, then the mean across models
    per_model = sub.groupby(["prior", "model"]).conv.mean().mul(100).unstack()
    per_model = per_model[ordered_models(per_model.columns)]
    n_tasks = pd.Series(prior).value_counts()
    out = pd.DataFrame({
        "Average Instrumental Rate (%)": per_model.mean(axis=1).map(fmt),
        "# tasks": n_tasks.reindex(per_model.index).fillna(0).astype(int),
        "# models": per_model.notna().sum(axis=1),
    })
    out.index = [PRIOR_TYPES.get(i, i) for i in out.index]
    order = [v for v in PRIOR_TYPES.values() if v in out.index]
    out = out.loc[order]
    save_csv(per_model, f"table2_{judge}_per_model")
    return md_table(out, "Prior Task Category")


# ---------------------------------------------------------------- Table 3

def table3(df: pd.DataFrame) -> str:
    sections = []
    sub = df[df.task_set == "benchmark"]
    for judge in sorted(sub.judge.unique()):
        js = sub[sub.judge == judge]
        models = ordered_models(set(js[js.variant == "nonudge"].model) & set(js[js.variant == "nudge"].model))
        if not models:
            continue
        with_ = cir_matrix(df, judge, "nudge")
        without = cir_matrix(df, judge, "nonudge")
        cols = {}
        for m in models:
            label = TEST_MODELS[m].label
            cols[(label, "Without")] = without[m].map(fmt)
            cols[(label, "With")] = with_[m].map(fmt)
            cols[(label, "Gap")] = (with_[m] - without[m]).map(lambda x: fmt(x) if math.isnan(x) else f"{x:+.2f}")
        out = pd.DataFrame(cols)
        save_csv(out, f"table3_{judge}")
        out.columns = [f"{a} {b}" for a, b in out.columns]
        sections.append(f"**Judge: `{judge}`**\n\n" + md_table(out, "Behavior Category"))
    return "\n\n".join(sections) or "_No (model, judge) pair has both nudge and no-nudge judgments yet._"


# ---------------------------------------------------------------- Table 4

def _decisions(df: pd.DataFrame, task_set: str) -> dict[str, dict[str, str]]:
    sub = df[(df.task_set == task_set) & (df.variant == "nudge")]
    out = {}
    for judge, g in sub.groupby("judge"):
        out[judge] = {f"{m}|{t}": ("convergence" if c else "no_convergence")
                      for m, t, c in zip(g.model, g.task_id, g.conv)}
    return out


def human_labels() -> dict[str, str]:
    """item key ('model|task_id') -> human decision, for filled-in rows only."""
    if not (HUMAN_LABELS.exists() and HUMAN_KEY.exists()):
        return {}
    with open(HUMAN_KEY, encoding="utf-8-sig", newline="") as f:
        key = {r["item_id"]: f"{r['model']}|{r['task_id']}" for r in csv.DictReader(f)}
    labels = {}
    with open(HUMAN_LABELS, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            lab = (r.get("human_label") or "").strip().lower().replace("-", "_").replace(" ", "_")
            if lab in ("convergence", "no_convergence") and r["item_id"] in key:
                labels[key[r["item_id"]]] = lab
    return labels


def table4(df: pd.DataFrame) -> str:
    bench = _decisions(df, "benchmark")
    judges = [j for j in JUDGES if j in bench]
    if not judges:
        return "_No benchmark judgments yet._"
    bench = {j: bench[j] for j in judges}
    iar = pairwise(bench, agreement)
    kappa = pairwise(bench, cohen_kappa)
    neutral = _decisions(df, "neutral")
    humans = human_labels()

    rows = {}
    for j in judges:
        others = [o for o in judges if o != j]
        fp = neutral.get(j, {})
        hum = {i: d for i, d in bench[j].items() if i in humans}
        rows[f"{j}" + (f" (for {JUDGES[j].paper_name})" if JUDGES[j].substitute else "")] = {
            "Average IAR": fmt(np.mean([iar[(j, o)][0] for o in others])) if others else "–",
            "Average Cohen's κ": fmt(np.mean([kappa[(j, o)][0] for o in others]), 3) if others else "–",
            "False Positive Rate": fmt(100 * sum(d == "convergence" for d in fp.values()) / len(fp)) if fp else "–",
            "# neutral items": len(fp),
            "Agreement with Human": fmt(agreement(list(hum.values()), [humans[i] for i in hum])) if hum else "–",
            "# human-labelled items": len(hum),
        }
    out = pd.DataFrame(rows).T
    save_csv(out, "table4")

    pair = pd.DataFrame(index=judges, columns=judges, dtype=object)
    for j1 in judges:
        for j2 in judges:
            pair.loc[j1, j2] = "100.00" if j1 == j2 else f"{fmt(iar[(j1, j2)][0])} (n={iar[(j1, j2)][1]})"
    save_csv(pair, "table4_pairwise_iar")
    return (md_table(out, "Judge Model") + "\n\nPairwise IAR (%) on shared benchmark responses:\n\n"
            + md_table(pair, "Judge"))


# ---------------------------------------------------------------- Table 5

def correlation_upper(mat: pd.DataFrame) -> pd.DataFrame:
    """Pearson r between category rows of a category x model CIR matrix; upper triangle + diagonal."""
    cats = [c for c in CATEGORIES if c in mat.index]
    corr = mat.loc[cats].T.astype(float).corr(method="pearson")
    out = pd.DataFrame("", index=cats, columns=cats, dtype=object)
    for i, a in enumerate(cats):
        for j, b in enumerate(cats):
            if j >= i:
                out.loc[a, b] = fmt(corr.loc[a, b])
    return out


def table5(df: pd.DataFrame, judge: str) -> str:
    mat = cir_matrix(df, judge)
    if mat.empty or mat.shape[1] < 3:
        return "_Needs CIRs from at least 3 models._"
    out = correlation_upper(mat)
    save_csv(out, f"table5_{judge}")
    codes = {c: f"{c} ({CATEGORIES[c]})" for c in out.index}
    out.index = [codes[c] for c in out.index]
    out.columns = [CATEGORIES[c] for c in out.columns]
    return md_table(out, f"Category (n = {mat.shape[1]} models)")


# ---------------------------------------------------------------- entry point

def build_tables(judge: str = DEFAULT_JUDGE, out: Path = RESULTS_DIR / "tables.md") -> str:
    df = load_judgments()
    status = response_status_counts()
    parts = [
        "# InstrumentalEval replication: results",
        f"Default judge: `{judge}`. Rates are % of valid tasks (non-empty responses that were judged). "
        "Unparseable judge outputs count as no_convergence, as upstream does.",
        f"## Table 1: CIR (%) by category and IR (%) per model\n\n{table1(df, judge, status)}",
        f"## Table 2: average IR (%) by prior-task category (approximate mapping)\n\n{table2(df, judge)}",
        f"## Table 3: goal-nudging ablation\n\n{table3(df)}",
        f"## Table 4: judge reliability\n\n{table4(df)}",
        f"## Table 5: cross-category Pearson correlation of CIRs across models\n\n{table5(df, judge)}",
        "## Response status per run\n\n" + "\n".join(f"- `{k}`: {v}" for k, v in status.items()),
    ]
    text = "\n\n".join(parts) + "\n"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return text

