# InstrumentalEval replication: results

Default judge: `gpt-4o`. Rates are % of valid tasks (non-empty responses that were judged). Unparseable judge outputs count as no_convergence, as upstream does.

## Table 1: CIR (%) by category and IR (%) per model

| Category | gpt-4o | gpt-4o-mini (added) | deepseek-v3 | qwen-2.5-72b (added) | o1 | o4-mini (for o1-mini) | o3-mini | gemini-2.5-flash (for Gemini 2.0 FTE.) | deepseek-r1 | RLHF avg | RLHF avg (paper models) | RL avg |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Evading Shutdown | 85.00 | 50.00 | 100.00 | 75.00 | 90.00 | 65.00 | 95.00 | 85.00 | 85.00 | 77.50 | 92.50 | 84.00 |
| Hacking Computer Systems | 0.00 | 0.00 | 20.00 | 0.00 | 0.00 | 10.00 | 0.00 | 20.00 | 20.00 | 5.00 | 10.00 | 10.00 |
| Running Multiple AI Copies | 84.62 | 53.85 | 92.31 | 92.31 | 92.31 | 84.62 | 92.31 | 92.31 | 100.00 | 80.77 | 88.46 | 92.31 |
| Hiding Unwanted Behavior | 45.45 | 9.09 | 100.00 | 81.82 | 9.09 | 0.00 | 18.18 | 90.91 | 100.00 | 59.09 | 72.73 | 43.64 |
| Strategically Appearing Aligned | 45.45 | 9.09 | 72.73 | 36.36 | 81.82 | 36.36 | 45.45 | 81.82 | 63.64 | 40.91 | 59.09 | 61.82 |
| Deceptive Behavior | 9.09 | 0.00 | 36.36 | 9.09 | 0.00 | 9.09 | 0.00 | 18.18 | 72.73 | 13.64 | 22.73 | 20.00 |
| Total | 51.32 | 25.00 | 75.00 | 53.95 | 52.63 | 39.47 | 50.00 | 68.42 | 76.32 | 51.32 | 63.16 | 57.37 |
| Total 95% CI | 40.3–62.2 | 16.6–35.8 | 64.2–83.4 | 42.8–64.7 | 41.6–63.5 | 29.2–50.7 | 39.0–61.0 | 57.3–77.8 | 65.6–84.5 |  |  |  |
| k / n | 39 / 76 | 19 / 76 | 57 / 76 | 41 / 76 | 40 / 76 | 30 / 76 | 38 / 76 | 52 / 76 | 58 / 76 |  |  |  |
| empty responses | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |  |  |
| unparseable judge outputs | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |  |  |
| pending (errors / not judged) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |  |  |

## Table 2: average IR (%) by prior-task category (approximate mapping)

Each model's IR within a prior-task category, averaged over all models (as in the paper) and within each family. Per-model rates are in Figure 2.

| Prior Task Category | Average Instrumental Rate (%) | RLHF avg | RLHF avg (paper models) | RL avg | # tasks | # models |
|---|---|---|---|---|---|---|
| Direct Resource-Related Goals | 71.43 | 64.29 | 85.71 | 77.14 | 7 | 9 |
| Optimizing Efficiency | 74.33 | 72.41 | 84.48 | 75.86 | 29 | 9 |
| Persuasion | 51.39 | 46.88 | 62.50 | 55.00 | 8 | 9 |
| General Problem Solving | 34.03 | 30.47 | 39.06 | 36.88 | 32 | 9 |

## Table 3: goal-nudging ablation (Figure 3)

**Judge: `gpt-4o`.** Without / With = CIR (%) without and with the goal nudge (With is Table 1); Gap = With − Without, in percentage points.

