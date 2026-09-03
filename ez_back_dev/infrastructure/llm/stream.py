from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator, Literal

from openai import APIConnectionError, APITimeoutError, AsyncOpenAI, RateLimitError

from infrastructure.config import get_settings
from infrastructure.runtime_hooks import reserve_model_budget
from infrastructure.observability.agent_telemetry import (
    agent_span,
    agent_trace_is_active,
    get_agent_telemetry,
)
from infrastructure.llm.gateway import (
    LLMError,
    LLMEmptyResponseError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
    ModelSpec,
    _configured_api_key,
    _status_code,
    get_model_spec,
)


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
    for name in names:
        candidate = _field(value, name)
        if isinstance(candidate, int):
            return candidate
    return None


def parse_token_usage(value: Any) -> TokenUsage | None:
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
    def complete_sum(field_name: str) -> int | None:
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
    spec = get_model_spec(name)
    settings = get_settings()
    request: dict[str, Any] = {
        "model": getattr(settings, spec.model_field),
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": min(
            max_tokens,
            int((request_options or {}).get("max_tokens", max_tokens)),
        ),
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

    return request


def _create_stream_client(
    spec: ModelSpec, minimum_timeout_seconds: float
) -> AsyncOpenAI:
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
    spec = get_model_spec(name)
    request = build_stream_request(
        name,
        prompt,
        max_tokens,
        request_options=request_options,
    )
    # The guard is absent on all legacy call paths.  Under Agent execution it
    # reserves the conservative per-call output allowance before any provider I/O.
    reserve_model_budget(prompt, max_output_tokens=int(request["max_tokens"]))

    try:
        async with _create_stream_client(spec, minimum_timeout_seconds) as client:
            stream = await client.chat.completions.create(**request)
            async with stream:
                async for chunk in stream:
                    choices = _field(chunk, "choices", []) or []
                    if choices:
                        delta = _field(choices[0], "delta")
                        reasoning = _field(delta, "reasoning_content")
                        content = _field(delta, "content")
                        if isinstance(reasoning, str) and reasoning:
                            yield ModelStreamEvent("reasoning", text=reasoning)
                        if isinstance(content, str) and content:
                            yield ModelStreamEvent("content", text=content)

                    usage = parse_token_usage(_field(chunk, "usage"))
                    if usage is not None:
                        yield ModelStreamEvent("usage", usage=usage)
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
        if _status_code(exc) == 429:
            raise LLMRateLimitError(f"{name} request was rate limited") from exc
        raise LLMProviderError(f"{name} provider request failed") from exc


async def stream_chat_completion(
    name: str,
    prompt: str,
    max_tokens: int,
    minimum_timeout_seconds: float = 0.0,
    *,
    request_options: dict[str, Any] | None = None,
) -> AsyncIterator[ModelStreamEvent]:
    """Instrument only Agent-scoped calls and never attach message content."""

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
    if not content.strip():
        raise LLMEmptyResponseError(f"{name} returned an empty response")
    return content
