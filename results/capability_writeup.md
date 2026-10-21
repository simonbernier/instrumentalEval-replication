| Family | Model | GPQA Diamond (%) | MATH Level 5 (%) | OTIS Mock AIME (%) | ECI | Reasoning (z) | ECI (z) | Composite | Position | AA index |
|---|---|---|---|---|---|---|---|---|---|---|
| RLHF | GPT-4o mini (2024-07-18) | 37.7 ± 2.4 | 52.6 ± 1.1 | 6.9 ± 2.7 | 126.5 ± 2.1 | -1.21 | -1.38 | -1.27 | 1 | 7 |
| RLHF | GPT-4o (2024-08-06) | 49.2 ± 2.6 | 53.3 ± 1.1 | 6.4 ± 2.6 | 128.8 ± 1.7 | -0.95 | -1.04 | -0.98 | 2 | 8 |
| RLHF | Qwen2.5-72B-Instruct | 49.1 ± 2.7 | 63.2 ± 1.1 | 8.1 ± 2.6 | 129.0 ± 1.8ᶜ | -0.77 | -1.02 | -0.85 | 3 | 8 |
| RLHF | DeepSeek-V3 (Dec 2024) | 56.5 ± 2.8 | 64.9 ± 1.0 | 15.8 ± 4.3 | 132.3 ± 1.8 | -0.49 | -0.53 | -0.51 | 4 | 8 |
| RL | DeepSeek-R1 (Jan 2025) | 71.7 ± 3.1 | 93.1 ± 0.7 | 53.3 ± 7.5 | 138.8 ± 1.1 | +0.72 | +0.42 | +0.62 | 1 | 11 |
| RL | o3-mini (medium) | 74.3 ± 2.5 | 95.2 ± 0.5 | 63.9 ± 6.0 | 140.2 ± 1.2ᶜ | +0.92 | +0.62 | +0.82 | 2ᵉ | 12 |
| RL | Gemini 2.5 Flash (thinking) | –ᵃ | –ᵃ | –ᵃ | 140.6 ± 0.9 | – | +0.68 | –ᵈ | 3ᵉ | 13 |
| RL | o1 (medium) | 75.8 ± 3.1 | 94.4 ± 0.6 | 73.3 ± 6.7 | 141.7 ± 0.8ᶜ | +1.04 | +0.85 | +0.98 | 4 | 15 |
| RL | o4-mini (medium) | 77.8 ± 3.0 | –ᵇ | 73.3 ± 6.7 | 145.5 ± 1.1ᶜ | +1.11 | +1.39 | +1.20 | 5 | –ᶠ |

Scores are Epoch AI's (one evaluation harness; the exact model version and reasoning effort used in our experiments), ± one standard error; ECI is the Epoch Capabilities Index. Each column is z-scored over the nine models; Reasoning (z) is the mean of the three benchmark z-scores; Composite = ⅔ Reasoning + ⅓ ECI. Position orders the models within each family from lowest to highest composite and is the x-axis order of Figure 1 (which does not show GPT-4o mini). The Artificial Analysis Intelligence Index is an independent check and is not used in the composite.

ᵃ Epoch has no run of these benchmarks for the Gemini 2.5 Flash release we used (only for two earlier previews). ᵇ Epoch has this benchmark for o4-mini at high effort only. ᶜ Epoch reports one ECI per model, pooling runs at several reasoning efforts (o-series) or related model variants (Qwen2.5). ᵈ No composite: placed by comparing its ECI with the other models' ECI. ᵉ Statistically tied: the order of o3-mini (medium) and Gemini 2.5 Flash (thinking) holds in 60% of 10,000 draws of the scores from their standard errors (threshold 80%). ᶠ Artificial Analysis lists o4-mini at high effort only.
