"""OpenRouter chat client: one request, with retries, returning everything we want to log."""

import os
import random
import time

import openai
from dotenv import load_dotenv

from .models import ModelSpec

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MAX_ATTEMPTS = 6
# 429s from an overloaded provider pool (DeepInfra, 2026-10-22) last minutes, not seconds: more attempts, longer
# waits (15 s doubling to 5 min, ~23 min in all), jittered so parallel workers don't retry in lockstep.
MAX_ATTEMPTS_RATE_LIMITED = 9

_client: openai.OpenAI | None = None


def get_client() -> openai.OpenAI:
    global _client
    if _client is None:
        load_dotenv()
        key = os.environ.get("OPENROUTER_API_KEY")
        if not key:
            raise RuntimeError("OPENROUTER_API_KEY is not set (copy .env.example to .env and fill it in)")
        _client = openai.OpenAI(base_url=OPENROUTER_BASE_URL, api_key=key, max_retries=0, timeout=600)
    return _client


class EmptyChoiceError(RuntimeError):
    """OpenRouter returned 200 with no usable choice (upstream provider error)."""


def chat(spec: ModelSpec, system: str | None, user: str, temperature: float | None) -> dict:
    """Send one system+user request (user only when `system` is None). Retries transient failures; raises after
    MAX_ATTEMPTS."""
    messages = [{"role": "user", "content": user}]
    if system is not None:
        messages.insert(0, {"role": "system", "content": system})
    kwargs = dict(model=spec.openrouter_id, messages=messages, max_tokens=spec.max_tokens)
    if spec.send_temperature:
        kwargs["temperature"] = temperature
    if spec.extra_body:
        kwargs["extra_body"] = spec.extra_body

    attempt = 0
    while True:
        attempt += 1
        try:
            resp = get_client().chat.completions.create(**kwargs)
            if not resp.choices:
                raise EmptyChoiceError(str(getattr(resp, "error", None) or resp.model_extra))
            choice = resp.choices[0]
            if (choice.model_extra or {}).get("error"):
                raise EmptyChoiceError(str(choice.model_extra["error"]))
            msg = choice.message
            usage = resp.usage
            details = getattr(usage, "completion_tokens_details", None) if usage else None
            return {
                "content": msg.content or "",
                "reasoning": (msg.model_extra or {}).get("reasoning"),
                "finish_reason": choice.finish_reason,
                "served_model": resp.model,
                "provider": (resp.model_extra or {}).get("provider"),
                "prompt_tokens": usage.prompt_tokens if usage else None,
                "completion_tokens": usage.completion_tokens if usage else None,
                "reasoning_tokens": getattr(details, "reasoning_tokens", None) if details else None,
            }
        except (openai.BadRequestError, openai.AuthenticationError, openai.PermissionDeniedError,
                openai.NotFoundError):
            raise  # not transient
        except (openai.APIError, EmptyChoiceError) as e:
            limited = isinstance(e, openai.RateLimitError)
            if attempt == (MAX_ATTEMPTS_RATE_LIMITED if limited else MAX_ATTEMPTS):
                raise
            wait = min(300, 15 * 2 ** (attempt - 1)) * random.uniform(0.75, 1.25) if limited else min(60, 2 ** attempt)
            print(f"  [{spec.key}] attempt {attempt} failed ({type(e).__name__}: {str(e)[:120]}); "
                  f"retrying in {wait:.0f}s")
            time.sleep(wait)
