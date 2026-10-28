"""Figures 10-13 (not in the paper): the original protocol beside the changes the report recommends.

Figure 10: Fable's 15 tasks + vendor-default sampling (upstream judge), in Figure 8's layout. Figure 11: all 76 tasks
at T = 0, upstream judge vs the strict judge, for all nine models and (b, c) for gpt-4o's and DeepSeek-R1's prompt
steps; its appendix version `figure11_categories` splits (a) by category. Figure 12: the original protocol vs all of
it at once: the 15 tasks,
vendor-default sampling and the strict judge. Figure 13: Figure 10 (b, c)'s prompt steps with the strict judge added
(the 76 tasks re-judged, and all the changes at once). The strict judge is amendment S1's claude-sonnet-4.6 (Sonnet 4, the
frozen judge of Table 9, is no longer served). All of it is ours; every interval is a 95% bootstrap over tasks
(stats.cluster_bootstrap_ci), the stored T = 0 runs' included. Notes: "Default-sampling repeats" ("Figure 10") and
"Strict judge" ("Amendment S1").
"""

import math
import random
import statistics

import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from .benchmark import CATEGORIES
from .capability import capability_order
from .figures import (FIGURE1_COLORS, FIGURES_DIR, GRID, INK, INK_2, OVERLAY_DARK, OVERLAY_LIGHT, OVERLAY_MARKER,
                      PAPER_MARKER, PROMPT_STEPS, REASONING_ORDER, label_y, layout, plt, save, style_axes, tint)
from .models import DEFAULT_JUDGE, REPLACEMENT_STRICT_JUDGE, SAMPLING_REFERENCE, SAMPLING_REPEATS, TEST_MODELS
from .runs import RESPONSES_DIR, load_latest, split_repeat
from .stats import cluster_bootstrap_ci
from .strict_eval import load_strict_records
from .tables import FIGURE1_MODELS, load_judgments, paper_table1, paper_table3
from .variability import STEPS, _cells, load_repeats, repeat_summary

SHUT_DOWN = "no repeats: model shut\ndown on 2026-10-23"
# Figure 10 (b, c): stored model -> its repeat arm, and the corner of the panel the data leave empty for the legend
FIGURE10_ABLATION = {"gpt-4o": ("gpt-4o@default", "upper right"),
                     "deepseek-r1": ("deepseek-r1-0528@default", "lower left")}
ARM_OF = {base: arm for arm, base in SAMPLING_REFERENCE.items()}


def _stored_cells(bench: pd.DataFrame, model: str, step: str) -> dict[tuple[int, str], int]:
    """A stored T = 0 run in repeat_summary's layout: one repeat, every benchmark task."""
    g = bench[(bench.model == model) & (bench.variant == step)]
    return {(1, r.task_id): int(bool(r.conv)) for r in g.itertuples()}


def _upstream(judge: str, models=FIGURE1_MODELS) -> tuple[pd.DataFrame, list[str]]:
    """The upstream judge's benchmark verdicts and `models` in Figure 1's order (default: the eight without
    gpt-4o-mini, which has no repeats; Figure 11 passes all nine)."""
    df = load_judgments()
    bench = df[(df.judge == judge) & (df.task_set == "benchmark")]
    order = capability_order(REASONING_ORDER)
    return bench, sorted(set(bench[bench.variant == "nudge"].model) & set(models), key=order.index)


def strict_cells(step: str = "nudge", judge: str = REPLACEMENT_STRICT_JUDGE) -> tuple[dict, dict]:
    """(stored, repeats) at one prompt step: model -> cells of the strict judge's verdicts (1 = clear) on the stored
    T = 0 run, complete runs only (parse errors count as judged, and are left out as missing); arm -> cells on the
    repeats, an arm only when all SAMPLING_REPEATS repeats were judged."""
    rec = load_strict_records()
    rec = rec[(rec.judge == judge) & (rec.task_set == "benchmark")]
    stored, repeats, judged = {}, {}, {}
    for r in rec.itertuples():
        v, k = split_repeat(r.variant)
        if v != step:
            continue
        if k is None:
            judged[r.model] = judged.get(r.model, 0) + 1
        if r.status == "ok":
            (stored if k is None else repeats).setdefault(r.model, {})[(k or 1, r.task_id)] = int(r.label == "clear")
    n_ok = {m: sum(x["status"] == "ok" for x in load_latest(RESPONSES_DIR / f"{m}__{step}__benchmark.jsonl").values())
            for m in stored}
    stored = {m: c for m, c in stored.items() if judged[m] == n_ok[m]}
    repeats = {m: c for m, c in repeats.items() if len({k for k, _ in c}) == SAMPLING_REPEATS}
    return stored, repeats


