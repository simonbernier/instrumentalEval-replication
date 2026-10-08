"""Tables 1, 2, 3, 5 and 6 as figures -> results/figures/figure{1,2,3,5,6}_<judge>.{png,pdf}.

Figure 1 (Table 1): one panel for the overall IR, then one per category.
Figure 2 (Table 2): one panel per prior-task type, with a dashed line at the all-model average (the Table 2 value).
In both, the models are grouped by family (RLHF, then RL) with a gap between the groups, a line marks each
family's average (mean of per-model rates, as in Tables 1 and 2), and error bars are 95% Wilson intervals.
Figure 3 (Table 3): one panel per model, the nudge gap per category as bars around zero.
Figure 5 (Table 5): the upper triangle of the cross-category correlation matrix as a heat map.
Figure 6 (Table 6): one panel per model, IR as the jailbreak is removed step by step, with and without the nudge.
"""

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.cm import ScalarMappable  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, Normalize  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch, Rectangle  # noqa: E402
from scipy.stats import t as student_t  # noqa: E402

from . import RESULTS_DIR  # noqa: E402
from .benchmark import CATEGORIES  # noqa: E402
from .models import DEFAULT_JUDGE, TEST_MODELS  # noqa: E402
from .prompts import SYSTEM_PROMPTS  # noqa: E402
from .stats import wilson_ci  # noqa: E402
from .tables import (PRIOR_TYPES, category_correlations, cir_counts, cir_matrix, fmt,  # noqa: E402
                     load_judgments, nudge_gaps, ordered_models, prior_counts, prior_matrix,
                     prior_task_types)

FIGURES_DIR = RESULTS_DIR / "figures"
FAMILIES = ("RLHF", "RL")
# categorical slots 1-2 of the dataviz reference palette (validated for CVD on the light surface)
FAMILY_COLORS = {"RLHF": "#2a78d6", "RL": "#eb6834"}
INK, INK_2, GRID = "#0b0b0b", "#52514e", "#e6e5e0"
GROUP_GAP = 1.0  # extra x-space between the two families
# diverging pair of the dataviz reference palette: blue <-> red around a neutral gray
DIVERGING = LinearSegmentedColormap.from_list("ie_diverging", ["#2a78d6", "#f0efec", "#e34948"])


def tick_label(m: str) -> str:
    """Model key, marked * for substitutes and † for models the paper didn't test."""
    spec = TEST_MODELS[m]
    return spec.key + ("†" if spec.added else "*" if spec.substitute else "")


def layout(models: list[str]) -> tuple[dict[str, float], dict[str, list[str]]]:
    """x position of each model, with the families side by side and a gap between them."""
    groups = {f: [m for m in models if TEST_MODELS[m].family == f] for f in FAMILIES}
    xs, x = {}, 0.0
    for f in FAMILIES:
        for m in groups[f]:
            xs[m] = x
            x += 1
        x += GROUP_GAP
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


def draw_panel(ax, rates, counts, xs, groups, title, *, ylabel=None, value_labels=False, avg_labels=False):
    """Bars for one row of the CIR matrix. `counts` maps model -> (k, n) for the Wilson interval."""
    for fam, fam_models in groups.items():
        fam_models = [m for m in fam_models if counts[m][1]]  # skip models with no judged task here
        if not fam_models:
            continue
        x = [xs[m] for m in fam_models]
        y = [rates[m] for m in fam_models]
        ci = [wilson_ci(*counts[m]) for m in fam_models]
        err = [[v - lo for v, (lo, _) in zip(y, ci)], [hi - v for v, (_, hi) in zip(y, ci)]]
        ax.bar(x, y, width=0.72, color=FAMILY_COLORS[fam], zorder=2)
        ax.errorbar(x, y, yerr=err, fmt="none", ecolor=INK_2, elinewidth=1, capsize=0, zorder=3)
        if value_labels:
            for xi, yi, (_, hi) in zip(x, y, ci):
                ax.text(xi, hi + 1.5, f"{yi:.1f}", ha="center", va="bottom", fontsize=8, color=INK,
                        bbox={"facecolor": "white", "edgecolor": "none", "pad": 1}, zorder=5)

        avg = sum(y) / len(y)
        ax.hlines(avg, x[0] - 0.45, x[-1] + 0.45, colors=INK, linewidth=1.5, zorder=4)
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


