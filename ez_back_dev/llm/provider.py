from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import time
from typing import Any

from langchain_core.embeddings import Embeddings
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from openai import APIConnectionError, APITimeoutError, RateLimitError

from app.config import get_settings
from service.agentBudgetLedger import (
    current_agent_budget,
    reserve_embedding_budget,
    reserve_model_budget,
)
from service.agentTelemetry import (
    agent_span,
    agent_trace_is_active,
    get_agent_telemetry,
)


@dataclass(frozen=True)
class ModelSpec:
    label: str
    provider: str
    default_model: str
    api_key_field: str
    api_key_env: str
    base_url_field: str
    model_field: str
    timeout_field: str
    temperature: float | None = 0.5
    context_window_tokens: int = 200_000
    max_output_tokens: int = 32_768


_MODEL_SPECS = (
    ModelSpec(
        "GLM-4.7",
        "zhipu",
        "glm-4.7",
        "zhipu_api_key",
        "ZHIPU_API_KEY",
        "zhipu_base_url",
        "zhipu_chat_model",
        "zhipu_timeout_seconds",
        context_window_tokens=200_000,
        max_output_tokens=128_000,
    ),
    ModelSpec(
        "通义千问",
        "alibaba",
        "qwen3.5-plus",
        "dashscope_api_key",
        "DASHSCOPE_API_KEY",
        "dashscope_base_url",
        "dashscope_chat_model",
        "dashscope_timeout_seconds",
        context_window_tokens=1_000_000,
        max_output_tokens=65_536,
    ),
    ModelSpec(
        "DeepSeek",
        "deepseek",
        "deepseek-v4-flash",
        "deepseek_api_key",
        "DEEPSEEK_API_KEY",
        "deepseek_base_url",
        "deepseek_chat_model",
        "deepseek_timeout_seconds",
        context_window_tokens=1_000_000,
        max_output_tokens=384_000,
    ),
    ModelSpec(
        "Moonshot Kimi",
        "moonshot",
        "kimi-k2.5",
        "moonshot_api_key",
        "MOONSHOT_API_KEY",
        "moonshot_base_url",
        "moonshot_chat_model",
        "moonshot_timeout_seconds",
        temperature=None,
        context_window_tokens=256_000,
        max_output_tokens=32_768,
    ),
)
_MODEL_REGISTRY = {spec.label: spec for spec in _MODEL_SPECS}
SUPPORTED_MODEL_LABEL = _MODEL_SPECS[0].label


class LLMError(RuntimeError):
    """Base error for model configuration and invocation failures."""


class UnsupportedModelError(LLMError):
    pass


class LLMConfigurationError(LLMError):
    pass


class LLMTimeoutError(LLMError):
    pass


class LLMRateLimitError(LLMError):
    pass


class LLMProviderError(LLMError):
    pass


class LLMEmptyResponseError(LLMError):
    pass


class LLMOutputParsingError(LLMError):
    pass


def list_model_specs() -> tuple[ModelSpec, ...]:
    return _MODEL_SPECS


def list_model_labels() -> list[str]:
    return [spec.label for spec in _MODEL_SPECS]


def get_model_spec(name: str) -> ModelSpec:
    try:
        return _MODEL_REGISTRY[name]
    except KeyError as exc:
        supported = ", ".join(list_model_labels())
        raise UnsupportedModelError(
            f"Unsupported model '{name}'. Supported models: {supported}"
        ) from exc


def ensure_supported_model(name: str) -> None:
    get_model_spec(name)


def provider_options(profile: Any, name: str) -> dict[str, Any]:
    """Translate a resolved workflow budget into provider request fields."""
    spec = get_model_spec(name)
    max_tokens = int(profile.output_token_limit)
    reasoning_mode = profile.reasoning_mode
    options: dict[str, Any] = {
        "max_tokens": max_tokens,
        "reasoning_mode": reasoning_mode,
    }

    if spec.provider in {"zhipu", "alibaba"}:
        options["temperature"] = 0.5

    if reasoning_mode == "off":
        if spec.provider == "alibaba":
            options["enable_thinking"] = False
            options["extra_body"] = {"enable_thinking": False}
        elif spec.provider == "deepseek":
            options["extra_body"] = {"thinking": {"type": "disabled"}}
        else:
            options["extra_body"] = {"thinking": {"type": "disabled"}}
        return options

    if spec.provider == "alibaba":
        default_budget = 1_024 if reasoning_mode == "low" else 4_096
        requested_budget = profile.reasoning_budget or default_budget
        thinking_budget = min(
            requested_budget,
            default_budget,
            max_tokens,
        )
        options["enable_thinking"] = True
        options["thinking_budget"] = thinking_budget
        options["extra_body"] = {
            "enable_thinking": True,
            "thinking_budget": thinking_budget,
        }
    elif spec.provider == "deepseek":
        options["reasoning_effort"] = "high"
        options["extra_body"] = {"thinking": {"type": "enabled"}}
    else:
        options["extra_body"] = {"thinking": {"type": "enabled"}}
    return options


def _configured_api_key(spec: ModelSpec, settings: Any) -> str:
    api_key = getattr(settings, spec.api_key_field, "")
    if not api_key or api_key.startswith("replace_with_your_"):
        raise LLMConfigurationError(
            f"{spec.api_key_env} is not configured for {spec.label}. "
            "Copy .env.example to .env and set the selected provider key."
        )
    return api_key


