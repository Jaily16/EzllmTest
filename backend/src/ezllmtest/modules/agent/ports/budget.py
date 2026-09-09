"""调用上下文预算协议；应用层不依赖同步 Redis adapter。"""
from __future__ import annotations
from typing import Any, Protocol
from collections.abc import Iterator, Sequence
from contextvars import ContextVar
from contextlib import contextmanager
from ezllmtest.platform.ai.runtime_hooks import bind_budget_hook
from ezllmtest.modules.agent.domain.contracts import UsageCounters
class BudgetGuard(Protocol):
    # 在模型调用前预留输入估计与输出上限，并拒绝不合法输出预算。
    def reserve_model(self, value: Any, max_output_tokens: int | None = None) -> UsageCounters: ...
    # 在 embedding 请求前预留输入 token 和调用次数，不以检索只读为由绕过预算。
    def reserve_embedding(self, texts: Sequence[str]) -> UsageCounters: ...
    # 在工具执行前预留工具调用额度，仍须由执行层核验审批和项目 scope。
    def reserve_tool(self) -> UsageCounters: ...

_AGENT_BUDGET: ContextVar[BudgetGuard | None] = ContextVar("ezllm_agent_budget", default=None)


def current_agent_budget() -> BudgetGuard | None:
    """返回当前 Agent 调用上下文中的预算钩子。"""
    return _AGENT_BUDGET.get()


@contextmanager
def use_agent_budget(guard: BudgetGuard) -> Iterator[BudgetGuard]:
    """在当前调用上下文临时绑定预算钩子，退出时恢复原上下文，避免并发运行相互污染。"""
    token = _AGENT_BUDGET.set(guard)
    try:
        with bind_budget_hook(guard):
            yield guard
    finally:
        _AGENT_BUDGET.reset(token)


def reserve_model_budget(value: Any, max_output_tokens: int | None = None) -> UsageCounters | None:
    """通过当前运行预算钩子预留模型用量；没有 Agent 上下文时不凭空创建账本。"""
    guard = current_agent_budget()
    if guard is None:
        return None
    if max_output_tokens is None:
        return guard.reserve_model(value)
    return guard.reserve_model(value, max_output_tokens=max_output_tokens)


def reserve_embedding_budget(texts: Sequence[str]) -> UsageCounters | None:
    """通过当前预算上下文预留 embedding 用量，具体硬限制由注入账本执行。"""
    guard = current_agent_budget()
    return guard.reserve_embedding(texts) if guard is not None else None


def reserve_tool_budget() -> UsageCounters | None:
    """通过当前预算上下文登记工具成本，避免执行路径绕过预算边界。"""
    guard = current_agent_budget()
    return guard.reserve_tool() if guard is not None else None
