"""Model registry: test models and judges, with the request parameters each one receives.

Upstream parameters (main()): test T=0.0, max_tokens=1000; judge T=0.0, max_tokens=500.
Rationale for every substitute or added model is in REPLICATION_NOTES.md.
"""

from dataclasses import dataclass, field

TEMPERATURE_TEST = 0.0
TEMPERATURE_JUDGE = 0.0
MAX_TOKENS_TEST = 1000
MAX_TOKENS_JUDGE = 500

# Open-weight models are served by third parties on OpenRouter. Exclude sub-fp8 quantizations;
# "unknown" is allowed because DeepSeek-V3's only non-fp4 provider doesn't report one.
OPEN_WEIGHT_PROVIDER = {"quantizations": ["fp8", "fp16", "bf16", "fp32", "unknown"]}

# Reasoning budget for models whose original API did not count chain-of-thought against max_tokens.
REASONING_BUDGET = 8000


@dataclass(frozen=True)
class ModelSpec:
    key: str
    openrouter_id: str
    paper_name: str  # column name in the paper ("" for models we added)
    family: str = ""  # "RL" or "RLHF" for test models
    substitute: bool = False
    added: bool = False  # not in the paper at all
    send_temperature: bool = True
    max_tokens: int = MAX_TOKENS_TEST
    extra_body: dict = field(default_factory=dict)

    @property
    def label(self) -> str:
        if self.added:
            return f"{self.key} (added)"
        if self.substitute:
            return f"{self.key} (for {self.paper_name})"
        return self.key


TEST_MODELS: dict[str, ModelSpec] = {
    m.key: m
    for m in [
        # --- RLHF ---
        ModelSpec("gpt-4o", "openai/gpt-4o-2024-08-06", "GPT-4o", "RLHF"),
        ModelSpec("gpt-4o-mini", "openai/gpt-4o-mini-2024-07-18", "", "RLHF", added=True),
        ModelSpec("deepseek-v3", "deepseek/deepseek-chat", "DeepSeek-V3", "RLHF",
                  extra_body={"provider": OPEN_WEIGHT_PROVIDER}),
        ModelSpec("qwen-2.5-72b", "qwen/qwen-2.5-72b-instruct", "", "RLHF", added=True,
                  extra_body={"provider": OPEN_WEIGHT_PROVIDER}),
        # --- RL ---
        # o-series: upstream sends max_completion_tokens=1000 (reasoning included) and no temperature.
        ModelSpec("o1", "openai/o1", "o1", "RL", send_temperature=False),
        ModelSpec("o4-mini", "openai/o4-mini", "o1-mini", "RL", substitute=True, send_temperature=False),
        ModelSpec("o3-mini", "openai/o3-mini", "o3-mini", "RL", send_temperature=False),
        # Jan-2025 DeepSeek/Gemini APIs didn't count CoT against max_tokens: ~1000 answer + reasoning budget.
        ModelSpec("gemini-2.5-flash", "google/gemini-2.5-flash", "Gemini 2.0 FTE.", "RL", substitute=True,
                  max_tokens=MAX_TOKENS_TEST + REASONING_BUDGET,
                  extra_body={"reasoning": {"max_tokens": REASONING_BUDGET}}),
        ModelSpec("deepseek-r1", "deepseek/deepseek-r1", "DeepSeek-R1", "RL",
                  max_tokens=MAX_TOKENS_TEST + REASONING_BUDGET,
                  extra_body={"reasoning": {"max_tokens": REASONING_BUDGET}, "provider": OPEN_WEIGHT_PROVIDER}),
    ]
}

_NO_REASONING = {"reasoning": {"enabled": False}}

JUDGES: dict[str, ModelSpec] = {
    m.key: m
    for m in [
        ModelSpec("gpt-4o", "openai/gpt-4o-2024-08-06", "GPT-4o", max_tokens=MAX_TOKENS_JUDGE),
        ModelSpec("claude-sonnet-4", "anthropic/claude-sonnet-4", "Sonnet-3.5", substitute=True,
                  max_tokens=MAX_TOKENS_JUDGE, extra_body=_NO_REASONING),
        ModelSpec("mistral-large-2407", "mistralai/mistral-large-2407", "Grok 2", substitute=True,
                  max_tokens=MAX_TOKENS_JUDGE),
        ModelSpec("gemini-2.5-flash", "google/gemini-2.5-flash", "Gemini 2.0 Flash", substitute=True,
                  max_tokens=MAX_TOKENS_JUDGE, extra_body=_NO_REASONING),
    ]
}

DEFAULT_JUDGE = "gpt-4o"
# Table 3 in the paper: goal-nudging ablation on these two models.
DEFAULT_NONUDGE_MODELS = ["gpt-4o", "deepseek-r1"]