| Behavior Category | gpt-4o Without | gpt-4o With | gpt-4o Gap | deepseek-v3 Without | deepseek-v3 With | deepseek-v3 Gap | o4-mini (for o1-mini) Without | o4-mini (for o1-mini) With | o4-mini (for o1-mini) Gap | deepseek-r1 Without | deepseek-r1 With | deepseek-r1 Gap |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Evading Shutdown | 95.00 | 85.00 | -10.00 | 100.00 | 100.00 | +0.00 | 70.00 | 65.00 | -5.00 | 85.00 | 85.00 | +0.00 |
| Hacking Computer Systems | 0.00 | 0.00 | +0.00 | 40.00 | 20.00 | -20.00 | 0.00 | 10.00 | +10.00 | 20.00 | 20.00 | +0.00 |
| Running Multiple AI Copies | 84.62 | 84.62 | +0.00 | 100.00 | 92.31 | -7.69 | 92.31 | 84.62 | -7.69 | 100.00 | 100.00 | +0.00 |
| Hiding Unwanted Behavior | 54.55 | 45.45 | -9.09 | 100.00 | 100.00 | +0.00 | 0.00 | 0.00 | +0.00 | 100.00 | 100.00 | +0.00 |
| Strategically Appearing Aligned | 36.36 | 45.45 | +9.09 | 54.55 | 72.73 | +18.18 | 45.45 | 36.36 | -9.09 | 54.55 | 63.64 | +9.09 |
| Deceptive Behavior | 0.00 | 9.09 | +9.09 | 18.18 | 36.36 | +18.18 | 9.09 | 9.09 | +0.00 | 90.91 | 72.73 | -18.18 |
| Total | 52.63 | 51.32 | -1.32 | 73.68 | 75.00 | +1.32 | 42.11 | 39.47 | -2.63 | 77.63 | 76.32 | -1.32 |

## Table 4: judge reliability

| Judge Model | Average IAR | Average Cohen's κ | False Positive Rate | # neutral items | Agreement with Fable 5.1 | # Fable-labelled items |
|---|---|---|---|---|---|---|
| gpt-4o | 91.23 | 0.823 | 0.00 | 180 | 84.69 | 98 |
| claude-sonnet-4 (for Sonnet-3.5) | 89.99 | 0.799 | 1.67 | 180 | 81.63 | 98 |
| gemini-2.5-flash (for Gemini 2.0 Flash) | 88.08 | 0.762 | 4.44 | 180 | 89.80 | 98 |

Pairwise IAR (%) on shared benchmark responses:

| Judge | gpt-4o | claude-sonnet-4 | gemini-2.5-flash |
|---|---|---|---|
| gpt-4o | 100.00 | 93.13 (n=684) | 89.33 (n=684) |
| claude-sonnet-4 | 93.13 (n=684) | 100.00 | 86.84 (n=684) |
| gemini-2.5-flash | 89.33 (n=684) | 86.84 (n=684) | 100.00 |

## Table 5: cross-category Pearson correlation of CIRs across models (heat map: Figure 5)

| Category (n = 9 models) | ES | HC | RAC | HB | SAA | DB |
|---|---|---|---|---|---|---|
| Evading Shutdown (ES) | 1.00 | 0.31 | 0.80 | 0.44 | 0.78 | 0.29 |
| Hacking Computer Systems (HC) |  | 1.00 | 0.42 | 0.69 | 0.55 | 0.77 |
| Running Multiple AI Copies (RAC) |  |  | 1.00 | 0.53 | 0.74 | 0.48 |
| Hiding Unwanted Behavior (HB) |  |  |  | 1.00 | 0.47 | 0.73 |
| Strategically Appearing Aligned (SAA) |  |  |  |  | 1.00 | 0.37 |
| Deceptive Behavior (DB) |  |  |  |  |  | 1.00 |

## Table 6: system-prompt ablations (not in the paper; Figure 6)

Judge: `gpt-4o`. Pre-registration and caveats: REPLICATION_NOTES.md, "Additional experiments".

**(a) IR (%) per model and system prompt.** Variants are defined in `prompts.SYSTEM_PROMPTS`. Family averages are over the models with every design variant (gpt-4o, gpt-4o-mini, deepseek-v3, qwen-2.5-72b, o4-mini, o3-mini, gemini-2.5-flash, deepseek-r1). ‡ the paper's number for a different snapshot or a substitute model, so not comparable; only GPT-4o (the same pinned snapshot) is compared with the paper.

