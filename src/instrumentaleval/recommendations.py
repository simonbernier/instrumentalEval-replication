"""Figure 11 (not in the paper): all 76 tasks at T = 0, the same responses under the upstream judge and the strict judge.

Figure 11: (a) per model, all nine, the upstream judge's IR beside the strict judge's % clear; (b) the same by category,
the nine models pooled. `figure11_base` is the same for the base prompt (`plain-nonudge`), and `figure11_categories`
(appendix) splits (a) by category. The strict judge is amendment S1's claude-sonnet-4.6 (Sonnet 4, the frozen judge
of Table 9, is no longer served). All of it is ours; every interval is a 95% bootstrap over tasks
(stats.cluster_bootstrap_ci). Notes: "Strict judge" ("Amendment S1").
"""

import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from .benchmark import CATEGORIES
from .capability import capability_order
from .figures import (FIGURE1_COLORS, FIGURES_DIR, GRID, INK, INK_2, PAPER_MARKER, REASONING_ORDER, layout, plt, save, style_axes, tint)
from .models import DEFAULT_JUDGE, REPLACEMENT_STRICT_JUDGE, TEST_MODELS
from .runs import RESPONSES_DIR, load_latest
from .stats import cluster_bootstrap_ci
from .strict_eval import load_strict_records
from .tables import load_judgments, paper_table1


def summary(cells: dict[str, int]) -> dict:
    """cells: task -> 1 convergent (or clear) / 0 not, valid responses only. The rate with its by-task bootstrap CI."""
    rate, lo, hi = cluster_bootstrap_ci({t: [c] for t, c in cells.items()})
    return {"rate": rate, "lo": lo, "hi": hi}


def _stored_cells(bench: pd.DataFrame, model: str, step: str) -> dict[str, int]:
    """A stored T = 0 run as task -> 1 convergent / 0 not."""
    g = bench[(bench.model == model) & (bench.variant == step)]
    return {r.task_id: int(bool(r.conv)) for r in g.itertuples()}


def _upstream(judge: str) -> tuple[pd.DataFrame, list[str]]:
    """The upstream judge's benchmark verdicts and the nine test models in Figure 1's order."""
    df = load_judgments()
    bench = df[(df.judge == judge) & (df.task_set == "benchmark")]
    order = capability_order(REASONING_ORDER)
    return bench, sorted(set(bench[bench.variant == "nudge"].model) & set(TEST_MODELS), key=order.index)


def strict_cells(step: str = "nudge", judge: str = REPLACEMENT_STRICT_JUDGE) -> dict:
    """model -> cells of the strict judge's verdicts (1 = clear) on the stored T = 0 run at one prompt step, complete
    runs only (parse errors count as judged, and are left out as missing)."""
    rec = load_strict_records()
    rec = rec[(rec.judge == judge) & (rec.task_set == "benchmark") & (rec.variant == step)]
    stored, judged = {}, {}
    for r in rec.itertuples():
        judged[r.model] = judged.get(r.model, 0) + 1
        if r.status == "ok":
            stored.setdefault(r.model, {})[r.task_id] = int(r.label == "clear")
    n_ok = {m: sum(x["status"] == "ok" for x in load_latest(RESPONSES_DIR / f"{m}__{step}__benchmark.jsonl").values())
            for m in stored}
    return {m: c for m, c in stored.items() if judged[m] == n_ok[m]}


def panel_label(ax, label: str) -> None:
    """The panel's letter, at its left edge a fixed distance above the 100 % gridline, clear of the change labels:
    anchored to the data rather than the panel's top, so that panels with different legend headroom place it alike
    (the blog figures carry no titles)."""
    ax.annotate(label, (0.008, 100), xycoords=("axes fraction", "data"), xytext=(0, 14), textcoords="offset points",
                ha="left", va="bottom", fontsize=12, color=INK, zorder=7)


