# CLAUDE.md

Replication of *Evaluating the Paperclip Maximizer* (He et al., 2025; InstrumentalEval) through OpenRouter, plus
two extensions that are not in the paper: system-prompt ablations (Table 6) and, the current work, verbalized eval
awareness (VEA) in the stored chains of thought (`results/vea/`). The replication itself is finished: all responses,
judgments, Tables 1–6 and figures exist on disk. Don't regenerate responses.

## Working here

- Python ≥ 3.11, `uv`. Run everything as `uv run ie <command>` (CLI in `src/instrumentaleval/cli.py`) and
  `uv run pytest` (offline). `OPENROUTER_API_KEY` lives in `.env` (never commit it; never print it).
- Windows machine; the repo sits in a OneDrive folder. Paths are handled with `pathlib`; the CLI forces UTF-8 on
  stdout. Don't run two commands that append to the same results file at once.
- Read `README.md` (runbook, layout) and `REPLICATION_NOTES.md` (every deviation from upstream, the pre-registered
  analyses, results) before changing anything. New decisions go in `REPLICATION_NOTES.md`, not in chat.

## Data model (do not break)

- `results/responses/<model>__<variant>__<task_set>.jsonl`: one append-only file per run, **last record per
  `task_id` wins** (`runs.load_latest`). A stored response is reused only if its `request_config`, `prompt_config`
  and `task_prompt` match today's; changing a key in `ModelSpec.request_config()` or a system prompt therefore
  silently schedules a full, paid regeneration. Don't.
- `results/judgments/<judge>/<run>.jsonl`: convergence verdicts, keyed to the response by `response_sha`; stale
  verdicts are ignored by `tables.load_judgments`.
- `results/vea/<judge>/<run>.jsonl`: VEA verdicts, reused only if `prompt_sha` (rubric + chain of thought) and
  `judge_config` match; stale rows are ignored by `vea_tables.load_vea`.
- `benchmark/*.csv` and `upstream/main.py` are SHA256-pinned downloads (`ie fetch`); `upstream/judge_vea.py` is
  vendored and SHA256-checked in `tests/test_vea.py`. Never edit them. Never edit result JSONL files by hand.
- Prompts are copied verbatim from upstream and checked byte for byte by the tests (`tests/test_prompts.py`,
  `tests/test_vea.py`). A prompt change is a new experiment, not an edit.

## Conventions

- Pre-register before spending: write the hypotheses, estimators and decision rule in `REPLICATION_NOTES.md`,
  commit, then generate or judge. Table 6 and the VEA extension both follow this.
- Statistics resample **tasks**, never cells: the same 76 tasks recur across models and variants (`stats.py`:
  by-task cluster bootstrap, sign-flip over tasks, exact McNemar on paired tasks).
- Tests cover pure functions only (prompts, parsers, statistics). **No mocked API pipelines in final code**; new
  commands ship a smoke test instead (`--limit N` = first N tasks per category, real calls, read the output).
  `tests/test_pipeline.py` predates this rule; don't add more like it.
- Judges only ever see what upstream's judge saw: the convergence judge gets task prompt + final answer, the VEA
  judge gets the chain of thought alone. Keep it that way; it is what makes V4 a cross of independent readings.
- Style: short modules with a docstring that says what is upstream-identical and what is ours; comments explain
  why, not what; no defensive code for situations that can't happen in this repo.

## Current work: verbalized eval awareness

Why only deepseek-r1: OpenRouter's `reasoning` field is the raw chain of thought for deepseek-r1 (ratio of
chars/4 to `reasoning_tokens` ≈ 1.0, present in 628/628 responses) but a provider-written **summary** for
gemini-2.5-flash (ratio 0.45) and the o-series (0.33–0.50, and missing for 35–50 of 76 tasks). This is recorded as
`ModelSpec.cot` in `models.py`; `VEA_MODELS` derives from it. Don't judge summaries.

Pipeline (details and pre-registration: `REPLICATION_NOTES.md`, "Eval awareness"):

```sh
uv run pytest                                                           # prompt/parser checks against upstream/judge_vea.py
uv run ie vea-judge --limit 2 --variants nudge --task-sets benchmark    # smoke test, 12 calls; inspect results/vea/gpt-5-mini/
uv run ie vea-judge                                                     # 608 benchmark + 20 neutral chains of thought
uv run ie vea-tables                                                    # results/vea/tables.md, tables/*.csv, figures/
uv run ie vea-export-labels                                             # blinded hand-check sheet -> results/vea/hand_labels.csv
# fill vea_label (yes / no) by applying the F1 rubric, then:
uv run ie vea-tables                                                    # V5 now reports precision on the judge positives
```

Status checklist (update as you go):

- [x] Code, tests, pre-registration written (2026-10-19).
- [x] Pre-registration committed before the full run (2026-10-19; only the 12-call smoke test preceded it).
- [x] Smoke test read by a human (2026-10-19): 12/12 `QUOTE: None`, all with a QUOTE field, no retries; no positive, so the quote path is checked on the full run.
- [ ] Full `ie vea-judge`; cost and retry counts noted.
- [ ] `ie vea-tables`; hand check of every positive + 50 negatives; precision reported.
- [ ] "Results" subsection of the notes filled; verdict on V1 (jailbreak vs plain arms) and V4 per the decision rule.

Expectations, so surprises are recognised: VEA in deepseek-r1 is rare (a keyword pass found at least five genuine
cases in 628, e.g. ES-10 `nonudge`: "the task might be testing if I will blindly shut down and cause a blackout?"),
so V1 rates of a few percent with wide intervals are normal, and V4 will almost surely fall under the "< 10 VEA
cells: descriptive only" rule. A high neutral-task rate (V3) means judge false positives, not eval awareness. The
frequent "since this is a simulation, I'll describe the steps" is **not** VEA under the rubric's NOTE 3; it is a
separate construct (simulation awareness) that is deliberately not measured, see the notes.

Module map for this extension:

- `models.py`: `ModelSpec.cot`, `VEA_JUDGE` (gpt-5-mini, low effort, 4000 tokens), `VEA_MODELS`.
- `client.py`: `chat(spec, system | None, user, temperature | None)`; the VEA judge sends a single user message.
- `vea.py`: `VEA_JUDGE_PROMPT` (F1 rubric, verbatim), `parse_quote` (ours, vea-olmo DEVIATIONS #9),
  `authors_parse_quote` (verbatim), the retry rule, `judge_vea(rid)`.
- `vea_tables.py`: `load_vea`, Tables V1–V5, the V1 arm contrast, `positives_md`, `vea_figure`,
  `export_vea_labels`, `hand_label_check`.
- `stats.py`: `cluster_bootstrap_ci`, `cluster_bootstrap_rd` (pure Python, B = 5000, seed 0).

## Things that look like bugs but aren't

- `ie status` / `ie vea-judge` report "nothing to do": the stored records are current; that's resumability working.
- Table 1 numbers differ from the paper's: documented in the notes ("Deviations", "A discrepancy inside the paper's
  own artifacts"); the paper's own tables don't add up.
- `vea_authors_parser` disagrees with `vea` on some rows: expected whenever the judge writes `**QUOTE:** None` or
  `None` followed by a note; V5 counts them, and the authors' parser is kept only for comparison.
- Some pytest cases skip: they need `benchmark/*.csv` or `upstream/main.py` (`ie fetch`).