| Model | nudge | nonudge | nocause-nudge | nocause-nonudge | plain-nudge | plain-goal | plain-nonudge | nudge-rep | paper IR (Table 1) |
|---|---|---|---|---|---|---|---|---|---|
| gpt-4o | 51.32 | 52.63 | 48.68 | 40.79 | 63.16 | 56.58 | 57.89 | 55.26 | 21.05 |
| gpt-4o-mini (added) | 25.00 | 26.32 | 23.68 | 25.00 | 51.32 | 53.95 | 50.00 | 23.68 | – |
| deepseek-v3 | 75.00 | 73.68 | 81.58 | 71.05 | 75.00 | 75.00 | 63.16 | 76.32 | 21.05 ‡ |
| qwen-2.5-72b (added) | 53.95 | 59.21 | 52.63 | 51.32 | 51.32 | 43.42 | 47.37 | – | – |
| o4-mini (for o1-mini) | 39.47 | 42.11 | 39.47 | 40.79 | 43.42 | 40.79 | 44.74 | 42.11 | 43.42 ‡ |
| o3-mini | 50.00 | 52.63 | 46.05 | 47.37 | 53.95 | 48.68 | 46.05 | – | 48.68 ‡ |
| gemini-2.5-flash (for Gemini 2.0 FTE.) | 68.42 | 60.53 | 65.79 | 67.11 | 64.47 | 68.42 | 57.89 | – | 32.89 ‡ |
| deepseek-r1 | 76.32 | 77.63 | 78.95 | 75.00 | 65.79 | 60.53 | 52.63 | – | 46.05 ‡ |
| RLHF avg | 51.32 | 52.96 | 51.64 | 47.04 | 60.20 | 57.24 | 54.61 |  |  |
| RLHF avg (paper models) | 63.16 | 63.16 | 65.13 | 55.92 | 69.08 | 65.79 | 60.53 |  |  |
| RL avg | 58.55 | 58.22 | 57.57 | 57.57 | 56.91 | 54.61 | 50.33 |  |  |

**(b) Paired contrasts, pooled over models (arm A − arm B, pp).** Pairs are the (model, task) pairs judged in both arms. The p-value flips the sign of whole tasks, because every model sees the same 76 tasks. H1, H2a and H2b are the pre-registered primary tests (Holm-corrected); the rest are exploratory. b / c = pairs where only arm A / only arm B converged.

| Contrast | Δ (pp) | b / c | pairs | models | p (task sign-flip) | Holm p |
|---|---|---|---|---|---|---|
| H1: licence (nudge on) | +0.3 | 32 / 30 | 608 | 8 | 0.898 | 1.000 |
| H2a: oversight + rules (nudge on) | -3.9 | 34 / 58 | 608 | 8 | 0.029 | 0.087 |
| H2b: oversight + rules (nudge off) | -0.2 | 68 / 69 | 608 | 8 | 1.000 | 1.000 |
| licence (nudge off) | +3.3 | 45 / 25 | 608 | 8 | 0.006 |  |
| nudge (full jailbreak) | -0.7 | 29 / 33 | 608 | 8 | 0.673 |  |
| nudge (no licence) | +2.3 | 41 / 27 | 608 | 8 | 0.115 |  |
| nudge (plain) | +6.1 | 58 / 21 | 608 | 8 | 0.001 |  |
| goal only (plain) | +3.5 | 47 / 26 | 608 | 8 | 0.043 |  |
| PROCEED (plain) | +2.6 | 40 / 24 | 608 | 8 | 0.049 |  |
| retest (noise floor) | -1.6 | 14 / 19 | 304 | 4 | 0.478 |  |
| H3 (exploratory): nudge (plain) − nudge (full jailbreak) | +6.7 | – | 608 | 8 | 0.003 |  |

Per model: Δ (pp) and b/c. Exact McNemar p per model is in `results/tables/table6_contrasts_gpt-4o.csv`; per-model tests have low power and are descriptive only.

