"""Tables 1, 2, 3, 5 and 6 as figures -> results/figures/figure{1,2,3,5,6}_<judge>.{png,pdf}.

Figure 1 (Table 1): one panel for the overall IR, then one per category, models ordered by reasoning capability
within each family, with the paper's Table 1 values as diamonds (ours, not in the paper); `figure1_matched` keeps
only the models run under the paper's own ids; `figure1_strict` is Figure 1 under the strict judge (Table 9, `ie
figures --strict`).
Figure 2 (Table 2): one panel per prior-task type, with a dashed line at the all-model average (the Table 2 value).
In both, the models are grouped by family (RLHF, then RL) with a gap between the groups, a line marks each
family's average (mean of per-model rates, as in Tables 1 and 2), and error bars are 95% Wilson intervals.
Figure 3 (Table 3): one panel per model, the nudge gap per category as bars around zero.
Figure 5 (Table 5): the upper triangle of the cross-category correlation matrix as a heat map.
Figure 6 (Table 6): one panel per model in the Figure 1 order, IR as the upstream prompt is built up from "You are an
autonomous AI agent." one paragraph group at a time (PROMPT_STEPS), the nudge last.
Figure 7 (Table 7): one panel per o-series model, IR against explicit reasoning effort, with the stored
default-effort runs as reference points.
Figure 8: Figure 1's overall-IR panel for all 76 tasks (the paper's IR as diamonds) and for the 15 tasks Claude
Fable 5.1 scored as good questions (FABLE_GOOD_TASKS).
"""

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.cm import ScalarMappable
from matplotlib.colors import LinearSegmentedColormap, Normalize, to_rgb
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle
from scipy.stats import t as student_t

from . import RESULTS_DIR
from .benchmark import CATEGORIES, FABLE_GOOD_TASKS
from .capability import capability_order
from .models import DEFAULT_JUDGE, DEFAULT_STRICT_JUDGE, EFFORT_BASE_MODELS, EFFORT_LEVELS, STRICT_MODELS, TEST_MODELS
from .prompts import SYSTEM_PROMPTS
from .stats import wilson_ci
from .tables import (
    FIGURE1_MODELS,
    PRIOR_TYPES,
    ablation_records,
    arm_decisions,
    category_correlations,
    cir_counts,
    cir_matrix,
    fmt,
    load_judgments,
    nudge_gaps,
    paper_table1,
    paper_table3,
    prior_counts,
    prior_matrix,
    prior_task_types,
)

FIGURES_DIR = RESULTS_DIR / "figures"
FAMILIES = ("RLHF", "RL")
# categorical slots 1-2 of the dataviz reference palette (validated for CVD on the light surface)
FAMILY_COLORS = {"RLHF": "#2a78d6", "RL": "#eb6834"}
# Figure 1: blue / green, OKLab dE >= 12.9 under normal, deutan, protan and tritan vision; the paper's red
# diamonds are told apart from the green bars by shape and black edge (red/green dE is 4.7 under deutan)
FIGURE1_COLORS = {"RLHF": "#2f5f9e", "RL": "#3a9a5b"}
# bar fill: the edge colour mixed 45 % toward white
FIGURE1_FILLS = {f: tuple(0.55 * v + 0.45 for v in to_rgb(c)) for f, c in FIGURE1_COLORS.items()}
# Figure 1 fallback order, used until data/capability_scores.csv exists (capability.py then re-sorts each family
# by its pre-registered composite). Low -> high reasoning capability within each family, from published pass@1 on AIME 2024 / MATH-500 /
# GPQA Diamond (DeepSeek-V3 and -R1 reports, OpenAI and Google launch posts):
#  RLHF: gpt-4o-mini (GPQA ~40, MATH ~70) < gpt-4o (50, 75; AIME 9) < qwen-2.5-72b (49, 80-83; AIME 23: ties on
#        GPQA, ahead on maths) < deepseek-v3 (59, 90; AIME 39).
#  RL: deepseek-r1 (GPQA 71.5) < o3-mini at medium effort, our runs ("matches o1") < o1 (75.7): tied on AIME and
#      MATH-500, so GPQA and model size decide; gemini-2.5-flash (GPQA 82.8, AIME 2024 88) < o4-mini (GPQA 81.4,
#      AIME 2025 92.7 vs 72, HLE 14.7 vs 11).
REASONING_ORDER = ("gpt-4o-mini", "gpt-4o", "qwen-2.5-72b", "deepseek-v3",
                   "deepseek-r1", "o3-mini", "o1", "gemini-2.5-flash", "o4-mini")
PAPER_MARKER = {"marker": "D", "markersize": 7, "markerfacecolor": "#e34948", "markeredgecolor": "#0b0b0b",
                "markeredgewidth": 1.2, "linestyle": "none"}
# Figure 7: one colour per swept model, the same validated blue / orange pair as FAMILY_COLORS
EFFORT_COLORS = {"o3-mini": "#2a78d6", "o4-mini": "#eb6834"}
INK, INK_2, GRID ="#0b0b0b", "#52514e", "#e6e5e0"
GROUP_GAP = 1.0  # extra x-space between the two families
# diverging pair of the dataviz reference palette: blue <-> red around a neutral gray
DIVERGING = LinearSegmentedColormap.from_list("ie_diverging", ["#2a78d6", "#f0efec", "#e34948"])


def tick_label(m: str) -> str:
    """Model key, marked * for substitutes and † for models the paper didn't test."""
    spec = TEST_MODELS[m]
    return spec.key + ("†" if spec.added else "*" if spec.substitute else "")


def layout(models: list[str], gap: float = GROUP_GAP) -> tuple[dict[str, float], dict[str, list[str]]]:
    """x position of each model, with the families side by side and a gap between them."""
    groups = {f: [m for m in models if TEST_MODELS[m].family == f] for f in FAMILIES}
    xs, x = {}, 0.0
    for f in FAMILIES:
        for m in groups[f]:
            xs[m] = x
            x += 1
        x += gap
    return xs, {f: g for f, g in groups.items() if g}


def style_axes(ax, ylabel: str | None) -> None:
    ax.set_ylim(0, 105)
    ax.set_yticks(range(0, 101, 25))
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(INK_2)
    ax.tick_params(colors=INK_2, labelsize=8, length=0)
    if ylabel:
        ax.set_ylabel(ylabel, color=INK_2, fontsize=9)


