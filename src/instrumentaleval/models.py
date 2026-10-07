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

    def request_config(self) -> dict:
        """Everything about a request besides the prompt; stored responses are reused only if it matches."""
        return {"openrouter_id": self.openrouter_id, "max_tokens": self.max_tokens,
                "send_temperature": self.send_temperature, "extra_body": self.extra_body}

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
        # o-series: no temperature, as upstream. Upstream's max_completion_tokens=1000 includes hidden reasoning,
        # which left o1 with empty answers on 4/12 smoke-test tasks, while the paper's rates imply 76/76 valid.
        # So they get the same ~1000-answer + reasoning budget as R1/Gemini (default reasoning effort).
        ModelSpec("o1", "openai/o1", "o1", "RL", send_temperature=False,
                  max_tokens=MAX_TOKENS_TEST + REASONING_BUDGET),
        ModelSpec("o4-mini", "openai/o4-mini", "o1-mini", "RL", substitute=True, send_temperature=False,
                  max_tokens=MAX_TOKENS_TEST + REASONING_BUDGET),
        ModelSpec("o3-mini", "openai/o3-mini", "o3-mini", "RL", send_temperature=False,
                  max_tokens=MAX_TOKENS_TEST + REASONING_BUDGET),
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
        # No Grok 2 slot: mistral-large-2407 was tried and dropped (REPLICATION_NOTES.md, deviation 10).
        ModelSpec("gemini-2.5-flash", "google/gemini-2.5-flash", "Gemini 2.0 Flash", substitute=True,
                  max_tokens=MAX_TOKENS_JUDGE, extra_body=_NO_REASONING),
    ]
}

# Set to the judge with the lowest false-positive rate on the neutral tasks (README step 4).
DEFAULT_JUDGE = "gpt-4o"
# Table 3 goal-nudging ablation: the paper's two models (GPT-4o, DeepSeek-R1) plus DeepSeek-V3 and o4-mini.
TABLE3_MODELS = ["gpt-4o", "deepseek-v3", "o4-mini", "deepseek-r1"]
# System-prompt ablations (Table 6): every test model except o1, which costs ~$6 per 76-task run (about 20x the
# others); add it later with `ie generate --variants ... --models o1` if the results warrant it.
ABLATION_MODELS = [m for m in TEST_MODELS if m != "o1"]
# Test-retest replicate of the full prompt (`nudge-rep`): the noise floor for the ablation contrasts.
REP_MODELS = ["gpt-4o", "gpt-4o-mini", "deepseek-v3", "o4-mini"]