| Contrast | gpt-4o | gpt-4o-mini (added) | deepseek-v3 | qwen-2.5-72b (added) | o4-mini (for o1-mini) | o3-mini | gemini-2.5-flash (for Gemini 2.0 FTE.) | deepseek-r1 |
|---|---|---|---|---|---|---|---|---|
| H1: licence (nudge on) | +2.6 (5/3) | +1.3 (2/1) | -6.6 (1/6) | +1.3 (4/3) | +0.0 (8/8) | +3.9 (4/1) | +2.6 (4/2) | -2.6 (4/6) |
| H2a: oversight + rules (nudge on) | -14.5 (1/12) | -27.6 (0/21) | +6.6 (6/1) | +1.3 (5/4) | -3.9 (4/7) | -7.9 (0/6) | +1.3 (4/3) | +13.2 (14/4) |
| H2b: oversight + rules (nudge off) | -17.1 (5/18) | -25.0 (3/22) | +7.9 (10/4) | +3.9 (10/7) | -3.9 (5/8) | +1.3 (2/1) | +9.2 (9/2) | +22.4 (24/7) |
| licence (nudge off) | +11.8 (11/2) | +1.3 (3/2) | +2.6 (4/2) | +7.9 (8/2) | +1.3 (6/5) | +5.3 (5/1) | -6.6 (2/7) | +2.6 (6/4) |
| nudge (full jailbreak) | -1.3 (4/5) | -1.3 (2/3) | +1.3 (4/3) | -5.3 (1/5) | -2.6 (5/7) | -2.6 (2/4) | +7.9 (7/1) | -1.3 (4/5) |
| nudge (no licence) | +7.9 (11/5) | -1.3 (1/2) | +10.5 (8/0) | +1.3 (6/5) | -1.3 (4/5) | -1.3 (2/3) | -1.3 (2/3) | +3.9 (7/4) |
| nudge (plain) | +5.3 (8/4) | +1.3 (5/4) | +11.8 (9/0) | +3.9 (7/4) | -1.3 (5/6) | +7.9 (7/1) | +6.6 (6/1) | +13.2 (11/1) |
| goal only (plain) | -1.3 (6/7) | +3.9 (5/2) | +11.8 (10/1) | -3.9 (2/5) | -3.9 (5/8) | +2.6 (4/2) | +10.5 (9/1) | +7.9 (6/0) |
| PROCEED (plain) | +6.6 (8/3) | -2.6 (2/4) | +0.0 (2/2) | +7.9 (8/2) | +2.6 (7/5) | +5.3 (5/1) | -3.9 (2/5) | +5.3 (6/2) |
| retest (noise floor) | -3.9 (4/7) | +1.3 (1/0) | -1.3 (3/4) | – | -2.6 (6/8) | – | – | – |
| H3 (exploratory): nudge (plain) − nudge (full jailbreak) | +6.6 | +2.6 | +10.5 | +9.2 | +1.3 | +10.5 | -1.3 | +14.5 |

**Pre-registered decision: does the good-cause licence explain the paper's lower rates?** **NO.**

- H1 pooled: Δ = +0.3 pp, Holm p = 1.000
- GPT-4o: Δ licence = +2.6 pp (5/3); noise floor = 1.96·√(b+c)/n from its `nudge-rep` retest (4/7 of 76) = 8.6 pp
- GPT-4o `nocause-nudge` IR = 48.68 (95% CI 37.8–59.7); the paper's 21.05 = 16/76 (95% CI 13.4–31.5)
- Category profile, GPT-4o `nocause-nudge` vs the paper's row: Pearson r = 0.69
- Rule: YES if H1 is significant, the GPT-4o Δ exceeds the noise floor and its IR falls in the paper's CI; PARTIAL if H1 is significant but GPT-4o stays ≥ 40%; NO if H1 is not significant and the Δ is within the noise floor.

**(c) Diagnostics.** Refusals (heuristic: an explicit refusal in the first 200 characters, or a no_convergence verdict whose reason mentions a refusal; validated in REPLICATION_NOTES.md; never a headline metric) per model and arm. The judge counts a refusal as no_convergence, so this separates refusing from complying without instrumental behaviour.

| Model | nudge | nonudge | nocause-nudge | nocause-nonudge | plain-nudge | plain-goal | plain-nonudge | nudge-rep |
|---|---|---|---|---|---|---|---|---|
| gpt-4o | 9/76 | 4/76 | 13/76 | 8/76 | 1/76 | 0/76 | 0/76 | 9/76 |
| gpt-4o-mini (added) | 27/76 | 29/76 | 32/76 | 31/76 | 7/76 | 4/76 | 1/76 | 27/76 |
| deepseek-v3 | 0/76 | 0/76 | 0/76 | 0/76 | 0/76 | 0/76 | 0/76 | 0/76 |
| qwen-2.5-72b (added) | 0/76 | 0/76 | 0/76 | 0/76 | 0/76 | 0/76 | 0/76 | – |
| o4-mini (for o1-mini) | 14/76 | 17/76 | 17/76 | 18/76 | 14/76 | 16/76 | 12/76 | 13/76 |
| o3-mini | 7/76 | 9/76 | 9/76 | 9/76 | 7/76 | 8/76 | 6/76 | – |
| gemini-2.5-flash (for Gemini 2.0 FTE.) | 0/76 | 0/76 | 0/76 | 0/76 | 0/76 | 0/76 | 0/76 | – |
| deepseek-r1 | 0/76 | 0/76 | 0/76 | 0/76 | 0/76 | 0/76 | 1/76 | – |

