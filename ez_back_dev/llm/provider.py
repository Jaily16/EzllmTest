from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from langchain_core.embeddings import Embeddings
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from openai import APIConnectionError, APITimeoutError, RateLimitError

from app.config import get_settings


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
    try:
        client = (
            get_chat_client(name, minimum_timeout_seconds)
            if minimum_timeout_seconds > 0
            else get_chat_client(name)
        )
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

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return get_embeddings().embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return get_embeddings().embed_query(text)


@lru_cache(maxsize=1)
def get_lazy_embeddings() -> LazyZhipuEmbeddings:
    return LazyZhipuEmbeddings()


def clear_provider_caches() -> None:
    get_chat_client.cache_clear()
    get_chat_model.cache_clear()
    get_embeddings.cache_clear()
    get_lazy_embeddings.cache_clear()
