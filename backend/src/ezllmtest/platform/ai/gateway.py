# 统一 Provider 请求、预算和错误映射；输出截断必须与完整成功区分。
from __future__ import annotations

import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from ezllmtest.platform.settings import get_settings
from langchain_core.embeddings import Embeddings
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from openai import APIConnectionError, APITimeoutError, RateLimitError
from ezllmtest.platform.ai.runtime_hooks import current_budget_hook, reserve_embedding_budget, reserve_model_budget
from ezllmtest.platform.telemetry.agent_telemetry import agent_span, agent_trace_is_active, get_agent_telemetry


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
        "kimi-k3",
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
    def __init__(
        self, message: str, *, code: str = "provider_error", retryable: bool = True
    ) -> None:
        """为 Provider 故障携带稳定错误码与可重试标记，避免上层依赖 SDK 异常类型。"""
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class LLMTruncatedResponseError(LLMProviderError):
    def __init__(
        self, name: str, max_tokens: int, *, reasoning_only: bool = False
    ) -> None:
        """将输出预算耗尽标为不可自动重试的截断错误，并区分仅有推理和正文不完整的情况。"""
        detail = "推理尚未生成正文" if reasoning_only else "正文尚未完整生成"
        super().__init__(
            f"{name} 已达到本次 {max_tokens} Token 输出上限，{detail}。"
            "本次结果未保存，请调整输出预算或生成模式后重试。",
            code="output_truncated",
            retryable=False,
        )


class LLMEmptyResponseError(LLMError):
    pass


class LLMOutputParsingError(LLMError):
    pass


def list_model_specs() -> tuple[ModelSpec, ...]:
    """返回配置支持的不可变模型规格集合，不建立 Provider 连接。"""
    return _MODEL_SPECS


def list_model_labels() -> list[str]:
    """从唯一模型规格集合派生公开标签，避免界面维护另一份允许列表。"""
    return [spec.label for spec in _MODEL_SPECS]


def get_model_spec(name: str) -> ModelSpec:
    """从明确模型注册表查找规格，未知模型标签返回稳定错误，不猜测 provider。"""
    try:
        return _MODEL_REGISTRY[name]
    except KeyError as exc:
        supported = ", ".join(list_model_labels())
        raise UnsupportedModelError(
            f"Unsupported model '{name}'. Supported models: {supported}"
        ) from exc


def ensure_supported_model(name: str) -> None:
    """复用模型目录查询拒绝未知标签，校验本身不调用 Provider。"""
    get_model_spec(name)


def is_kimi_k3(name: str) -> bool:
    """依据注册规格识别 K3，以统一特定模型的预算和请求选项分支。"""
    spec = get_model_spec(name)
    return spec.provider == "moonshot" and getattr(
        get_settings(), spec.model_field
    ) == "kimi-k3"


def provider_options(profile: Any, name: str) -> dict[str, Any]:
    """将统一预算映射到 provider 支持的字段，保持各供应商请求契约。"""
    spec = get_model_spec(name)
    max_tokens = int(profile.output_token_limit)
    reasoning_mode = profile.reasoning_mode
    options: dict[str, Any] = {
        "max_tokens": max_tokens,
        "reasoning_mode": reasoning_mode,
    }

    if is_kimi_k3(name):
        # K3 always reasons; keep a bounded low-effort default even on stages
        # whose generic profile requests off. The stream adapter translates
        # this logical output allowance to max_completion_tokens.
        options.update(reasoning_mode="low", reasoning_effort="low")
        return options

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
        options["reasoning_effort"] = "low" if reasoning_mode == "low" else "high"
        options["extra_body"] = {"thinking": {"type": "enabled"}}
    else:
        options["extra_body"] = {"thinking": {"type": "enabled"}}
    return options


def _configured_api_key(spec: ModelSpec, settings: Any) -> str:
    """从已装配配置读取指定 provider 的凭据，缺失时抛出安全配置错误，不发现其他文件。"""
    api_key = getattr(settings, spec.api_key_field, "")
    if not api_key or api_key.startswith("replace_with_your_"):
        raise LLMConfigurationError(
            f"{spec.api_key_env} is not configured for {spec.label}. "
            "请在后端实际加载的配置中设置此密钥；分模块启动可使用 "
            "--backend-env-file；旧兼容模式使用 --env-file 或 --model-env-file。"
            "更新后受控重启后端，不要放入前端配置。"
        )
    return api_key


@lru_cache(maxsize=len(_MODEL_SPECS) * 2)
def get_chat_client(name: str, minimum_timeout_seconds: float = 0.0) -> ChatOpenAI:
    """按明确模型及配置创建对应 SDK 客户端，禁止动态猜测供应商或秘密来源。"""
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
    if is_kimi_k3(name):
        # Do not inherit K3's much larger platform completion default on
        # legacy synchronous paths. Agent hooks may reduce this ceiling.
        kwargs.update(reasoning_effort="low", max_completion_tokens=8_192)
    return ChatOpenAI(**kwargs)


def _status_code(error: Exception) -> int | None:
    """从 provider 异常中提取可用的 HTTP 状态码。"""
    direct_status = getattr(error, "status_code", None)
    if isinstance(direct_status, int):
        return direct_status
    response = getattr(error, "response", None)
    response_status = getattr(response, "status_code", None)
    return response_status if isinstance(response_status, int) else None


