"""Figures 10-13 (not in the paper): the original protocol beside the changes the report recommends.

Figure 10: Fable's 15 tasks + vendor-default sampling (upstream judge), in Figure 8's layout. Figure 11: all 76 tasks
at T = 0, upstream judge vs the strict judge. Figure 12: the original protocol vs all of it at once: the 15 tasks,
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

from .capability import capability_order
from .figures import (FIGURE1_COLORS, FIGURES_DIR, GRID, INK, INK_2, PAPER_MARKER, PROMPT_STEPS, REASONING_ORDER,
                      label_y, layout, plt, save, style_axes, tint)
from .models import DEFAULT_JUDGE, REPLACEMENT_STRICT_JUDGE, SAMPLING_REFERENCE, SAMPLING_REPEATS, TEST_MODELS
from .runs import RESPONSES_DIR, load_latest, split_repeat
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


def _upstream(judge: str) -> tuple[pd.DataFrame, list[str]]:
    """The upstream judge's benchmark verdicts and the Figure 1 models in Figure 1's order."""
    df = load_judgments()
    bench = df[(df.judge == judge) & (df.task_set == "benchmark")]
    order = capability_order(REASONING_ORDER)
    return bench, sorted(set(bench[bench.variant == "nudge"].model) & set(FIGURE1_MODELS), key=order.index)


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
                missing: str, pair_word: str, xlabels: list[str] | None = None) -> None:
    """Per model, `left` (dark; the paper's Table 1 IR as a diamond) beside `right` (light; one dot per repeat when it
    has several), each a repeat_summary dict with its interval and value label. A model missing from `right` keeps
    its slot, marked `missing`. Family averages in the legend: over the models shown, and when only some have both
    bars, the dark bars' average over those same models too, so that the two compare like with like."""
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
                ax.text(x, max(s["hi"], s["run_max"]) + 1.2, f"{s['rate']:.1f}", ha="center", va="bottom",
                        fontsize=7.5, color=INK, zorder=5)
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
    ax.plot([xs[m] - 0.2 for m in on_paper], [paper[m]["ir"] for m in on_paper], zorder=6, **PAPER_MARKER)
    # two columns, filled column by column: RLHF and the paper on the left, RL and the repeat dot on the right
    handles[2:2] = [Line2D([], [], **PAPER_MARKER, label="paper (Table 1, all 76 tasks, T = 0)")]
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


def figure11(judge: str = DEFAULT_JUDGE, out_dir=FIGURES_DIR) -> list:
    """All 76 tasks at T = 0, per model: the upstream judge's IR (dark; the paper's IR as a diamond) beside the
    strict judge's % clear on the same responses (light)."""
    bench, models = _upstream(judge)
    stored, _ = strict_cells()
    if not stored:
        return []
    old = {m: repeat_summary(_stored_cells(bench, m, "nudge")) for m in models}
    strict = {m: repeat_summary(stored[m]) for m in models if m in stored}
    fig, ax = plt.subplots(figsize=(12, 5.8))
    paired_bars(ax, models, old, strict, f"upstream judge ({judge})", f"strict judge ({REPLACEMENT_STRICT_JUDGE}, % clear)",
                "Instrumental Rate with the goal nudge, all 76 tasks at T = 0 (the same responses):\n"
                f"upstream judge ({judge}) and strict judge ({REPLACEMENT_STRICT_JUDGE})", "not judged",
                "strict verdicts")
    return save(fig, out_dir, f"figure11_{judge}")


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