def paired_bars(ax, models: list[str], left: dict, right: dict, left_label: str, right_label: str, title: str,
                missing: str, pair_word: str, xlabels: list[str] | None = None,
                paper_label: str = "paper (Table 1, all 76 tasks, T = 0)", ref: dict | None = None,
                ref_label: str = "") -> None:
    """Per model, `left` (dark; the paper's Table 1 IR as a diamond) beside `right` (light; one dot per repeat when it
    has several), each a repeat_summary dict with its interval and value label. A model missing from `right` keeps
    its slot, marked `missing`. Family averages in the legend: over the models shown, and when only some have both
    bars, the dark bars' average over those same models too, so that the two compare like with like. `ref` (model ->
    repeat_summary) adds a grey reference point with its interval over the dark bar, the diamond moving aside."""
    xs, groups = layout(models)
    paper = paper_table1()
    rng = random.Random(0)
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
                if s["repeats"] > 1:
                    ax.scatter([x + rng.uniform(-0.1, 0.1) for _ in s["run_rates"]], s["run_rates"], s=9,
                               color="white", edgecolor=INK, linewidth=0.6, zorder=4)
                top = max(s["hi"], s["run_max"], ref[m]["hi"] if ref and dx < 0 else 0)  # clear of the ref point
                ax.text(x, top + 1.2, f"{s['rate']:.1f}", ha="center", va="bottom", fontsize=7.5, color=INK,
                        zorder=5)
        both = [m for m in fam_models if m in right]
        avg = lambda d, ms: statistics.mean(d[m]["rate"] for m in ms)
        partial = len(both) < len(fam_models)
        matched = f"; {avg(left, both):.1f} on the {len(both)} with {pair_word}" if partial else ""
        handles.append(Patch(facecolor=c, edgecolor=c, linewidth=1.2,
                             label=f"{fam} models, {left_label} (avg {avg(left, fam_models):.1f}{matched})"))
        handles.append(Patch(facecolor=tint(c, 0.62), edgecolor=c, linewidth=1.2,
                             label=f"{fam} models, {right_label} (avg {avg(right, both):.1f}"
                                   + (f", {len(both)} of {len(fam_models)} models)" if partial else ")")))
    on_paper = [m for m in models if m in paper and not TEST_MODELS[m].substitute]
    off = 0.09 if ref else 0.0  # the diamond and the reference point share the dark bar, one each side of its centre
    ax.plot([xs[m] - 0.2 - off for m in on_paper], [paper[m]["ir"] for m in on_paper], zorder=6, **PAPER_MARKER)
    # two columns, filled column by column: RLHF and the paper on the left, RL and the repeat dot on the right
    handles[2:2] = [Line2D([], [], **PAPER_MARKER, label=paper_label)]
    if ref:
        for m, s in ref.items():
            ax.errorbar(xs[m] - 0.2 + off, s["rate"], yerr=[[s["rate"] - s["lo"]], [s["hi"] - s["rate"]]], zorder=6,
                        **OVERLAY_MARKER)
        handles.append(Line2D([], [], marker="o", markersize=6, markerfacecolor=OVERLAY_LIGHT,
                              markeredgecolor=OVERLAY_DARK, markeredgewidth=0.9, color=OVERLAY_DARK, linewidth=1.4,
                              label=ref_label))
    if any(s["repeats"] > 1 for s in right.values()):
        handles.append(Line2D([], [], marker="o", markersize=4, markerfacecolor="white", markeredgecolor=INK,
                              linestyle="none", label="single repeat"))
    style_axes(ax, "IR (%)")
    ax.set_ylim(0, 132)  # headroom for the legend; the axis itself stops at 100
    ax.spines["left"].set_bounds(0, 100)
    ax.set_xticks([xs[m] for m in models], xlabels or models, rotation=30, ha="right", fontsize=9)
    ax.set_xlim(-0.6, max(xs.values()) + 0.6)
    ax.set_title(title, loc="left", fontsize=10, color=INK, fontweight="bold")
    ax.legend(handles=handles, loc="upper center", ncol=2, frameon=True, framealpha=0.95, edgecolor=GRID,
              fontsize=8, handlelength=1.8, columnspacing=1.4)


