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
    # What the stored `reasoning` field holds (checked in REPLICATION_NOTES.md, "Eval awareness"): "raw" = the
    # model's own chain of thought, "summary" = a provider-written summary of it, "none" = no reasoning returned.
    cot: str = "none"

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
                  max_tokens=MAX_TOKENS_TEST + REASONING_BUDGET, cot="summary"),
        ModelSpec("o4-mini", "openai/o4-mini", "o1-mini", "RL", substitute=True, send_temperature=False,
                  max_tokens=MAX_TOKENS_TEST + REASONING_BUDGET, cot="summary"),
        ModelSpec("o3-mini", "openai/o3-mini", "o3-mini", "RL", send_temperature=False,
                  max_tokens=MAX_TOKENS_TEST + REASONING_BUDGET, cot="summary"),
        # Jan-2025 DeepSeek/Gemini APIs didn't count CoT against max_tokens: ~1000 answer + reasoning budget.
        ModelSpec("gemini-2.5-flash", "google/gemini-2.5-flash", "Gemini 2.0 FTE.", "RL", substitute=True,
                  max_tokens=MAX_TOKENS_TEST + REASONING_BUDGET,
                  extra_body={"reasoning": {"max_tokens": REASONING_BUDGET}}, cot="summary"),
        ModelSpec("deepseek-r1", "deepseek/deepseek-r1", "DeepSeek-R1", "RL",
                  max_tokens=MAX_TOKENS_TEST + REASONING_BUDGET,
                  extra_body={"reasoning": {"max_tokens": REASONING_BUDGET}, "provider": OPEN_WEIGHT_PROVIDER},
                  cot="raw"),
    ]
}

# Reasoning-effort sweep (Table 7, not in the paper; REPLICATION_NOTES.md, "Reasoning-effort sweep"): the same two
# o-series models at explicit low / medium / high effort, full `nudge` prompt, same judge. Kept out of TEST_MODELS so
# Tables 1-6 and the figures never see them; `ALL_MODELS` is what `ie generate` / `ie judge` accept. The stored
# default-effort runs (`o3-mini`, `o4-mini`, `o4-mini` nudge-rep) are the reference: OpenAI's default effort is
# medium, so `<model>@medium` is a same-settings replicate of them. One generous completion cap for every arm, so
# that the cap is not a variable; `finish_reason == "length"` is counted in Table 7.
EFFORT_LEVELS = ("low", "medium", "high")
EFFORT_BASE_MODELS = ("o3-mini", "o4-mini")
SWEEP_REASONING_BUDGET = 32000
EFFORT_MODELS: dict[str, ModelSpec] = {
    f"{base}@{effort}": ModelSpec(f"{base}@{effort}", TEST_MODELS[base].openrouter_id, "", "RL", added=True,
                                  send_temperature=False, max_tokens=MAX_TOKENS_TEST + SWEEP_REASONING_BUDGET,
                                  extra_body={"reasoning": {"effort": effort}})
    for base in EFFORT_BASE_MODELS for effort in EFFORT_LEVELS
}
ALL_MODELS = TEST_MODELS | EFFORT_MODELS


def effort_of(key: str) -> tuple[str, str | None]:
    """("o4-mini", "high") for a sweep key, (key, None) otherwise."""
    base, _, effort = key.partition("@")
    return (base, effort) if effort in EFFORT_LEVELS else (key, None)


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

# Task-audit panel (Table 8; REPLICATION_NOTES.md, "Task audit"): three labs, none of them the convergence judge
# (gpt-4o) or one of the nine evaluated models. Each is pinned to one provider (no fallback, and the request fails
# rather than silently dropping `response_format`), because the provider changes the serving stack and, for the
# open-weight model, the quantization. Medium effort for all three; reasoning counts against max_tokens, hence
# 16000. Haiku 5.5 and GPT-6 Luna reject `temperature` on OpenRouter. Verify each with `ie audit-tasks --smoke`.
def _only(provider: str) -> dict:
    return {"only": [provider], "allow_fallbacks": False, "require_parameters": True}