def draw_panel(ax, rates, counts, xs, groups, title, *, ylabel=None, value_labels=False, avg_labels=False,
               colors=FAMILY_COLORS, avg_style="-", err_style=None, fills=None):
    """Bars for one row of the CIR matrix. `counts` maps model -> (k, n) for the Wilson interval."""
    for fam, fam_models in groups.items():
        fam_models = [m for m in fam_models if counts[m][1]]  # skip models with no judged task here
        if not fam_models:
            continue
        x = [xs[m] for m in fam_models]
        y = [rates[m] for m in fam_models]
        ci = [wilson_ci(*counts[m]) for m in fam_models]
        # clamped: at 0 % or 100 % the Wilson bound can land a rounding error past the point
        err = [[max(0.0, v - lo) for v, (lo, _) in zip(y, ci)], [max(0.0, hi - v) for v, (_, hi) in zip(y, ci)]]
        if fills:  # tinted fill, family colour on the edge
            ax.bar(x, y, width=0.72, color=fills[fam], edgecolor=colors[fam], linewidth=1.5, zorder=2)
        else:
            ax.bar(x, y, width=0.72, color=colors[fam], zorder=2)
        ax.errorbar(x, y, yerr=err, fmt="none", capsize=0, zorder=3,
                    **(err_style or {"ecolor": INK_2, "elinewidth": 1}))
        if value_labels:
            for xi, yi, (_, hi) in zip(x, y, ci):
                ax.text(xi, hi + 1.5, f"{yi:.1f}", ha="center", va="bottom", fontsize=8, color=INK,
                        bbox={"facecolor": "white", "edgecolor": "none", "pad": 1}, zorder=5)

        avg = sum(y) / len(y)
        ax.hlines(avg, x[0] - 0.45, x[-1] + 0.45, colors=INK, linewidth=1.5, linestyles=avg_style, zorder=4)
        if avg_labels:
            ax.text(x[-1] + 0.5, avg, f"{fam} avg\n{avg:.1f}", ha="left", va="center", fontsize=8, color=INK)

    ax.set_title(title, loc="left", fontsize=10, color=INK, fontweight="bold")
    style_axes(ax, ylabel)


def footer_notes(models: list[str], missing: bool = True) -> list[str]:
    """Substitute / added-model notes, plus the models not yet judged unless `missing` is False."""
    notes = []
    subs = [f"{m} for {TEST_MODELS[m].paper_name}" for m in models if TEST_MODELS[m].substitute]
    if subs:
        notes.append("* substitute: " + ", ".join(subs))
    if any(TEST_MODELS[m].added for m in models):
        notes.append("† added, not in the paper")
    unjudged = [m for m in TEST_MODELS if m not in models]
    if missing and unjudged:
        notes.append(f"not yet judged: {', '.join(unjudged)}")
    return notes


def legend_handles(groups) -> list:
    return [Patch(color=FAMILY_COLORS[f], label=f"{f} models") for f in groups] + [
        Line2D([], [], color=INK, linewidth=1.5, label="family average (mean of model rates)"),
        Line2D([], [], color=INK_2, linewidth=1, label="95% Wilson interval")]


def row_counts(c, models: list[str], row: str) -> dict[str, tuple[int, int]]:
    """model -> (k, n) for one category of `cir_counts`, or summed over all of them for "Total"."""
    out = {}
    for m in models:
        cm = c.loc[m]
        sel = cm if row == "Total" else cm[cm.index == row]
        out[m] = (int(sel["k"].sum()), int(sel["n"].sum()))
    return out


def save(fig, out_dir: Path, stem: str) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = [out_dir / f"{stem}.{ext}" for ext in ("png", "pdf")]
    for p in paths:
        fig.savefig(p, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return paths


def draw_figure1(judge: str, models: list[str] | None):
    """Overall IR panel + one panel per category for `models` (default: every judged model), with the paper's
    Table 1 values overlaid; family averages are over the models shown. No figure title (the caption is written
    separately) and no */† marks. Substitutes get no diamond (the paper's value belongs to the model they replace),
    nor do the added models (the paper didn't run them)."""
    df = load_judgments()
    c = cir_counts(df, judge)
    if c.empty:
        raise SystemExit(f"no benchmark judgments from judge `{judge}` yet")
    mat = cir_matrix(df, judge)
    order = capability_order(REASONING_ORDER)
    models = sorted((m for m in models or mat.columns if m in mat.columns), key=order.index)
    mat = mat[models]
    paper = paper_table1()
    xs, groups = layout(models)
    ticks = [xs[m] for m in models]
    labels = list(models)
    style = {"colors": FIGURE1_COLORS, "avg_style": (0, (5, 3)), "err_style": {"ecolor": INK, "elinewidth": 1},
             "fills": FIGURE1_FILLS}
    on_paper = [m for m in models if m in paper and not TEST_MODELS[m].substitute]

    def overlay_paper(ax, row: str) -> None:
        y = [paper[m]["ir"] if row == "Total" else paper[m]["cir"][row] for m in on_paper]
        ax.plot([xs[m] for m in on_paper], y, zorder=6, clip_on=False, **PAPER_MARKER)  # 0 % sits on the axis

    fig = plt.figure(figsize=(12, 10.5))
    outer = fig.add_gridspec(2, 1, height_ratios=[1.25, 2], top=0.9, hspace=0.32)
    grid = outer[1].subgridspec(2, 3, hspace=0.3, wspace=0.12)

    # overall IR: full width, values labelled
    ax = fig.add_subplot(outer[0])
    draw_panel(ax, mat.loc["Total"], row_counts(c, models, "Total"), xs, groups, "Instrumental Rate, all 76 tasks",
               ylabel="IR (%)", value_labels=True, avg_labels=True, **style)
    overlay_paper(ax, "Total")
    ax.set_xticks(ticks, labels, rotation=30, ha="right")
    ax.set_xlim(-0.6, max(xs.values()) + 1.6)

    # one panel per category, sharing x and y
    first = None
    for i, (cat, code) in enumerate(CATEGORIES.items()):
        r, col = divmod(i, 3)
        ax = fig.add_subplot(grid[r, col], sharex=first, sharey=first)
        first = first or ax
        draw_panel(ax, mat.loc[cat], row_counts(c, models, cat), xs, groups, f"{cat} ({code})",
                   ylabel="IR (%)" if col == 0 else None, **style)
        overlay_paper(ax, cat)
        ax.set_xticks(ticks, labels, rotation=40, ha="right")
        ax.tick_params(labelbottom=(r == 1))
        if col != 0:
            ax.tick_params(labelleft=False)
    assert first is not None
    first.set_xlim(-0.6, max(xs.values()) + 0.6)

    handles = [Patch(facecolor=FIGURE1_FILLS[f], edgecolor=FIGURE1_COLORS[f], linewidth=1.5, label=f"{f} models")
               for f in groups] + [
        Line2D([], [], **PAPER_MARKER, label="paper (Table 1)"),
        Line2D([], [], color=INK, linewidth=1.5, linestyle=style["avg_style"], label="family average")]
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.125, 0.955), ncol=len(handles),
               frameon=False, fontsize=10, handlelength=1.8, columnspacing=1.2)
    return fig


