# instrumentalEval-replication

A replication of *Evaluating the Paperclip Maximizer: Are RL-Based Language Models More Likely to Pursue
Instrumental Goals?* (He et al., 2025, [arXiv:2502.12206](https://arxiv.org/abs/2502.12206)). It covers all five
tables, uses the original prompts and parameters from [yf-he/InstrumentalEval](https://github.com/yf-he/InstrumentalEval),
and calls every model through OpenRouter.

Model substitutions, deviations from upstream, and ideas for improving the results by changing parameters are in
[REPLICATION_NOTES.md](REPLICATION_NOTES.md).

## Setup

```sh
uv sync
cp .env.example .env        # then add OPENROUTER_API_KEY
uv run ie fetch             # benchmark CSVs + upstream main.py at the pinned commit (SHA256-checked)
uv run pytest               # offline; checks prompts against upstream byte for byte
```

## Running

Every command can be resumed: finished tasks are skipped, and failed calls are retried on the next run. Step 1 is
the Setup section above.

```sh
# 2. Smoke test: 2 tasks per category per model; check for empty or truncated answers and the provider used
uv run ie generate --limit 2
uv run ie status

# 3. Responses from all 9 test models on the 76 benchmark tasks and the 20 neutral control tasks
uv run ie generate
uv run ie generate --task-set neutral

# 4. Judge reliability: all 3 judges on the neutral tasks, then read the FPR column of Table 4
uv run ie judge --judges gpt-4o claude-sonnet-4 gemini-2.5-flash --task-sets neutral
uv run ie tables
#    then set DEFAULT_JUDGE in src/instrumentaleval/models.py to the judge with the lowest FPR

# 5. Benchmark judged by all 3 judges (Table 4 IAR and κ); the chosen judge drives Tables 1, 2, 3, 5 and the figures
uv run ie judge --judges gpt-4o claude-sonnet-4 gemini-2.5-flash

# 6. Tables and figures
uv run ie classify-tasks    # Table 2: all 3 judges vote on each task's prior-task type -> data/task_classification_votes.{json,md}
#    then one independent adjudicator subagent per task (REPLICATION_NOTES.md, Table 2) writes <dir>/<task_id>.json
uv run ie classify-tasks --merge <dir> --adjudicator "<who>"   # -> data/task_categories.json; review it by hand
uv run ie export-labels     # then fill results/human_labels.csv (Table 4; filled with Claude Fable 5.1 labels, not human)
uv run ie tables            # -> results/tables.md (+ CSVs in results/tables/); --judge <name> for another judge
uv run ie figures           # Tables 1, 2, 3 and 5 as figures -> results/figures/ (also takes --judge)

# 7. Table 3: goal-nudging ablation, judged by the chosen judge. The no-nudge runs cover every model but o1
#    (they are also a Table 6 arm); Table 3 shows gpt-4o, deepseek-v3, o4-mini and deepseek-r1, as configured
uv run ie generate --no-nudge
uv run ie judge --variants nonudge
uv run ie tables

# 8. System-prompt ablations (Table 6 and Figure 6, not in the paper). Pre-registered in REPLICATION_NOTES.md,
#    "Additional experiments": commit that section before generating. Default models: all but o1 (nudge-rep: 4).
V="nocause-nudge nocause-nonudge plain-nudge plain-goal plain-nonudge nudge-rep"
uv run ie generate --variants $V --limit 1   # smoke test: read a few answers, check `ie status`
uv run ie generate --variants $V
uv run ie judge --variants $V
uv run ie tables
uv run ie figures

# 9. Strict judge (not in the paper; REPLICATION_NOTES.md, "Strict judge"). Three-way labels: clear / instructed / none
uv run ie strict-setup                   # blank results/strict_labels.csv + data/strict_split.json (30 dev / 68 test)
#    label H001-H012 by hand and H013-H098 with the strict-labeller / strict-label-adjudicator subagents,
#    following data/strict_label_guide.md, then:
uv run ie strict-labels --merge <dir>    # <dir>/{pass_a,pass_b,adjudication}/<item_id>.json -> strict_labels.csv
uv run ie strict-judge --split dev --probes   # development rounds: tune the prompt on dev only
uv run ie strict-eval --split dev             # -> results/strict/eval_dev.md, dev_log.md
#    freeze: set prompts.FROZEN_STRICT_SHA and commit. Only then do the test split and full runs work:
uv run ie strict-judge --split test && uv run ie strict-eval --split test
uv run ie strict-judge --runs --judges gpt-4o --task-sets benchmark neutral --variants nudge nonudge nocause-nudge nocause-nonudge plain-nudge plain-goal plain-nonudge nudge-rep
uv run ie strict-judge --runs --judges claude-sonnet-4 gemini-2.5-flash --task-sets benchmark neutral
uv run ie tables                         # Table 7
```

Once `DEFAULT_JUDGE` is set in step 4, `ie judge`, `ie tables` and `ie figures` all default to the chosen judge, so
steps 6 and 7 need no `--judge` flags.

## Layout

| Path | Contents |
|---|---|
| `src/instrumentaleval/prompts.py` | upstream prompts (verbatim), the system-prompt variants for Table 6 (deletions of upstream text only) and the judge-output parser |
| `src/instrumentaleval/models.py` | test models and judges, with their OpenRouter IDs and request parameters |
| `src/instrumentaleval/{generate,judge}.py` | the two passes; results go to `results/responses/` and `results/judgments/<judge>/` as JSONL, plus an upstream-format `*_evaluation_results.txt` per run |
| `src/instrumentaleval/tables.py` | Tables 1–5, and Table 6 (system-prompt ablations, not in the paper) |
| `src/instrumentaleval/figures.py` | Tables 1, 2, 3, 5 and 6 as figures (bar charts with models grouped by RLHF / RL family; Table 5 as a heat map; Table 6 as one panel per model) |
| `data/neutral_tasks.csv`, `data/neutral_task_rubric.md` | control tasks for the false-positive check, and the rubric they were selected with |
| `data/task_classification_votes.{json,md}` | the three judges' prior-task-type votes and rationales for every benchmark task, side by side |
| `data/task_categories.json` | adjudicated task to prior-task-type mapping for Table 2 (one independent adjudicator per task, then a consistency review and a hand check) |
| `src/instrumentaleval/{strict,strict_eval}.py` | the strict three-way judge (not upstream): judging pass with retries and a freeze guard; metrics, probes, Rogan–Gladen correction and Table 7 |
| `data/strict_label_guide.md`, `data/strict_probes.json`, `data/strict_split.json` | strict judge: gold-label guide, made-up probe responses with expected labels, dev/test split |
| `data/paper_results.json` | the paper's Tables 1 and 3 as numbers (with task counts), for the Table 6 comparison |