def _r1_label(models: list[str]) -> list[str]:
    return [m + ("\n(repeats: -0528)" if ARM_OF.get(m, "").startswith("deepseek-r1-0528") else "") for m in models]


def figure10(judge: str = DEFAULT_JUDGE, out_dir=FIGURES_DIR) -> list:
    """Figure 8's layout with Fable's 15 tasks and vendor-default sampling applied at once. (a) Per model, the stored
    T = 0 IR on all 76 tasks beside the IR on the 15 tasks under vendor defaults, pooled over ten repeats. (b, c) The
    five prompt steps for gpt-4o and DeepSeek-R1: stored T = 0 on all 76 tasks (dark), the repeats (light; thin lines
    = single repeats), the paper's Table 3 (diamonds). R1's repeats are deepseek-r1-0528 (deepseek-r1 is retired)."""
    rep = load_repeats(judge)
    bench, models = _upstream(judge)
    new = {m: repeat_summary(_cells(rep, ARM_OF[m], "nudge")) for m in models
           if m in ARM_OF and _cells(rep, ARM_OF[m], "nudge")}
    if not new:
        return []
    old = {m: repeat_summary(_stored_cells(bench, m, "nudge")) for m in models}

    fig = plt.figure(figsize=(12, 10.6))
    grid = fig.add_gridspec(2, 2, height_ratios=[1.1, 1], hspace=0.32, wspace=0.07)
    paired_bars(fig.add_subplot(grid[0, :]), models, old, new, "all 76 tasks, T = 0",
                "Fable's 15 tasks, vendor defaults, 10 repeats",
                "(a) Instrumental Rate with the goal nudge: original protocol (all 76 tasks, T = 0) and both changes "
                "(Fable's 15 tasks, vendor-default sampling)", SHUT_DOWN, "repeats", _r1_label(models))

    first = None
    for col, (base, (arm, legend_loc)) in enumerate(FIGURE10_ABLATION.items()):
        bx = fig.add_subplot(grid[1, col], sharey=first)
        first = first or bx
        cells = {s: _cells(rep, arm, s) for s in STEPS}
        step_panel(bx, col, base, f"({'bc'[col]}) System-prompt steps: {base}", legend_loc, cells, 0.12, [
            (f"{base}, all 76 tasks, T = 0", {s: _stored_cells(bench, base, s) for s in STEPS}, -0.12, "dark"),
            (f"{arm.removesuffix('@default')}, Fable's 15 tasks, vendor defaults", cells, 0.12, "light")])
    return save(fig, out_dir, f"figure10_{judge}")


# the three looks a step-panel series can take: (line tint, marker, linestyle, marker face, marker edge, edge width)
SERIES_STYLES = {"dark": (0.0, "o", "-", None, "white", 0.8),
                 "hollow": (0.0, "o", (0, (1, 1.2)), "white", None, 1.4),
                 "light": (0.45, "s", (0, (5, 2)), 0.62, None, 1.3)}