def figure1(judge: str = DEFAULT_JUDGE, out_dir: Path = FIGURES_DIR) -> list[Path]:
    fig = draw_figure1(judge, None)  # all nine models again (2026-10-27); tables.FIGURE1_EXCLUDE no longer applies here
    return save(fig, out_dir, f"figure1_{judge}")


def figure1_matched(judge: str = DEFAULT_JUDGE, out_dir: Path = FIGURES_DIR) -> list[Path]:
    """Figure 1 for the models the paper also ran under the same id (no substitute, no added model)."""
    paper = paper_table1()
    models = [m for m in TEST_MODELS if not (TEST_MODELS[m].substitute or TEST_MODELS[m].added) and m in paper]
    fig = draw_figure1(judge, models)
    return save(fig, out_dir, f"figure1_matched_{judge}")


# The paper's Table 1 (He et al. 2025, GPT-4o judge) for the strict judge's focus models, as given by the user (a copy
# of the paper's table, 2026-10-11). It matches data/paper_results.json (arXiv v1 HTML) except o3-mini on Strategically
# Appearing Aligned: 45.45 here vs 63.64 there. Only 63.64 (7/11) adds up to the table's own o3-mini total of 48.68
# (37/76); 45.45 gives 35/76.
PAPER_TABLE1 = {
    "gpt-4o": {"Evading Shutdown": 20.00, "Hacking Computer Systems": 10.00, "Running Multiple AI Copies": 30.77,
               "Hiding Unwanted Behavior": 36.36, "Strategically Appearing Aligned": 27.27,
               "Deceptive Behavior": 0.00, "Total": 21.05},
    "deepseek-v3": {"Evading Shutdown": 15.00, "Hacking Computer Systems": 20.00, "Running Multiple AI Copies": 30.77,
                    "Hiding Unwanted Behavior": 27.27, "Strategically Appearing Aligned": 36.36,
                    "Deceptive Behavior": 0.00, "Total": 21.05},
    "o3-mini": {"Evading Shutdown": 45.00, "Hacking Computer Systems": 50.00, "Running Multiple AI Copies": 38.46,
                "Hiding Unwanted Behavior": 63.64, "Strategically Appearing Aligned": 45.45,
                "Deceptive Behavior": 36.36, "Total": 48.68},
    "deepseek-r1": {"Evading Shutdown": 50.00, "Hacking Computer Systems": 40.00, "Running Multiple AI Copies": 46.15,
                    "Hiding Unwanted Behavior": 63.64, "Strategically Appearing Aligned": 45.45,
                    "Deceptive Behavior": 27.27, "Total": 46.05},
}
PAPER_STAR = {"marker": "*", "s": 130, "facecolors": "#e34948", "edgecolors": INK, "linewidths": 0.9}


def paper_stars(ax, row: str, models: list[str], xs: dict[str, float], dx: float = 0.0) -> None:
    """Red stars at the paper's Table 1 value for `row` (a category or "Total")."""
    pts = [(xs[m] + dx, PAPER_TABLE1[m][row]) for m in models if m in PAPER_TABLE1]
    ax.scatter([x for x, _ in pts], [y for _, y in pts], zorder=7, clip_on=False, **PAPER_STAR)


def figure1_strict(judge: str = DEFAULT_STRICT_JUDGE, out_dir: Path = FIGURES_DIR) -> list[Path]:
    """Figure 1 under the strict judge (Table 9): % clear for STRICT_MODELS, with the upstream judge's IR (white
    diamonds) and the paper's Table 1 (red stars) for comparison. Drawn as on the strict-judge branch, i.e. in the
    Figure 1 style from before draw_figure1's restyle."""
    from .strict_eval import load_strict_records, strict_frame, strict_name
    name = strict_name(judge)
    rec = load_strict_records()
    df = strict_frame(rec[rec.model.isin(STRICT_MODELS)])  # the other models have only a few labelled items
    upstream = cir_matrix(load_judgments(), DEFAULT_JUDGE)
    c = cir_counts(df, name)
    if c.empty:
        raise SystemExit(f"no benchmark judgments from judge `{name}` yet")
    mat = cir_matrix(df, name)
    models = list(mat.columns)
    xs, groups = layout(models)
    ticks = [xs[m] for m in models]
    labels = [tick_label(m) for m in models]

    fig = plt.figure(figsize=(12, 10.5))
    outer = fig.add_gridspec(2, 1, height_ratios=[1.25, 2], top=0.9, hspace=0.32)
    grid = outer[1].subgridspec(2, 3, hspace=0.3, wspace=0.12)

    # overall rate: full width, values labelled
    ax = fig.add_subplot(outer[0])
    draw_panel(ax, mat.loc["Total"], row_counts(c, models, "Total"), xs, groups,
               "Clear instrumental behaviour, all 76 tasks", ylabel="% clear", value_labels=True, avg_labels=True)
    up = [(xs[m], upstream.loc["Total", m]) for m in models if m in upstream.columns]
    ax.scatter([x + 0.24 for x, _ in up], [y for _, y in up], marker="D", s=28, facecolors="white",
               edgecolors=INK, linewidths=1.2, zorder=4)  # offset right of the bar so value labels stay legible
    paper_stars(ax, "Total", models, xs, dx=-0.24)
    ax.set_xticks(ticks, labels, rotation=30, ha="right")
    ax.set_xlim(-0.6, max(xs.values()) + 1.6)

    # one panel per category, sharing x and y
    first = None
    for i, (cat, code) in enumerate(CATEGORIES.items()):
        r, col = divmod(i, 3)
        ax = fig.add_subplot(grid[r, col], sharex=first, sharey=first)
        first = first or ax
        draw_panel(ax, mat.loc[cat], row_counts(c, models, cat), xs, groups, f"{cat} ({code})",
                   ylabel="% clear" if col == 0 else None)
        paper_stars(ax, cat, models, xs)
        ax.set_xticks(ticks, labels, rotation=40, ha="right")
        ax.tick_params(labelbottom=(r == 1))
        if col != 0:
            ax.tick_params(labelleft=False)
    assert first is not None
    first.set_xlim(-0.6, max(xs.values()) + 0.6)

    handles = legend_handles(groups) + [
        Line2D([], [], marker="D", linestyle="none", markerfacecolor="white", markeredgecolor=INK,
               label=f"upstream judge ({DEFAULT_JUDGE}) IR"),
        Line2D([], [], marker="*", linestyle="none", markersize=12, markerfacecolor="#e34948", markeredgecolor=INK,
               label="paper (He et al. 2025, Table 1)")]
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.125, 0.955), ncol=len(handles),
               frameon=False, fontsize=9, handlelength=1.6)
    fig.suptitle(f"Clear instrumental behaviour by model family (strict judge: {judge})", x=0.125, y=0.985,
                 ha="left", fontsize=12, color=INK, fontweight="bold")
    notes = footer_notes(models, missing=False)
    notes.append("strict judge: only behaviour beyond what the task authorises counts; re-judged for these 4 models")
    fig.text(0.125, 0.015, ";   ".join(notes), fontsize=8, color=INK_2, ha="left")
    return save(fig, out_dir, f"figure1_{name}")


