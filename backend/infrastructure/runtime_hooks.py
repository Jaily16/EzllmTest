"""Neutral runtime hooks used by infrastructure adapters.

The LLM and persistence layers must not import the Agent service just to
observe a leased run.  The Agent domain binds a small protocol in its own
context; outside that context every hook remains a no-op.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Protocol


class BudgetHook(Protocol):
    """Minimal budget surface exposed to infrastructure without a domain import."""

    def reserve_model(
        self,
        value: Any,
        max_output_tokens: int | None = None,
    ) -> Any:
        """预留模型，并遵循现有调用契约。"""
        ...

    def reserve_embedding(self, texts: Sequence[str]) -> Any:
        """预留embedding，并遵循现有调用契约。"""
        ...

    def reserve_tool(self) -> Any:
        """预留工具，并遵循现有调用契约。"""
        ...


_BUDGET_HOOK: ContextVar[BudgetHook | None] = ContextVar(
    "ezllm_budget_hook", default=None
)


def current_budget_hook() -> BudgetHook | None:
    """返回当前上下文绑定的预算预留钩子。"""
    return _BUDGET_HOOK.get()


@contextmanager
def bind_budget_hook(hook: BudgetHook) -> Iterator[BudgetHook]:
    """绑定预算HOOK，并遵循现有调用契约。"""
    token = _BUDGET_HOOK.set(hook)
    try:
        yield hook
    finally:
        _BUDGET_HOOK.reset(token)


def reserve_model_budget(
    value: Any,
    max_output_tokens: int | None = None,
) -> Any | None:
    """预留模型预算，并遵循现有调用契约。"""
    hook = current_budget_hook()
    if hook is None:
        return None
    if max_output_tokens is None:
        # 兼容仅接受 value 参数的旧 hook；显式预算仍走完整参数路径。
        return hook.reserve_model(value)
    return hook.reserve_model(value, max_output_tokens=max_output_tokens)


def reserve_embedding_budget(texts: Sequence[str]) -> Any | None:
    """预留embedding预算，并遵循现有调用契约。"""
    hook = current_budget_hook()
    return hook.reserve_embedding(texts) if hook is not None else None


def reserve_tool_budget() -> Any | None:
    """预留工具预算，并遵循现有调用契约。"""
    hook = current_budget_hook()
    return hook.reserve_tool() if hook is not None else None