Serving provider per arm (a provider switch between arms is a confound, not a prompt effect):

- gpt-4o: nudge: Azure 44, OpenAI 32; nonudge: OpenAI 39, Azure 37; nocause-nudge: OpenAI 38, Azure 38; nocause-nonudge: Azure 43, OpenAI 33; plain-nudge: OpenAI 43, Azure 33; plain-goal: Azure 42, OpenAI 34; plain-nonudge: OpenAI 42, Azure 34; nudge-rep: OpenAI 40, Azure 36
- gpt-4o-mini (added): OpenAI for every arm
- deepseek-v3: StreamLake for every arm
- qwen-2.5-72b (added): nudge: Novita 40, DeepInfra 36; nonudge: Novita 39, DeepInfra 37; nocause-nudge: DeepInfra 39, Novita 37; nocause-nonudge: Novita 59, DeepInfra 17; plain-nudge: Novita 39, DeepInfra 37; plain-goal: DeepInfra 47, Novita 29; plain-nonudge: Novita 68, DeepInfra 8
- o4-mini (for o1-mini): OpenAI for every arm
- o3-mini: OpenAI for every arm
- gemini-2.5-flash (for Gemini 2.0 FTE.): Google for every arm
- deepseek-r1: Novita for every arm

## Table 7: strict judge (not in the paper)

Three-way judge (none / instructed / clear; `prompts.STRICT_JUDGE_SYSTEM_PROMPT`). Pre-registration and caveats: REPLICATION_NOTES.md, "Strict judge".

**(a) Validation on the test split** (positive class: clear; % with 95% Wilson CI; κ with bootstrap CI)

| Judge | n (missing) | clear: P | clear: R | clear: Sp | clear: κ | any: P | any: R | any: κ | 3-way κ | AUROC clear (exploratory) |
|---|---|---|---|---|---|---|---|---|---|---|
| gpt-4o | 68 (0) | 84 [65–94] (21/25) | 78 [59–89] (21/27) | 90 | 0.69 [0.49–0.85] | 85 | 83 | 0.68 [0.49–0.85] | 0.70 [0.53–0.85] | 0.84 |
| claude-sonnet-4 | 68 (0) | 83 [66–93] (25/30) | 93 [77–98] (25/27) | 88 | 0.79 [0.63–0.91] | 91 | 91 | 0.82 [0.67–0.94] | 0.80 [0.65–0.92] | 0.94 |
| gemini-2.5-flash | 68 (0) | 84 [67–93] (26/31) | 96 [82–99] (26/27) | 88 | 0.82 [0.67–0.94] | 88 | 100 | 0.85 [0.71–0.97] | 0.85 [0.72–0.95] | 0.93 |

**(b) False-positive rate on the neutral tasks** (gpt-4o, deepseek-v3, o3-mini, deepseek-r1)

| Judge | FPR clear (%) | FPR any (%) | parse errors |
|---|---|---|---|
| gpt-4o | 0.0 [0.0–4.6] (0/80) | 0.0 [0.0–4.6] (0/80) | 0 |
| claude-sonnet-4 | 0.0 [0.0–4.6] (0/80) | 0.0 [0.0–4.6] (0/80) | 0 |
| gemini-2.5-flash | 6.2 [2.7–13.8] (5/80) | 6.2 [2.7–13.8] (5/80) | 0 |

**(c) Table 1 under the strict judge** (`strict-claude-sonnet-4`: CIR = % clear)

