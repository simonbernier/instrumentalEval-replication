# Capability ordering (Figure 1 x-axis)

REPLICATION_NOTES.md, "Capability ordering" (amendment A1). Scored cells are Epoch AI's (one harness, the exact model version and reasoning effort we ran): accuracy in %, ECI in index points, ± SE. Blocks are mean z-scores over the nine models; composite = 2/3 reasoning + 1/3 general (ECI); a general-only model is placed by ECI against ECI (A2). Artificial Analysis index and HLE (exact-match entries only, rounded) and Arena Elo (style-controlled, 2026-10-20) are context only.

| model | family | gpqa_diamond | math_level_5 | otis_mock_aime | eci | reasoning z | general z | composite | basis | AA index | HLE (AA) | Arena Elo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| gpt-4o-mini | RLHF | 37.7 ± 2.4 | 52.6 ± 1.1 | 6.9 ± 2.7 | 126.5 ± 2.1 | -1.21 | -1.38 | -1.27 | both | 7 | 4 | 1318 |
| gpt-4o | RLHF | 49.2 ± 2.6 | 53.3 ± 1.1 | 6.4 ± 2.6 | 128.8 ± 1.7 | -0.95 | -1.04 | -0.98 | both | 8 | 2 | 1336 |
| qwen-2.5-72b | RLHF | 49.1 ± 2.7 | 63.2 ± 1.1 | 8.1 ± 2.6 | 129.0 ± 1.8 | -0.77 | -1.02 | -0.85 | both | 8 | 4 | 1303 |
| deepseek-v3 | RLHF | 56.5 ± 2.8 | 64.9 ± 1.0 | 15.8 ± 4.3 | 132.3 ± 1.8 | -0.49 | -0.53 | -0.51 | both | 8 | 3 | 1358 |
| deepseek-r1 | RL | 71.7 ± 3.1 | 93.1 ± 0.7 | 53.3 ± 7.5 | 138.8 ± 1.1 | +0.72 | +0.42 | +0.62 | both | 11 | 9 | 1398 |
| o3-mini | RL | 74.3 ± 2.5 | 95.2 ± 0.5 | 63.9 ± 6.0 | 140.2 ± 1.2 | +0.92 | +0.62 | +0.82 | both | 12 | 8 | 1348 |
| gemini-2.5-flash | RL | – | – | – | 140.6 ± 0.9 | – | +0.68 | +0.68 | general only | 13 | 12 | 1409 |
| o1 | RL | 75.8 ± 3.1 | 94.4 ± 0.6 | 73.3 ± 6.7 | 141.7 ± 0.8 | +1.04 | +0.85 | +0.98 | both | 15 | 7 | 1402 |
| o4-mini | RL | 77.8 ± 3.0 | – | 73.3 ± 6.7 | 145.5 ± 1.1 | +1.11 | +1.39 | +1.20 | both | – | – | 1391 |

**Order within family, low to high:** gpt-4o-mini < gpt-4o < qwen-2.5-72b < deepseek-v3 | deepseek-r1 < o3-mini < gemini-2.5-flash < o1 < o4-mini

- Tied adjacent pairs (order holds in < 80 % of 10,000 draws): o3-mini / gemini-2.5-flash (P = 0.60)
- Fragile pairs (flip on the reasoning block alone): none
- Cross-source check, Spearman ρ (Epoch reasoning block vs developer-reported GPQA / AIME 2024 / MATH-500, ≥ 2 cells): 0.94 over 6 models

## Cells scored