def provider_request_error(name: str, error: Exception) -> LLMError:
    """把供应商异常映射为安全类别和允许消息，不暴露请求、凭据或完整响应。"""
    status = _status_code(error)
    if type(status) is not int or not 100 <= status <= 599:
        status = None
    if status == 429:
        return LLMRateLimitError(f"{name} 请求受到限流，请稍后重试（HTTP 429）")

    failures = {
        400: ("provider_bad_request", "请求参数被模型接口拒绝，请检查模型与参数兼容性"),
        401: ("provider_authentication", "模型接口鉴权失败，请检查密钥及对应平台地址"),
        402: ("provider_billing", "模型接口要求检查账户余额或计费状态"),
        403: ("provider_permission", "模型接口拒绝访问，请检查账户、模型权限或平台限制"),
        404: ("provider_not_found", "模型或接口地址不存在，请检查配置与模型可用性"),
        413: ("provider_input_limit", "模型接口拒绝过大的请求，请缩小输入"),
        422: ("provider_bad_request", "模型接口参数校验失败，请检查模型与参数兼容性"),
    }
    if status in failures:
        code, detail = failures[status]
        parameter = ""
        # The parameter name is useful for compatibility errors; its value and
        # the provider's free-text explanation may contain credentials or input.
        if status in {400, 422}:
            body = getattr(error, "body", None)
            if isinstance(body, dict):
                nested = body.get("error", body)
                candidate = nested.get("param") if isinstance(nested, dict) else None
                if isinstance(candidate, str) and candidate in {
                    "model", "messages", "temperature", "top_p", "max_tokens",
                    "max_completion_tokens",
                    "thinking", "reasoning_effort", "stream", "stream_options",
                    "response_format", "n", "presence_penalty", "frequency_penalty",
                }:
                    parameter = f"；参数：{candidate}"
        return LLMProviderError(
            f"{name} {detail}（HTTP {status}{parameter}）",
            code=code,
            retryable=False,
        )
    if status is not None:
        return LLMProviderError(
            f"{name} 模型接口请求失败（HTTP {status}），请检查服务状态。",
            retryable=status >= 500 or status == 408,
        )
    return LLMProviderError(f"{name} 模型接口请求失败，未获得可识别的 HTTP 状态。")


def invoke_chat_model(name: str, value: Any, minimum_timeout_seconds: float = 0.0):
    # A no-op for every legacy REST/SSE call.  Aspect 3 installs the guard only
    # while a leased Agent step is executing.
    """在共享预算 hook 和 provider 错误边界内执行同步模型调用，返回结果仍需经过后续有效性检查。"""
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
            budget_hook = current_budget_hook()
            max_output_tokens = getattr(budget_hook, "model_max_output_tokens", None)
            if max_output_tokens is not None and isinstance(client, ChatOpenAI):
                if is_kimi_k3(name):
                    client = client.bind(max_completion_tokens=min(8_192, max_output_tokens))
                else:
                    client = client.bind(max_tokens=max_output_tokens)
            result = client.invoke(value)
            if is_kimi_k3(name) and getattr(result, "response_metadata", {}).get("finish_reason") == "length":
                raise LLMTruncatedResponseError(
                    name, min(8_192, max_output_tokens) if max_output_tokens is not None else 8_192,
                    reasoning_only=not bool(getattr(result, "content", "")),
                )
    except LLMError:
        raise
    except (APITimeoutError, APIConnectionError, TimeoutError, ConnectionError) as exc:
        raise LLMTimeoutError(f"{name} request timed out or could not connect") from exc
    except RateLimitError as exc:
        raise LLMRateLimitError(f"{name} request was rate limited") from exc
    except Exception as exc:
        raise provider_request_error(name, exc) from exc

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
    """缓存按模型与最低超时绑定的惰性 Runnable，真正的 Provider 请求发生在 invoke 时。"""
    ensure_supported_model(name)
    return RunnableLambda(lambda value: invoke_chat_model(name, value, minimum_timeout_seconds))


def get_lazy_chat_model(name: str = SUPPORTED_MODEL_LABEL) -> RunnableLambda:
    """返回默认超时策略下的惰性模型包装，不因获取包装而发送请求。"""
    return get_chat_model(name)


@lru_cache(maxsize=1)
def get_embeddings() -> OpenAIEmbeddings:
    """按显式进程配置构造并缓存 embedding SDK 实例，调用嵌入方法时才执行请求。"""
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
        """读取显式进程配置中的 embedding 模型名，不自行发现环境文件。"""
        return get_settings().zhipu_embedding_model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """在确需索引时延迟建立 embedding 客户端，并通过预算 hook 处理文档向量请求。"""
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
            telemetry.counter("ezllm.agent.embedding.calls", labels={"status": "success"})
            telemetry.histogram(
                "ezllm.agent.embedding.duration",
                (time.perf_counter() - started) * 1_000,
                {"status": "success"},
            )
        return result

    def embed_query(self, text: str) -> list[float]:
        """为检索查询显式请求向量，仍受模型配置和 embedding 预算边界约束。"""
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
            telemetry.counter("ezllm.agent.embedding.calls", labels={"status": "success"})
            telemetry.histogram(
                "ezllm.agent.embedding.duration",
                (time.perf_counter() - started) * 1_000,
                {"status": "success"},
            )
        return result


@lru_cache(maxsize=1)
def get_lazy_embeddings() -> LazyZhipuEmbeddings:
    """返回惰性 embedding 包装，避免导入业务模块时立即构造真实依赖。"""
    return LazyZhipuEmbeddings()


def clear_provider_caches() -> None:
    """显式清空进程内 Provider 与包装缓存，配置变更后不能继续复用旧客户端。"""
    get_chat_client.cache_clear()
    get_chat_model.cache_clear()
    get_embeddings.cache_clear()
    get_lazy_embeddings.cache_clear()
