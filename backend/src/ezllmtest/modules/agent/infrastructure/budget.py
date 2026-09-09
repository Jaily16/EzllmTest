# 用 Redis 原子账本预留与结算 Agent 预算，并向 Provider 调用提供硬预算守卫。
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
from ezllmtest.platform.ai.runtime_hooks import bind_budget_hook
from ezllmtest.modules.agent.domain.contracts import RunBudget, UsageCounters
from ezllmtest.modules.agent.ports.coordination import LeaseHandle, LeaseLostError
from ezllmtest.modules.agent.infrastructure.coordinator import AgentRedisCoordinator


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
    """要求带时区的时钟值后转换为毫秒，避免不同进程的本地时间歧义影响预算期限。"""
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
        """复用运行协调器的 Redis 边界，使预算预留与结算遵循同一项目和运行作用域。"""
        self.coordinator = coordinator

    def _keys(self, lease: LeaseHandle) -> tuple[str, str, str, str]:
        """先验证租约，再定位预算和 fence 对应的 Redis 键，禁止脱离执行身份计费。"""
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
        """在租约保护下原子建立运行预算和截止时间，重复初始化不能重置已消耗额度。"""
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
        """通过原子脚本预留调用所需额度，在实际付费操作前检查上限和执行租约。"""
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
        """区分失租约、非法响应与预算耗尽；失败不能被解释为已成功预留。"""
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
        """持有效租约读取当前用量，发现 fence 不符拒绝继续以旧执行权使用快照。"""
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
        """只读查询运行累计用量供工作台展示，不预留额度或授予调用权。"""

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
        """为同步 provider 边界创建预算 guard，复用同一租约键与原子预算脚本。"""
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
        """在同步调用边界原子登记本次预算预留；随机请求标识用于区分计费动作。"""
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
        """在模型调用前预留输入估计与输出上限，并拒绝不合法输出预算。"""
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
        """在 embedding 请求前预留输入 token 和调用次数，不以检索只读为由绕过预算。"""
        return self._reserve(
            UsageCounters(
                input_tokens=_estimate_tokens(texts),
                embedding_calls=1,
                estimated_cost_units=self.embedding_cost_units,
            )
        )

    def reserve_tool(self) -> UsageCounters:
        """在工具执行前预留工具调用额度，仍须由执行层核验审批和项目 scope。"""
        return self._reserve(UsageCounters(steps=1, tool_calls=1))

    def close(self) -> None:
        """释放同步预算客户端，不撤销已经记录的消耗。"""
        self.redis.close()


def _estimate_tokens(value: Any) -> int:
    """为预算预留提供保守的离线 token 估计，不把该估计当作供应商实际账单。"""
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
