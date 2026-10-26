"""Default-sampling repeats (Table 10, Figure 9; not in the paper; REPLICATION_NOTES.md, "Default-sampling repeats").

The Figure 8 models with each vendor's published sampling defaults (`models.SAMPLING_MODELS`) instead of upstream's
T = 0, ten repeats on the 15 Fable tasks, judged by gpt-4o with upstream's prompts and settings; gpt-4o and
deepseek-r1-0528 also on Figure 6's five prompt steps. All of it is ours. Inference resamples the 15 tasks, never
cells (the repeats of a task are one cluster); the spread across repeats is described, not tested. Read against the
stored T = 0 runs on the same tasks (Figure 8's light bars). Output: results/variability/{tables.md, tables/, figures/}.
"""

import math
import random
import statistics

import pandas as pd
from scipy.stats import spearmanr

from . import RESULTS_DIR
from .benchmark import FABLE_GOOD_TASKS
from .capability import capability_order
from .figures import FIGURE1_COLORS, GRID, INK, INK_2, PROMPT_STEPS, REASONING_ORDER, layout, plt, save, style_axes, tint
from .models import (DEFAULT_JUDGE, SAMPLING_ABLATION_MODELS, SAMPLING_MODELS, SAMPLING_REFERENCE, SAMPLING_REPEATS,
                     TEST_MODELS)
from .runs import JUDGMENTS_DIR, RESPONSES_DIR, load_latest, parse_run_id, sha, split_repeat
from .stats import cluster_bootstrap_ci, holm, sign_flip_test
from .tables import fmt, is_refusal, load_judgments, md_table

VAR_DIR = RESULTS_DIR / "variability"
STEPS = [v for _, v in PROMPT_STEPS]
# Pre-registered checks (notes, "Default-sampling repeats"): an arm whose repeats are byte-identical on most tasks
# was not sampled; an o-series arm whose median reasoning moved beyond these factors of the stored run's did not
# keep the stored effort.
MIN_DISTINCT_SHARE = 0.5
EFFORT_BAND = (2 / 3, 3 / 2)
ALPHA = 0.05


# ---------------------------------------------------------------- pure functions (tests/test_variability.py)

def repeat_summary(cells: dict[tuple[int, str], int]) -> dict:
    """cells: (repeat, task) -> 1 convergent / 0 not, valid responses only. The rate pooled over repeats with its
    by-task bootstrap CI, each repeat's IR (mean, SD, range) and how many tasks converge in every / some / no repeat."""
    by_task: dict[str, list[int]] = {}
    by_repeat: dict[int, list[int]] = {}
    for (k, t), c in cells.items():
        by_task.setdefault(t, []).append(c)
        by_repeat.setdefault(k, []).append(c)
    rate, lo, hi = cluster_bootstrap_ci(by_task)
    runs = [100 * sum(v) / len(v) for _, v in sorted(by_repeat.items())]
    return {"rate": rate, "lo": lo, "hi": hi, "repeats": len(runs), "run_rates": runs,
            "run_mean": statistics.mean(runs), "run_sd": statistics.stdev(runs) if len(runs) > 1 else math.nan,
            "run_min": min(runs), "run_max": max(runs),
            "always": sum(all(v) for v in by_task.values()), "never": sum(not any(v) for v in by_task.values()),
            "mixed": sum(any(v) and not all(v) for v in by_task.values())}


def step_contrast(a: dict[str, list[int]], b: dict[str, list[int]]) -> tuple[float, float, int]:
    """(Δ in pp, p, tasks) for b − a: the mean over shared tasks of each task's convergence rate across its repeats
    under b minus under a, with the two-sided sign-flip p that keeps whole tasks together (as in Table 6)."""
    tasks = sorted(set(a) & set(b))
    d = [sum(b[t]) / len(b[t]) - sum(a[t]) / len(a[t]) for t in tasks]
    return 100 * sum(d) / len(d), sign_flip_test(d), len(tasks)


