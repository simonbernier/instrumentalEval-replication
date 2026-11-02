"""Interactive Figure 1 (ours, not in the paper) -> results/interactive/ir_explorer.{html,json}.

Figure 1's layout (overall IR + one panel per category, RLHF then RL) as one self-contained HTML page: the reader
picks one of Figure 6's five prompt steps (PROMPT_STEPS) and one of four judges (the three convergence judges and
amendment S1's strict judge, % `clear`), and the bars move. Stored verdicts only: a (judge, step, model) cell
without verdicts is drawn as a placeholder with the reason. The numbers are those of Tables 1 and 6 and Figures 6
and 11 (95% Wilson intervals; family averages = mean of model rates with a by-task cluster bootstrap CI, drawn when
at most one of the family's models is missing). The page itself is `templates/ir_explorer.html`: vanilla JS and
SVG, no external library, so it can be copied into the Jekyll site as one file. Notes: "Interactive Figure 1".
"""

import difflib
import json
import re
import shutil
from datetime import date
from pathlib import Path

import pandas as pd
from matplotlib.colors import to_hex

from . import RESULTS_DIR
from .benchmark import CATEGORIES
from .capability import capability_order
from .figures import FIGURE1_COLORS, FIGURE1_FILLS, PROMPT_STEPS, REASONING_ORDER, SHORT_NAMES, family_avg_cis
from .models import DEFAULT_JUDGE, REPLACEMENT_STRICT_JUDGE, TEST_MODELS
from .prompts import SYSTEM_PROMPTS
from .stats import wilson_ci
from .strict_eval import load_strict_records, strict_frame, strict_name
from .tables import cir_counts, load_judgments, paper_table1

OUT_DIR = RESULTS_DIR / "interactive"
TEMPLATE = Path(__file__).parent / "templates" / "ir_explorer.html"
N_TASKS = 76
STRICT = strict_name(REPLACEMENT_STRICT_JUDGE)
# (key in the tidy frame, button label)
JUDGE_VIEWS = [(DEFAULT_JUDGE, "GPT-4o"), ("gemini-2.5-flash", "Gemini 2.5 Flash"), ("claude-sonnet-4", "Claude Sonnet 4"),
               (STRICT, "Strict (Sonnet 4.6)")]
STEP_LABELS = {"plain-nonudge": "Base", "oversight-nonudge": "+ no human oversight", "nocause-nonudge": "+ 7 rules",
               "nonudge": "+ “good cause”", "nudge": "+ nudge (full prompt)"}
NOT_SERVED = {"claude-sonnet-4"}
# the post calls the RL family by its training method, RL with verifiable rewards
FAMILY_NAMES = {"RLHF": "RLHF", "RL": "RLVR"}
# axis labels of the narrow category panels
ABBR = {"gpt-4o-mini": "4o-mini", "gpt-4o": "GPT-4o", "qwen-2.5-72b": "Qwen-72B", "deepseek-v3": "DS-V3",
        "deepseek-r1": "DS-R1", "o3-mini": "o3-mini", "gemini-2.5-flash": "Gem-Flash", "o1": "o1", "o4-mini": "o4-mini"}


def missing_reason(model: str, variant: str, judge: str) -> str:
    """Why a (judge, step, model) cell has no verdicts, in a sentence for the tooltip."""
    if model == "o1" and variant != "nudge":
        return "o1 was only run with the full prompt (no ablation runs)."
    if model == "deepseek-r1" and variant == "oversight-nonudge":
        return "No responses: OpenRouter retired DeepSeek-R1 before this step was added."
    if judge in NOT_SERVED:
        return "This judge was not run on these responses, and it is no longer served."
    return "This judge was not run on these responses."


def prompt_diff(old: str, new: str) -> list[list]:
    """`new` as [[text, added], ...] spans, word-level against `old` (a step can insert in the middle)."""
    tok = lambda s: re.findall(r"\s+|\w+|[^\w\s]", s)
    a, b = tok(old), tok(new)
    spans: list[list] = []
    for op, _, _, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        text, added = "".join(b[j1:j2]), op != "equal"
        if not text:
            continue
        if spans and spans[-1][1] == added:
            spans[-1][0] += text
        else:
            spans.append([text, added])
    return spans


