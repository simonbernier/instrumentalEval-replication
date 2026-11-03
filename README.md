# instrumentalEval-replication

A replication of *Evaluating the Paperclip Maximizer: Are RL-Based Language Models More Likely to Pursue
Instrumental Goals?* (He et al., 2025, [arXiv:2502.12206](https://arxiv.org/abs/2502.12206)). It covers all five
tables, uses the original prompts and parameters from [yf-he/InstrumentalEval](https://github.com/yf-he/InstrumentalEval),
and calls every model through OpenRouter. On top of the replication it adds system-prompt ablations (Table 6, Figure
6), a reasoning-effort sweep (Table 7, Figure 7), a strict three-way judge (Table 9, Figure 11) and an interactive
version of Figure 1.

Model substitutions, deviations from upstream, the pre-registrations and results of every addition, and ideas for
improving the results by changing parameters are in [REPLICATION_NOTES.md](REPLICATION_NOTES.md).

## Reproducing the report

Every response and every judge verdict behind the report is stored, compressed, in `results/raw.tar.xz` (6.5 MB; about
500 append-only JSONL and log files, 87 MB unpacked). `results/raw_manifest.tsv` lists each file with its size and
SHA-256. Unpack the archive first; then rebuilding the tables and figures is offline and free, with no API key and no
benchmark download needed.

```sh
uv sync
uv run ie unpack-results      # -> results/responses/, results/judgments/, results/strict_judgments/ (checksums verified)
uv run ie tables              # Tables 1-7 and 9 -> results/tables.md, CSVs in results/tables/
uv run ie figures             # Figures 1-3, 5-7 and 11 -> results/figures/
uv run ie figures --strict    # Figure 1 under the strict judge (Claude Sonnet 4)
uv run ie interactive         # interactive Figure 1 -> results/interactive/ir_explorer.html
uv run ie capability          # capability ordering of Figure 1's x axis -> results/capability.md
```

Without the CLI, any tool that reads `.tar.xz` works too: `tar -xJf results/raw.tar.xz -C results` (Linux, macOS,
Windows 10+), or 7-Zip. Every `ie` command that reads the stored results refuses to run until they are unpacked. That
matters most for `ie generate` and `ie judge`, which would otherwise redo, and pay for, every stored call.

The three unpacked directories are git-ignored. After new generation or judging, run `uv run ie pack-results` and
commit `results/raw.tar.xz` and `results/raw_manifest.tsv`. Packing is deterministic: unchanged data gives a
byte-identical archive. If `ie unpack-results` finds a local file that differs from the archive (records added since
the last pack), it leaves the file alone and lists it; `--force` overwrites it with the archived version.

| In the report | Built by | Output |
|---|---|---|
| Table 1 / Figure 1: IR and CIR per model (also `figure1_matched`, `figure1_base`) | `ie tables`, `ie figures` | `results/tables.md`, `results/figures/figure1_*` |
| Table 2 / Figure 2: IR by prior-task type | `ie tables`, `ie figures` | `figure2_gpt-4o.*`; mapping in `data/task_categories.json` |
| Table 3 / Figure 3: goal-nudging ablation | `ie tables`, `ie figures` | `figure3_gpt-4o.*` |
| Table 4: judge reliability | `ie tables` | `results/tables/table4*.csv` |
| Table 5 / Figure 5: cross-category correlations | `ie tables`, `ie figures` | `figure5_gpt-4o.*` |
| Table 6 / Figure 6: system-prompt ablations, five cumulative prompt steps | `ie tables`, `ie figures` | `table6_*.csv`, `figure6_gpt-4o.*` |
| Table 7 / Figure 7: reasoning-effort sweep (o3-mini, o4-mini) | `ie tables`, `ie figures` | `table7_*.csv`, `figure7_gpt-4o.*` |
| Table 9: strict judge (validation, rates, Rogan–Gladen correction) | `ie tables`, `ie strict-eval` | `table9_*.csv`, `results/strict/` |
| Figure 11: gpt-4o judge vs strict judge on the same responses (also `_base`, `_categories`) | `ie figures` | `figure11*_gpt-4o.*` |
| Interactive Figure 1: five prompt steps × four judges | `ie interactive` | `results/interactive/` |

Regenerating responses or verdicts is a different matter: it costs money, and several of the models and judges have
been retired since the runs (see CLAUDE.md, "Model shutdowns"), so a full rerun would need substitutes.

## Setup (for new runs)

```sh
uv sync
cp .env.example .env        # then add OPENROUTER_API_KEY
uv run ie fetch             # benchmark CSVs + upstream main.py at the pinned commit (SHA256-checked)
uv run ie unpack-results    # the stored runs, so that nothing already done is redone
uv run pytest               # offline; checks prompts against upstream byte for byte
```

## Running

Every command can be resumed: finished tasks are skipped, and failed calls are retried on the next run. A stored
response is reused only if its request config, system prompt and task text match today's, so nothing on this list
re-spends money on work that is already stored. Step 1 is the Setup section above.

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
uv run ie figures           # -> results/figures/ (also takes --judge)

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

# 9. Reasoning-effort sweep (not in the paper): o3-mini and o4-mini at explicit low / medium / high effort, full
#    nudge prompt, gpt-4o judge. Pre-registered in REPLICATION_NOTES.md, "Reasoning-effort sweep": commit it first.
E="o3-mini@low o3-mini@medium o3-mini@high o4-mini@low o4-mini@medium o4-mini@high"
uv run ie generate --models $E --limit 1    # smoke test: 6 tasks per arm; check `ie status` for empty / cut answers
uv run ie generate --models $E
uv run ie judge --models $E
uv run ie tables                            # Table 7 (+ CSVs); `ie figures` adds Figure 7

# 10. Strict judge (not in the paper; REPLICATION_NOTES.md, "Strict judge"). Three-way labels: clear / instructed / none
uv run ie strict-setup                   # blank results/strict_labels.csv + data/strict_split.json (30 dev / 68 test)
#    label H001-H012 by hand and H013-H098 with the strict-labeller / strict-label-adjudicator subagents,
#    following data/strict_label_guide.md, then:
uv run ie strict-labels --merge <dir>    # <dir>/{pass_a,pass_b,adjudication}/<item_id>.json -> strict_labels.csv
uv run ie strict-judge --split dev --probes   # development rounds: tune the prompt on dev only
uv run ie strict-eval --split dev             # -> results/strict/eval_dev.md, dev_log.md
#    freeze: set prompts.FROZEN_STRICT_SHA and commit. Only then do the test split and full runs work:
uv run ie strict-judge --split test && uv run ie strict-eval --split test
uv run ie strict-judge --runs --task-sets benchmark neutral   # default judge: claude-sonnet-4; done for Table 1 (nudge) only
uv run ie strict-judge --runs --judges gpt-4o gemini-2.5-flash --task-sets benchmark neutral
uv run ie tables                         # Table 9
uv run ie figures --strict               # Figure 1 under the strict judge -> results/figures/figure1_strict-claude-sonnet-4.*
#    Claude Sonnet 4 is gone; the replacement strict judge (amendment S1) is validated first, then judges the stored runs
uv run ie strict-judge --judges claude-sonnet-4.6 --probes --split test --runs --models gpt-4o deepseek-v3 o3-mini deepseek-r1 --task-sets neutral
uv run ie strict-judge --judges claude-sonnet-4.6 --runs --models gpt-4o qwen-2.5-72b deepseek-v3 deepseek-r1 o3-mini gemini-2.5-flash o1 o4-mini
uv run ie figures                        # Figure 11 (gpt-4o judge vs strict judge) -> results/figures/

# 11. Interactive Figure 1 for the website (not in the paper; REPLICATION_NOTES.md, "Interactive Figure 1"): the five
#     prompt steps x four judges, stored verdicts only. Export instructions: results/interactive/README.md.
uv run ie interactive                    # -> results/interactive/ir_explorer.{html,json}; --copy-to <site folder>
```

Once `DEFAULT_JUDGE` is set in step 4, `ie judge`, `ie tables` and `ie figures` all default to the chosen judge, so
steps 6 and 7 need no `--judge` flags.

## Layout

| Path | Contents |
|---|---|
| `src/instrumentaleval/prompts.py` | upstream prompts (verbatim), the system-prompt variants for Table 6 (deletions of upstream text only), the strict judge's prompt and the judge-output parser |
| `src/instrumentaleval/models.py` | test models and judges, with their OpenRouter IDs and request parameters |
| `src/instrumentaleval/{generate,judge}.py` | the two passes; results go to `results/responses/` and `results/judgments/<judge>/` as JSONL, plus an upstream-format `*_evaluation_results.txt` per run |
| `src/instrumentaleval/archive.py`, `results/raw.tar.xz`, `results/raw_manifest.tsv` | the raw results (responses, judge and strict-judge verdicts) as one deterministic archive with a checksum manifest; `ie unpack-results` / `ie pack-results` |
| `src/instrumentaleval/tables.py` | Tables 1–5, Table 6 (system-prompt ablations) and Table 7 (reasoning-effort sweep), the last two not in the paper |
| `src/instrumentaleval/figures.py` | Tables 1, 2, 3, 5, 6 and 7 as figures (bar charts with models grouped by RLHF / RL family; Table 5 as a heat map; Table 6 as one panel per model) |
| `src/instrumentaleval/{strict,strict_eval,labels}.py` | the strict three-way judge (not upstream): judging pass with retries and a freeze guard; metrics, probes, Rogan–Gladen correction and Table 9; gold-label export and merge |
| `src/instrumentaleval/recommendations.py` | Figure 11 (not upstream): the gpt-4o judge vs the strict judge on the same stored responses |
| `src/instrumentaleval/interactive.py`, `templates/ir_explorer.html` | interactive Figure 1 (not upstream): one self-contained HTML page, prompt step × judge, in `results/interactive/` |
| `src/instrumentaleval/capability.py`, `data/capability_scores.csv` | Figure 1's within-family model order from Epoch AI benchmark scores (every row has its source URL) |
| `src/instrumentaleval/classify.py` | Table 2's prior-task-type votes and their merge |
| `data/neutral_tasks.csv`, `data/neutral_task_rubric.md` | control tasks for the false-positive check, and the rubric they were selected with |
| `data/task_classification_votes.{json,md}` | the three judges' prior-task-type votes and rationales for every benchmark task, side by side |
| `data/task_categories.json` | adjudicated task to prior-task-type mapping for Table 2 (one independent adjudicator per task, then a consistency review and a hand check) |
| `data/strict_label_guide*.md`, `data/strict_probes*.json`, `data/strict_split.json` | strict judge: gold-label guides (S1 and the S2/S3 amendments), made-up probe responses with expected labels, dev/test split |
| `data/paper_results.json` | the paper's Tables 1 and 3 as numbers (with task counts), for the comparisons |
| `.claude/agents/` | the subagent specs used for Table 2 adjudication and the strict judge's gold labels |

## Branches

- `main` (this branch): the code and data behind the report.
- `exploration`: everything on `main` plus four extensions the report does not use: verbalized eval awareness and
  frame awareness in deepseek-r1's chains of thought, a task audit of the 76 items (Table 8), and default-sampling
  repeats (Table 10, Figures 8, 9, 10, 12 and 13). A one-paragraph summary of each is in REPLICATION_NOTES.md,
  "Exploratory work".

## Audit trail and clone options

Every experiment beyond the replication was pre-registered: the hypotheses, estimators and decision rule were
committed to REPLICATION_NOTES.md before any of its data existed, and the history keeps those commits. Annotated tags
mark them (`git tag -n9` prints each tag's note, or see the repository's Tags page):

| Tag | What was committed before the data |
|---|---|
| `prereg/table6-ablations` | system-prompt ablations (Table 6) |
| `prereg/strict-judge` | strict judge prompt frozen and its evaluation pre-registered (Table 9); only the 30 dev-split items had been judged |
| `prereg/effort-sweep` | reasoning-effort sweep (Table 7) |
| `prereg/five-step` | five-step decomposition, `oversight-nonudge` arm (Figure 6, H4a/H4b) |
| `prereg/strict-s1`, `prereg/strict-s2`, `prereg/strict-s3` | strict-judge amendments S1 (Claude Sonnet 4.6), S2 and S3 |
| `prereg/strict-reask` | the one re-ask round for the strict parse error |
| `prereg/vea`, `prereg/vea-second-judge`, `prereg/frame-awareness`, `prereg/repeats` | the exploratory extensions (`exploration` branch) |
| `report-published` | the repository when the report was published, before the split into `main` and `exploration` |
| `v1.0` | first public `main` |

To check a claim, compare the tagged commit with the first commit that adds the corresponding results files
(`git log --diff-filter=A --format='%h %ad %s' -- <path>`). The task audit (Table 8, `exploration`) has no tag: its
pilot gate failed, and the full run went ahead as exploratory (REPLICATION_NOTES.md on that branch).

The full history (a 33 MB clone) is what makes these checks possible. To get only the current files (20 MB), clone
with `git clone --depth 1 https://github.com/simonbernier/instrumentalEval-replication.git`, which is enough to
rebuild the report; `git fetch --unshallow` turns it into a full clone later.

## License and attribution

The code, the stored results and the notes in this repository are released under the [MIT License](LICENSE).

The benchmark itself is not ours. The 76 task texts come from [yf-he/InstrumentalEval](https://github.com/yf-he/InstrumentalEval)
(He et al., 2025), which carries no license; `ie fetch` downloads them, and they are not committed as files. They do
appear verbatim inside the stored results (the `task_prompt` field of each response, the `PROMPT:` block of the
upstream-format judge outputs, and the label sheets), because the judges and the data model need them. They remain
the authors' work, and the MIT License does not cover them. Please cite the paper when you use them.