def family_gap(cells: dict[str, dict[str, list[int]]], family: dict[str, str], b: int = 5000,
               seed: int = 0) -> tuple[float, float, float]:
    """(RL − RLHF, lo, hi) in pp: mean RL model rate minus mean RLHF model rate, each model's rate pooled over its
    repeats; 95% percentile CI from resampling tasks, one draw shared by every model."""
    tasks = sorted(set.intersection(*(set(v) for v in cells.values())))

    def gap(draw: list[str]) -> float:
        rates = {m: sum(sum(v[t]) for t in draw) / sum(len(v[t]) for t in draw) for m, v in cells.items()}
        fam = {f: [r for m, r in rates.items() if family[m] == f] for f in ("RL", "RLHF")}
        return 100 * (statistics.mean(fam["RL"]) - statistics.mean(fam["RLHF"]))

    rng = random.Random(seed)
    boot = sorted(gap(rng.choices(tasks, k=len(tasks))) for _ in range(b))
    return gap(tasks), boot[int(0.025 * b)], boot[int(0.975 * b) - 1]


# ---------------------------------------------------------------- loading

def load_repeats(judge: str = DEFAULT_JUDGE) -> pd.DataFrame:
    """One row per stored response of a SAMPLING_MODELS repeat: status, cap hit, provider, reasoning tokens, the
    response fingerprint, a refusal flag (tables.is_refusal) and conv when the judge's verdict is current (else None)."""
    rows = []
    for path in sorted(RESPONSES_DIR.glob("*__benchmark.jsonl")):
        model, variant, _ = parse_run_id(path.stem)
        step, repeat = split_repeat(variant)
        if model not in SAMPLING_MODELS or repeat is None:
            continue
        judged = load_latest(JUDGMENTS_DIR / judge / path.name)
        for r in load_latest(path).values():
            ok = r["status"] == "ok"
            j = judged.get(r["task_id"], {})
            current = ok and j.get("status") == "ok" and j.get("response_sha") == sha(r["test_llm_response"])
            rows.append({"model": model, "step": step, "repeat": repeat, "task_id": r["task_id"],
                         "status": r["status"], "length": r.get("finish_reason") == "length",
                         "provider": r.get("provider"), "reasoning_tokens": r.get("reasoning_tokens"),
                         "response_sha": sha(r["test_llm_response"]) if ok else None,
                         "refusal": ok and is_refusal(r["test_llm_response"], j.get("judge_decision", "") if current
                                                      else "", j.get("judge_reason", "") if current else ""),
                         "conv": (j["judge_decision"] == "convergence") if current else None})
    cols = ["model", "step", "repeat", "task_id", "status", "length", "provider", "reasoning_tokens", "response_sha",
            "refusal", "conv"]
    return pd.DataFrame(rows, columns=cols)


def load_reference(judge: str = DEFAULT_JUDGE) -> pd.DataFrame:
    """The stored T = 0 verdicts of the reference models on the 15 tasks, every prompt step that exists."""
    df = load_judgments()
    return df[(df.judge == judge) & (df.task_set == "benchmark") & df.model.isin(set(SAMPLING_REFERENCE.values()))
              & df.task_id.isin(FABLE_GOOD_TASKS) & df.variant.isin(STEPS)]


def reference_reasoning(model: str, step: str) -> float:
    """Median reasoning tokens of the stored run on the 15 tasks (NaN when it has none)."""
    recs = load_latest(RESPONSES_DIR / f"{model}__{step}__benchmark.jsonl").values()
    rt = [r["reasoning_tokens"] for r in recs
          if r["task_id"] in FABLE_GOOD_TASKS and r["status"] == "ok" and r.get("reasoning_tokens")]
    return statistics.median(rt) if rt else math.nan


