# 用中立运行上下文衔接租约和预算守卫，Provider 层不反向导入 Agent 业务。
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
        """模型预算钩子按输入及可选输出上限预留额度，具体账本由运行装配注入。"""
        ...

    def reserve_embedding(self, texts: Sequence[str]) -> Any:
        """embedding 预算钩子根据待嵌入文本预留额度，SDK 层不依赖 Agent 仓储。"""
        ...

    def reserve_tool(self) -> Any:
        """工具预算钩子在执行前预留调用成本，超限由具体实现拒绝。"""
        ...


_BUDGET_HOOK: ContextVar[BudgetHook | None] = ContextVar(
    "ezllm_budget_hook", default=None
)


def current_budget_hook() -> BudgetHook | None:
    """返回当前上下文绑定的预算预留钩子。"""
    return _BUDGET_HOOK.get()


@contextmanager
def bind_budget_hook(hook: BudgetHook) -> Iterator[BudgetHook]:
    """临时绑定预算钩子并在退出时还原上下文，防止并发运行串用额度。"""
    token = _BUDGET_HOOK.set(hook)
    try:
        yield hook
    finally:
        _BUDGET_HOOK.reset(token)


def reserve_model_budget(
    value: Any,
    max_output_tokens: int | None = None,
) -> Any | None:
    """有运行钩子时预留模型输入和输出预算；未绑定时返回 None，不创建新的预算上下文。"""
    hook = current_budget_hook()
    if hook is None:
        return None
    if max_output_tokens is None:
        # 兼容仅接受 value 参数的旧 hook；显式预算仍走完整参数路径。
        return hook.reserve_model(value)
    return hook.reserve_model(value, max_output_tokens=max_output_tokens)


def reserve_embedding_budget(texts: Sequence[str]) -> Any | None:
    """将文本集合交给当前 embedding 预算钩子，无运行钩子时保持普通调用路径。"""
    hook = current_budget_hook()
    return hook.reserve_embedding(texts) if hook is not None else None


def reserve_tool_budget() -> Any | None:
    """将工具调用预留交给当前预算钩子，无钩子时不虚构账本记录。"""
    hook = current_budget_hook()
    return hook.reserve_tool() if hook is not None else None