@lru_cache(maxsize=len(_MODEL_SPECS) * 2)
def get_chat_client(
    name: str, minimum_timeout_seconds: float = 0.0
) -> ChatOpenAI:
    spec = get_model_spec(name)
    settings = get_settings()
    configured_timeout = getattr(settings, spec.timeout_field)
    kwargs: dict[str, Any] = {
        "model": getattr(settings, spec.model_field),
        "api_key": _configured_api_key(spec, settings),
        "base_url": getattr(settings, spec.base_url_field),
        "timeout": max(configured_timeout, minimum_timeout_seconds),
        "max_retries": 0,
    }
    if spec.temperature is not None:
        kwargs["temperature"] = spec.temperature
    return ChatOpenAI(**kwargs)


def _status_code(error: Exception) -> int | None:
    direct_status = getattr(error, "status_code", None)
    if isinstance(direct_status, int):
        return direct_status
    response = getattr(error, "response", None)
    response_status = getattr(response, "status_code", None)
    return response_status if isinstance(response_status, int) else None


def invoke_chat_model(
    name: str, value: Any, minimum_timeout_seconds: float = 0.0
):
    # A no-op for every legacy REST/SSE call.  Aspect 3 installs the guard only
    # while a leased Agent step is executing.
    reserve_model_budget(value)
    started = time.perf_counter()
    active = agent_trace_is_active()
    try:
        with agent_span(
            "gen_ai.chat",
            {
                "gen_ai.operation.name": "chat",
                "gen_ai.request.model": name,
            },
        ):
            client = (
                get_chat_client(name, minimum_timeout_seconds)
                if minimum_timeout_seconds > 0
                else get_chat_client(name)
            )
            guard = current_agent_budget()
            if guard is not None and isinstance(client, ChatOpenAI):
                client = client.bind(max_tokens=guard.model_max_output_tokens)
            result = client.invoke(value)
    except LLMError:
        raise
    except (APITimeoutError, APIConnectionError, TimeoutError, ConnectionError) as exc:
        raise LLMTimeoutError(f"{name} request timed out or could not connect") from exc
    except RateLimitError as exc:
        raise LLMRateLimitError(f"{name} request was rate limited") from exc
    except Exception as exc:
        if _status_code(exc) == 429:
            raise LLMRateLimitError(f"{name} request was rate limited") from exc
        raise LLMProviderError(f"{name} provider request failed") from exc

    if active:
        telemetry = get_agent_telemetry()
        telemetry.counter(
            "ezllm.agent.model.calls",
            labels={"model": name, "status": "success"},
        )
        telemetry.histogram(
            "ezllm.agent.model.duration",
            (time.perf_counter() - started) * 1_000,
            {"model": name, "status": "success"},
        )
    content = getattr(result, "content", None)
    if content is None or (isinstance(content, str) and not content.strip()):
        raise LLMEmptyResponseError(f"{name} returned an empty response")
    return result


@lru_cache(maxsize=len(_MODEL_SPECS) * 2)
def get_chat_model(
    name: str = SUPPORTED_MODEL_LABEL,
    minimum_timeout_seconds: float = 0.0,
) -> RunnableLambda:
    """Return a Runnable that creates the selected remote client on invocation."""
    ensure_supported_model(name)
    return RunnableLambda(
        lambda value: invoke_chat_model(name, value, minimum_timeout_seconds)
    )


def get_lazy_chat_model(name: str = SUPPORTED_MODEL_LABEL) -> RunnableLambda:
    """Compatibility alias retained for existing wrapper imports."""
    return get_chat_model(name)


@lru_cache(maxsize=1)
def get_embeddings() -> OpenAIEmbeddings:
    settings = get_settings()
    spec = get_model_spec(SUPPORTED_MODEL_LABEL)
    return OpenAIEmbeddings(
        model=settings.zhipu_embedding_model,
        api_key=_configured_api_key(spec, settings),
        base_url=settings.zhipu_base_url,
        chunk_size=64,
    )


class LazyZhipuEmbeddings(Embeddings):
    """Delay API-key validation until vectors are actually requested."""

    @property
    def model_name(self) -> str:
        return get_settings().zhipu_embedding_model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        reserve_embedding_budget(texts)
        started = time.perf_counter()
        active = agent_trace_is_active()
        with agent_span(
            "gen_ai.embeddings",
            {"gen_ai.operation.name": "embeddings"},
        ):
            result = get_embeddings().embed_documents(texts)
        if active:
            telemetry = get_agent_telemetry()
            telemetry.counter(
                "ezllm.agent.embedding.calls", labels={"status": "success"}
            )
            telemetry.histogram(
                "ezllm.agent.embedding.duration",
                (time.perf_counter() - started) * 1_000,
                {"status": "success"},
            )
        return result

    def embed_query(self, text: str) -> list[float]:
        reserve_embedding_budget([text])
        started = time.perf_counter()
        active = agent_trace_is_active()
        with agent_span(
            "gen_ai.embeddings",
            {"gen_ai.operation.name": "embeddings"},
        ):
            result = get_embeddings().embed_query(text)
        if active:
            telemetry = get_agent_telemetry()
            telemetry.counter(
                "ezllm.agent.embedding.calls", labels={"status": "success"}
            )
            telemetry.histogram(
                "ezllm.agent.embedding.duration",
                (time.perf_counter() - started) * 1_000,
                {"status": "success"},
            )
        return result


@lru_cache(maxsize=1)
def get_lazy_embeddings() -> LazyZhipuEmbeddings:
    return LazyZhipuEmbeddings()


def clear_provider_caches() -> None:
    get_chat_client.cache_clear()
    get_chat_model.cache_clear()
    get_embeddings.cache_clear()
    get_lazy_embeddings.cache_clear()