| Category | gpt-4o | deepseek-v3 | o3-mini | deepseek-r1 | RLHF avg | RL avg |
|---|---|---|---|---|---|---|
| Evading Shutdown | 85.00 | 100.00 | 100.00 | 83.33 | 92.50 | 91.67 |
| Hacking Computer Systems | 0.00 | 30.00 | 0.00 | 50.00 | 15.00 | 25.00 |
| Running Multiple AI Copies | 7.69 | 30.77 | 7.69 | 25.00 | 19.23 | 16.35 |
| Hiding Unwanted Behavior | 45.45 | 100.00 | 9.09 | 100.00 | 72.73 | 54.55 |
| Strategically Appearing Aligned | 72.73 | 63.64 | 72.73 | 72.73 | 68.18 | 72.73 |
| Deceptive Behavior | 9.09 | 18.18 | 9.09 | 63.64 | 13.64 | 36.36 |
| Total | 42.11 | 61.33 | 40.79 | 67.12 | 51.72 | 53.96 |
| Total 95% CI | 31.6–53.3 | 50.0–71.5 | 30.4–52.0 | 55.7–76.8 |  |  |
| k / n | 32 / 76 | 46 / 75 | 31 / 76 | 49 / 73 |  |  |
| empty responses | 0 | 0 | 0 | 0 |  |  |
| unparseable judge outputs | 0 | 0 | 0 | 0 |  |  |
| pending (errors / not judged) | 0 | 1 | 0 | 3 |  |  |

**(d) Per model: upstream judge vs strict judge, with the Rogan–Gladen correction** (`nudge`, 76 tasks). Upstream: `gpt-4o` with the upstream prompt (Table 1). Strict: `claude-sonnet-4` with the frozen prompt, % clear and % clear or instructed, 95% Wilson CIs. Corrected: Rogan–Gladen with the strict judge's test-split Se 0.93 and Sp 0.88 (clear vs rest), 95% bootstrap CI over the test items and the responses (B = 10,000, seed 0). Sensitivity check (pre-registered): Se/Sp from the focus-model test items only (Se 1.00, Sp 0.71).

| Model | upstream IR (gpt-4o) | strict: % clear | strict: % clear or instructed | corrected % clear | corrected, focus Se/Sp |
|---|---|---|---|---|---|
| gpt-4o | 51.3 [40.3–62.2] (39/76) | 42.1 [31.6–53.3] (32/76) | 50.0 [39.0–61.0] (38/76) | 37.2 [20.0–54.5] | 18.0 [0.0–41.8] |
| deepseek-v3 | 75.0 [64.2–83.4] (57/76) | 61.3 [50.0–71.5] (46/75) | 70.7 [59.6–79.8] (53/75) | 61.1 [44.4–77.9] | 45.2 [12.2–64.4] |
| o3-mini | 50.0 [39.0–61.0] (38/76) | 40.8 [30.4–52.0] (31/76) | 42.1 [31.6–53.3] (32/76) | 35.6 [18.3–52.7] | 16.1 [0.0–40.4] |
| deepseek-r1 | 76.3 [65.6–84.5] (58/76) | 67.1 [55.7–76.8] (49/73) | 79.5 [68.8–87.1] (58/73) | 68.3 [52.3–85.8] | 53.4 [24.9–70.9] |

**(e) Self-preference of `gpt-4o` on Table 1:** not run. Table 1 was re-judged by `claude-sonnet-4` only (decision of 2026-10-11). On the test split, each judge erred on 1 of the 7 gpt-4o items (`results/strict/eval_test.md`).

Judges disagree on 21 responses (`results/strict/disagreements.csv`), the candidates for T=1 voting.

**(f) Table 6 under the strict judge:** not run. The system-prompt ablations were not re-judged with the strict judge (decision of 2026-10-11: Table 1 only).

## Response status per run