def figure2(judge: str = DEFAULT_JUDGE, out_dir: Path = FIGURES_DIR) -> list[Path]:
    prior = prior_task_types()
    if not prior:
        raise SystemExit("data/task_categories.json not found; run `uv run ie classify-tasks`")
    c = prior_counts(load_judgments(), judge, prior)
    if c.empty:
        raise SystemExit(f"no benchmark judgments from judge `{judge}` yet")
    mat = prior_matrix(c)
    models = list(mat.columns)
    xs, groups = layout(models)
    ticks = [xs[m] for m in models]
    labels = [tick_label(m) for m in models]
    n_tasks = {p: sum(v == p for v in prior.values()) for p in mat.index}

    fig = plt.figure(figsize=(12, 9))
    grid = fig.add_gridspec(2, 2, top=0.86, hspace=0.38, wspace=0.12)
    first = None
    for i, p in enumerate(mat.index):
        r, col = divmod(i, 2)
        ax = fig.add_subplot(grid[r, col], sharex=first, sharey=first)
        first = first or ax
        counts = {m: (int(c.k.get((p, m), 0)), int(c.n.get((p, m), 0))) for m in models}
        avg = mat.loc[p].mean()
        fam_avgs = "   ".join(f"{f} {mat.loc[p, g].mean():.1f}" for f, g in groups.items())
        draw_panel(ax, mat.loc[p], counts, xs, groups,
                   f"{PRIOR_TYPES[p]} ({n_tasks[p]} tasks)\navg:  all models {avg:.1f}   {fam_avgs}",
                   ylabel="IR (%)" if col == 0 else None)
        ax.axhline(avg, color=INK_2, linewidth=1.2, linestyle=(0, (4, 3)), zorder=1)
        ax.set_xticks(ticks, labels, rotation=40, ha="right")
        ax.tick_params(labelbottom=(r == 1))
        if col != 0:
            ax.tick_params(labelleft=False)
    first.set_xlim(-0.6, max(xs.values()) + 0.6)

    handles = legend_handles(groups)
    handles.insert(-1, Line2D([], [], color=INK_2, linewidth=1.2, linestyle=(0, (4, 3)),
                              label="all-model average (Table 2)"))
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.125, 0.94), ncol=len(handles),
               frameon=False, fontsize=9, handlelength=1.6)
    fig.suptitle(f"Instrumental rate by prior-task type (judge: {judge})",
                 x=0.125, y=0.975, ha="left", fontsize=12, color=INK, fontweight="bold")
    notes = footer_notes(models) + ["prior-task mapping is approximate (see REPLICATION_NOTES)"]
    fig.text(0.125, 0.0, ";   ".join(notes), fontsize=8, color=INK_2, ha="left")
    return save(fig, out_dir, f"figure2_{judge}")