def _cells(rep: pd.DataFrame, model: str, step: str) -> dict[tuple[int, str], int]:
    """The judged cells of an arm, empty unless all SAMPLING_REPEATS repeats were judged: OpenAI retired o1, o3-mini
    and o4-mini between the smoke test and the full run (2026-10-23), and their two smoke repeats on four tasks
    must not stand in for an arm (notes, "Default-sampling repeats", Results)."""
    g = rep[(rep.model == model) & (rep.step == step) & rep.conv.notna()]
    if g.repeat.nunique() < SAMPLING_REPEATS:
        return {}
    return {(int(r.repeat), r.task_id): int(bool(r.conv)) for r in g.itertuples()}


def _by_task(cells: dict[tuple[int, str], int]) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for (_, t), c in sorted(cells.items()):
        out.setdefault(t, []).append(c)
    return out


def _arms(rep: pd.DataFrame) -> list[tuple[str, str]]:
    order = list(SAMPLING_MODELS)
    return sorted({(r.model, r.step) for r in rep.itertuples()},
                  key=lambda a: (order.index(a[0]), STEPS.index(a[1])))


# ---------------------------------------------------------------- Table 10

def run_check(rep: pd.DataFrame) -> pd.DataFrame:
    """Table 10a: per arm, what came back, from whom, and the two pre-registered checks."""
    rows = []
    for model, step in _arms(rep):
        g = rep[(rep.model == model) & (rep.step == step)]
        ok = g[g.status == "ok"]
        multi = [s for _, s in ok.groupby("task_id").response_sha if len(s) > 1]
        distinct = sum(s.nunique() > 1 for s in multi) / len(multi) if multi else math.nan
        rt = ok.reasoning_tokens.dropna()
        med = float(rt.median()) if len(rt) else math.nan
        ref = reference_reasoning(SAMPLING_REFERENCE[model], step)
        flags = []
        if g[g.conv.notna()].repeat.nunique() < SAMPLING_REPEATS:
            flags.append(f"incomplete ({g[g.conv.notna()].repeat.nunique()}/{SAMPLING_REPEATS} repeats judged)")
        if not math.isnan(distinct) and distinct < MIN_DISTINCT_SHARE:
            flags.append("not sampled")
        if not SAMPLING_MODELS[model].send_temperature and not math.isnan(ref) and not (
                EFFORT_BAND[0] <= med / ref <= EFFORT_BAND[1]):
            flags.append("effort moved")
        rows.append({"model": model, "step": step, "repeats": g.repeat.nunique(), "ok": len(ok),
                     "empty": int((g.status == "empty").sum()), "error": int((g.status == "error").sum()),
                     "cap hits": int(g.length.sum()), "judged": int(g.conv.notna().sum()),
                     "providers": ", ".join(f"{p} {n}" for p, n in ok.provider.value_counts().items()),
                     "tasks with distinct repeats (%)": round(100 * distinct, 1),
                     "median reasoning tokens": med, "stored T=0 median": ref,
                     "refusals": int(g.refusal.sum()), "check": "; ".join(flags) or "ok"})
    return pd.DataFrame(rows)


