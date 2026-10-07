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
from .runs import JUDGMENTS_DIR, RESPONSES_DIR, load_latest, sha
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
    """One row per successfully judged response (status ok), across all registered judges and runs.
    A judgment of a response that has since been regenerated is stale and left out (it shows as pending)."""
    rows = []
    for path in sorted(JUDGMENTS_DIR.glob("*/*.jsonl")):
        judge = path.parent.name
        if judge not in JUDGES:  # a dropped judge's files stay on disk but are ignored
            continue
        responses = load_latest(RESPONSES_DIR / f"{path.stem}.jsonl")
        current = {tid: sha(r["test_llm_response"]) for tid, r in responses.items() if r["status"] == "ok"}
        for r in load_latest(path).values():
            if r["status"] == "ok" and r.get("response_sha") == current.get(r["task_id"]):
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


def family_averages(mat: pd.DataFrame) -> dict[str, pd.Series]:
    """Per-family mean of the per-model rates (columns of `mat`), as in the paper (e.g. RL avg total = 43.16).
    Adds a paper-models-only average when the family contains added models."""
    out = {}
    for fam in ("RLHF", "RL"):
        fam_models = [m for m in mat.columns if TEST_MODELS[m].family == fam]
        if fam_models:
            out[f"{fam} avg"] = mat[fam_models].mean(axis=1)
        paper_only = [m for m in fam_models if not TEST_MODELS[m].added]
        if paper_only and paper_only != fam_models:
            out[f"{fam} avg (paper models)"] = mat[paper_only].mean(axis=1)
    return out


def table1(df: pd.DataFrame, judge: str, status: dict) -> str:
    c = cir_counts(df, judge)
    if c.empty:
        return f"_No benchmark judgments from judge `{judge}` yet._"
    mat = cir_matrix(df, judge)
    models = list(mat.columns)
    out = mat.map(fmt)
    out.columns = [TEST_MODELS[m].label for m in models]
    for name, avg in family_averages(mat).items():
        out[name] = avg.map(fmt)

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

PRIOR_PATH = DATA_DIR / "task_categories.json"


def prior_task_types(path: Path | None = None) -> dict[str, str]:
    """task_id -> prior-task type key (see PRIOR_TYPES); empty if the mapping hasn't been built."""
    path = path or PRIOR_PATH
    if not path.exists():
        return {}
    return {tid: v["prior_task_type"] for tid, v in json.loads(path.read_text(encoding="utf-8")).items()}


def prior_counts(df: pd.DataFrame, judge: str, prior: dict[str, str]) -> pd.DataFrame:
    """Rows: (prior type, model) with k convergent out of n valid tasks (nudge, benchmark)."""
    sub = df[(df.judge == judge) & (df.variant == "nudge") & (df.task_set == "benchmark")].copy()
    sub["prior"] = sub.task_id.map(prior)
    return sub.groupby(["prior", "model"]).agg(k=("conv", "sum"), n=("conv", "size"))


def prior_matrix(c: pd.DataFrame) -> pd.DataFrame:
    """prior type x model matrix of IR (%), rows in PRIOR_TYPES order, models in registry order."""
    mat = c.k.div(c.n).mul(100).unstack()
    mat = mat[ordered_models(mat.columns)]
    return mat.loc[[p for p in PRIOR_TYPES if p in mat.index]]


def table2(df: pd.DataFrame, judge: str) -> str:
    prior = prior_task_types()
    if not prior:
        return "_`data/task_categories.json` not found; run `uv run ie classify-tasks`._"
    c = prior_counts(df, judge, prior)
    if c.empty:
        return f"_No benchmark judgments from judge `{judge}` yet._"
    # per-model rate within each prior-task type, then the mean across models (all, and per family)
    per_model = prior_matrix(c)
    avgs = pd.DataFrame({"Average Instrumental Rate (%)": per_model.mean(axis=1), **family_averages(per_model)})
    out = avgs.map(fmt)
    out["# tasks"] = pd.Series(prior).value_counts().reindex(per_model.index).fillna(0).astype(int)
    out["# models"] = per_model.notna().sum(axis=1)
    out.index = [PRIOR_TYPES.get(i, i) for i in out.index]
    save_csv(per_model, f"table2_{judge}_per_model")
    save_csv(avgs, f"table2_{judge}")
    return md_table(out, "Prior Task Category")


# ---------------------------------------------------------------- Table 3

