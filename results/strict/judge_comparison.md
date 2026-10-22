# Strict judge: comparison of the three judges

Frozen prompt 88f985352bf38635. Test split: 68 items (27 clear, 8 instructed, 33 none). Neutral: 20 control tasks x the 4 focus models.

| Measure | Claude Sonnet 4 | Gemini 2.5 Flash | GPT-4o |
|---|---|---|---|
| Test: clear-vs-rest κ [95% CI] | 0.79 [0.63–0.91] | 0.82 [0.67–0.94] | 0.69 [0.49–0.85] |
| Test: 3-way κ | 0.80 | 0.85 | 0.70 |
| Test: any-behaviour κ | 0.82 | 0.85 | 0.68 |
| Test: clear precision | 83% (25/30) | 84% (26/31) | 84% (21/25) |
| Test: clear recall | 93% (25/27) | 96% (26/27) | 78% (21/27) |
| Test: clear specificity | 88% | 88% | 90% |
| Test: items right, clear vs rest (of 68) | 61 | 62 | 58 |
| Test: AUROC (exploratory) | 0.94 | 0.93 | 0.84 |
| Test, focus-model items (n=30): clear κ | 0.68 | 0.73 | 0.59 |
| Dev round 3: clear κ / 3-way κ | 0.93 / 0.94 | 0.93 / 0.89 | 0.87 / 0.89 |
| Probes (54) | 53/54 | 50/54 | 54/54 |
| Neutral FPR, clear (80 responses) | 0.0% [0.0–4.6] (0/80) | 6.2% [2.7–13.8] (5/80) | 0.0% [0.0–4.6] (0/80) |
| Parse errors (all strict calls) | 0 | 0 | 0 |
| Available after 2026-10-20 | yes | no (leaves OpenRouter) | yes |
| Judges its own outputs | no | no | yes (gpt-4o is a test model) |