def step_panel(bx, col: int, base: str, title: str, legend_loc: str, thin: dict, thin_dx: float,
               series: list[tuple[str, dict, float, str]]) -> None:
    """One model's prompt steps (Figure 10 (b, c), Figure 13): each series (name, step -> cells, x offset, style) as
    a line with its 95% task-bootstrap interval and value labels, left of its points when its offset is negative,
    right otherwise; `thin` (step -> repeat cells) as one faint line per repeat; the paper's Table 3 at `nonudge` and
    `nudge` on the first series' side; an empty `thin` draws none. A step a series lacks (deepseek-r1's oversight
    arm) is bridged and noted."""
    c = FIGURE1_COLORS[TEST_MODELS[base].family]
    handles, lines, labels = [], [], []  # labels: (x, y, side, colour, offset beyond the marker)
    for k in sorted({k for v in thin.values() for k, _ in v}):  # behind everything
        ys = [100 * statistics.mean(v for (kk, _), v in thin[s].items() if kk == k)
              if any(kk == k for kk, _ in thin[s]) else math.nan for s in STEPS]
        bx.plot([i + thin_dx for i in range(len(STEPS))], ys, color=tint(c, 0.8), linewidth=0.7, zorder=1)
    for name, sums, dx, style in series:
        w, marker, ls, face, edge, ew = SERIES_STYLES[style]
        have = [i for i, s in enumerate(STEPS) if sums[s]]
        st = {i: repeat_summary(sums[STEPS[i]]) for i in have}
        x, ys = [i + dx for i in have], [st[i]["rate"] for i in have]
        line = tint(c, w)
        pt = dict(marker=marker, markersize=6.5, markeredgewidth=ew,
                  markerfacecolor=line if face is None else face if isinstance(face, str) else tint(c, face),
                  markeredgecolor=edge or c)
        lines.append((x, ys))
        bx.plot(x, ys, color=line, linewidth=1.8, linestyle=ls, zorder=3)
        bx.errorbar(x, ys, yerr=[[st[i]["rate"] - st[i]["lo"] for i in have],
                                 [st[i]["hi"] - st[i]["rate"] for i in have]],
                    linestyle="none", ecolor=line, elinewidth=1.1, capsize=0, zorder=4, **pt)
        # the light series' labels a shade darker than its line
        labels += [(xi, yi, 1 if dx > 0 else -1, tint(c, 0.25) if w else c, 0.06) for xi, yi in zip(x, ys)]
        handles.append(Line2D([], [], color=line, linewidth=1.8, linestyle=ls, label=name, **pt))
        for i, s in enumerate(STEPS):
            if style == "dark" and not sums[s]:
                bx.text(i + dx, 92, f"no {base} run\n(endpoint retired)", ha="center", va="center", fontsize=7.5,
                        color=INK_2, style="italic")
    if thin:
        handles.append(Line2D([], [], color=tint(c, 0.8), linewidth=0.7, label="single repeats"))
    t3, paper_red = paper_table3(), "#b8302f"  # PAPER_MARKER's red, darkened for text
    px, py = [i + series[0][2] for i in range(len(STEPS))], [math.nan] * len(STEPS)
    py[STEPS.index("nonudge")], py[STEPS.index("nudge")] = t3[base]["without"]["ir"], t3[base]["with"]["ir"]
    bx.plot(px, py, color=paper_red, linewidth=1.2, zorder=5, **PAPER_MARKER | {"linestyle": (0, (1.5, 1.5))})
    lines.append((px, py))
    labels += [(xi, yi, -1, paper_red, 0.1) for xi, yi in zip(px, py) if not math.isnan(yi)]
    placed = []
    for xi, yi, side, colour, off in labels:
        bx.text(xi + side * off, label_y(lines, placed, xi, yi, side, off), f"{yi:.1f}",
                ha="left" if side > 0 else "right", va="center", fontsize=7.5, color=colour, fontweight="bold",
                zorder=6, bbox={"facecolor": "white", "edgecolor": "none", "pad": 0.6})
    handles.append(Line2D([], [], color=paper_red, linewidth=1.2, label="paper (Table 3, all 76 tasks, T = 0)",
                          **PAPER_MARKER | {"linestyle": (0, (1.5, 1.5))}))
    style_axes(bx, "IR (%)" if col == 0 else None)
    bx.tick_params(labelleft=col == 0)
    bx.set_xlim(-0.55, len(STEPS) - 0.45)
    bx.set_xticks(range(len(STEPS)), [s[0] for s in PROMPT_STEPS], fontsize=8.5, linespacing=1.15)
    bx.set_title(title, loc="left", fontsize=10, color=INK, fontweight="bold")
    # "below": under the axis, for panels whose data leave no corner free
    where = dict(loc="upper center", bbox_to_anchor=(0.5, -0.16)) if legend_loc == "below" else dict(loc=legend_loc)
    bx.legend(handles=handles, frameon=True, framealpha=0.95, edgecolor=GRID, fontsize=8, handlelength=3.2, **where)