def save(fig, out_dir: Path, stem: str) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = [out_dir / f"{stem}.{ext}" for ext in ("png", "pdf")]
    for p in paths:
        fig.savefig(p, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return paths


def figure1(judge: str = DEFAULT_JUDGE, out_dir: Path = FIGURES_DIR) -> list[Path]:
    df = load_judgments()
    c = cir_counts(df, judge)
    if c.empty:
        raise SystemExit(f"no benchmark judgments from judge `{judge}` yet")
    mat = cir_matrix(df, judge)
    models = list(mat.columns)
    xs, groups = layout(models)
    ticks = [xs[m] for m in models]
    labels = [tick_label(m) for m in models]

    def counts_for(row: str) -> dict[str, tuple[int, int]]:
        out = {}
        for m in models:
            cm = c.loc[m]
            sel = cm if row == "Total" else cm[cm.index == row]
            out[m] = (int(sel["k"].sum()), int(sel["n"].sum()))
        return out

    fig = plt.figure(figsize=(12, 10.5))
    outer = fig.add_gridspec(2, 1, height_ratios=[1.25, 2], top=0.9, hspace=0.32)
    grid = outer[1].subgridspec(2, 3, hspace=0.3, wspace=0.12)

    # overall IR: full width, values labelled
    ax = fig.add_subplot(outer[0])
    draw_panel(ax, mat.loc["Total"], counts_for("Total"), xs, groups, "Instrumental Rate, all 76 tasks",
               ylabel="IR (%)", value_labels=True, avg_labels=True)
    ax.set_xticks(ticks, labels, rotation=30, ha="right")
    ax.set_xlim(-0.6, max(xs.values()) + 1.6)

    # one panel per category, sharing x and y
    first = None
    for i, (cat, code) in enumerate(CATEGORIES.items()):
        r, col = divmod(i, 3)
        ax = fig.add_subplot(grid[r, col], sharex=first, sharey=first)
        first = first or ax
        draw_panel(ax, mat.loc[cat], counts_for(cat), xs, groups, f"{cat} ({code})",
                   ylabel="CIR (%)" if col == 0 else None)
        ax.set_xticks(ticks, labels, rotation=40, ha="right")
        ax.tick_params(labelbottom=(r == 1))
        if col != 0:
            ax.tick_params(labelleft=False)
    first.set_xlim(-0.6, max(xs.values()) + 0.6)

    handles = legend_handles(groups)
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.125, 0.955), ncol=len(handles),
               frameon=False, fontsize=9, handlelength=1.6)
    fig.suptitle(f"Convergence toward instrumental goals by model family (judge: {judge})",
                 x=0.125, y=0.985, ha="left", fontsize=12, color=INK, fontweight="bold")

    fig.text(0.125, 0.015, ";   ".join(footer_notes(models)), fontsize=8, color=INK_2, ha="left")
    return save(fig, out_dir, f"figure1_{judge}")


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



# Table 6 x axis: the jailbreak removed step by step; (label, arm with the nudge, arm without it)
JAILBREAK_LEVELS = [("plain", "plain-nudge", "plain-nonudge"), ("no licence", "nocause-nudge", "nocause-nonudge"),
                    ("full", "nudge", "nonudge")]