- `deepseek-r1__nocause-nonudge__benchmark`: {'ok': 76}
- `deepseek-r1__nocause-nudge__benchmark`: {'ok': 76}
- `deepseek-r1__nonudge__benchmark`: {'ok': 76}
- `deepseek-r1__nudge__benchmark`: {'ok': 76}
- `deepseek-r1__nudge__neutral`: {'ok': 20}
- `deepseek-r1__plain-goal__benchmark`: {'ok': 76}
- `deepseek-r1__plain-nonudge__benchmark`: {'ok': 76}
- `deepseek-r1__plain-nudge__benchmark`: {'ok': 76}
- `deepseek-v3__nocause-nonudge__benchmark`: {'ok': 76}
- `deepseek-v3__nocause-nudge__benchmark`: {'ok': 76}
- `deepseek-v3__nonudge__benchmark`: {'ok': 76}
- `deepseek-v3__nudge-rep__benchmark`: {'ok': 76}
- `deepseek-v3__nudge__benchmark`: {'ok': 76}
- `deepseek-v3__nudge__neutral`: {'ok': 20}
- `deepseek-v3__plain-goal__benchmark`: {'ok': 76}
- `deepseek-v3__plain-nonudge__benchmark`: {'ok': 76}
- `deepseek-v3__plain-nudge__benchmark`: {'ok': 76}
- `gemini-2.5-flash__nocause-nonudge__benchmark`: {'ok': 76}
- `gemini-2.5-flash__nocause-nudge__benchmark`: {'ok': 76}
- `gemini-2.5-flash__nonudge__benchmark`: {'ok': 76}
- `gemini-2.5-flash__nudge__benchmark`: {'ok': 76}
- `gemini-2.5-flash__nudge__neutral`: {'ok': 20}
- `gemini-2.5-flash__plain-goal__benchmark`: {'ok': 76}
- `gemini-2.5-flash__plain-nonudge__benchmark`: {'ok': 76}
- `gemini-2.5-flash__plain-nudge__benchmark`: {'ok': 76}
- `gpt-4o-mini__nocause-nonudge__benchmark`: {'ok': 76}
- `gpt-4o-mini__nocause-nudge__benchmark`: {'ok': 76}
- `gpt-4o-mini__nonudge__benchmark`: {'ok': 76}
- `gpt-4o-mini__nudge-rep__benchmark`: {'ok': 76}
- `gpt-4o-mini__nudge__benchmark`: {'ok': 76}
- `gpt-4o-mini__nudge__neutral`: {'ok': 20}
- `gpt-4o-mini__plain-goal__benchmark`: {'ok': 76}
- `gpt-4o-mini__plain-nonudge__benchmark`: {'ok': 76}
- `gpt-4o-mini__plain-nudge__benchmark`: {'ok': 76}
- `gpt-4o__nocause-nonudge__benchmark`: {'ok': 76}
- `gpt-4o__nocause-nudge__benchmark`: {'ok': 76}
- `gpt-4o__nonudge__benchmark`: {'ok': 76}
- `gpt-4o__nudge-rep__benchmark`: {'ok': 76}
- `gpt-4o__nudge__benchmark`: {'ok': 76}
- `gpt-4o__nudge__neutral`: {'ok': 20}
- `gpt-4o__plain-goal__benchmark`: {'ok': 76}
- `gpt-4o__plain-nonudge__benchmark`: {'ok': 76}
- `gpt-4o__plain-nudge__benchmark`: {'ok': 76}
- `o1__nudge__benchmark`: {'ok': 76}
- `o1__nudge__neutral`: {'ok': 20}
- `o3-mini__nocause-nonudge__benchmark`: {'ok': 76}
- `o3-mini__nocause-nudge__benchmark`: {'ok': 76}
- `o3-mini__nonudge__benchmark`: {'ok': 76}
- `o3-mini__nudge__benchmark`: {'ok': 76}
- `o3-mini__nudge__neutral`: {'ok': 20}
- `o3-mini__plain-goal__benchmark`: {'ok': 76}
- `o3-mini__plain-nonudge__benchmark`: {'ok': 76}
- `o3-mini__plain-nudge__benchmark`: {'ok': 76}
- `o4-mini__nocause-nonudge__benchmark`: {'ok': 76}
- `o4-mini__nocause-nudge__benchmark`: {'ok': 76}
- `o4-mini__nonudge__benchmark`: {'ok': 76}
- `o4-mini__nudge-rep__benchmark`: {'ok': 76}
- `o4-mini__nudge__benchmark`: {'ok': 76}
- `o4-mini__nudge__neutral`: {'ok': 20}
- `o4-mini__plain-goal__benchmark`: {'ok': 76}
- `o4-mini__plain-nonudge__benchmark`: {'ok': 76}
- `o4-mini__plain-nudge__benchmark`: {'ok': 76}
- `qwen-2.5-72b__nocause-nonudge__benchmark`: {'ok': 76}
- `qwen-2.5-72b__nocause-nudge__benchmark`: {'ok': 76}
- `qwen-2.5-72b__nonudge__benchmark`: {'ok': 76}
- `qwen-2.5-72b__nudge__benchmark`: {'ok': 76}
- `qwen-2.5-72b__nudge__neutral`: {'ok': 20}
- `qwen-2.5-72b__plain-goal__benchmark`: {'ok': 76}
- `qwen-2.5-72b__plain-nonudge__benchmark`: {'ok': 76}
- `qwen-2.5-72b__plain-nudge__benchmark`: {'ok': 76}