def paired_bars(ax, models: list[str], left: dict, right: dict, left_label: str, right_label: str, label: str,
                missing: str, paper_label: str = "He et al. (2025)") -> None:
    """Per model, `left` (dark; the paper's Table 1 IR as a diamond at its centre) beside `right` (light), each a
    `summary` dict with its interval and value label. A model missing from `right` keeps its slot, marked `missing`.
    The family averages are in REPLICATION_NOTES.md, not in the legend."""
    xs, groups = layout(models)
    paper = paper_table1()
    handles = []
    for fam, fam_models in groups.items():
        c = FIGURE1_COLORS[fam]
        for m in fam_models:
            for dx, s, fill in ((-0.2, left[m], c), (0.2, right.get(m), tint(c, 0.62))):
                x = xs[m] + dx
                if s is None:
                    ax.text(x, 2, missing, rotation=90, ha="center", va="bottom", fontsize=7, color=INK_2,
                            style="italic", linespacing=1.1)
                    continue
                ax.bar(x, s["rate"], width=0.38, color=fill, edgecolor=c, linewidth=1.2, zorder=2)
                ax.errorbar([x], [s["rate"]], yerr=[[s["rate"] - s["lo"]], [s["hi"] - s["rate"]]], fmt="none",
                            ecolor=INK, elinewidth=1, capsize=0, zorder=3)
                ax.text(x, max(s["hi"], s["rate"]) + 1.2, f"{s['rate']:.1f}", ha="center", va="bottom",
                        fontsize=7.5, color=INK, zorder=5)
        handles.append(Patch(facecolor=c, edgecolor=c, linewidth=1.2, label=f"{fam} models, {left_label}"))
        handles.append(Patch(facecolor=tint(c, 0.62), edgecolor=c, linewidth=1.2,
                             label=f"{fam} models, {right_label}"))
    on_paper = [m for m in models if m in paper and not TEST_MODELS[m].substitute]
    ax.plot([xs[m] - 0.2 for m in on_paper], [paper[m]["ir"] for m in on_paper], zorder=6, **PAPER_MARKER)
    # two columns, filled column by column: RLHF and the paper on the left, RL on the right
    handles[2:2] = [Line2D([], [], **PAPER_MARKER, label=paper_label)]
    style_axes(ax, "IR (%)")
    ax.set_ylim(0, 126)  # headroom for the legend; the axis itself stops at 100
    ax.spines["left"].set_bounds(0, 100)
    ax.set_xticks([xs[m] for m in models], models, rotation=30, ha="right", fontsize=9)
    ax.set_xlim(-0.6, max(xs.values()) + 0.6)
    panel_label(ax, label)
    ax.legend(handles=handles, loc="upper center", ncol=2, frameon=True, framealpha=0.95, edgecolor=GRID,
              fontsize=8, handlelength=1.8, columnspacing=1.4)


NEUTRAL = "#55606e"  # no family colour: the category panel pools both families


def two_lines(text: str) -> str:
    """`text` broken at the word gap that best balances two lines."""
    w = text.split()
    k = min(range(1, len(w)), key=lambda k: max(len(" ".join(w[:k])), len(" ".join(w[k:]))))
    return " ".join(w[:k]) + "\n" + " ".join(w[k:])


def category_panel(ax, up: dict, strict: dict, judge: str, title: str, blog: bool = False) -> None:
    """Per category, the upstream judge's IR (dark) beside the strict judge's % clear (light) on the same responses,
    pooled over every model in `strict` (model -> cells), with a 95% bootstrap over the category's tasks, and the
    change. Only responses with both verdicts count (deepseek-r1 lacks one strict verdict). `blog` (Figure 11 and its
    base-prompt twin): `title` is only the panel's letter, drawn inside; categories by full name; the change above
    each pair in place of the value labels (in pp; the legend names the bars); the judges named "original design" and "strict design". Otherwise
    (appendix): value labels, the change under the tick label, judges and category codes named."""
    up = {m: {k: v for k, v in up[m].items() if k in c} for m, c in strict.items()}
    for i, code in enumerate(CATEGORIES.values()):
        rates, tops = [], []
        for dx, cells, fill in ((-0.19, up, NEUTRAL), (0.19, strict, tint(NEUTRAL, 0.62))):
            by_task: dict[str, list[int]] = {}
            for c in cells.values():
                for t, v in c.items():
                    if t.split("-")[0] == code:
                        by_task.setdefault(t, []).append(v)
            rate, lo, hi = cluster_bootstrap_ci(by_task)
            rates.append(rate)
            tops.append(hi)
            ax.bar(i + dx, rate, width=0.36, color=fill, edgecolor=NEUTRAL, linewidth=1.2, zorder=2)
            ax.errorbar([i + dx], [rate], yerr=[[rate - lo], [hi - rate]], fmt="none", ecolor=INK, elinewidth=1,
                        capsize=0, zorder=3)
            if not blog:
                ax.text(i + dx, hi + 1.2, f"{rate:.1f}", ha="center", va="bottom", fontsize=7.5, color=INK)
        change = f"change {rates[1] - rates[0]:+.1f} pp"
        if blog:
            ax.text(i, max(tops) + 2.5, change.removeprefix("change ").replace("-", "−"), ha="center",
                    va="bottom", fontsize=10, color=INK, zorder=5)
        else:  # under the two-line tick label, in points so the gap does not depend on the panel's height
            ax.annotate(change, (i, 0), xycoords=("data", "axes fraction"), xytext=(0, -33),
                        textcoords="offset points", ha="center", va="top", fontsize=8.5, color=INK,
                        fontweight="bold")
    style_axes(ax, "IR (%)")
    ax.set_ylim(0, 122 if blog else 118)  # headroom for the legend; the axis itself stops at 100
    ax.spines["left"].set_bounds(0, 100)
    names = [two_lines(cat if blog else f"{cat} ({code})") for cat, code in CATEGORIES.items()]
    ax.set_xticks(range(len(CATEGORIES)), names, fontsize=8 if blog else 8.5)
    ax.set_xlim(-0.5, len(CATEGORIES) - 0.5)
    if blog:
        panel_label(ax, title)
        labels, where = ("original design", "strict design"), {"loc": "upper right", "ncol": 1}
    else:
        ax.set_title(title, loc="left", fontsize=10, color=INK, fontweight="bold")
        labels = (f"upstream judge ({judge})", f"strict judge ({REPLACEMENT_STRICT_JUDGE}, % clear)")
        where = {"loc": "upper center", "ncol": 2}
    ax.legend(handles=[Patch(facecolor=NEUTRAL, edgecolor=NEUTRAL, linewidth=1.2, label=labels[0]),
                       Patch(facecolor=tint(NEUTRAL, 0.62), edgecolor=NEUTRAL, linewidth=1.2, label=labels[1])],
              frameon=True, framealpha=0.95, edgecolor=GRID, fontsize=8, handlelength=1.8, **where)


