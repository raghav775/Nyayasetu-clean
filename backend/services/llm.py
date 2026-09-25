import os
import time

# Groq retired llama-3.3-70b-versatile and llama-3.1-8b-instant for free/developer accounts on
# 2026-08-16 — calls to them now fail with 404 "model_not_found". Groq keeps replacing models,
# so the chain tried is: GROQ_MODEL, then GROQ_FALLBACK_MODELS, then these built-in defaults.
# A model that reports itself retired is skipped for the rest of the process, so a stale
# GROQ_MODEL in the environment can't take the whole app down.
# Current list: https://console.groq.com/docs/models
DEFAULT_GROQ_MODELS = ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

# Groq rejects a request up-front (HTTP 413) when prompt tokens + completion cap exceed the
# model's tokens-per-minute limit (free tier: 8k for gpt-oss). Every request is trimmed to these
# budgets, which sit a little under the real limits. Paid tiers can raise them for every model
# with GROQ_TOKEN_BUDGET.
TOKEN_BUDGETS = {
    "openai/gpt-oss-120b": 7_000,
    "openai/gpt-oss-20b": 7_000,
    "llama-3.3-70b-versatile": 10_000,  # only for accounts where these are still served
    "llama-3.1-8b-instant": 5_000,
}
DEFAULT_TOKEN_BUDGET = 5_000
CHARS_PER_TOKEN = 3.5  # deliberately pessimistic — English legal text averages ~4.4
# gpt-oss models are reasoning models: reasoning tokens are spent from the same completion cap
# as the answer, so callers' max_tokens gets this much extra room.
REASONING_HEADROOM = 600

REQUEST_TIMEOUT_S = 30
TOTAL_DEADLINE_S = 60

# Lower index = more useful to tell the user when several models failed differently.
REASON_PRIORITY = ["auth", "rate_limited", "too_large", "model_unavailable", "timeout", "provider_error"]
USER_MESSAGES = {
    "not_configured": "The AI service is not configured on the server. Please contact the administrator.",
    "auth": "The AI service rejected the server's credentials. Please contact the administrator.",
    "rate_limited": "The AI service has reached its usage limit. Please wait a minute and try again.",
    "too_large": "That request is too large for the AI service. Please try a shorter query.",
    "model_unavailable": "The AI model configured on the server is no longer available. Please contact the administrator.",
    "timeout": "The AI service did not respond in time. Please try again.",
    "provider_error": "The AI service is temporarily unavailable. Please try again.",
}

_last_failure = None
_retired_models = set()


class LLMUnavailableError(Exception):
    """No configured LLM provider could answer. `message` is safe to show to end users."""

    def __init__(self, reason: str):
        self.reason = reason
        self.message = USER_MESSAGES.get(reason, USER_MESSAGES["provider_error"])
        super().__init__(self.message)


def clip(text: str, max_chars: int) -> str:
    """Trim text to max_chars so prompts stay inside the token budget."""
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + " …"


def _groq_configured() -> bool:
    key = os.getenv("GROQ_API_KEY", "").strip()
    return bool(key) and key != "your_groq_api_key_here"


def _groq_models() -> list:
    configured = [os.getenv("GROQ_MODEL", "")] + os.getenv("GROQ_FALLBACK_MODELS", "").split(",")
    models = [m.strip() for m in configured if m.strip()] + DEFAULT_GROQ_MODELS
    return [m for m in dict.fromkeys(models) if m not in _retired_models]  # de-duplicate, keep order


def _is_reasoning_model(model: str) -> bool:
    return model.startswith("openai/gpt-oss")


def _token_budget(model: str) -> int:
    override = os.getenv("GROQ_TOKEN_BUDGET", "").strip()
    if override.isdigit():
        return int(override)
    return TOKEN_BUDGETS.get(model, DEFAULT_TOKEN_BUDGET)


def _estimate_tokens(text: str) -> int:
    return int(len(text) / CHARS_PER_TOKEN) + 1