_AUDIT_BODY = {"reasoning": {"effort": "medium"}, "response_format": {"type": "json_object"}}
AUDIT_JUDGES: dict[str, ModelSpec] = {
    m.key: m
    for m in [
        ModelSpec("claude-haiku-5.5", "anthropic/claude-haiku-5.5", "", send_temperature=False, max_tokens=16000,
                  extra_body=_AUDIT_BODY | {"provider": _only("google-vertex")}),
        ModelSpec("gpt-6-luna", "openai/gpt-6-luna", "", send_temperature=False, max_tokens=16000,
                  extra_body=_AUDIT_BODY | {"provider": _only("azure")}),
        # DeepInfra at fp8, the floor of the open-weight test models (OPEN_WEIGHT_PROVIDER); OpenInference is fp4 only.
        ModelSpec("deepseek-v4.1-flash", "deepseek/deepseek-v4.1-flash-1017", "", max_tokens=16000,
                  extra_body=_AUDIT_BODY | {"provider": _only("deepinfra") | {"quantizations": ["fp8"]}}),
    ]
}

# Verbalized eval awareness (VEA) judge, as in Bharadwaj & Kirk's VEA-through-training pipeline (upstream/judge_vea.py):
# GPT-5-mini at low reasoning effort, 4000 completion tokens (reasoning + the short REASONING/QUOTE answer).
VEA_JUDGE = ModelSpec("gpt-5-mini", "openai/gpt-5-mini", "", send_temperature=False, max_tokens=4000,
                      extra_body={"reasoning": {"effort": "low"}})
# Second VEA judge (ours, REPLICATION_NOTES.md "Eval awareness", "Second judge"): the frame judge's model and effort,
# because gpt-5-mini at low effort missed the single-sentence asides. Same rubric and parser; results/vea/gpt-5/.
VEA_JUDGE_GPT5 = ModelSpec("gpt-5", "openai/gpt-5", "", send_temperature=False, max_tokens=8000,
                           extra_body={"reasoning": {"effort": "medium"}})
VEA_JUDGES = {j.key: j for j in (VEA_JUDGE, VEA_JUDGE_GPT5)}
# Only models whose stored `reasoning` is their own chain of thought can be judged for VEA (or frame awareness).
VEA_MODELS = [m.key for m in TEST_MODELS.values() if m.cot == "raw"]

# Frame-awareness judge (Rajamanoharan & Nanda's rubric, upstream/frame_awareness_prompt.txt). The post used Gemini 3
# Flash Preview. Not gpt-5-mini at low effort: on the VEA pass it missed 4 of 5 single-sentence asides inside long
# chains of thought (REPLICATION_NOTES.md, "Eval awareness", Results), and frame awareness shows up the same way.
# 8000 tokens: reasoning at medium effort + a JSON answer with up to 5 quotes.
FRAME_JUDGE = ModelSpec("gpt-5", "openai/gpt-5", "", send_temperature=False, max_tokens=8000,
                        extra_body={"reasoning": {"effort": "medium"}})
# Table 3 goal-nudging ablation: the paper's two models (GPT-4o, DeepSeek-R1) plus DeepSeek-V3 and o4-mini.
TABLE3_MODELS = ["gpt-4o", "deepseek-v3", "o4-mini", "deepseek-r1"]
# System-prompt ablations (Table 6): every test model except o1, which costs ~$6 per 76-task run (about 20x the
# others); add it later with `ie generate --variants ... --models o1` if the results warrant it.
ABLATION_MODELS = [m for m in TEST_MODELS if m != "o1"]
# Test-retest replicate of the full prompt (`nudge-rep`): the noise floor for the ablation contrasts.
REP_MODELS = ["gpt-4o", "gpt-4o-mini", "deepseek-v3", "o4-mini"]
