"""Atomic hard-budget ledger and Agent-only provider guards."""

from __future__ import annotations

import json
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterator, Sequence
from uuid import uuid4

from redis import Redis as SyncRedis
from infrastructure.runtime_hooks import bind_budget_hook
from service.agent.contracts import RunBudget, UsageCounters
from service.agent.coordinator import (
    AgentRedisCoordinator,
    LeaseHandle,
    LeaseLostError,
)


class AgentBudgetExceeded(RuntimeError):
    pass


_DIMENSIONS = (
    "steps",
    "elapsed_ms",
    "input_tokens",
    "output_tokens",
    "model_calls",
    "embedding_calls",
    "tool_calls",
    "estimated_cost_units",
)

_LIMITS = {
    "steps": "max_steps",
    "elapsed_ms": "max_elapsed_ms",
    "input_tokens": "max_input_tokens",
    "output_tokens": "max_output_tokens",
    "model_calls": "max_model_calls",
    "embedding_calls": "max_embedding_calls",
    "tool_calls": "max_tool_calls",
    "estimated_cost_units": "max_estimated_cost_units",
}

_INITIALIZE = """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then return -1 end
local existing = redis.call('GET', KEYS[2])
if existing and existing ~= ARGV[3] then return -2 end
if not existing then redis.call('SET', KEYS[2], ARGV[3], 'EX', ARGV[2]) end
if redis.call('EXISTS', KEYS[3]) == 0 then
  redis.call('HSET', KEYS[3],
    'steps', 0, 'elapsed_ms', 0, 'input_tokens', 0, 'output_tokens', 0,
    'model_calls', 0, 'embedding_calls', 0, 'tool_calls', 0,
    'estimated_cost_units', 0)
end
redis.call('EXPIRE', KEYS[3], ARGV[2])
redis.call('EXPIRE', KEYS[4], ARGV[2])
return 1
"""

_RESERVE = """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then return {-1, 'lease'} end
local encoded = redis.call('GET', KEYS[2])
if not encoded then return {-2, 'uninitialized'} end
local definition = cjson.decode(encoded)
local now_ms = tonumber(ARGV[3])
if now_ms >= tonumber(definition.deadline_ms) then return {-3, 'deadline'} end
local existing = redis.call('HGET', KEYS[4], ARGV[4])
if existing then
  if existing ~= ARGV[5] then return {-4, 'immutable_reservation'} end
  local response = {0}
  for index = 1, 8 do
    response[index + 1] = tonumber(redis.call('HGET', KEYS[3], ARGV[5 + index]) or '0')
  end
  return response
end
local reservation = cjson.decode(ARGV[5])
local elapsed = math.max(
  tonumber(redis.call('HGET', KEYS[3], 'elapsed_ms') or '0'),
  now_ms - tonumber(definition.started_ms)
)
reservation.elapsed_ms = math.max(tonumber(reservation.elapsed_ms or 0), elapsed)
for index = 1, 8 do
  local dimension = ARGV[5 + index]
  local current = tonumber(redis.call('HGET', KEYS[3], dimension) or '0')
  local increment = tonumber(reservation[dimension] or 0)
  local candidate
  if dimension == 'elapsed_ms' then candidate = increment else candidate = current + increment end
  local limit_name = ARGV[13 + index]
  local limit = tonumber(definition.budget[limit_name])
  if candidate > limit then return {-5, dimension} end
end
local response = {1}
for index = 1, 8 do
  local dimension = ARGV[5 + index]
  local increment = tonumber(reservation[dimension] or 0)
  local value
  if dimension == 'elapsed_ms' then
    redis.call('HSET', KEYS[3], dimension, increment)
    value = increment
  else
    value = redis.call('HINCRBY', KEYS[3], dimension, increment)
  end
  response[index + 1] = tonumber(value)
end
redis.call('HSET', KEYS[4], ARGV[4], ARGV[5])
redis.call('EXPIRE', KEYS[2], ARGV[2])
redis.call('EXPIRE', KEYS[3], ARGV[2])
redis.call('EXPIRE', KEYS[4], ARGV[2])
return response
"""


