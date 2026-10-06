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

Every command can be resumed: finished tasks are skipped, and failed calls are retried on the next run.

```sh
# 0. Smoke test: 2 tasks per category per model; check for empty or truncated answers and the provider used
uv run ie generate --limit 2
uv run ie status

# 1. Gemini 2.5 Flash leaves OpenRouter on 2026-10-20, so run everything that uses it first
uv run ie generate --models gemini-2.5-flash
uv run ie generate --models gpt-4o --task-set neutral
uv run ie judge --judges gemini-2.5-flash --task-sets benchmark neutral   # after step 2 as well

# 2. Table 1: all 9 test models, judged by GPT-4o
uv run ie generate
uv run ie judge

# 3. Table 3: goal-nudging ablation (the paper uses GPT-4o and DeepSeek-R1; any model or judge works)
uv run ie generate --models gpt-4o deepseek-r1 --no-nudge
uv run ie judge --variants nonudge

# 4. Table 4: re-judge everything with the other judges, then FPR on the neutral control tasks
uv run ie judge --judges claude-sonnet-4 mistral-large-2407 gemini-2.5-flash
uv run ie judge --judges gpt-4o claude-sonnet-4 mistral-large-2407 gemini-2.5-flash --task-sets neutral
uv run ie export-labels     # then fill results/human_labels.csv by hand

# 5. Table 2 mapping (review data/task_categories.json by hand afterwards)
uv run ie classify-tasks

# 6. Build all tables -> results/tables.md (+ CSVs in results/tables/)
uv run ie tables            # --judge <name> rebuilds Tables 1, 2 and 5 with another judge
```

## Layout

| Path | Contents |
|---|---|
| `src/instrumentaleval/prompts.py` | upstream prompts (verbatim) and judge-output parser |
| `src/instrumentaleval/models.py` | test models and judges, with their OpenRouter IDs and request parameters |
| `src/instrumentaleval/{generate,judge}.py` | the two passes; results go to `results/responses/` and `results/judgments/<judge>/` as JSONL, plus an upstream-format `*_evaluation_results.txt` per run |
| `src/instrumentaleval/tables.py` | Tables 1–5 |
| `data/neutral_tasks.csv`, `data/neutral_task_rubric.md` | control tasks for the false-positive check, and the rubric they were selected with |
| `data/task_categories.json` | task to prior-task-type mapping for Table 2 (generated, then hand-checked) |