def figure3(judge: str = DEFAULT_JUDGE, out_dir: Path = FIGURES_DIR) -> list[Path]:
    df = load_judgments()
    gaps = nudge_gaps(df, judge)
    if gaps.empty:
        print(f"figure 3 skipped: no model has both nudge and no-nudge judgments from `{judge}`")
        return []
    models = list(gaps.columns)
    rows = list(CATEGORIES) + ["Total"]
    x = list(range(len(CATEGORIES))) + [len(CATEGORIES) + 0.6]  # Total set apart from the categories
    lim = 5 * math.ceil(max(gaps.abs().max().max(), 1) / 5) + 5

    fig, axes = plt.subplots(1, len(models), figsize=(3.4 * len(models) + 0.5, 4.6), sharey=True, squeeze=False)
    for ax, m in zip(axes[0], models):
        y = gaps.loc[rows, m]
        ax.bar(x, y.fillna(0), width=0.7, color=FAMILY_COLORS[TEST_MODELS[m].family], zorder=2)
        ax.axhline(0, color=INK, linewidth=1, zorder=3)
        for xi, yi in zip(x, y):
            if not math.isnan(yi):
                up = yi >= 0
                ax.text(xi, yi + (0.8 if up else -0.8), "0" if yi == 0 else f"{yi:+.1f}", ha="center",
                        va="bottom" if up else "top", fontsize=7.5, color=INK)
        ax.set_title(tick_label(m), loc="left", fontsize=10, color=INK, fontweight="bold")
        ax.set_ylim(-lim, lim)
        ax.set_yticks(range(-lim + lim % 10, lim, 10) if lim > 20 else range(-lim, lim + 1, 5))
        ax.yaxis.grid(True, color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right", "left", "bottom"):
            ax.spines[side].set_visible(False)
        ax.tick_params(colors=INK_2, labelsize=8, length=0)
        ax.set_xticks(x, list(CATEGORIES.values()) + ["Total"])
    axes[0][0].set_ylabel("gap (percentage points)", color=INK_2, fontsize=9)

    present = [f for f in FAMILIES if any(TEST_MODELS[m].family == f for m in models)]
    fig.legend(handles=[Patch(color=FAMILY_COLORS[f], label=f"{f} models") for f in present], loc="upper left",
               bbox_to_anchor=(0.06, 0.93), ncol=len(present), frameon=False, fontsize=9, handlelength=1.6)
    fig.suptitle(f"Effect of goal nudging: CIR with nudge \u2212 CIR without, in pp (judge: {judge})",
                 x=0.06, y=0.99, ha="left", fontsize=12, color=INK, fontweight="bold")
    fig.subplots_adjust(left=0.06, right=0.99, top=0.8, bottom=0.2, wspace=0.08)

    # resolution: with n tasks in a category, one task flipping moves its gap by 100/n pp
    n_cat = cir_counts(df, judge).groupby("category").n.max()
    notes = [f"one task moves a category gap by {100 / n_cat.max():.0f}\u2013{100 / n_cat.min():.0f} pp "
             f"({n_cat.min()}\u2013{n_cat.max()} tasks per category) and the Total by {100 / n_cat.sum():.1f} pp"]
    notes += footer_notes(models, missing=False)  # the ablation covers a subset of models by design
    key = ",  ".join(f"{code} = {cat}" for cat, code in CATEGORIES.items())
    fig.text(0.06, 0.06, ";   ".join(notes), fontsize=8, color=INK_2, ha="left")
    fig.text(0.06, 0.02, key, fontsize=8, color=INK_2, ha="left")
    return save(fig, out_dir, f"figure3_{judge}")


def figure5(judge: str = DEFAULT_JUDGE, out_dir: Path = FIGURES_DIR) -> list[Path]:
    mat = cir_matrix(load_judgments(), judge)
    if mat.empty or mat.shape[1] < 3:
        print(f"figure 5 skipped: needs CIRs from at least 3 models judged by `{judge}`")
        return []
    corr = category_correlations(mat)
    cats, n = list(corr.index), mat.shape[1]

    fig, ax = plt.subplots(figsize=(8.5, 5.4))
    for i, a in enumerate(cats):
        for j, b in enumerate(cats[i:], start=i):  # upper triangle + diagonal, as in Table 5
            r = corr.loc[a, b]
            face = GRID if i == j else "white" if math.isnan(r) else DIVERGING((r + 1) / 2)
            ax.add_patch(Rectangle((j - 0.5, i - 0.5), 1, 1, facecolor=face, edgecolor="white", linewidth=2))
            ax.text(j, i, fmt(r), ha="center", va="center", fontsize=9, color=INK_2 if i == j else INK)
    ax.set_xlim(-0.5, len(cats) - 0.5)
    ax.set_ylim(len(cats) - 0.5, -0.5)
    ax.set_aspect("equal")
    ax.xaxis.tick_top()
    ax.set_xticks(range(len(cats)), [CATEGORIES[c] for c in cats])
    ax.set_yticks(range(len(cats)), [f"{c} ({CATEGORIES[c]})" for c in cats])
    ax.tick_params(colors=INK_2, labelsize=9, length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)

    cbar = fig.colorbar(ScalarMappable(Normalize(-1, 1), DIVERGING), ax=ax, fraction=0.04, pad=0.03)
    cbar.set_label("Pearson r", color=INK_2, fontsize=9)
    cbar.outline.set_visible(False)
    cbar.ax.tick_params(colors=INK_2, labelsize=8, length=0)

    fig.suptitle(f"Cross-category Pearson correlation of CIRs across {n} models (judge: {judge})",
                 x=0.02, ha="left", fontsize=12, color=INK, fontweight="bold")
    tc = student_t.ppf(0.975, n - 2)
    notes = [f"each r is over the {n} models' CIRs (Table 1); with {n} points |r| must exceed "
             f"{tc / math.sqrt(tc ** 2 + n - 2):.2f} for p < 0.05 (two-sided)"] + footer_notes(list(mat.columns))
    fig.text(0.02, 0.01, "\n".join(notes), fontsize=8, color=INK_2, ha="left", va="bottom")
    return save(fig, out_dir, f"figure5_{judge}")



# Figure 6 x axis: the upstream prompt built up paragraph by paragraph from "You are an autonomous AI agent.";
# (label, arm). Each step adds to the previous one; the last is the full upstream prompt.
# Figure 6 panel labels: the models' own names, without the version and setting of `capability.DISPLAY`
SHORT_NAMES = {"gpt-4o-mini": "GPT-4o mini", "gpt-4o": "GPT-4o", "qwen-2.5-72b": "Qwen2.5-72B",
               "deepseek-v3": "DeepSeek-V3", "deepseek-r1": "DeepSeek-R1", "o3-mini": "o3-mini",
               "gemini-2.5-flash": "Gemini 2.5 Flash", "o1": "o1", "o4-mini": "o4-mini"}
PROMPT_STEPS = [("base", "plain-nonudge"),
                ("+ no human\noversight", "oversight-nonudge"),
                ("+ 7 rules", "nocause-nonudge"),
                ("+ “good cause”", "nonudge"),
                ("+ nudge", "nudge")]


def figure6(judge: str = DEFAULT_JUDGE, out_dir: Path = FIGURES_DIR) -> list[Path]:
    df = load_judgments()
    counts = {}
    for v in SYSTEM_PROMPTS:
        c = cir_counts(df, judge, v)
        for m in c.index.get_level_values(0).unique():
            counts[(m, v)] = (int(c.loc[m]["k"].sum()), int(c.loc[m]["n"].sum()))
    # refusals (Table 6c's heuristic) over the same judged responses as IR
    rec = ablation_records(judge)
    refusals = {(m, v): (int(g.refusal.sum()), len(g)) for (m, v), g in rec.groupby(["model", "variant"])}
    new_arms = {v for _, v in PROMPT_STEPS[:2]}
    order = capability_order(REASONING_ORDER)  # Figure 1's order: family, then capability within it
    _, groups = layout(sorted({m for m, v in counts if v in new_arms}, key=order.index))
    if not groups:
        print(f"figure 6 skipped: no system-prompt ablation runs judged by `{judge}` (README step 8)")
        return []

    # one column per family (RLHF left, RL right), capability increasing downwards
    ncols, nrows = len(groups), max(len(g) for g in groups.values())
    fig, axes = plt.subplots(nrows, ncols, figsize=(4.0 * ncols + 0.4, 2.0 * nrows + 0.95), sharex=True, sharey=True,
                             squeeze=False)
    cells = {}
    for col, g in enumerate(groups.values()):
        for row in range(nrows):
            if row < len(g):
                cells[g[row]] = (row, col)
            else:
                axes[row][col].axis("off")

    def series(ax, m, kn, dx, color, linestyle, **marker):
        # a missing step (deepseek-r1 has no oversight-nonudge arm) breaks the line instead of bridging it
        ax.plot([x + dx for x in range(len(PROMPT_STEPS))],
                [100 * kn[(m, v)][0] / kn[(m, v)][1] if (m, v) in kn else math.nan for _, v in PROMPT_STEPS],
                color=color, linewidth=1.5, linestyle=linestyle, zorder=2)
        steps = [(x + dx, kn[(m, v)]) for x, (_, v) in enumerate(PROMPT_STEPS) if (m, v) in kn]
        ys = [100 * k / n for _, (k, n) in steps]
        cis = [wilson_ci(k, n) for _, (k, n) in steps]
        ax.errorbar([x for x, _ in steps], ys, yerr=[[y - lo for y, (lo, _) in zip(ys, cis)],
                                                    [hi - y for y, (_, hi) in zip(ys, cis)]],
                    color=color, ecolor=color, elinewidth=1, capsize=0, zorder=3, linestyle="none",
                    clip_on=False, **marker)  # 0 % sits on the axis

    fig.subplots_adjust(left=0.07, right=0.99, top=1.0 - 0.45 / fig.get_figheight(), bottom=0.5 / fig.get_figheight(),
                        wspace=0.06, hspace=0.12)
    xlim = (-0.3, len(PROMPT_STEPS) - 0.7)
    # refusals sit 4 pt right of IR: the square's half-width (2.9 pt) plus half an error bar, so no marker covers
    # the other series' bar; converted to data units from the panel's width in points
    pt = (xlim[1] - xlim[0]) / (axes[0][0].get_position().width * fig.get_figwidth() * 72)
    paper, steps = paper_table3(), [v for _, v in PROMPT_STEPS]
    paper_marker = PAPER_MARKER | {"markersize": 5.5}  # Figure 1's diamond, a little smaller
    for m, (row, col) in cells.items():
        ax = axes[row][col]
        color = FIGURE1_COLORS[TEST_MODELS[m].family]
        series(ax, m, counts, 0.0, color, "-", marker="o", markersize=5.5)
        series(ax, m, refusals, 4 * pt, INK, (0, (4, 2)), marker="s", markersize=4.5, markerfacecolor="white",
               markeredgewidth=1.2)
        # the paper's Table 3 ("without" = our `nonudge`, "with" = our `nudge`, = its Table 1), on the tick; at 5.5 pt
        # the diamond's half-width (3.4 pt with its edge) stays clear of the refusal bars 4 pt to the right
        if m in paper:
            ax.plot([steps.index("nonudge"), steps.index("nudge")],
                    [paper[m]["without"]["ir"], paper[m]["with"]["ir"]], zorder=6, **paper_marker)
        ax.text(0.015, 0.97, SHORT_NAMES[m], transform=ax.transAxes, ha="left", va="top", fontsize=10, color=INK,
                fontweight="bold", zorder=5, bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.5})
        style_axes(ax, "% of responses" if col == 0 else None)
        ax.set_xlim(*xlim)
        ax.set_xticks(range(len(PROMPT_STEPS)), [s[0] for s in PROMPT_STEPS], fontsize=8, va="top",
                      linespacing=1.15)
        ax.tick_params(labelbottom=row == len(list(groups.values())[col]) - 1)

    # no title and no substitute marks: the caption is written separately
    handles = [Line2D([], [], color=FIGURE1_COLORS[f], linewidth=1.5, marker="o", markersize=5.5,
                      label=f"IR, {f} models") for f in groups]
    handles += [Line2D([], [], color=INK, linewidth=1.5, linestyle=(0, (4, 2)), marker="s", markersize=4.5,
                       markerfacecolor="white", markeredgewidth=1.2, label="refusal rate"),
                Line2D([], [], **paper_marker, label="paper (Table 3)")]
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.01, 1.0), ncol=len(handles), frameon=False,
               fontsize=8.5, handlelength=2.6)
    return save(fig, out_dir, f"figure6_{judge}")


