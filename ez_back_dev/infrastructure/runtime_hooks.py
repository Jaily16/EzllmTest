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
    ) -> Any: ...

    def reserve_embedding(self, texts: Sequence[str]) -> Any: ...

    def reserve_tool(self) -> Any: ...


_BUDGET_HOOK: ContextVar[BudgetHook | None] = ContextVar(
    "ezllm_budget_hook", default=None
)


def current_budget_hook() -> BudgetHook | None:
    return _BUDGET_HOOK.get()


@contextmanager
def bind_budget_hook(hook: BudgetHook) -> Iterator[BudgetHook]:
    token = _BUDGET_HOOK.set(hook)
    try:
        yield hook
    finally:
        _BUDGET_HOOK.reset(token)


def reserve_model_budget(
    value: Any,
    max_output_tokens: int | None = None,
) -> Any | None:
    hook = current_budget_hook()
    if hook is None:
        return None
    if max_output_tokens is None:
        # 兼容仅接受 value 参数的旧 hook；显式预算仍走完整参数路径。
        return hook.reserve_model(value)
    return hook.reserve_model(value, max_output_tokens=max_output_tokens)


def reserve_embedding_budget(texts: Sequence[str]) -> Any | None:
    hook = current_budget_hook()
    return hook.reserve_embedding(texts) if hook is not None else None


def reserve_tool_budget() -> Any | None:
    hook = current_budget_hook()
    return hook.reserve_tool() if hook is not None else None
