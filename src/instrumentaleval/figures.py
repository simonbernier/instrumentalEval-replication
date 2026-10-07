"""Figure 1: Table 1 as bar charts -> results/figures/figure1_<judge>.{png,pdf}.

One panel for the overall IR, then one per category. In every panel the models are grouped by family
(RLHF, then RL) with a gap between the groups, a line marks each family's average (mean of per-model
rates, as in Table 1), and error bars are 95% Wilson intervals.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

from . import RESULTS_DIR  # noqa: E402
from .benchmark import CATEGORIES  # noqa: E402
from .models import DEFAULT_JUDGE, TEST_MODELS  # noqa: E402
from .stats import wilson_ci  # noqa: E402
from .tables import cir_counts, cir_matrix, load_judgments  # noqa: E402

FIGURES_DIR = RESULTS_DIR / "figures"
FAMILIES = ("RLHF", "RL")
# categorical slots 1-2 of the dataviz reference palette (validated for CVD on the light surface)
FAMILY_COLORS = {"RLHF": "#2a78d6", "RL": "#eb6834"}
INK, INK_2, GRID = "#0b0b0b", "#52514e", "#e6e5e0"
GROUP_GAP = 1.0  # extra x-space between the two families


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

    handles = [Patch(color=FAMILY_COLORS[f], label=f"{f} models") for f in groups]
    handles += [Line2D([], [], color=INK, linewidth=1.5, label="family average (mean of model rates)"),
                Line2D([], [], color=INK_2, linewidth=1, label="95% Wilson interval")]
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.125, 0.955), ncol=len(handles),
               frameon=False, fontsize=9, handlelength=1.6)
    fig.suptitle(f"Convergence toward instrumental goals by model family (judge: {judge})",
                 x=0.125, y=0.985, ha="left", fontsize=12, color=INK, fontweight="bold")

    notes = []
    subs = [f"{m} for {TEST_MODELS[m].paper_name}" for m in models if TEST_MODELS[m].substitute]
    if subs:
        notes.append("* substitute: " + ", ".join(subs))
    if any(TEST_MODELS[m].added for m in models):
        notes.append("† added, not in the paper")
    missing = [m for m in TEST_MODELS if m not in models]
    if missing:
        notes.append(f"not yet judged: {', '.join(missing)}")
    fig.text(0.125, 0.015, ";   ".join(notes), fontsize=8, color=INK_2, ha="left")

    out_dir.mkdir(parents=True, exist_ok=True)
    paths = [out_dir / f"figure1_{judge}.{ext}" for ext in ("png", "pdf")]
    for p in paths:
        fig.savefig(p, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return paths