def _fit_request(system_prompt: str, user_message: str, max_tokens: int, budget: int, reasoning: bool):
    """Return (user_message, completion_cap) sized so prompt + completion fit within `budget` tokens."""
    wanted = max_tokens + (REASONING_HEADROOM if reasoning else 0)
    out_tokens = min(wanted, budget // 2)
    room = max(budget - out_tokens - _estimate_tokens(system_prompt) - 50, 200)
    if _estimate_tokens(user_message) > room:
        cut = int(room * CHARS_PER_TOKEN)
        user_message = user_message[:cut].rstrip() + "\n\n[Context truncated to fit the model's request limit.]"
    return user_message, out_tokens


def _classify(exc: Exception):
    """Map a provider exception to (reason, worth_retrying_same_model)."""
    status = getattr(exc, "status_code", None)
    name = type(exc).__name__
    text = str(exc).lower()
    if status in (401, 403):
        return "auth", False
    if status == 429:
        return "rate_limited", False
    if status == 413:
        return "too_large", False
    if status == 404 or (status == 400 and ("decommission" in text or "model_not_found" in text)):
        return "model_unavailable", False
    if status is not None and status >= 500:
        return "provider_error", True
    if status == 400:
        return "bad_request", False
    if status is not None:
        return "provider_error", False
    if "Timeout" in name or "Connection" in name:
        return "timeout", True
    return "provider_error", False


def call_groq(system_prompt: str, user_message: str, model: str, max_tokens: int, reasoning: bool = False) -> str:
    from groq import Groq
    # max_retries=0: the SDK would otherwise sleep up to 60s honouring Retry-After on a
    # 429 — call_llm falls back to the next model instead of waiting.
    client = Groq(
        api_key=os.getenv("GROQ_API_KEY", "").strip(),
        timeout=REQUEST_TIMEOUT_S,
        max_retries=0,
    )

    kwargs = {}
    if reasoning:
        kwargs["reasoning_effort"] = "low"  # keeps reasoning tokens from eating the answer's budget

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.1,
        max_completion_tokens=max_tokens,
        # response_format deliberately not set — models ignore the schema in json_object
        # mode and return a generic dummy object instead of the requested structure.
        **kwargs,
    )
    content = response.choices[0].message.content
    if not content or not content.strip():
        raise ValueError("Groq returned an empty completion (finish_reason=%s)" % response.choices[0].finish_reason)
    return content.strip()


def call_ollama(system_prompt: str, user_message: str, json_mode: bool = False) -> str:
    import ollama

    kwargs = dict(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
    if json_mode:
        kwargs["format"] = "json"  # safe to keep for Ollama, it respects the schema

    response = ollama.chat(**kwargs)
    return response["message"]["content"].strip()


def call_llm(system_prompt: str, user_message: str, json_mode: bool = False, max_tokens: int = 2048) -> str:
    """
    Groq (each model in turn) → Ollama (local/offline).
    Raises LLMUnavailableError if nothing could answer.
    """
    global _last_failure
    started = time.monotonic()
    failures = []

    if _groq_configured():
        for model in _groq_models():
            if time.monotonic() - started > TOTAL_DEADLINE_S:
                break
            reasoning = _is_reasoning_model(model)
            retried = False
            scale = 1.0
            while True:
                user, out_tokens = _fit_request(
                    system_prompt, user_message, max_tokens, int(_token_budget(model) * scale), reasoning
                )
                try:
                    answer = call_groq(system_prompt, user, model, out_tokens, reasoning=reasoning)
                    _last_failure = None
                    return answer
                except Exception as e:
                    reason, retryable = _classify(e)
                    print(f"[LLM] Groq {model} failed ({reason}, status={getattr(e, 'status_code', None)}): {e}")
                    if reason == "bad_request" and reasoning:
                        reasoning = False  # some accounts reject reasoning_effort — retry plain
                        continue
                    if reason == "too_large" and scale > 0.4:
                        scale *= 0.7  # the token estimate was optimistic for this text — shrink and retry
                        continue
                    if retryable and not retried:
                        retried = True
                        time.sleep(1)
                        continue
                    if reason == "model_unavailable":
                        _retired_models.add(model)
                        print(f"[LLM] {model} is not available on Groq (retired?) — skipping it from now on. "
                              "Set GROQ_MODEL to a current model: https://console.groq.com/docs/models")
                    failures.append(reason)
                    break
    else:
        print("[LLM] GROQ_API_KEY is not set — skipping Groq")

    try:
        return call_ollama(system_prompt, user_message, json_mode=json_mode)
    except Exception as e:
        print(f"[LLM] Ollama unavailable: {e}")

    failures = [f if f in REASON_PRIORITY else "provider_error" for f in failures]
    if failures:
        reason = min(failures, key=REASON_PRIORITY.index)
    elif _groq_configured():
        reason = "model_unavailable"  # every configured model was already known to be retired
    else:
        reason = "not_configured"
    _last_failure = {"reason": reason, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    raise LLMUnavailableError(reason)


def llm_status() -> dict:
    """Coarse, secret-free status for the /health endpoint."""
    configured = _groq_configured()
    return {
        "groq_configured": configured,
        "models": _groq_models() if configured else [],
        "retired_models": sorted(_retired_models),
        "last_failure": _last_failure,
    }