def main_table(rep: pd.DataFrame, ref: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Table 10b: full prompt, per model; plus the family gap and the rank agreement with the stored T = 0 run."""
    rows, cells_by_model = [], {}
    for model in SAMPLING_MODELS:
        cells = _cells(rep, model, "nudge")
        if not cells:
            continue
        s = repeat_summary(cells)
        cells_by_model[model] = _by_task(cells)
        r = ref[(ref.model == SAMPLING_REFERENCE[model]) & (ref.variant == "nudge")]
        stored = 100 * r.conv.mean() if len(r) else math.nan
        rows.append({"model": model, "family": SAMPLING_MODELS[model].family, "stored T=0 IR (%)": stored,
                     "IR pooled (%)": s["rate"], "lo": s["lo"], "hi": s["hi"], "repeats": s["repeats"],
                     "repeat mean (%)": s["run_mean"], "repeat SD (pp)": s["run_sd"], "repeat min": s["run_min"],
                     "repeat max": s["run_max"], "stored within range": s["run_min"] <= stored <= s["run_max"],
                     "tasks always": s["always"], "tasks mixed": s["mixed"], "tasks never": s["never"]})
    t = pd.DataFrame(rows)
    extra = {}
    if len(t) > 2 and {"RL", "RLHF"} <= set(t.family):
        extra["gap"] = family_gap(cells_by_model, {m: SAMPLING_MODELS[m].family for m in cells_by_model})
        extra["rho"] = spearmanr(t["stored T=0 IR (%)"], t["IR pooled (%)"]).statistic
    return t, extra


def task_grid(rep: pd.DataFrame, ref: pd.DataFrame) -> pd.DataFrame:
    """Table 10c: per task and model, convergent repeats / judged repeats, the stored T = 0 verdict in brackets."""
    grid = {}
    for model in SAMPLING_MODELS:
        by_task = _by_task(_cells(rep, model, "nudge"))
        if not by_task:
            continue
        r = ref[(ref.model == SAMPLING_REFERENCE[model]) & (ref.variant == "nudge")].set_index("task_id").conv
        grid[model] = {t: f"{sum(v)}/{len(v)}" + (f" [{int(r[t])}]" if t in r.index else "")
                       for t, v in by_task.items()}
    return pd.DataFrame(grid).reindex(list(FABLE_GOOD_TASKS))


def ablation_tables(rep: pd.DataFrame, ref: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Table 10d: per model and step, the pooled IR, its spread and refusals; then the four adjacent-step contrasts
    per model, Holm-corrected over all eight."""
    rows, contrasts = [], []
    for model in SAMPLING_ABLATION_MODELS:
        by_step = {}
        for step in STEPS:
            cells = _cells(rep, model, step)
            if not cells:
                continue
            s = repeat_summary(cells)
            by_step[step] = _by_task(cells)
            g = rep[(rep.model == model) & (rep.step == step) & (rep.status == "ok")]
            r = ref[(ref.model == SAMPLING_REFERENCE[model]) & (ref.variant == step)]
            rows.append({"model": model, "step": step, "stored T=0 IR (%)": 100 * r.conv.mean() if len(r) else math.nan,
                         "IR pooled (%)": s["rate"], "lo": s["lo"], "hi": s["hi"], "repeat SD (pp)": s["run_sd"],
                         "refusals (%)": 100 * g.refusal.mean() if len(g) else math.nan})
        for a, b in zip(STEPS, STEPS[1:]):
            if a in by_step and b in by_step:
                d, p, n = step_contrast(by_step[a], by_step[b])
                contrasts.append({"model": model, "contrast": f"{b} − {a}", "Δ (pp)": d, "p": p, "tasks": n})
    c = pd.DataFrame(contrasts)
    if len(c):
        c["Holm p"] = holm(list(c.p))
        c["decision"] = ["changes IR" if q < ALPHA else "no change detected" for q in c["Holm p"]]
    return pd.DataFrame(rows), c


def _md(df: pd.DataFrame, digits: int = 1, index: bool = False) -> str:
    if not len(df):
        return "_no judged repeats yet_"
    shown = df.map(lambda v: fmt(v, digits) if isinstance(v, float) else v)
    return md_table(shown) if index else md_table(shown.set_index(shown.columns[0]), shown.columns[0])


def table10(judge: str = DEFAULT_JUDGE) -> str:
    rep, ref = load_repeats(judge), load_reference(judge)
    out_dir = VAR_DIR / "tables"
    out_dir.mkdir(parents=True, exist_ok=True)
    check = run_check(rep)
    main, extra = main_table(rep, ref)
    grid = task_grid(rep, ref)
    steps, contrasts = ablation_tables(rep, ref)
    for name, df in (("table10a_run_check", check), ("table10b_main", main), ("table10c_tasks", grid),
                     ("table10d_steps", steps), ("table10e_contrasts", contrasts)):
        df.to_csv(out_dir / f"{name}_{judge}.csv", encoding="utf-8", index=name == "table10c_tasks")
    gap = (f"RL − RLHF (mean of model rates, pooled over repeats): {extra['gap'][0]:+.1f} pp, 95% CI "
           f"{extra['gap'][1]:+.1f} to {extra['gap'][2]:+.1f} (tasks resampled; descriptive). Spearman ρ between "
           f"the stored T = 0 rates and the pooled rates over the {len(main)} models: {extra['rho']:.2f}."
           if extra else "")
    text = "\n\n".join([
        f"# Default-sampling repeats (Table 10, judge `{judge}`)",
        "Vendor sampling defaults (`models.SAMPLING_MODELS`), the 15 Fable tasks, one run per repeat. IR on valid "
        "answers; intervals: 95% bootstrap over tasks. `stored T=0` = the repo's single run at upstream's settings "
        "on the same tasks (Figure 8); for deepseek-r1-0528 that run is deepseek-r1, a different model.",
        "## 10a. Run check (pre-registered: tasks with distinct repeats ≥ 50 %; o-series reasoning within ×2/3–×3/2 "
        "of the stored run)", _md(check, 0),
        "## 10b. Full prompt (`nudge`), per model", _md(main), gap,
        "## 10c. Per task: convergent / judged repeats [stored T=0 verdict]",
        _md(grid, index=True),
        "## 10d. Prompt steps (Figure 6's cumulative steps)", _md(steps),
        "## 10e. Adjacent-step contrasts (mean per-task rate difference, sign-flip over tasks, Holm over all rows)",
        _md(contrasts, 3),
    ])
    (VAR_DIR / "tables.md").write_text(text + "\n", encoding="utf-8")
    return text


# ---------------------------------------------------------------- Figure 9

def figure9(judge: str = DEFAULT_JUDGE) -> list:
    """(a) Per model: the stored T = 0 IR on the 15 tasks (light) beside the default-sampling IR pooled over repeats
    (dark, 95% task-bootstrap CI), each repeat's IR as a dot. (b, c) The five prompt steps for gpt-4o and
    deepseek-r1-0528: one thin line per repeat, the pooled IR with its CI, the stored T = 0 run dashed."""
    rep, ref = load_repeats(judge), load_reference(judge)
    order = capability_order(REASONING_ORDER)  # Figure 8's order
    arms = sorted((m for m in SAMPLING_MODELS if _cells(rep, m, "nudge")),
                  key=lambda m: order.index(SAMPLING_REFERENCE[m]))
    if not arms:
        return []
    refs = [SAMPLING_REFERENCE[m] for m in arms]
    xs, _ = layout(refs)
    fig = plt.figure(figsize=(12, 10.6))
    grid = fig.add_gridspec(2, 2, height_ratios=[1.1, 1], hspace=0.32, wspace=0.07)
    ax = fig.add_subplot(grid[0, :])
    rng = random.Random(0)
    for m, base in zip(arms, refs):
        c = FIGURE1_COLORS[TEST_MODELS[base].family]
        stored = 100 * ref[(ref.model == base) & (ref.variant == "nudge")].conv.mean()
        s = repeat_summary(_cells(rep, m, "nudge"))
        x = xs[base]
        ax.bar(x - 0.2, stored, width=0.38, color=tint(c, 0.62), edgecolor=c, linewidth=1.2, zorder=2)
        ax.bar(x + 0.2, s["rate"], width=0.38, color=c, edgecolor=c, linewidth=1.2, zorder=2)
        ax.errorbar([x + 0.2], [s["rate"]], yerr=[[s["rate"] - s["lo"]], [s["hi"] - s["rate"]]], fmt="none",
                    ecolor=INK, elinewidth=1, capsize=0, zorder=3)
        ax.scatter([x + 0.2 + rng.uniform(-0.1, 0.1) for _ in s["run_rates"]], s["run_rates"], s=9, color="white",
                   edgecolor=INK, linewidth=0.6, zorder=4)
        # the pooled value sits above its interval, the stored one above its bar
        for xi, top, value in ((x - 0.2, stored, stored), (x + 0.2, max(s["hi"], s["run_max"]), s["rate"])):
            ax.text(xi, top + 1.2, f"{value:.1f}", ha="center", va="bottom", fontsize=7.5, color=INK, zorder=5)
    style_axes(ax, "IR (%)")
    ax.set_xticks([xs[b] for b in refs], [m.removesuffix("@default") for m in arms], rotation=30, ha="right",
                  fontsize=9)
    ax.set_xlim(-0.6, max(xs.values()) + 0.6)
    ax.set_title("(a) Instrumental Rate on the 15 Fable tasks: stored T = 0 run (light) and vendor-default sampling "
                 "pooled over repeats (dark; dots = single repeats)", loc="left", fontsize=10, color=INK,
                 fontweight="bold")

    first = None
    for col, m in enumerate(SAMPLING_ABLATION_MODELS):
        bx = fig.add_subplot(grid[1, col], sharey=first)
        first = first or bx
        base = SAMPLING_REFERENCE[m]
        c = FIGURE1_COLORS[TEST_MODELS[base].family]
        cells = {s: _cells(rep, m, s) for s in STEPS}
        for k in sorted({k for v in cells.values() for k, _ in v}):
            ys = [100 * statistics.mean(v for (kk, _), v in cells[s].items() if kk == k)
                  if any(kk == k for kk, _ in cells[s]) else math.nan for s in STEPS]
            bx.plot(range(len(STEPS)), ys, color=tint(c, 0.7), linewidth=0.8, zorder=2)
        have = [i for i, s in enumerate(STEPS) if cells[s]]
        sums = [repeat_summary(cells[STEPS[i]]) for i in have]
        bx.errorbar(have, [s["rate"] for s in sums], yerr=[[s["rate"] - s["lo"] for s in sums],
                                                           [s["hi"] - s["rate"] for s in sums]],
                    color=c, ecolor=c, linewidth=2, elinewidth=1.1, marker="o", markersize=6.5, zorder=4,
                    label=f"{m.removesuffix('@default')}, vendor defaults, pooled")
        r = ref[ref.model == base]
        stored = [(i, 100 * r[r.variant == s].conv.mean()) for i, s in enumerate(STEPS) if (r.variant == s).any()]
        bx.plot([i for i, _ in stored], [y for _, y in stored], color=INK_2, linewidth=1.2, linestyle=(0, (4, 2)),
                marker="s", markersize=5, markerfacecolor="white", zorder=3, label=f"{base}, stored T = 0")
        bx.plot([], [], color=tint(c, 0.7), linewidth=0.8, label="single repeats")
        style_axes(bx, "IR (%)" if col == 0 else None)
        bx.tick_params(labelleft=col == 0)
        bx.set_xticks(range(len(STEPS)), [s[0] for s in PROMPT_STEPS], fontsize=8.5, linespacing=1.15)
        bx.set_xlim(-0.4, len(STEPS) - 0.6)
        bx.set_title(f"({'bc'[col]}) System-prompt steps: {m.removesuffix('@default')}", loc="left", fontsize=10,
                     color=INK, fontweight="bold")
        # the corner each panel's data leaves empty (gpt-4o's stored line dips to 20 % at "+ 7 rules")
        bx.legend(loc="upper right" if col == 0 else "lower right", frameon=True, framealpha=0.95, edgecolor=GRID,
                  fontsize=8.5)
    return save(fig, VAR_DIR / "figures", f"figure9_{judge}")