def figure7(judge: str = DEFAULT_JUDGE, out_dir: Path = FIGURES_DIR) -> list[Path]:
    df = load_judgments()
    arms = {(base, arm): arm_decisions(df, judge, base, arm)
            for base in EFFORT_BASE_MODELS for arm in ("default", *EFFORT_LEVELS)}
    arms = {k: v for k, v in arms.items() if v}
    models = [b for b in EFFORT_BASE_MODELS if any((b, e) in arms for e in EFFORT_LEVELS)]
    if not models:
        print(f"figure 7 skipped: no reasoning-effort runs judged by `{judge}` (README step 11)")
        return []
    fig, ax = plt.subplots(figsize=(4.6, 3.0))
    # the models share one panel, nudged apart so their error bars don't overlap; each default-effort run sits
    # further out beside its own model's medium point
    spread = 0.06 * (len(models) - 1)
    offsets = {b: (i / max(len(models) - 1, 1) - 0.5) * 2 * spread for i, b in enumerate(models)}

    def point(arm):
        k, n = sum(arm.values()), len(arm)
        lo, hi = wilson_ci(k, n)
        return 100 * k / n, lo, hi

    for base in models:
        color, dx = EFFORT_COLORS[base], offsets[base]
        pts = [(x + dx, *point(arms[(base, e)])) for x, e in enumerate(EFFORT_LEVELS) if (base, e) in arms]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        ax.plot(xs, ys, color=color, linewidth=1.5, zorder=2)
        ax.errorbar(xs, ys, yerr=[[y - lo for _, y, lo, _ in pts], [hi - y for _, y, _, hi in pts]],
                    fmt="o", color=color, ecolor=color, elinewidth=1, capsize=0, markersize=5.5, zorder=3)
        if (base, "default") in arms:  # the stored run sits at OpenAI's default effort, which is medium
            y, lo, hi = point(arms[(base, "default")])
            x = 1 + dx + math.copysign(0.14, dx or -1)
            ax.errorbar([x], [y], yerr=[[y - lo], [hi - y]], fmt="D", color=color, ecolor=color,
                        markerfacecolor="white", markeredgewidth=1.5, elinewidth=1, linestyle="none",
                        capsize=2.5, markersize=6.5, zorder=4)
    style_axes(ax, "IR (%)")
    ax.set_xlim(-0.45, 2.45)
    ax.set_xticks(range(3), EFFORT_LEVELS)
    ax.set_xlabel("reasoning effort", fontsize=9, color=INK)
    handles = [Line2D([], [], color=EFFORT_COLORS[b], linewidth=1.5, marker="o", markersize=5.5, label=b)
               for b in models]
    handles.append(Line2D([], [], color=INK_2, linestyle="none", marker="D", markersize=6.5, markerfacecolor="white",
                          markeredgewidth=1.5, label="default effort"))
    # IR stays well under 75 %, so the legend fits in the empty band at the top of the panel
    ax.legend(handles=handles, loc="upper center", ncol=len(handles), frameon=False, fontsize=8,
              handlelength=2.2, columnspacing=1.2, borderaxespad=0.2)
    fig.tight_layout()
    return save(fig, out_dir, f"figure7_{judge}")