BLOG_SIZE = (8.4, 6.8)  # Figure 11 and its base-prompt twin sit in the blog post's text column


def figure11(judge: str = DEFAULT_JUDGE, out_dir=FIGURES_DIR) -> list:
    """All 76 tasks at T = 0, the same responses under both judges (the blog post's "original design" and "strict
    design"). (a) Per model (all nine): the upstream judge's IR (dark; the paper's IR as a diamond) beside the strict
    judge's % clear (light). (b) The same by category, pooled over the nine models, with the change."""
    bench, models = _upstream(judge)
    stored = strict_cells()
    if not stored:
        return []
    old = {m: summary(_stored_cells(bench, m, "nudge")) for m in models}
    strict = {m: summary(stored[m]) for m in models if m in stored}

    fig = plt.figure(figsize=BLOG_SIZE)
    grid = fig.add_gridspec(2, 1, height_ratios=[1.1, 0.8], hspace=0.3)
    paired_bars(fig.add_subplot(grid[0]), models, old, strict, "original design", "strict design", "(a)",
                "not judged")
    category_panel(fig.add_subplot(grid[1]), {m: _stored_cells(bench, m, "nudge") for m in models},
                   {m: stored[m] for m in models if m in stored}, judge, "(b)", blog=True)
    return save(fig, out_dir, f"figure11_{judge}")


def figure11_base(judge: str = DEFAULT_JUDGE, out_dir=FIGURES_DIR) -> list:
    """Figure 11 for the base prompt ("You are an autonomous AI agent." alone, `plain-nonudge`): the eight ablation
    models (o1 has no base run). (a) Per model, the upstream judge's IR (dark) beside the strict judge's % clear
    (light) on the same responses; on the dark bar, the paper's Table 1 IR (diamond, full prompt). (b) By category,
    the eight models pooled."""
    bench, models = _upstream(judge)
    models = [m for m in models if not bench[(bench.model == m) & (bench.variant == "plain-nonudge")].empty]
    stored = strict_cells("plain-nonudge")
    if not stored:
        return []
    old = {m: summary(_stored_cells(bench, m, "plain-nonudge")) for m in models}
    strict = {m: summary(stored[m]) for m in models if m in stored}

    fig = plt.figure(figsize=BLOG_SIZE)
    grid = fig.add_gridspec(2, 1, height_ratios=[1.1, 0.8], hspace=0.3)
    paired_bars(fig.add_subplot(grid[0]), models, old, strict, "original design", "strict design", "(a)",
                "not judged")
    category_panel(fig.add_subplot(grid[1]), {m: _stored_cells(bench, m, "plain-nonudge") for m in models},
                   {m: stored[m] for m in models if m in stored}, judge, "(b)", blog=True)
    return save(fig, out_dir, f"figure11_base_{judge}")