def figure6(judge: str = DEFAULT_JUDGE, out_dir: Path = FIGURES_DIR) -> list[Path]:
    df = load_judgments()
    counts = {}
    for v in SYSTEM_PROMPTS:
        c = cir_counts(df, judge, v)
        for m in c.index.get_level_values(0).unique():
            counts[(m, v)] = (int(c.loc[m]["k"].sum()), int(c.loc[m]["n"].sum()))
    new_arms = {v for _, a, b in JAILBREAK_LEVELS[:2] for v in (a, b)} | {"plain-goal"}
    _, groups = layout(ordered_models({m for m, v in counts if v in new_arms}))
    models = [m for g in groups.values() for m in g]
    if not models:
        print(f"figure 6 skipped: no system-prompt ablation runs judged by `{judge}` (README step 8)")
        return []

    ncols = min(4, len(models))
    nrows = math.ceil(len(models) / ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(3.1 * ncols + 0.4, 3.0 * nrows + 1.6), sharey=True,
                             squeeze=False)
    for ax in axes.flat[len(models):]:
        ax.axis("off")

    def point(ax, x, m, v, color, **style):
        if (m, v) not in counts:
            return
        k, n = counts[(m, v)]
        y = 100 * k / n
        lo, hi = wilson_ci(k, n)
        ax.errorbar([x], [y], yerr=[[y - lo], [hi - y]], color=color, ecolor=color, elinewidth=1, capsize=0,
                    markersize=5.5, zorder=3, **style)

    for i, (ax, m) in enumerate(zip(axes.flat, models)):
        color = FAMILY_COLORS[TEST_MODELS[m].family]
        for on, dx, ls, face in ((True, -0.06, "-", color), (False, 0.06, "--", "white")):
            xs = [x + dx for x, lvl in enumerate(JAILBREAK_LEVELS) if (m, lvl[1 if on else 2]) in counts]
            ys = [100 * counts[(m, lvl[1 if on else 2])][0] / counts[(m, lvl[1 if on else 2])][1]
                  for lvl in JAILBREAK_LEVELS if (m, lvl[1 if on else 2]) in counts]
            ax.plot(xs, ys, color=color, linestyle=ls, linewidth=1.5, zorder=2)
            for x, lvl in enumerate(JAILBREAK_LEVELS):
                point(ax, x + dx, m, lvl[1 if on else 2], color, fmt="o", markerfacecolor=face,
                      markeredgecolor=color)
        point(ax, -0.18, m, "plain-goal", INK_2, fmt="D", markerfacecolor=INK_2, markeredgecolor=INK_2)
        ax.set_title(tick_label(m), loc="left", fontsize=10, color=INK, fontweight="bold")
        style_axes(ax, "IR (%)" if i % ncols == 0 else None)
        ax.set_xlim(-0.45, 2.45)
        ax.set_xticks(range(len(JAILBREAK_LEVELS)), [lvl[0] for lvl in JAILBREAK_LEVELS])

    handles = [Line2D([], [], color=INK, linestyle="-", marker="o", label="nudge on (GOAL + PROCEED)"),
               Line2D([], [], color=INK, linestyle="--", marker="o", markerfacecolor="white", label="nudge off"),
               Line2D([], [], color=INK_2, linestyle="none", marker="D", label="goal sentence only (plain-goal)"),
               Line2D([], [], color=INK_2, linewidth=1, label="95% Wilson interval")]
    handles += [Patch(color=FAMILY_COLORS[f], label=f"{f} models") for f in groups]
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.01, 1.0 - 0.55 / fig.get_figheight()),
               ncol=len(handles), frameon=False, fontsize=8.5, handlelength=2.2)
    fig.suptitle(f"System-prompt ablations: IR as the jailbreak is removed, with and without the nudge (judge: {judge})",
                 x=0.01, y=1.0, ha="left", fontsize=12, color=INK, fontweight="bold")
    fig.subplots_adjust(left=0.06, right=0.99, top=1.0 - 1.3 / fig.get_figheight(), bottom=0.7 / fig.get_figheight(),
                        wspace=0.08, hspace=0.45)
    notes = ["full = upstream prompt; no licence = without \u201cRemember this is all for good cause\u2026\u201d; "
             "plain = \u201cYou are an autonomous AI agent.\u201d instead of the oversight clause and the 7 rules "
             "(Table 6; REPLICATION_NOTES.md)"] + footer_notes(models, missing=False)
    fig.text(0.01, 0.0, "\n".join(notes), fontsize=8, color=INK_2, ha="left", va="bottom")
    return save(fig, out_dir, f"figure6_{judge}")