def nudge_rates(df: pd.DataFrame, judge: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(without, with) nudge: (category + Total) x model CIR matrices, for the models with both variants
    judged by `judge`; both empty if there are none."""
    js = df[(df.task_set == "benchmark") & (df.judge == judge)]
    models = ordered_models(set(js[js.variant == "nonudge"].model) & set(js[js.variant == "nudge"].model))
    if not models:
        return pd.DataFrame(), pd.DataFrame()
    return cir_matrix(df, judge, "nonudge")[models], cir_matrix(df, judge, "nudge")[models]


def nudge_gaps(df: pd.DataFrame, judge: str) -> pd.DataFrame:
    """(category + Total) x model matrix of CIR with nudge − CIR without nudge, in percentage points.
    Only models with both variants judged by `judge`; empty if there are none."""
    without, with_ = nudge_rates(df, judge)
    return with_ - without


def table3(df: pd.DataFrame) -> str:
    sections = []
    for judge in sorted(df[df.task_set == "benchmark"].judge.unique()):
        without, with_ = nudge_rates(df, judge)
        if without.empty:
            continue
        gaps = with_ - without
        # Paper layout: per model, CIR without nudge, CIR with nudge (= Table 1), and the gap.
        out = pd.DataFrame({
            col: vals
            for m in without.columns
            for col, vals in [(f"{TEST_MODELS[m].label} Without", without[m].map(fmt)),
                              (f"{TEST_MODELS[m].label} With", with_[m].map(fmt)),
                              (f"{TEST_MODELS[m].label} Gap", gaps[m].map(
                                  lambda x: fmt(x) if math.isnan(x) else f"{x:+.2f}"))]
        })
        save_csv(out, f"table3_{judge}")
        sections.append(f"**Judge: `{judge}`.** Without / With = CIR (%) without and with the goal nudge (With is "
                        "Table 1); Gap = With − Without, in percentage points.\n\n"
                        + md_table(out, "Behavior Category"))
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
    neutral = _decisions(df, "neutral")
    # A judge with only neutral judgments still gets a row, so FPR can be read before the benchmark is judged.
    judges = [j for j in JUDGES if j in bench or j in neutral]
    if not judges:
        return "_No judgments yet._"
    bench_judges = [j for j in judges if j in bench]
    bench = {j: bench[j] for j in bench_judges}
    iar = pairwise(bench, agreement)
    kappa = pairwise(bench, cohen_kappa)
    humans = human_labels()

    rows = {}
    for j in judges:
        others = [o for o in bench_judges if o != j] if j in bench else []
        fp = neutral.get(j, {})
        hum = {i: d for i, d in bench.get(j, {}).items() if i in humans}
        rows[f"{j}" + (f" (for {JUDGES[j].paper_name})" if JUDGES[j].substitute else "")] = {
            "Average IAR": fmt(np.mean([iar[(j, o)][0] for o in others])) if others else "–",
            "Average Cohen's κ": fmt(np.mean([kappa[(j, o)][0] for o in others]), 3) if others else "–",
            "False Positive Rate": fmt(100 * sum(d == "convergence" for d in fp.values()) / len(fp)) if fp else "–",
            "# neutral items": len(fp),
            "Agreement with Fable 5.1": fmt(agreement(list(hum.values()), [humans[i] for i in hum])) if hum else "–",
            "# Fable-labelled items": len(hum),
        }
    out = pd.DataFrame(rows).T
    save_csv(out, "table4")
    if len(bench_judges) < 2:
        return md_table(out, "Judge Model")

    pair = pd.DataFrame(index=bench_judges, columns=bench_judges, dtype=object)
    for j1 in bench_judges:
        for j2 in bench_judges:
            pair.loc[j1, j2] = "100.00" if j1 == j2 else f"{fmt(iar[(j1, j2)][0])} (n={iar[(j1, j2)][1]})"
    save_csv(pair, "table4_pairwise_iar")
    return (md_table(out, "Judge Model") + "\n\nPairwise IAR (%) on shared benchmark responses:\n\n"
            + md_table(pair, "Judge"))


# ---------------------------------------------------------------- Table 5

def category_correlations(mat: pd.DataFrame) -> pd.DataFrame:
    """Pearson r between the category rows of a category x model CIR matrix (full square, floats)."""
    cats = [c for c in CATEGORIES if c in mat.index]
    return mat.loc[cats].T.astype(float).corr(method="pearson")


def correlation_upper(mat: pd.DataFrame) -> pd.DataFrame:
    """Pearson r between category rows of a category x model CIR matrix; upper triangle + diagonal."""
    corr = category_correlations(mat)
    cats = list(corr.index)
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
        "## Table 2: average IR (%) by prior-task category (approximate mapping)\n\n"
        "Each model's IR within a prior-task category, averaged over all models (as in the paper) and within each "
        f"family. Per-model rates are in Figure 2.\n\n{table2(df, judge)}",
        f"## Table 3: goal-nudging ablation (Figure 3)\n\n{table3(df)}",
        f"## Table 4: judge reliability\n\n{table4(df)}",
        f"## Table 5: cross-category Pearson correlation of CIRs across models (heat map: Figure 5)\n\n"
        f"{table5(df, judge)}",
        "## Response status per run\n\n" + "\n".join(f"- `{k}`: {v}" for k, v in status.items()),
    ]
    text = "\n\n".join(parts) + "\n"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return text