| model | benchmark | score | SE | setting | url | note |
|---|---|---|---|---|---|---|
| gpt-4o-mini | eci | 126.46 | 2.14 | GPT-4o mini | https://epoch.ai/data/benchmark_data.zip | 95% CI 120.11 to 128.49 (eci_ci_low/high); all inputs from gpt-4o-mini-2024-07-18 |
| gpt-4o-mini | gpqa_diamond | 37.7210 | 2.41 | gpt-4o-mini-2024-07-18 | https://epoch.ai/data/benchmark_data.zip | run id L9yfwZC3snsKZshBXTaXjc started 2025-01-27 |
| gpt-4o-mini | math_level_5 | 52.6341 | 1.13 | gpt-4o-mini-2024-07-18 | https://epoch.ai/data/benchmark_data.zip | run id 5iyKgWVhAmNwrA5rNL7MbW started 2025-01-27 |
| gpt-4o-mini | otis_mock_aime | 6.9444 | 2.74 | gpt-4o-mini-2024-07-18 | https://epoch.ai/data/benchmark_data.zip | run id MPJkYPEMsQrowqtecK3mmz started 2025-07-30 |
| gpt-4o | eci | 128.83 | 1.71 | GPT-4o (Aug 2024) | https://epoch.ai/data/benchmark_data.zip | 95% CI 124.26 to 130.96 (eci_ci_low/high); all inputs from gpt-4o-2024-08-06 |
| gpt-4o | gpqa_diamond | 49.2109 | 2.60 | gpt-4o-2024-08-06 | https://epoch.ai/data/benchmark_data.zip | run id fairJpL9VekDBKxYHG9ZoG started 2025-01-27 |
| gpt-4o | math_level_5 | 53.2761 | 1.12 | gpt-4o-2024-08-06 | https://epoch.ai/data/benchmark_data.zip | run id ZQgz8AGm4KHin9MFupLu58 started 2025-01-27 |
| gpt-4o | otis_mock_aime | 6.3889 | 2.56 | gpt-4o-2024-08-06 | https://epoch.ai/data/benchmark_data.zip | run id mBUKqiVQsqXd3qmdtKP5UP started 2025-02-25 |
| qwen-2.5-72b | eci | 128.97 | 1.85 | Qwen2.5-72B | https://epoch.ai/data/benchmark_data.zip | 95% CI 123.48 to 130.73 (eci_ci_low/high); model group mixes inputs from Qwen2.5-72B base (7 benchmarks, third-party reports) and Qwen2.5-VL-72B-Instruct (2) with qwen2.5-72b-instruct [usable under amendment A1: model-group value, flagged] |
| qwen-2.5-72b | gpqa_diamond | 49.1477 | 2.69 | qwen2.5-72b-instruct | https://epoch.ai/data/benchmark_data.zip | run id WtALgW6VSFdihDZWXRm2AZ started 2025-01-27 |
| qwen-2.5-72b | math_level_5 | 63.1703 | 1.07 | qwen2.5-72b-instruct | https://epoch.ai/data/benchmark_data.zip | run id ni4DJboYYpdRssVeAuro2V started 2025-01-27 |
| qwen-2.5-72b | otis_mock_aime | 8.0556 | 2.61 | qwen2.5-72b-instruct | https://epoch.ai/data/benchmark_data.zip | run id 67YbVQfJh7sd77KH3zFgTn started 2025-02-25 |
| deepseek-v3 | eci | 132.3 | 1.83 | DeepSeek-V3 | https://epoch.ai/data/benchmark_data.zip | 95% CI 128.06 to 135.23 (eci_ci_low/high); Dec 2024 group; 1 of 14 inputs (PIQA) from DeepSeek-V3-Base |
| deepseek-v3 | gpqa_diamond | 56.5341 | 2.76 | DeepSeek-V3 | https://epoch.ai/data/benchmark_data.zip | run id Vwo3nMA8g2gGBCyTdKFMQJ started 2025-01-27 |
| deepseek-v3 | math_level_5 | 64.8508 | 1.05 | DeepSeek-V3 | https://epoch.ai/data/benchmark_data.zip | run id exvQCLCiga6gE7zvQNp2Z6 started 2025-01-27 |
| deepseek-v3 | otis_mock_aime | 15.8333 | 4.34 | DeepSeek-V3 | https://epoch.ai/data/benchmark_data.zip | run id 7saSEhfVvXuz4yTcGy5u2y started 2025-02-25 |
| deepseek-r1 | eci | 138.82 | 1.06 | DeepSeek-R1 | https://epoch.ai/data/benchmark_data.zip | 95% CI 136.04 to 140.21 (eci_ci_low/high); Jan 2025 group; all inputs from DeepSeek-R1 |
| deepseek-r1 | gpqa_diamond | 71.7172 | 3.07 | DeepSeek-R1 | https://epoch.ai/data/benchmark_data.zip | mean_score=69.22 differs from Best score across scorers (Epoch's score column); run id fFGyQR2mfDufvrSV2rzWyV started 2025-05-26 |
| deepseek-r1 | math_level_5 | 93.0514 | 0.70 | DeepSeek-R1 | https://epoch.ai/data/benchmark_data.zip | run id XVqLs2khGFSNwEbHJTEgRU started 2025-01-31 |
| deepseek-r1 | otis_mock_aime | 53.3333 | 7.52 | DeepSeek-R1 | https://epoch.ai/data/benchmark_data.zip | run id bBY5VZzpDkmTBdSSvu5Ups started 2025-02-26 |
| o3-mini | eci | 140.2 | 1.22 | o3-mini | https://epoch.ai/data/benchmark_data.zip | 95% CI 137.03 to 141.8 (eci_ci_low/high); model-group value; its inputs come from a mix of low, medium and high effort runs, not medium only [usable under amendment A1: model-group value, flagged] |
| o3-mini | gpqa_diamond | 74.2740 | 2.54 | o3-mini-2025-01-31_medium | https://epoch.ai/data/benchmark_data.zip | run id ehvA5nisC7GMbgbyy3Z4Et started 2025-01-31 |
| o3-mini | math_level_5 | 95.1662 | 0.47 | o3-mini-2025-01-31_medium | https://epoch.ai/data/benchmark_data.zip | run id 2RiSB2ii5kf2Q6fDBv2P3E started 2025-01-31 |
| o3-mini | otis_mock_aime | 63.8889 | 6.04 | o3-mini-2025-01-31_medium | https://epoch.ai/data/benchmark_data.zip | run id ajytUBY9bDPNNxuBfi5UBS started 2025-02-25 |
| gemini-2.5-flash | eci | 140.59 | 0.95 | Gemini 2.5 Flash (Jun 2025) | https://epoch.ai/data/benchmark_data.zip | 95% CI 138.32 to 142.03 (eci_ci_low/high); GA group, inputs from gemini-2.5-flash only (thinking setting not stated by Epoch; 7 inputs, 5 external) |
| o1 | eci | 141.72 | 0.82 | o1 | https://epoch.ai/data/benchmark_data.zip | 95% CI 139.71 to 142.94 (eci_ci_low/high); model-group value; its inputs come from a mix of low, medium and high effort runs, not medium only [usable under amendment A1: model-group value, flagged] |
| o1 | gpqa_diamond | 75.7576 | 3.05 | o1-2024-12-17_medium | https://epoch.ai/data/benchmark_data.zip | run id Uczhz7MKLstjLkSbbGuwdN started 2025-01-27 |
| o1 | math_level_5 | 94.4109 | 0.63 | o1-2024-12-17_medium | https://epoch.ai/data/benchmark_data.zip | run id AzanNoyhhVrtQi63Azo6hu started 2025-01-27 |
| o1 | otis_mock_aime | 73.3333 | 6.67 | o1-2024-12-17_medium | https://epoch.ai/data/benchmark_data.zip | run id KvcqycaJpCQMBigiEosyzC started 2025-02-27 |
| o4-mini | eci | 145.46 | 1.10 | o4-mini | https://epoch.ai/data/benchmark_data.zip | 95% CI 142.9 to 147.21 (eci_ci_low/high); model-group value; its inputs come from a mix of low, medium and high effort runs, not medium only [usable under amendment A1: model-group value, flagged] |
| o4-mini | gpqa_diamond | 77.7778 | 2.96 | o4-mini-2025-04-16_medium | https://epoch.ai/data/benchmark_data.zip | run id noAGevebNp5W5yAnmbEYaz started 2026-08-07 |
| o4-mini | otis_mock_aime | 73.3333 | 6.67 | o4-mini-2025-04-16_medium | https://epoch.ai/data/benchmark_data.zip | run id TWJtwC5bzXa9HorTH8DNJy started 2026-08-07; run after Sept 2025 answer-extractor change |