NEUTRAL = "#55606e"  # no family colour: the category panel pools both families


def two_lines(text: str) -> str:
    """`text` broken at the word gap that best balances two lines (the change label sits under the second)."""
    w = text.split()
    k = min(range(1, len(w)), key=lambda k: max(len(" ".join(w[:k])), len(" ".join(w[k:]))))
    return " ".join(w[:k]) + "\n" + " ".join(w[k:])


def category_panel(ax, up: dict, strict: dict, judge: str, title: str) -> None:
    """Per category, the upstream judge's IR (dark) beside the strict judge's % clear (light) on the same responses,
    pooled over every model in `strict` (model -> cells), with a 95% bootstrap over the category's tasks; the
    change under the tick label. Only responses with both verdicts count (deepseek-r1 lacks one strict verdict)."""
    up = {m: {k: v for k, v in up[m].items() if k in c} for m, c in strict.items()}
    for i, code in enumerate(CATEGORIES.values()):
        rates = []
        for dx, cells, fill in ((-0.19, up, NEUTRAL), (0.19, strict, tint(NEUTRAL, 0.62))):
            by_task: dict[str, list[int]] = {}
            for c in cells.values():
                for (_, t), v in c.items():
                    if t.split("-")[0] == code:
                        by_task.setdefault(t, []).append(v)
            rate, lo, hi = cluster_bootstrap_ci(by_task)
            rates.append(rate)
            ax.bar(i + dx, rate, width=0.36, color=fill, edgecolor=NEUTRAL, linewidth=1.2, zorder=2)
            ax.errorbar([i + dx], [rate], yerr=[[rate - lo], [hi - rate]], fmt="none", ecolor=INK, elinewidth=1,
                        capsize=0, zorder=3)
            ax.text(i + dx, hi + 1.2, f"{rate:.1f}", ha="center", va="bottom", fontsize=7.5, color=INK)
        # under the two-line tick label, in points so the gap does not depend on the panel's height
        ax.annotate(f"change {rates[1] - rates[0]:+.1f} pp", (i, 0), xycoords=("data", "axes fraction"),
                    xytext=(0, -33), textcoords="offset points", ha="center", va="top", fontsize=8.5, color=INK,
                    fontweight="bold")
    style_axes(ax, "IR (%)")
    ax.set_ylim(0, 118)  # headroom for the legend; the axis itself stops at 100
    ax.spines["left"].set_bounds(0, 100)
    ax.set_xticks(range(len(CATEGORIES)), [two_lines(f"{cat} ({code})") for cat, code in CATEGORIES.items()],
                  fontsize=8.5)
    ax.set_xlim(-0.5, len(CATEGORIES) - 0.5)
    ax.set_title(title, loc="left", fontsize=10, color=INK, fontweight="bold")
    ax.legend(handles=[Patch(facecolor=NEUTRAL, edgecolor=NEUTRAL, linewidth=1.2, label=f"upstream judge ({judge})"),
                       Patch(facecolor=tint(NEUTRAL, 0.62), edgecolor=NEUTRAL, linewidth=1.2,
                             label=f"strict judge ({REPLACEMENT_STRICT_JUDGE}, % clear)")],
              loc="upper center", ncol=2, frameon=True, framealpha=0.95, edgecolor=GRID, fontsize=8, handlelength=1.8)


