# 适配 Provider 流式响应、usage 和终止原因，向上层报告完整或截断结果。
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator, Literal

from openai import APIConnectionError, APITimeoutError, AsyncOpenAI, RateLimitError

from ezllmtest.platform.settings import get_settings
from ezllmtest.platform.ai.runtime_hooks import reserve_model_budget
from ezllmtest.platform.telemetry.agent_telemetry import agent_span, agent_trace_is_active, get_agent_telemetry
from ezllmtest.platform.ai.gateway import LLMError, LLMEmptyResponseError, LLMProviderError, LLMRateLimitError, LLMTimeoutError, LLMTruncatedResponseError, ModelSpec, _configured_api_key, get_model_spec, is_kimi_k3, provider_request_error


THINKING_BUDGET_TOKENS = 8192
INTERMEDIATE_MAX_TOKENS = 8192
FINAL_MAX_TOKENS = 32768


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int | None = None
    reasoning_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None

    def as_dict(self) -> dict[str, int | None]:
        """将 Token 用量转换为稳定字典结构。"""
        return {
            "input_tokens": self.input_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass(frozen=True)
class ModelStreamEvent:
    kind: Literal["reasoning", "content", "usage"]
    text: str = ""
    usage: TokenUsage | None = None


def _field(value: Any, name: str, default: Any = None) -> Any:
    """兼容字典、SDK 属性及 model_extra 中的 usage 字段，缺失值使用调用方回退。"""
    if value is None:
        return default
    if isinstance(value, dict):
        return value.get(name, default)
    result = getattr(value, name, default)
    if result is not default:
        return result
    model_extra = getattr(value, "model_extra", None)
    if isinstance(model_extra, dict):
        return model_extra.get(name, default)
    return default


def _integer_field(value: Any, *names: str) -> int | None:
    """从 provider 用量字段读取有效整数，缺失或不合法值保持统一未报告语义。"""
    for name in names:
        candidate = _field(value, name)
        if isinstance(candidate, int):
            return candidate
    return None


def parse_token_usage(value: Any) -> TokenUsage | None:
    """兼容不同 Provider 的 usage 字段名，区分输入、推理、正文和总量的未知状态。"""
    if value is None:
        return None

    input_tokens = _integer_field(value, "prompt_tokens", "input_tokens")
    completion_tokens = _integer_field(value, "completion_tokens", "output_tokens")
    total_tokens = _integer_field(value, "total_tokens")
    details = _field(value, "completion_tokens_details") or _field(
        value, "output_tokens_details"
    )
    reasoning_tokens = _integer_field(details, "reasoning_tokens")

    output_tokens = None
    if completion_tokens is not None and reasoning_tokens is not None:
        output_tokens = max(completion_tokens - reasoning_tokens, 0)

    if total_tokens is None and input_tokens is not None and completion_tokens is not None:
        total_tokens = input_tokens + completion_tokens

    if all(
        item is None
        for item in (input_tokens, reasoning_tokens, output_tokens, total_tokens)
    ):
        return None
    return TokenUsage(
        input_tokens=input_tokens,
        reasoning_tokens=reasoning_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
    )


def combine_token_usage(usages: list[TokenUsage]) -> TokenUsage:
    """逐字段合并调用用量，任何一次缺失该字段就保持未知，避免把不完整计数当作总量。"""
    def complete_sum(field_name: str) -> int | None:
        """仅当所有调用的字段计数均已知时求和，否则返回 None。"""
        if not usages:
            return None
        values = [getattr(usage, field_name) for usage in usages]
        if any(value is None for value in values):
            return None
        return sum(value for value in values if value is not None)

    return TokenUsage(
        input_tokens=complete_sum("input_tokens"),
        reasoning_tokens=complete_sum("reasoning_tokens"),
        output_tokens=complete_sum("output_tokens"),
        total_tokens=complete_sum("total_tokens"),
    )


def get_stream_model_metadata(name: str) -> dict[str, str]:
    """返回公开模型标签、Provider 和实际模型名，秘密配置不进入流元数据。"""
    spec = get_model_spec(name)
    settings = get_settings()
    return {
        "label": spec.label,
        "provider": spec.provider,
        "model": getattr(settings, spec.model_field),
    }


def build_stream_request(
    name: str,
    prompt: str,
    max_tokens: int,
    *,
    request_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """依据模型规格和明确参数构造流式请求，输出预算与 provider 字段由统一规则转换。"""
    spec = get_model_spec(name)
    settings = get_settings()
    limits = [int(max_tokens)]
    for key in ("max_tokens", "max_completion_tokens"):
        if key in (request_options or {}):
            limits.append(int(request_options[key]))
    output_limit = min(limits)
    if output_limit <= 0:
        raise ValueError("output token limit must be positive")
    request: dict[str, Any] = {
        "model": getattr(settings, spec.model_field),
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": output_limit,
        "stream": True,
        "stream_options": {"include_usage": True},
    }

    if request_options is not None:
        for key in ("temperature", "extra_body", "reasoning_effort"):
            if key in request_options:
                request[key] = request_options[key]
        if "response_format" in request_options:
            response_format = request_options["response_format"]
            if response_format != {"type": "json_object"}:
                raise ValueError("unsupported response_format")
            request["response_format"] = {"type": "json_object"}
    elif spec.provider == "zhipu":
        request["temperature"] = 0.5
        request["extra_body"] = {"thinking": {"type": "enabled"}}
    elif spec.provider == "alibaba":
        request["temperature"] = 0.5
        request["extra_body"] = {
            "enable_thinking": True,
            "thinking_budget": THINKING_BUDGET_TOKENS,
        }
    elif spec.provider == "deepseek":
        request["reasoning_effort"] = "high"
        request["extra_body"] = {"thinking": {"type": "enabled"}}
    elif spec.provider == "moonshot":
        request["extra_body"] = {"thinking": {"type": "enabled"}}

    if is_kimi_k3(name):
        request["max_completion_tokens"] = request.pop("max_tokens")
        # K3 has no thinking toggle or configurable sampling temperature.
        request.pop("extra_body", None)
        request.pop("temperature", None)
        effort = (request_options or {}).get("reasoning_effort", "low")
        if effort not in {"low", "high", "max"}:
            raise ValueError("unsupported Kimi K3 reasoning effort")
        request["reasoning_effort"] = effort

    return request


def _create_stream_client(
    spec: ModelSpec, minimum_timeout_seconds: float
) -> AsyncOpenAI:
    """用已装配配置建立异步 Provider 客户端，采用最低超时且关闭 SDK 自动重试。"""
    settings = get_settings()
    return AsyncOpenAI(
        api_key=_configured_api_key(spec, settings),
        base_url=getattr(settings, spec.base_url_field),
        timeout=max(getattr(settings, spec.timeout_field), minimum_timeout_seconds),
        max_retries=0,
    )


async def _stream_chat_completion_impl(
    name: str,
    prompt: str,
    max_tokens: int,
    minimum_timeout_seconds: float = 0.0,
    *,
    request_options: dict[str, Any] | None = None,
) -> AsyncIterator[ModelStreamEvent]:
    """消费 provider 流并分别处理正文、推理和用量；供应商异常统一映射，不能把截断响应当完整成功。"""
    spec = get_model_spec(name)
    request = build_stream_request(
        name,
        prompt,
        max_tokens,
        request_options=request_options,
    )
    # The guard is absent on all legacy call paths.  Under Agent execution it
    # reserves the conservative per-call output allowance before any provider I/O.
    output_limit = int(request.get("max_completion_tokens", request.get("max_tokens")))
    reserve_model_budget(prompt, max_output_tokens=output_limit)

    finish_reason: str | None = None
    has_content = False
    has_reasoning = False
    try:
        async with _create_stream_client(spec, minimum_timeout_seconds) as client:
            stream = await client.chat.completions.create(**request)
            async with stream:
                async for chunk in stream:
                    choices = _field(chunk, "choices", []) or []
                    if choices:
                        delta = _field(choices[0], "delta")
                        terminal = _field(choices[0], "finish_reason")
                        if terminal is not None:
                            finish_reason = terminal if isinstance(terminal, str) else "unknown"
                        reasoning = _field(delta, "reasoning_content")
                        content = _field(delta, "content")
                        if isinstance(reasoning, str) and reasoning:
                            has_reasoning = has_reasoning or bool(reasoning.strip())
                            yield ModelStreamEvent("reasoning", text=reasoning)
                        if isinstance(content, str) and content:
                            has_content = has_content or bool(content.strip())
                            yield ModelStreamEvent("content", text=content)

                    usage = parse_token_usage(_field(chunk, "usage"))
                    if usage is not None:
                        yield ModelStreamEvent("usage", usage=usage)
        # Consume the trailing usage chunk before deciding whether the answer
        # is complete. A nonempty prefix is not a successful final answer.
        if finish_reason == "length":
            raise LLMTruncatedResponseError(
                name, output_limit,
                reasoning_only=has_reasoning and not has_content,
            )
        if finish_reason == "content_filter":
            raise LLMProviderError(
                f"{name} 的输出被模型平台内容策略拦截，本次结果未保存。",
                code="content_filtered", retryable=False,
            )
        if finish_reason in {None, "error", "insufficient_system_resource"}:
            raise LLMProviderError(
                f"{name} 的响应在完整结束前中断，本次结果未保存，请稍后重试。",
                code="incomplete_response",
            )
        if finish_reason != "stop":
            raise LLMProviderError(
                f"{name} 未以预期的正文格式结束响应，本次结果未保存。",
                code="unexpected_output", retryable=False,
            )
        if not has_content:
            detail = "仅返回了推理内容，未返回正文" if has_reasoning else "未返回可用正文"
            raise LLMEmptyResponseError(f"{name} {detail}，本次结果未保存。")
    except asyncio.CancelledError:
        raise
    except LLMError:
        raise
    except (APITimeoutError, APIConnectionError, TimeoutError, ConnectionError) as exc:
        raise LLMTimeoutError(
            f"{name} request timed out or could not connect"
        ) from exc
    except RateLimitError as exc:
        raise LLMRateLimitError(f"{name} request was rate limited") from exc
    except Exception as exc:
        raise provider_request_error(name, exc) from exc


async def stream_chat_completion(
    name: str,
    prompt: str,
    max_tokens: int,
    minimum_timeout_seconds: float = 0.0,
    *,
    request_options: dict[str, Any] | None = None,
) -> AsyncIterator[ModelStreamEvent]:
    """在运行预算 hook 和取消边界内转发实际模型流，调用方无需重复实现 provider 适配。"""

    started = time.perf_counter()
    active = agent_trace_is_active()
    status = "error"
    usage: TokenUsage | None = None
    spec = get_model_spec(name)
    try:
        with agent_span(
            "gen_ai.chat",
            {
                "gen_ai.operation.name": "chat",
                "gen_ai.provider.name": spec.provider,
                "gen_ai.request.model": name,
                "gen_ai.output.type": "stream",
            },
        ):
            async for event in _stream_chat_completion_impl(
                name,
                prompt,
                max_tokens,
                minimum_timeout_seconds,
                request_options=request_options,
            ):
                if event.kind == "usage" and event.usage is not None:
                    usage = event.usage
                yield event
        status = "success"
    finally:
        if active:
            telemetry = get_agent_telemetry()
            telemetry.counter(
                "ezllm.agent.model.calls",
                labels={"model": name, "status": status},
            )
            telemetry.histogram(
                "ezllm.agent.model.duration",
                (time.perf_counter() - started) * 1_000,
                {"model": name, "status": status},
            )
            if usage is not None:
                telemetry.counter(
                    "ezllm.agent.model.input_tokens",
                    usage.input_tokens or 0,
                    {"model": name},
                )
                telemetry.counter(
                    "ezllm.agent.model.output_tokens",
                    usage.output_tokens or 0,
                    {"model": name},
                )


def ensure_non_empty_response(name: str, content: str) -> str:
    """在调用结束后拒绝空正文，避免无有效产物的响应进入保存路径。"""
    if not content.strip():
        raise LLMEmptyResponseError(f"{name} returned an empty response")
    return content