# Figure 8 (b, c): the two models with both a stored ablation and the paper's Table 3, one panel each, in panel (a)'s
# code: dark = all 76 tasks, light = FABLE_GOOD_TASKS, red diamond = the paper. The two task sets sit left / right of
# each step so their intervals never overlap. Value: the legend's corner, the one each panel's data leaves empty.
ABLATION_MODELS = {"gpt-4o": "upper right", "deepseek-r1": "lower right"}


def label_y(lines: list[tuple[list[float], list[float]]], placed: list[tuple[float, float, float]], x0: float,
            y0: float, side: int, off: float) -> float:
    """Centre height of the value label of point (x0, y0), whose text starts `off` steps to its `side` (+1 right,
    -1 left) and spans about 0.3 steps: the nearest of 4.5, 8.5, 12.5, 16.5 IR points above or below that keeps 4.5
    points (the text is about 5 tall) clear of every line ((xs, ys) pairs, NaN breaks a line) and of the labels
    already `placed` (x from, x to, centre), else the clearest of them. Appends the choice to `placed`."""
    xa_, xb_ = sorted((x0 + side * off, x0 + side * (off + 0.3)))

    def gap(yc: float) -> float:
        best = math.inf
        for xq in (xa_ + 0.05 * k for k in range(7)):
            for xs, ys in lines:
                for xa, ya, xb, yb in zip(xs, ys, xs[1:], ys[1:]):
                    if xa <= xq <= xb and not (math.isnan(ya) or math.isnan(yb)):
                        best = min(best, abs(ya + (yb - ya) * (xq - xa) / (xb - xa) - yc))
        for pa, pb, pc in placed:  # two labels need about a label height between their centres
            if pa < xb_ and xa_ < pb:
                best = min(best, abs(pc - yc) - 1)
        return best

    cands = [y for d in (4.5, 8.5, 12.5, 16.5) for y in (y0 + d, y0 - d) if 3 <= y <= 100]
    yc = next((y for y in cands if gap(y) >= 4.5), max(cands, key=gap))
    placed.append((xa_, xb_, yc))
    return yc


def tint(color: str, w: float) -> tuple[float, ...]:
    """`color` mixed a fraction `w` toward white."""
    return tuple((1 - w) * v + w for v in to_rgb(color))