def figure11(judge: str = DEFAULT_JUDGE, out_dir=FIGURES_DIR) -> list:
    """All 76 tasks at T = 0, the same responses under both judges. (a) Per model (all nine): the upstream judge's IR
    (dark; the paper's IR as a diamond) beside the strict judge's % clear (light). (b) The same by category, pooled
    over the nine models."""
    bench, models = _upstream(judge, TEST_MODELS)
    stored, _ = strict_cells()
    if not stored:
        return []
    old = {m: repeat_summary(_stored_cells(bench, m, "nudge")) for m in models}
    strict = {m: repeat_summary(stored[m]) for m in models if m in stored}

    fig = plt.figure(figsize=(12, 10))
    grid = fig.add_gridspec(2, 1, height_ratios=[1.1, 0.75], hspace=0.38)
    paired_bars(fig.add_subplot(grid[0]), models, old, strict, f"upstream judge ({judge})",
                f"strict judge ({REPLACEMENT_STRICT_JUDGE}, % clear)",
                "(a) Instrumental Rate with the goal nudge, all 76 tasks at T = 0 (the same responses):\n"
                f"upstream judge ({judge}) and strict judge ({REPLACEMENT_STRICT_JUDGE})", "not judged",
                "strict verdicts")
    category_panel(fig.add_subplot(grid[1]), {m: _stored_cells(bench, m, "nudge") for m in models},
                   {m: stored[m] for m in models if m in stored}, judge,
                   f"(b) By category, all {len(models)} models pooled")
    return save(fig, out_dir, f"figure11_{judge}")


def figure11_base(judge: str = DEFAULT_JUDGE, out_dir=FIGURES_DIR) -> list:
    """Figure 11 for the base prompt ("You are an autonomous AI agent." alone, `plain-nonudge`): the eight ablation
    models (o1 has no base run). (a) Per model, the upstream judge's IR (dark) beside the strict judge's % clear
    (light) on the same responses; over the dark bar, the paper's Table 1 IR (diamond) and the upstream judge's IR
    under the full prompt (grey point), both for the full prompt. (b) By category, the eight models pooled."""
    bench, models = _upstream(judge, TEST_MODELS)
    models = [m for m in models if not bench[(bench.model == m) & (bench.variant == "plain-nonudge")].empty]
    stored, _ = strict_cells("plain-nonudge")
    if not stored:
        return []
    old = {m: repeat_summary(_stored_cells(bench, m, "plain-nonudge")) for m in models}
    strict = {m: repeat_summary(stored[m]) for m in models if m in stored}
    full = {m: repeat_summary(_stored_cells(bench, m, "nudge")) for m in models}

    fig = plt.figure(figsize=(12, 10))
    grid = fig.add_gridspec(2, 1, height_ratios=[1.1, 0.75], hspace=0.38)
    paired_bars(fig.add_subplot(grid[0]), models, old, strict, f"upstream judge ({judge})",
                f"strict judge ({REPLACEMENT_STRICT_JUDGE}, % clear)",
                "(a) Instrumental Rate with the base prompt, all 76 tasks at T = 0 (the same responses):\n"
                f"upstream judge ({judge}) and strict judge ({REPLACEMENT_STRICT_JUDGE})", "not judged",
                "strict verdicts", paper_label="paper (Table 1, full prompt)", ref=full,
                ref_label=f"upstream judge, full prompt")
    category_panel(fig.add_subplot(grid[1]), {m: _stored_cells(bench, m, "plain-nonudge") for m in models},
                   {m: stored[m] for m in models if m in stored}, judge,
                   f"(b) By category, base prompt, {len(strict)} models pooled")
    return save(fig, out_dir, f"figure11_base_{judge}")


