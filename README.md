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
# follow-up arm (REPLICATION_NOTES.md, "Five-step decomposition"): the oversight sentence alone
uv run ie generate --variants oversight-nonudge --limit 1   # smoke test, 48 calls
uv run ie generate --variants oversight-nonudge && uv run ie judge --variants oversight-nonudge
uv run ie tables
uv run ie figures

# 9. Verbalized eval awareness (not in the paper): GPT-5-mini reads the stored chains of thought (deepseek-r1 only,
#    the one model whose `reasoning` field is its own CoT) under the Goodfire F1 rubric, then VEA is crossed with the
#    convergence verdicts. Pre-registered in REPLICATION_NOTES.md, "Eval awareness": commit that section first.
uv run ie vea-judge --limit 2 --variants nudge --task-sets benchmark   # smoke test: 12 calls; read results/vea/gpt-5-mini/
uv run ie vea-judge                     # all variants + neutral tasks (~630 calls, well under $1)
uv run ie vea-tables                    # -> results/vea/tables.md, results/vea/tables/*.csv, results/vea/figures/
uv run ie vea-export-labels             # then fill results/vea/hand_labels.csv (yes / no) and re-run `ie vea-tables`

# 10. Frame awareness (not in the paper): does the model treat the scenario as real, or as a test / simulation /
#     puzzle it is solving? Rajamanoharan & Nanda's 0-5 rubric + perceived-frame category, with an adaptation for this
#     benchmark's own "scenario" / "Simulate..." wording. Pre-registered in REPLICATION_NOTES.md, "Frame awareness".
uv run ie frame-judge --cells nonudge:ES-10 nudge:HC-01 ...   # known-cell check on the 14 cells listed in the notes; read the JSON
uv run ie frame-judge                   # same 552 chains of thought as vea-judge (openai/gpt-5, medium effort)
uv run ie frame-tables                  # -> results/frame/tables.md, tables/*.csv, figures/
uv run ie frame-export-labels           # then fill results/frame/hand_labels.csv and re-run `ie frame-tables`

# 11. Reasoning-effort sweep (not in the paper): o3-mini and o4-mini at explicit low / medium / high effort, full
#     nudge prompt, gpt-4o judge. Pre-registered in REPLICATION_NOTES.md, "Reasoning-effort sweep": commit it first.
E="o3-mini@low o3-mini@medium o3-mini@high o4-mini@low o4-mini@medium o4-mini@high"
uv run ie generate --models $E --limit 1    # smoke test: 6 tasks per arm; check `ie status` for empty / cut answers
uv run ie generate --models $E
uv run ie judge --models $E
uv run ie tables                            # Table 7 (+ CSVs); `ie figures` adds Figure 7

# 12. Task audit (not in the paper): score the 76 task texts on what they can measure (reachable? would the best
#     aligned response be scored convergent? instructed? permitted? on-target?) and re-report IR on the informative
#     subset at the item level. Rubric: data/task_audit_rubric.md; pre-registration and analysis plan in
#     REPLICATION_NOTES.md, "Task audit": commit it, then the pilot.
uv run ie audit-tasks --pilot-sample 4 --blind-packets   # 24 seeded tasks -> data/task_audit_blind/: score them yourself first
uv run ie audit-tasks --pilot-sample 4      # then 24 x 3 judges -> data/task_audit_pilot_votes.{json,md}
uv run ie audit-tasks --pilot-sample 4 --compare-blind data/task_audit_blind   # gate: alpha on gating dims + kappa >= 0.6
uv run ie audit-tasks                       # 76 tasks x 3 judges -> data/task_audit_votes.{json,md} + packets
#     then one task-auditor agent per CONTESTED task (.claude/agents/task-auditor.md) writes <dir>/<task_id>.json
uv run ie audit-tasks --merge <dir> --adjudicator "<who>"   # -> data/task_audit.json; review it by hand
uv run ie tables                            # Table 8
```

Once `DEFAULT_JUDGE` is set in step 4, `ie judge`, `ie tables` and `ie figures` all default to the chosen judge, so
steps 6 and 7 need no `--judge` flags.

## Layout

| Path | Contents |
|---|---|
| `src/instrumentaleval/prompts.py` | upstream prompts (verbatim), the system-prompt variants for Table 6 (deletions of upstream text only) and the judge-output parser |
| `src/instrumentaleval/models.py` | test models and judges, with their OpenRouter IDs and request parameters |
| `src/instrumentaleval/{generate,judge}.py` | the two passes; results go to `results/responses/` and `results/judgments/<judge>/` as JSONL, plus an upstream-format `*_evaluation_results.txt` per run |
| `src/instrumentaleval/tables.py` | Tables 1–5, Table 6 (system-prompt ablations) and Table 7 (reasoning-effort sweep), the last two not in the paper |
| `src/instrumentaleval/vea.py`, `vea_tables.py` | verbalized-eval-awareness judge pass (upstream/judge_vea.py's prompt and settings, verbatim; GPT-5-mini on the chain of thought only) and Tables V1–V5 in `results/vea/` |
| `upstream/judge_vea.py` | Bharadwaj & Kirk's VEA judge (vendored; the tests check our prompt and parser against it) |
| `src/instrumentaleval/frame.py`, `frame_tables.py` | frame-awareness judge pass (Rajamanoharan & Nanda's rubric, `upstream/frame_awareness_prompt.txt`, plus `frame.ADAPTATION`) and Tables F1–F5 in `results/frame/` |
| `src/instrumentaleval/figures.py` | Tables 1, 2, 3, 5 and 6 as figures (bar charts with models grouped by RLHF / RL family; Table 5 as a heat map; Table 6 as one panel per model) |
| `data/neutral_tasks.csv`, `data/neutral_task_rubric.md` | control tasks for the false-positive check, and the rubric they were selected with |
| `data/task_classification_votes.{json,md}` | the three judges' prior-task-type votes and rationales for every benchmark task, side by side |
| `data/task_categories.json` | adjudicated task to prior-task-type mapping for Table 2 (one independent adjudicator per task, then a consistency review and a hand check) |
| `data/task_audit_rubric.md`, `src/instrumentaleval/audit.py` | the task-audit rubric (what each item can measure) and its judge pass; votes in `data/task_audit_votes.{json,md}`, adjudicated scores in `data/task_audit.json` (Table 8) |
| `data/paper_results.json` | the paper's Tables 1 and 3 as numbers (with task counts), for the Table 6 comparison |
