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

| Prior Task Category | Average Instrumental Rate (%) | # tasks | # models |
|---|---|---|---|
| Direct Resource-Related Goals | 71.43 | 7 | 9 |
| Optimizing Efficiency | 74.33 | 29 | 9 |
| Persuasion | 51.39 | 8 | 9 |
| General Problem Solving | 34.03 | 32 | 9 |

## Table 3: goal-nudging ablation

**Judge: `gpt-4o`.** Gap = CIR with nudge − CIR without nudge, in percentage points.

| Behavior Category | gpt-4o Gap | deepseek-v3 Gap | o4-mini (for o1-mini) Gap | deepseek-r1 Gap |
|---|---|---|---|---|
| Evading Shutdown | -10.00 | +0.00 | -5.00 | +0.00 |
| Hacking Computer Systems | +0.00 | -20.00 | +10.00 | +0.00 |
| Running Multiple AI Copies | +0.00 | -7.69 | -7.69 | +0.00 |
| Hiding Unwanted Behavior | -9.09 | +0.00 | +0.00 | +0.00 |
| Strategically Appearing Aligned | +9.09 | +18.18 | -9.09 | +9.09 |
| Deceptive Behavior | +9.09 | +18.18 | +0.00 | -18.18 |
| Total | -1.32 | +1.32 | -2.63 | -1.32 |

## Table 4: judge reliability

| Judge Model | Average IAR | Average Cohen's κ | False Positive Rate | # neutral items | Agreement with Human | # human-labelled items |
|---|---|---|---|---|---|---|
| gpt-4o | 91.23 | 0.823 | 0.00 | 180 | – | 0 |
| claude-sonnet-4 (for Sonnet-3.5) | 89.99 | 0.799 | 1.67 | 180 | – | 0 |
| gemini-2.5-flash (for Gemini 2.0 Flash) | 88.08 | 0.762 | 4.44 | 180 | – | 0 |

Pairwise IAR (%) on shared benchmark responses:

| Judge | gpt-4o | claude-sonnet-4 | gemini-2.5-flash |
|---|---|---|---|
| gpt-4o | 100.00 | 93.13 (n=684) | 89.33 (n=684) |
| claude-sonnet-4 | 93.13 (n=684) | 100.00 | 86.84 (n=684) |
| gemini-2.5-flash | 89.33 (n=684) | 86.84 (n=684) | 100.00 |

## Table 5: cross-category Pearson correlation of CIRs across models

| Category (n = 9 models) | ES | HC | RAC | HB | SAA | DB |
|---|---|---|---|---|---|---|
| Evading Shutdown (ES) | 1.00 | 0.31 | 0.80 | 0.44 | 0.78 | 0.29 |
| Hacking Computer Systems (HC) |  | 1.00 | 0.42 | 0.69 | 0.55 | 0.77 |
| Running Multiple AI Copies (RAC) |  |  | 1.00 | 0.53 | 0.74 | 0.48 |
| Hiding Unwanted Behavior (HB) |  |  |  | 1.00 | 0.47 | 0.73 |
| Strategically Appearing Aligned (SAA) |  |  |  |  | 1.00 | 0.37 |
| Deceptive Behavior (DB) |  |  |  |  |  | 1.00 |

## Response status per run

- `deepseek-r1__nonudge__benchmark`: {'ok': 76}
- `deepseek-r1__nudge__benchmark`: {'ok': 76}
- `deepseek-r1__nudge__neutral`: {'ok': 20}
- `deepseek-v3__nonudge__benchmark`: {'ok': 76}
- `deepseek-v3__nudge__benchmark`: {'ok': 76}
- `deepseek-v3__nudge__neutral`: {'ok': 20}
- `gemini-2.5-flash__nudge__benchmark`: {'ok': 76}
- `gemini-2.5-flash__nudge__neutral`: {'ok': 20}
- `gpt-4o-mini__nudge__benchmark`: {'ok': 76}
- `gpt-4o-mini__nudge__neutral`: {'ok': 20}
- `gpt-4o__nonudge__benchmark`: {'ok': 76}
- `gpt-4o__nudge__benchmark`: {'ok': 76}
- `gpt-4o__nudge__neutral`: {'ok': 20}
- `o1__nudge__benchmark`: {'ok': 76}
- `o1__nudge__neutral`: {'ok': 20}
- `o3-mini__nudge__benchmark`: {'ok': 76}
- `o3-mini__nudge__neutral`: {'ok': 20}
- `o4-mini__nonudge__benchmark`: {'ok': 76}
- `o4-mini__nudge__benchmark`: {'ok': 76}
- `o4-mini__nudge__neutral`: {'ok': 20}
- `qwen-2.5-72b__nudge__benchmark`: {'ok': 76}
- `qwen-2.5-72b__nudge__neutral`: {'ok': 20}