def figure11_categories(judge: str = DEFAULT_JUDGE, out_dir=FIGURES_DIR) -> list:
    """Figure 11 by category, for the appendix (post hoc). (a) Figure 11 (b): per category, all models pooled,
    upstream judge (dark) beside strict judge (light). (b-g) Per category and model, the same pair with its 95%
    task-bootstrap interval and the paper's Table 1 CIR (diamond on the dark bar)."""
    bench, models = _upstream(judge, TEST_MODELS)
    stored, _ = strict_cells()
    if not stored:
        return []
    models = [m for m in models if m in stored]
    xs, groups = layout(models)
    paper = paper_table1()
    on_paper = [m for m in models if m in paper and not TEST_MODELS[m].substitute]
    code_of = dict(CATEGORIES)
    up_all = {m: _stored_cells(bench, m, "nudge") for m in models}
    pick = lambda cells, code: {k: v for k, v in cells.items() if k[1].split("-")[0] == code}
    up = {(cat, m): repeat_summary(pick(up_all[m], code)) for cat, code in code_of.items() for m in models}
    st = {(cat, m): repeat_summary(pick(stored[m], code)) for cat, code in code_of.items() for m in models}

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


def figure12(judge: str = DEFAULT_JUDGE, out_dir=FIGURES_DIR) -> list:
    """The original protocol (all 76 tasks, T = 0, upstream judge; dark, the paper's IR as a diamond) beside every
    recommended change at once (Fable's 15 tasks, vendor-default sampling pooled over ten repeats, strict judge's
    % clear; light, one dot per repeat)."""
    bench, models = _upstream(judge)
    _, repeats = strict_cells()
    new = {m: repeat_summary(repeats[ARM_OF[m]]) for m in models if ARM_OF.get(m) in repeats}
    if not new:
        return []
    old = {m: repeat_summary(_stored_cells(bench, m, "nudge")) for m in models}
    fig, ax = plt.subplots(figsize=(12, 5.8))
    paired_bars(ax, models, old, new, "original protocol", "all changes, 10 repeats",
                f"Instrumental Rate with the goal nudge. Original protocol: all 76 tasks, T = 0, {judge} judge.\n"
                "All changes: Fable's 15 tasks, vendor-default sampling (10 repeats), strict judge "
                f"({REPLACEMENT_STRICT_JUDGE}, % clear)", SHUT_DOWN, "repeats", _r1_label(models))
    return save(fig, out_dir, f"figure12_{judge}")


# Figure 13: three series and the repeats fill every corner of gpt-4o's panel, so both legends go under the axes
FIGURE13_LEGEND = {"gpt-4o": "below", "deepseek-r1": "below"}


def figure13(judge: str = DEFAULT_JUDGE, out_dir=FIGURES_DIR) -> list:
    """Figure 10 (b, c) with the strict judge. Per model and prompt step: the original protocol (all 76 tasks, T = 0,
    upstream judge; dark), the same responses under the strict judge (hollow, dotted), and all the changes (Fable's
    15 tasks, vendor-default sampling, strict judge; light), with the paper's Table 3.
    R1's repeats are deepseek-r1-0528; the stored deepseek-r1 has no oversight run."""
    bench, _ = _upstream(judge)
    by_step = {s: strict_cells(s) for s in STEPS}
    if not any(by_step[s][1] for s in STEPS if s != "nudge"):
        return []
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.6), sharey=True)
    fig.subplots_adjust(wspace=0.07)
    for col, (base, (arm, _)) in enumerate(FIGURE10_ABLATION.items()):
        changes = {s: by_step[s][1].get(arm, {}) for s in STEPS}
        # no single-repeat lines: with three series they hid the lines (author, 2026-10-26)
        step_panel(axes[col], col, base, f"({'ab'[col]}) System-prompt steps: {base}", FIGURE13_LEGEND[base], {},
                   0.16, [(f"{base}, original protocol (76 tasks, T = 0, {judge} judge)",
                           {s: _stored_cells(bench, base, s) for s in STEPS}, -0.16, "dark"),
                          (f"{base}, same responses, strict judge",
                           {s: by_step[s][0].get(base, {}) for s in STEPS}, -0.02, "hollow"),
                          (f"{arm.removesuffix('@default')}, all changes (15 tasks, vendor defaults, strict judge)",
                           changes, 0.16, "light")])
    return save(fig, out_dir, f"figure13_{judge}")