def _timestamp_ms(value: datetime) -> int:
    """将时间值转换为毫秒时间戳。

    参数:
        `value`：待处理的值。

    返回:
        `int`，内容保持现有调用方契约。

    异常:
        `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("budget timestamps must be timezone-aware")
    return int(value.timestamp() * 1_000)


def _usage_payload(usage: UsageCounters) -> dict[str, int]:
    """将用量计数转换为稳定的预算载荷。"""
    return {name: int(getattr(usage, name)) for name in _DIMENSIONS}


def _usage_from_response(values: Sequence[Any]) -> UsageCounters:
    """从 Redis 响应字段中恢复用量计数。"""
    return UsageCounters(**{name: int(values[index + 1]) for index, name in enumerate(_DIMENSIONS)})


class RedisAgentBudgetLedger:
    def __init__(self, coordinator: AgentRedisCoordinator) -> None:
        """初始化实例并保存后续操作所需的依赖与状态。"""
        self.coordinator = coordinator

    def _keys(self, lease: LeaseHandle) -> tuple[str, str, str, str]:
        """处理键，并保持 `RedisAgentBudgetLedger` 的现有状态约束。

        参数:
            `lease`：沿用签名中 `LeaseHandle` 类型约束的输入。

        返回:
            `tuple[str, str, str, str]`，内容保持现有调用方契约。

        副作用:
            可能按照既有键空间读写 Redis 中的 Agent 协调状态。

        不变量:
            运行状态必须保持项目、线程与 revision 的既有绑定。"""
        self.coordinator._validate_lease(lease)
        return (
            self.coordinator._key("lease", lease.storage_id),
            self.coordinator._key("budget-definition", lease.storage_id),
            self.coordinator._key("budget-ledger", lease.storage_id),
            self.coordinator._key("budget-reservations", lease.storage_id),
        )

    async def initialize(
        self,
        lease: LeaseHandle,
        budget: RunBudget,
        *,
        started_at: datetime,
        deadline_at: datetime,
    ) -> None:
        """初始化当前运行的持久化状态，并保持重复调用幂等。

        参数:
            `lease`：沿用签名中 `LeaseHandle` 类型约束的输入。
            `budget`：沿用签名中 `RunBudget` 类型约束的输入。
            `started_at`：沿用签名中 `datetime` 类型约束的输入。
            `deadline_at`：沿用签名中 `datetime` 类型约束的输入。

        异常:
            `LeaseLostError, ValueError`：输入、状态或下游结果不满足现有约束时抛出。

        副作用:
            可能按照既有键空间读写 Redis 中的 Agent 协调状态。

        不变量:
            预算校验与预留必须保持原子性，余额不足时不得透支。"""
        if deadline_at <= started_at:
            # An already elapsed deadline is valid for recovery tests, but the
            # configured absolute deadline must still follow the original start.
            if _timestamp_ms(deadline_at) <= _timestamp_ms(started_at):
                raise ValueError("budget deadline must follow start time")
        definition = json.dumps(
            {
                "budget": budget.model_dump(mode="json"),
                "started_ms": _timestamp_ms(started_at),
                "deadline_ms": _timestamp_ms(deadline_at),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        lease_key, definition_key, ledger_key, reservations_key = self._keys(lease)
        result = int(
            await self.coordinator.redis.eval(
                _INITIALIZE,
                4,
                lease_key,
                definition_key,
                ledger_key,
                reservations_key,
                lease.value,
                self.coordinator.settings.state_ttl_seconds,
                definition,
            )
        )
        if result == -1:
            raise LeaseLostError("lease fence no longer owns the budget ledger")
        if result == -2:
            raise ValueError("budget definition is immutable and cannot be expanded")

    async def reserve(
        self,
        lease: LeaseHandle,
        reservation_id: str,
        usage: UsageCounters,
        *,
        now: datetime,
    ) -> UsageCounters:
        """原子预留本次调用所需预算，并返回预留后的累计用量。

        参数:
            `lease`：沿用签名中 `LeaseHandle` 类型约束的输入。
            `reservation_id`：沿用签名中 `str` 类型约束的输入。
            `usage`：沿用签名中 `UsageCounters` 类型约束的输入。
            `now`：沿用签名中 `datetime` 类型约束的输入。

        返回:
            `UsageCounters`，内容保持现有调用方契约。

        副作用:
            可能按照既有键空间读写 Redis 中的 Agent 协调状态。

        不变量:
            预算校验与预留必须保持原子性，余额不足时不得透支。"""
        return self._parse_reservation_result(
            await self.coordinator.redis.eval(
                _RESERVE,
                4,
                *self._keys(lease),
                lease.value,
                self.coordinator.settings.state_ttl_seconds,
                _timestamp_ms(now),
                reservation_id,
                json.dumps(_usage_payload(usage), sort_keys=True, separators=(",", ":")),
                *_DIMENSIONS,
                *(_LIMITS[name] for name in _DIMENSIONS),
            )
        )

    @staticmethod
    def _parse_reservation_result(values: Sequence[Any]) -> UsageCounters:
        """解析reservation结果，并遵循现有调用契约。

        参数:
            `values`：沿用签名中 `Sequence[Any]` 类型约束的输入。

        返回:
            `UsageCounters`，内容保持现有调用方契约。

        异常:
            `LeaseLostError, ValueError, AgentBudgetExceeded`：输入、状态或下游结果不满足现有约束时抛出。"""
        code = int(values[0])
        detail = (
            values[1].decode("utf-8")
            if len(values) > 1 and isinstance(values[1], bytes)
            else (str(values[1]) if len(values) > 1 else "unknown")
        )
        if code == -1:
            raise LeaseLostError("lease fence no longer owns the budget ledger")
        if code == -2:
            raise ValueError("budget ledger is not initialized")
        if code == -3:
            raise AgentBudgetExceeded("Agent budget deadline has expired")
        if code == -4:
            raise ValueError("budget reservation is immutable")
        if code == -5:
            raise AgentBudgetExceeded(f"Agent budget exceeded: {detail}")
        return _usage_from_response(values)

    async def snapshot(self, lease: LeaseHandle) -> UsageCounters:
        """读取当前持久化状态快照，不改变已有状态。

        参数:
            `lease`：沿用签名中 `LeaseHandle` 类型约束的输入。

        返回:
            `UsageCounters`，内容保持现有调用方契约。

        异常:
            `LeaseLostError, ValueError`：输入、状态或下游结果不满足现有约束时抛出。

        副作用:
            可能按照既有键空间读写 Redis 中的 Agent 协调状态。

        不变量:
            预算校验与预留必须保持原子性，余额不足时不得透支。"""
        lease_key, _, ledger_key, _ = self._keys(lease)
        current = await self.coordinator.redis.get(lease_key)
        expected = lease.value.encode("utf-8")
        if current != expected:
            raise LeaseLostError("lease fence no longer owns the budget ledger")
        values = await self.coordinator.redis.hgetall(ledger_key)
        if not values:
            raise ValueError("budget ledger is not initialized")
        decoded = {
            (key.decode("utf-8") if isinstance(key, bytes) else key): int(value)
            for key, value in values.items()
        }
        return UsageCounters(**decoded)

    async def snapshot_by_identity(self, storage_id: str) -> UsageCounters | None:
        """按可信运行身份读取预算账本快照。

        参数:
            `storage_id`：沿用签名中 `str` 类型约束的输入。

        返回:
            `UsageCounters | None`，内容保持现有调用方契约。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。

        副作用:
            可能按照既有键空间读写 Redis 中的 Agent 协调状态。

        不变量:
            预算校验与预留必须保持原子性，余额不足时不得透支。"""

        if not storage_id or len(storage_id) > 256:
            raise ValueError("storage ID must be bounded")
        values = await self.coordinator.redis.hgetall(
            self.coordinator._key("budget-ledger", storage_id)
        )
        if not values:
            return None
        decoded = {
            (key.decode("utf-8") if isinstance(key, bytes) else key): int(value)
            for key, value in values.items()
        }
        return UsageCounters(**decoded)

    def sync_guard(
        self,
        lease: LeaseHandle,
        *,
        model_max_output_tokens: int,
        model_cost_units: int = 0,
        embedding_cost_units: int = 0,
    ) -> "AgentBudgetGuard":
        """同步guard，并遵循现有调用契约。

        参数:
            `lease`：沿用签名中 `LeaseHandle` 类型约束的输入。
            `model_max_output_tokens`：沿用签名中 `int` 类型约束的输入。
            `model_cost_units`：沿用签名中 `int` 类型约束的输入。
            `embedding_cost_units`：沿用签名中 `int` 类型约束的输入。

        返回:
            `'AgentBudgetGuard'`，内容保持现有调用方契约。

        副作用:
            可能按照既有键空间读写 Redis 中的 Agent 协调状态。

        不变量:
            运行状态必须保持项目、线程与 revision 的既有绑定。"""
        return AgentBudgetGuard(
            redis=SyncRedis.from_url(self.coordinator.settings.url, decode_responses=False),
            keys=self._keys(lease),
            lease=lease,
            ttl_seconds=self.coordinator.settings.state_ttl_seconds,
            model_max_output_tokens=model_max_output_tokens,
            model_cost_units=model_cost_units,
            embedding_cost_units=embedding_cost_units,
        )


@dataclass
class AgentBudgetGuard:
    redis: SyncRedis
    keys: tuple[str, str, str, str]
    lease: LeaseHandle
    ttl_seconds: int
    model_max_output_tokens: int
    model_cost_units: int
    embedding_cost_units: int

    def _reserve(self, usage: UsageCounters) -> UsageCounters:
        """预留内部逻辑，并遵循现有调用契约。

        参数:
            `usage`：沿用签名中 `UsageCounters` 类型约束的输入。

        返回:
            `UsageCounters`，内容保持现有调用方契约。

        副作用:
            可能按照既有键空间读写 Redis 中的 Agent 协调状态。

        不变量:
            预算校验与预留必须保持原子性，余额不足时不得透支。"""
        values = self.redis.eval(
            _RESERVE,
            4,
            *self.keys,
            self.lease.value,
            self.ttl_seconds,
            int(datetime.now().astimezone().timestamp() * 1_000),
            uuid4().hex,
            json.dumps(_usage_payload(usage), sort_keys=True, separators=(",", ":")),
            *_DIMENSIONS,
            *(_LIMITS[name] for name in _DIMENSIONS),
        )
        return RedisAgentBudgetLedger._parse_reservation_result(values)

    def reserve_model(self, value: Any, max_output_tokens: int | None = None) -> UsageCounters:
        """预留模型，并遵循现有调用契约。

        参数:
            `value`：待处理的值。
            `max_output_tokens`：沿用签名中 `int | None` 类型约束的输入。

        返回:
            `UsageCounters`，内容保持现有调用方契约。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        output_reservation = (
            self.model_max_output_tokens if max_output_tokens is None else max_output_tokens
        )
        if output_reservation < 1:
            raise ValueError("model output reservation must be positive")
        return self._reserve(
            UsageCounters(
                input_tokens=_estimate_tokens(value),
                output_tokens=output_reservation,
                model_calls=1,
                estimated_cost_units=self.model_cost_units,
            )
        )

    def reserve_embedding(self, texts: Sequence[str]) -> UsageCounters:
        """预留embedding，并遵循现有调用契约。"""
        return self._reserve(
            UsageCounters(
                input_tokens=_estimate_tokens(texts),
                embedding_calls=1,
                estimated_cost_units=self.embedding_cost_units,
            )
        )

    def reserve_tool(self) -> UsageCounters:
        """预留工具，并遵循现有调用契约。"""
        return self._reserve(UsageCounters(steps=1, tool_calls=1))

    def close(self) -> None:
        """关闭当前资源并保持重复关闭安全。

        副作用:
            可能按照既有键空间读写 Redis 中的 Agent 协调状态。

        不变量:
            运行状态必须保持项目、线程与 revision 的既有绑定。"""
        self.redis.close()