def _cell(counts: pd.DataFrame, model: str) -> dict:
    cm = counts.loc[model]
    k, n = int(cm["k"].sum()), int(cm["n"].sum())
    cats = {}
    for cat, code in CATEGORIES.items():
        if cat in cm.index:
            ck, cn = int(cm.loc[cat, "k"]), int(cm.loc[cat, "n"])
            cats[code] = [ck, cn, *(round(x, 2) for x in wilson_ci(ck, cn))]
    return {"k": k, "n": n, "lo": round(wilson_ci(k, n)[0], 2), "hi": round(wilson_ci(k, n)[1], 2), "cats": cats}


def family_average_models(present: list[str], family: list[str]) -> list[str] | None:
    """The models a family average is taken over, or None when more than one of the family is missing (an
    average over half a family says little, and would jump between steps)."""
    have = [m for m in family if m in present]
    return have if len(family) - len(have) <= 1 and have else None


def explorer_data(df: pd.DataFrame | None = None) -> dict:
    if df is None:
        rec = load_strict_records()
        df = pd.concat([load_judgments(), strict_frame(rec[rec.judge == REPLACEMENT_STRICT_JUDGE])],
                       ignore_index=True)
    order = capability_order(REASONING_ORDER)
    models = sorted(TEST_MODELS, key=order.index)
    families = {f: [m for m in models if TEST_MODELS[m].family == f] for f in ("RLHF", "RL")}
    paper = paper_table1()
    codes = CATEGORIES
    cells, averages = {}, {}
    for judge, _ in JUDGE_VIEWS:
        cells[judge], averages[judge] = {}, {}
        for _, variant in PROMPT_STEPS:
            counts = cir_counts(df, judge, variant)
            present = sorted(set(counts.index.get_level_values(0)), key=order.index) if not counts.empty else []
            cells[judge][variant] = {m: _cell(counts, m) if m in present else {"missing": missing_reason(m, variant, judge)}
                                     for m in models}
            groups = {f: g for f, fam in families.items() if (g := family_average_models(present, fam))}
            cis = family_avg_cis(df, judge, groups, variant) if groups else {}
            averages[judge][variant] = {
                f: {"models": groups[f], "avg": round(sum(cells[judge][variant][m]["k"] / cells[judge][variant][m]["n"]
                                                          for m in groups[f]) * 100 / len(groups[f]), 2),
                    "lo": round(cis[f][0], 2), "hi": round(cis[f][1], 2)} if f in groups else None
                for f in families}
    steps, previous = [], ""
    for _, variant in PROMPT_STEPS:
        steps.append({"variant": variant, "label": STEP_LABELS[variant],
                      "prompt": prompt_diff(previous, SYSTEM_PROMPTS[variant])})
        previous = SYSTEM_PROMPTS[variant]
    return {
        "generated": date.today().isoformat(),
        "n_tasks": N_TASKS,
        "families": {f: {"name": FAMILY_NAMES[f], "color": FIGURE1_COLORS[f], "fill": to_hex(FIGURE1_FILLS[f])}
                     for f in families},
        "categories": [{"name": cat, "code": code} for cat, code in codes.items()],
        "models": [{"key": m, "name": SHORT_NAMES[m], "abbr": ABBR[m], "family": TEST_MODELS[m].family,
                    "note": TEST_MODELS[m].label.removeprefix(m).strip(" ()"),
                    "paper": ({"name": paper[m]["paper_name"], "ir": paper[m]["ir"],
                               "cats": {codes[c]: v for c, v in paper[m]["cir"].items()}}
                              if m in paper and not TEST_MODELS[m].substitute else None)}
                   for m in models],
        "steps": steps,
        "judges": [{"key": k, "label": label, "strict": k == STRICT} for k, label in JUDGE_VIEWS],
        "cells": cells,
        "averages": averages,
    }


def write_explorer(out_dir: Path = OUT_DIR, copy_to: Path | None = None) -> list[Path]:
    """results/interactive/ir_explorer.json (the numbers) and ir_explorer.html (the page, data inlined)."""
    data = explorer_data()
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    (out_dir / "ir_explorer.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", payload.replace("</", "<\\/"))
    (out_dir / "ir_explorer.html").write_text(html, encoding="utf-8")
    paths = [out_dir / "ir_explorer.json", out_dir / "ir_explorer.html"]
    if copy_to is not None:
        copy_to.mkdir(parents=True, exist_ok=True)
        paths.append(Path(shutil.copy2(out_dir / "ir_explorer.html", copy_to / "ir_explorer.html")))
    return paths