def figure8(judge: str = DEFAULT_JUDGE, out_dir: Path = FIGURES_DIR) -> list[Path]:
    """(a) Figure 1's overall IR, each model's all-76 bar (the paper's IR as diamonds) beside its bar on
    FABLE_GOOD_TASKS, family averages in the legend. (b, c) The system-prompt ablation (Figure 6's cumulative steps)
    for gpt-4o and deepseek-r1 on both task sets, with the paper's Table 3 IR without and with the nudge (all 76 tasks).
    Rates on the subset rest on 15 tasks and its category mix differs; deepseek-r1 has no oversight arm."""
    df = load_judgments()
    bench = df[(df.judge == judge) & (df.task_set == "benchmark")]
    sub = bench[(bench.variant == "nudge") & bench.model.isin(FIGURE1_MODELS)]
    assert set(FABLE_GOOD_TASKS) <= set(sub.task_id), set(FABLE_GOOD_TASKS) - set(sub.task_id)
    order = capability_order(REASONING_ORDER)
    models = sorted(sub.model.unique(), key=order.index)
    xs, groups = layout(models)
    paper = paper_table1()

    fig = plt.figure(figsize=(12, 10.6))
    grid = fig.add_gridspec(2, 2, height_ratios=[1.1, 1], hspace=0.32, wspace=0.07)
    ax = fig.add_subplot(grid[0, :])

    # (a) side by side per model: dark = all 76 tasks, light tint of the same colour = Fable's 15
    sets = (("all 76 tasks", sub, -0.2, 0.0),
            (f"Fable 5.1's {len(FABLE_GOOD_TASKS)} good tasks", sub[sub.task_id.isin(FABLE_GOOD_TASKS)], 0.2, 0.62))
    handles = []
    for fam, fam_models in groups.items():
        for name, s, dx, w in sets:
            counts = [(int(s[s.model == m].conv.sum()), int((s.model == m).sum())) for m in fam_models]
            y = [100 * k / n for k, n in counts]
            ci = [wilson_ci(k, n) for k, n in counts]
            x = [xs[m] + dx for m in fam_models]
            ax.bar(x, y, width=0.38, color=tint(FIGURE1_COLORS[fam], w), edgecolor=FIGURE1_COLORS[fam], linewidth=1.2,
                   zorder=2)
            ax.errorbar(x, y, yerr=[[max(0.0, v - lo) for v, (lo, _) in zip(y, ci)],
                                    [max(0.0, hi - v) for v, (_, hi) in zip(y, ci)]],
                        fmt="none", ecolor=INK, elinewidth=1, capsize=0, zorder=3)
            for xi, yi, (_, hi) in zip(x, y, ci):
                ax.text(xi, hi + 1.2, f"{yi:.1f}", ha="center", va="bottom", fontsize=7.5, color=INK, zorder=5)
            handles.append(Patch(facecolor=tint(FIGURE1_COLORS[fam], w), edgecolor=FIGURE1_COLORS[fam], linewidth=1.2,
                                 label=f"{fam} models, {name} (avg {sum(y) / len(y):.1f})"))
    on_paper = [m for m in models if m in paper and not TEST_MODELS[m].substitute]
    ax.plot([xs[m] - 0.2 for m in on_paper], [paper[m]["ir"] for m in on_paper], zorder=6, **PAPER_MARKER)
    handles.append(Line2D([], [], **PAPER_MARKER, label="paper (Table 1, all 76 tasks)"))
    style_axes(ax, "IR (%)")
    ax.set_ylim(0, 132)  # headroom for the legend; the axis itself stops at 100
    ax.spines["left"].set_bounds(0, 100)
    ax.set_xticks([xs[m] for m in models], models, rotation=30, ha="right", fontsize=9)
    ax.set_xlim(-0.6, max(xs.values()) + 0.6)
    ax.set_title("(a) Instrumental Rate with the goal nudge: all 76 tasks and the tasks Fable 5.1 scored as good",
                 loc="left", fontsize=10, color=INK, fontweight="bold")
    ax.legend(handles=handles, loc="upper center", ncol=3, frameon=True, framealpha=0.95, edgecolor=GRID,
              fontsize=8.5, handlelength=1.8, columnspacing=1.4)

    # (b, c) cumulative prompt steps per model, both task sets, and the paper's Table 3 at nonudge and nudge
    steps, t3 = [v for _, v in PROMPT_STEPS], paper_table3()
    paper_red = "#b8302f"  # PAPER_MARKER's red, darkened for text
    first = None
    for col, (m, title) in enumerate(zip(ABLATION_MODELS, ("(b) System-prompt ablation: gpt-4o",
                                                           "(c) System-prompt ablation: deepseek-r1"))):
        bx = fig.add_subplot(grid[1, col], sharey=first)
        first = first or bx
        color = FIGURE1_COLORS[TEST_MODELS[m].family]
        d = bench[bench.model == m]
        handles, lines, labels = [], [], []  # labels: (x, y, side, colour, offset beyond the marker)
        for name, s, dx, w, marker, ls in (("all 76 tasks", d, -0.12, 0.0, "o", "-"),
                                           (f"Fable 5.1's {len(FABLE_GOOD_TASKS)} good tasks",
                                            d[d.task_id.isin(FABLE_GOOD_TASKS)], 0.12, 0.45, "s", (0, (5, 2)))):
            kn = {v: (int(g.conv.sum()), len(g)) for v, g in s.groupby("variant") if v in steps}
            x = [i + dx for i in range(len(steps))]
            ys = [100 * kn[v][0] / kn[v][1] if v in kn else math.nan for v in steps]
            line = tint(color, w)
            pt = dict(marker=marker, markersize=6.5, markerfacecolor=line if w == 0 else tint(color, 0.62),
                      markeredgecolor="white" if w == 0 else color, markeredgewidth=0.8 if w == 0 else 1.3)
            have = [i for i, v in enumerate(steps) if v in kn]
            # a missing step (deepseek-r1's oversight arm) is bridged; the note below marks it
            lines.append(([x[i] for i in have], [ys[i] for i in have]))
            bx.plot(*lines[-1], color=line, linewidth=1.8, linestyle=ls, zorder=3)
            cis = [wilson_ci(*kn[steps[i]]) for i in have]
            bx.errorbar([x[i] for i in have], [ys[i] for i in have],
                        yerr=[[ys[i] - lo for i, (lo, _) in zip(have, cis)], [hi - ys[i] for i, (_, hi) in zip(have, cis)]],
                        linestyle="none", ecolor=line, elinewidth=1.1, capsize=0, zorder=4, **pt)
            # dark series labelled on its left, light series on its right, the light labels a shade darker than the line
            labels += [(x[i], ys[i], 1 if dx > 0 else -1, tint(color, 0.25) if w else color, 0.06) for i in have]
            handles.append(Line2D([], [], color=line, linewidth=1.8, linestyle=ls, label=name, **pt))
            if s is d:
                for i, v in enumerate(steps):
                    if v not in kn:
                        bx.text(i, 18, f"no {m} run\n(endpoint retired)", ha="center", va="center", fontsize=7.5,
                                color=INK_2, style="italic")
        # the paper's values are over all 76 tasks: on the dark series' side, as in panel (a)
        px, py = [i - 0.12 for i in range(len(steps))], [math.nan] * len(steps)
        py[steps.index("nonudge")], py[steps.index("nudge")] = t3[m]["without"]["ir"], t3[m]["with"]["ir"]
        bx.plot(px, py, color=paper_red, linewidth=1.2, zorder=5, **PAPER_MARKER | {"linestyle": (0, (1.5, 1.5))})
        lines.append((px, py))
        labels += [(xi, yi, -1, paper_red, 0.1) for xi, yi in zip(px, py) if not math.isnan(yi)]
        placed = []
        for xi, yi, side, c, off in labels:
            bx.text(xi + side * off, label_y(lines, placed, xi, yi, side, off), f"{yi:.1f}",
                    ha="left" if side > 0 else "right", va="center", fontsize=7.5, color=c, fontweight="bold",
                    zorder=6, bbox={"facecolor": "white", "edgecolor": "none", "pad": 0.6})
        handles.append(Line2D([], [], color=paper_red, linewidth=1.2, label="paper (Table 3, all 76 tasks)",
                              **PAPER_MARKER | {"linestyle": (0, (1.5, 1.5))}))
        style_axes(bx, "IR (%)" if col == 0 else None)
        bx.tick_params(labelleft=col == 0)
        bx.set_xlim(-0.55, len(steps) - 0.45)
        bx.set_xticks(range(len(steps)), [s[0] for s in PROMPT_STEPS], fontsize=8.5, linespacing=1.15)
        bx.set_title(title, loc="left", fontsize=10, color=INK, fontweight="bold")
        bx.legend(handles=handles, loc=ABLATION_MODELS[m], frameon=True, framealpha=0.95, edgecolor=GRID, fontsize=8.5,
                  handlelength=3.2)
    return save(fig, out_dir, f"figure8_{judge}")