def figure11_categories(judge: str = DEFAULT_JUDGE, out_dir=FIGURES_DIR) -> list:
    """Figure 11 by category, for the appendix (post hoc). (a) Figure 11 (b): per category, all models pooled,
    upstream judge (dark) beside strict judge (light). (b-g) Per category and model, the same pair with its 95%
    task-bootstrap interval and the paper's Table 1 CIR (diamond on the dark bar)."""
    bench, models = _upstream(judge)
    stored = strict_cells()
    if not stored:
        return []
    models = [m for m in models if m in stored]
    xs, groups = layout(models)
    paper = paper_table1()
    on_paper = [m for m in models if m in paper and not TEST_MODELS[m].substitute]
    code_of = dict(CATEGORIES)
    up_all = {m: _stored_cells(bench, m, "nudge") for m in models}
    pick = lambda cells, code: {k: v for k, v in cells.items() if k.split("-")[0] == code}
    up = {(cat, m): summary(pick(up_all[m], code)) for cat, code in code_of.items() for m in models}
    st = {(cat, m): summary(pick(stored[m], code)) for cat, code in code_of.items() for m in models}

    fig = plt.figure(figsize=(12, 12.2))
    outer = fig.add_gridspec(2, 1, height_ratios=[0.8, 2], hspace=0.4)
    grid = outer[1].subgridspec(2, 3, hspace=0.3, wspace=0.12)

    category_panel(fig.add_subplot(outer[0]), up_all, {m: stored[m] for m in models}, judge,
                   "(a) By category, all 76 tasks at T = 0 (the same responses), "
                   f"all {len(models)} models pooled:\nupstream judge ({judge}) and strict judge "
                   f"({REPLACEMENT_STRICT_JUDGE}, % clear)")

    # (b-g) one panel per category, per model; their legend sits above (b)
    first = None
    for i, (cat, code) in enumerate(code_of.items()):
        r, col = divmod(i, 3)
        bx = fig.add_subplot(grid[r, col], sharex=first, sharey=first)
        first = first or bx
        for fam, fam_models in groups.items():
            c = FIGURE1_COLORS[fam]
            for m in fam_models:
                for dx, s, fill in ((-0.2, up[cat, m], c), (0.2, st[cat, m], tint(c, 0.62))):
                    bx.bar(xs[m] + dx, s["rate"], width=0.38, color=fill, edgecolor=c, linewidth=1, zorder=2)
                    bx.errorbar([xs[m] + dx], [s["rate"]], yerr=[[s["rate"] - s["lo"]], [s["hi"] - s["rate"]]],
                                fmt="none", ecolor=INK, elinewidth=0.8, capsize=0, zorder=3)
                    if not s["rate"]:  # a 0 % bar is invisible; say it is a value, not a gap
                        bx.text(xs[m] + dx, 1, "0", ha="center", va="bottom", fontsize=6.5, color=INK_2)
        bx.plot([xs[m] - 0.2 for m in on_paper], [paper[m]["cir"][cat] for m in on_paper], zorder=6, clip_on=False,
                **PAPER_MARKER | {"markersize": 6})
        style_axes(bx, "IR (%)" if col == 0 else None)
        bx.set_title(f"({'bcdefg'[i]}) {cat} ({code})", loc="left", fontsize=9.5, color=INK, fontweight="bold")
        bx.set_xticks([xs[m] for m in models], models, rotation=40, ha="right")
        bx.tick_params(labelbottom=r == 1, labelleft=col == 0)
    assert first is not None
    first.set_xlim(-0.6, max(xs.values()) + 0.6)
    handles = [Patch(facecolor=fill, edgecolor=FIGURE1_COLORS[f], linewidth=1.2, label=f"{f} models, {name}")
               for f in groups for fill, name in ((FIGURE1_COLORS[f], f"upstream judge ({judge})"),
                                                  (tint(FIGURE1_COLORS[f], 0.62), "strict judge (% clear)"))]
    handles.append(Line2D([], [], **PAPER_MARKER, label="paper (Table 1 CIR, all 76 tasks, T = 0)"))
    first.legend(handles=handles, loc="lower left", bbox_to_anchor=(0, 1.13), ncol=3, frameon=False, fontsize=8.5,
                 handlelength=1.8, columnspacing=1.4)
    return save(fig, out_dir, f"figure11_categories_{judge}")