def _estimate_tokens(value: Any) -> int:
    """估算Token，并保持现有契约。"""
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            text = str(value)
    # A UTF-8 byte upper bound is intentionally more conservative than the
    # common chars/4 estimate and remains tokenizer/provider independent.
    return max(1, len(text.encode("utf-8")))


_AGENT_BUDGET: ContextVar[AgentBudgetGuard | None] = ContextVar("ezllm_agent_budget", default=None)


def current_agent_budget() -> AgentBudgetGuard | None:
    """返回当前 Agent 调用上下文中的预算钩子。"""
    return _AGENT_BUDGET.get()


@contextmanager
def use_agent_budget(guard: AgentBudgetGuard) -> Iterator[AgentBudgetGuard]:
    """临时绑定agent预算，并遵循现有调用契约。"""
    token = _AGENT_BUDGET.set(guard)
    try:
        with bind_budget_hook(guard):
            yield guard
    finally:
        _AGENT_BUDGET.reset(token)


def reserve_model_budget(value: Any, max_output_tokens: int | None = None) -> UsageCounters | None:
    """预留模型预算，并遵循现有调用契约。"""
    guard = current_agent_budget()
    if guard is None:
        return None
    if max_output_tokens is None:
        return guard.reserve_model(value)
    return guard.reserve_model(value, max_output_tokens=max_output_tokens)


def reserve_embedding_budget(texts: Sequence[str]) -> UsageCounters | None:
    """预留embedding预算，并遵循现有调用契约。"""
    guard = current_agent_budget()
    return guard.reserve_embedding(texts) if guard is not None else None


def reserve_tool_budget() -> UsageCounters | None:
    """预留工具预算，并遵循现有调用契约。"""
    guard = current_agent_budget()
    return guard.reserve_tool() if guard is not None else None
