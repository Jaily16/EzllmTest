"""Redis coordination primitives for the internal Aspect 3 Agent worker.

Only fixed commands and Lua scripts are exposed.  Callers operate on a
project/graph/thread-derived storage identity and must hold the current fenced
lease before mutating thread state.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue
from redis.asyncio import Redis
from redis.exceptions import ResponseError
from infrastructure.observability.agent_telemetry import TraceCarrier


class AgentRedisError(RuntimeError):
    pass


class LeaseLostError(AgentRedisError):
    pass


class IdempotencyStatus(str, Enum):
    RESERVED = "reserved"
    STARTED = "started"
    COMPLETED = "completed"
    OUTCOME_UNKNOWN = "outcome_unknown"


class _RedisModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class IdempotencyRecord(_RedisModel):
    idempotency_key: str = Field(min_length=1, max_length=256)
    operation: str = Field(min_length=1, max_length=64)
    persisted: bool
    status: IdempotencyStatus
    result: dict[str, JsonValue] | None = None
    reason: str | None = Field(default=None, max_length=128)


class ReplayEvent(_RedisModel):
    sequence: int = Field(ge=1)
    kind: str = Field(min_length=1, max_length=64)
    data: JsonValue


class AgentCommand(_RedisModel):
    stream_id: str
    command_id: str = Field(min_length=1, max_length=128)
    scope_hash: str = Field(min_length=1, max_length=128)
    graph_version: str = Field(min_length=1, max_length=128)
    thread_id: str = Field(min_length=1, max_length=128)
    kind: Literal["start", "resume", "recover"]
    traceparent: str | None = None

    @property
    def trace_carrier(self) -> TraceCarrier | None:
        """返回当前Trace传播载体。"""
        return (
            TraceCarrier(traceparent=self.traceparent)
            if self.traceparent
            else None
        )


@dataclass(frozen=True)
class AgentRedisSettings:
    url: str = "redis://127.0.0.1:6379/0"
    prefix: str = "ezllm:agent:v1"
    lease_ttl_seconds: int = 30
    lease_renew_seconds: int = 10
    command_claim_seconds: int = 45
    event_ttl_seconds: int = 3_600
    event_max_length: int = 2_000
    state_ttl_seconds: int = 604_800
    idempotency_ttl_seconds: int | None = None
    cancel_ttl_seconds: int | None = None

    def __post_init__(self) -> None:
        """在数据类初始化后校验并规范化实例状态。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        if not self.prefix or any(char.isspace() for char in self.prefix):
            raise ValueError("Redis prefix must be non-empty and contain no whitespace")
        for value in (
            self.lease_ttl_seconds,
            self.lease_renew_seconds,
            self.command_claim_seconds,
            self.event_ttl_seconds,
            self.event_max_length,
            self.state_ttl_seconds,
            self.idempotency_ttl_seconds or self.state_ttl_seconds,
            self.cancel_ttl_seconds or self.state_ttl_seconds,
        ):
            if value <= 0:
                raise ValueError("Redis coordination limits must be positive")
        if self.lease_renew_seconds >= self.lease_ttl_seconds:
            raise ValueError("lease renewal must occur before lease expiry")

    @property
    def idempotency_ttl(self) -> int:
        """返回当前幂等记录TTL。"""
        return self.idempotency_ttl_seconds or self.state_ttl_seconds

    @property
    def cancel_ttl(self) -> int:
        """返回当前取消标记TTL。"""
        return self.cancel_ttl_seconds or self.state_ttl_seconds


def agent_redis_settings_from_environment() -> AgentRedisSettings:
    """从环境变量解析agent Redis设置，并校验现有数据约束。

    返回:
        `AgentRedisSettings`，内容保持现有调用方契约。

    异常:
        `ValueError`：输入、状态或下游结果不满足现有约束时抛出。

    副作用:
        可能按照既有键空间读写 Redis 中的 Agent 协调状态。

    不变量:
        租约、幂等记录、审批凭据和事件游标必须保持原有归属约束。"""

    def integer(name: str, default: int) -> int:
        """读取并校验整数字段。

        参数:
            `name`：目标名称。
            `default`：沿用签名中 `int` 类型约束的输入。

        返回:
            `int`，内容保持现有调用方契约。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        raw = os.environ.get(name)
        if raw is None:
            return default
        try:
            return int(raw)
        except ValueError as exc:
            raise ValueError(f"{name} must be an integer") from exc

    return AgentRedisSettings(
        url=os.environ.get("AGENT_REDIS_URL", "redis://127.0.0.1:6379/0"),
        prefix=os.environ.get("AGENT_REDIS_PREFIX", "ezllm:agent:v1"),
        lease_ttl_seconds=integer("AGENT_LEASE_TTL_SECONDS", 30),
        lease_renew_seconds=integer("AGENT_LEASE_RENEW_SECONDS", 10),
        command_claim_seconds=integer("AGENT_COMMAND_CLAIM_SECONDS", 45),
        event_ttl_seconds=integer("AGENT_EVENT_TTL_SECONDS", 3_600),
        event_max_length=integer("AGENT_EVENT_MAX_LENGTH", 2_000),
        state_ttl_seconds=integer("AGENT_CHECKPOINT_TTL_SECONDS", 604_800),
        idempotency_ttl_seconds=integer(
            "AGENT_IDEMPOTENCY_TTL_SECONDS", 604_800
        ),
        cancel_ttl_seconds=integer("AGENT_CANCEL_TTL_SECONDS", 604_800),
    )


@dataclass(frozen=True)
# fence token 是 Redis 租约的单调代际号；释放或续租只能作用于当前 owner。
class LeaseHandle:
    namespace: str
    storage_id: str
    owner: str
    fence: int

    @property
    def value(self) -> str:
        """返回当前值。"""
        return f"{self.owner}:{self.fence}"


_ACQUIRE_LEASE = """
if redis.call('EXISTS', KEYS[1]) == 1 then return 0 end
local fence = redis.call('INCR', KEYS[2])
redis.call('SET', KEYS[1], ARGV[1] .. ':' .. fence, 'PX', ARGV[2])
redis.call('EXPIRE', KEYS[2], ARGV[3])
return fence
"""

_RENEW_LEASE = """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then return 0 end
redis.call('PEXPIRE', KEYS[1], ARGV[2])
return 1
"""

_RELEASE_LEASE = """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then return 0 end
return redis.call('DEL', KEYS[1])
"""

_RESERVE_IDEMPOTENCY = """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then return {-1} end
if redis.call('EXISTS', KEYS[2]) == 1 then
  if redis.call('HGET', KEYS[2], 'operation') ~= ARGV[3] or
     redis.call('HGET', KEYS[2], 'persisted') ~= ARGV[4] then
    return {-2}
  end
  return {0, redis.call('HGET', KEYS[2], 'status'),
          redis.call('HGET', KEYS[2], 'result') or '',
          redis.call('HGET', KEYS[2], 'reason') or ''}
end
redis.call('HSET', KEYS[2],
  'status', 'reserved', 'operation', ARGV[3], 'persisted', ARGV[4],
  'result', '', 'reason', '')
redis.call('EXPIRE', KEYS[2], ARGV[2])
return {1, 'reserved', '', ''}
"""

_TRANSITION_IDEMPOTENCY = """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then return {-1} end
if redis.call('EXISTS', KEYS[2]) == 0 then return {-2} end
local current = redis.call('HGET', KEYS[2], 'status')
local target = ARGV[3]
if current == target then
  local stored = redis.call('HGET', KEYS[2], 'result') or ''
  if target == 'completed' and stored ~= ARGV[4] then return {-4} end
  return {0, current, stored, redis.call('HGET', KEYS[2], 'reason') or ''}
end
if target == 'started' and current ~= 'reserved' then return {-3, current} end
if target == 'completed' and current ~= 'started' then return {-3, current} end
if target == 'outcome_unknown' and current ~= 'started' then return {-3, current} end
redis.call('HSET', KEYS[2], 'status', target, 'result', ARGV[4], 'reason', ARGV[5])
redis.call('EXPIRE', KEYS[2], ARGV[2])
return {1, target, ARGV[4], ARGV[5]}
"""

_CONSUME_NONCE = """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then return -1 end
if redis.call('GET', KEYS[2]) ~= 'issued' then return 0 end
redis.call('DEL', KEYS[2])
return 1
"""

_CLAIM_NONCE = """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then return -1 end
local current = redis.call('GET', KEYS[2])
local claimed = 'claimed:' .. ARGV[2]
if current == 'issued' then
  redis.call('SET', KEYS[2], claimed, 'EX', ARGV[3])
  return 1
end
if current == claimed then return 1 end
return 0
"""

_FINALIZE_NONCE = """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then return -1 end
if redis.call('GET', KEYS[2]) ~= 'claimed:' .. ARGV[2] then return 0 end
redis.call('DEL', KEYS[2])
return 1
"""

_APPEND_EVENT = """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then return -1 end
local sequence = redis.call('INCR', KEYS[2])
redis.call('XADD', KEYS[3], 'MAXLEN', '=', ARGV[2], sequence .. '-0',
  'kind', ARGV[3], 'data', ARGV[4])
redis.call('EXPIRE', KEYS[2], ARGV[5])
redis.call('EXPIRE', KEYS[3], ARGV[5])
return sequence
"""

_ENQUEUE_COMMAND = """
local existing = redis.call('GET', KEYS[2])
if existing then return existing end
local stream_id = redis.call('XADD', KEYS[1], '*',
  'command_id', ARGV[1], 'scope_hash', ARGV[2],
  'graph_version', ARGV[3], 'thread_id', ARGV[4], 'kind', ARGV[5],
  'traceparent', ARGV[6])
redis.call('SET', KEYS[2], stream_id, 'EX', ARGV[7], 'NX')
return stream_id
"""


# Redis 只保存短期运行协调状态，项目资料和最终 artifact 仍由 MySQL 负责长期保存。
class AgentRedisCoordinator:
    def __init__(
        self,
        settings: AgentRedisSettings,
        *,
        redis: Redis | None = None,
    ) -> None:
        """初始化实例并保存后续操作所需的依赖与状态。

        参数:
            `settings`：沿用签名中 `AgentRedisSettings` 类型约束的输入。
            `redis`：沿用签名中 `Redis | None` 类型约束的输入。

        副作用:
            可能按照既有键空间读写 Redis 中的 Agent 协调状态。

        不变量:
            租约、幂等记录、审批凭据和事件游标必须保持原有归属约束。"""
        self.settings = settings
        self.redis = redis or Redis.from_url(settings.url, decode_responses=False)

    def _storage_id(
        self, scope_hash: str, graph_version: str, thread_id: str
    ) -> str:
        """返回当前存储ID。

        参数:
            `scope_hash`：沿用签名中 `str` 类型约束的输入。
            `graph_version`：沿用签名中 `str` 类型约束的输入。
            `thread_id`：Agent 运行线程 ID。

        返回:
            `str`，内容保持现有调用方契约。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        for value in (scope_hash, graph_version, thread_id):
            if not value or len(value) > 256:
                raise ValueError("scope, graph version, and thread ID must be bounded")
        # The trusted scope hash already binds the graph version.  Use the same
        # derivation as the checkpointer so both layers fence on one lease key.
        return hashlib.sha256(
            f"{scope_hash}\x00{thread_id}".encode("utf-8")
        ).hexdigest()

    def storage_id(
        self, scope_hash: str, graph_version: str, thread_id: str
    ) -> str:
        """返回当前存储ID。"""
        return self._storage_id(scope_hash, graph_version, thread_id)

    def _key(self, kind: str, storage_id: str | None = None) -> str:
        """构造内部逻辑键，并保持现有命名空间格式。"""
        base = f"{self.settings.prefix}:{kind}"
        return f"{base}:{storage_id}" if storage_id else base

    def _validate_lease(self, lease: LeaseHandle) -> None:
        """校验租约，并保持现有契约。

        参数:
            `lease`：沿用签名中 `LeaseHandle` 类型约束的输入。

        异常:
            `LeaseLostError`：输入、状态或下游结果不满足现有约束时抛出。"""
        if lease.namespace != self.settings.prefix:
            raise LeaseLostError("lease belongs to a different Redis namespace")

    def _lease_key(self, lease: LeaseHandle) -> str:
        """构造租约键，并保持现有命名空间格式。"""
        self._validate_lease(lease)
        return self._key("lease", lease.storage_id)

    async def acquire_lease(
        self,
        scope_hash: str,
        graph_version: str,
        thread_id: str,
        owner: str,
    ) -> LeaseHandle | None:
        """获取租约，并遵循现有调用契约。

        参数:
            `scope_hash`：沿用签名中 `str` 类型约束的输入。
            `graph_version`：沿用签名中 `str` 类型约束的输入。
            `thread_id`：Agent 运行线程 ID。
            `owner`：沿用签名中 `str` 类型约束的输入。

        返回:
            `LeaseHandle | None`，内容保持现有调用方契约。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。

        副作用:
            可能按照既有键空间读写 Redis 中的 Agent 协调状态。

        不变量:
            租约、幂等记录、审批凭据和事件游标必须保持原有归属约束。"""
        if not owner or len(owner) > 128 or ":" in owner:
            raise ValueError("lease owner must be bounded and cannot contain ':'")
        storage_id = self._storage_id(scope_hash, graph_version, thread_id)
        fence = int(
            await self.redis.eval(
                _ACQUIRE_LEASE,
                2,
                self._key("lease", storage_id),
                self._key("fence", storage_id),
                owner,
                self.settings.lease_ttl_seconds * 1_000,
                self.settings.state_ttl_seconds,
            )
        )
        if fence == 0:
            return None
        return LeaseHandle(self.settings.prefix, storage_id, owner, fence)

    async def renew_lease(self, lease: LeaseHandle) -> bool:
        """续期租约，并遵循现有调用契约。

        参数:
            `lease`：沿用签名中 `LeaseHandle` 类型约束的输入。

        返回:
            `bool`，内容保持现有调用方契约。

        副作用:
            可能按照既有键空间读写 Redis 中的 Agent 协调状态。

        不变量:
            租约、幂等记录、审批凭据和事件游标必须保持原有归属约束。"""
        return bool(
            await self.redis.eval(
                _RENEW_LEASE,
                1,
                self._lease_key(lease),
                lease.value,
                self.settings.lease_ttl_seconds * 1_000,
            )
        )

    async def release_lease(self, lease: LeaseHandle) -> bool:
        """释放租约，并遵循现有调用契约。

        参数:
            `lease`：沿用签名中 `LeaseHandle` 类型约束的输入。

        返回:
            `bool`，内容保持现有调用方契约。

        副作用:
            可能按照既有键空间读写 Redis 中的 Agent 协调状态。

        不变量:
            租约、幂等记录、审批凭据和事件游标必须保持原有归属约束。"""
        return bool(
            await self.redis.eval(
                _RELEASE_LEASE,
                1,
                self._lease_key(lease),
                lease.value,
            )
        )

    def _idempotency_key(self, lease: LeaseHandle, value: str) -> str:
        """构造幂等记录键，并保持现有命名空间格式。

        参数:
            `lease`：沿用签名中 `LeaseHandle` 类型约束的输入。
            `value`：待处理的值。

        返回:
            `str`，内容保持现有调用方契约。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        if not value or len(value) > 256:
            raise ValueError("idempotency key must be bounded")
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
        return self._key("idempotency", f"{lease.storage_id}:{digest}")

    @staticmethod
    def _decode(value: bytes | str | None) -> str:
        """解码并校验当前存储值。"""
        if value is None:
            return ""
        return value.decode("utf-8") if isinstance(value, bytes) else value

    def _record(
        self,
        idempotency_key: str,
        operation: str,
        persisted: bool,
        values: list[Any],
    ) -> IdempotencyRecord:
        """记录内部逻辑，并遵循现有调用契约。

        参数:
            `idempotency_key`：沿用签名中 `str` 类型约束的输入。
            `operation`：工作流操作名。
            `persisted`：沿用签名中 `bool` 类型约束的输入。
            `values`：沿用签名中 `list[Any]` 类型约束的输入。

        返回:
            `IdempotencyRecord`，内容保持现有调用方契约。"""
        status = self._decode(values[1])
        raw_result = self._decode(values[2])
        reason = self._decode(values[3])
        return IdempotencyRecord(
            idempotency_key=idempotency_key,
            operation=operation,
            persisted=persisted,
            status=status,
            result=json.loads(raw_result) if raw_result else None,
            reason=reason or None,
        )

    async def reserve_idempotency(
        self,
        lease: LeaseHandle,
        *,
        idempotency_key: str,
        operation: str,
        persisted: bool,
    ) -> IdempotencyRecord:
        """预留幂等记录，并遵循现有调用契约。

        参数:
            `lease`：沿用签名中 `LeaseHandle` 类型约束的输入。
            `idempotency_key`：沿用签名中 `str` 类型约束的输入。
            `operation`：工作流操作名。
            `persisted`：沿用签名中 `bool` 类型约束的输入。

        返回:
            `IdempotencyRecord`，内容保持现有调用方契约。

        异常:
            `LeaseLostError, ValueError`：输入、状态或下游结果不满足现有约束时抛出。

        副作用:
            可能按照既有键空间读写 Redis 中的 Agent 协调状态。

        不变量:
            租约、幂等记录、审批凭据和事件游标必须保持原有归属约束。"""
        values = await self.redis.eval(
            _RESERVE_IDEMPOTENCY,
            2,
            self._lease_key(lease),
            self._idempotency_key(lease, idempotency_key),
            lease.value,
            self.settings.idempotency_ttl,
            operation,
            "1" if persisted else "0",
        )
        code = int(values[0])
        if code == -1:
            raise LeaseLostError("lease fence no longer owns the thread")
        if code == -2:
            raise ValueError("idempotency key conflicts with an existing operation")
        return self._record(idempotency_key, operation, persisted, values)

    async def get_idempotency(
        self,
        lease: LeaseHandle,
        *,
        idempotency_key: str,
    ) -> IdempotencyRecord | None:
        """获取幂等记录，并遵循现有调用契约。

        参数:
            `lease`：沿用签名中 `LeaseHandle` 类型约束的输入。
            `idempotency_key`：沿用签名中 `str` 类型约束的输入。

        返回:
            `IdempotencyRecord | None`，内容保持现有调用方契约。

        副作用:
            可能按照既有键空间读写 Redis 中的 Agent 协调状态。

        不变量:
            租约、幂等记录、审批凭据和事件游标必须保持原有归属约束。"""

        self._validate_lease(lease)
        values = await self.redis.hgetall(
            self._idempotency_key(lease, idempotency_key)
        )
        if not values:
            return None

        def field(name: str):
            """处理字段，并保持 `AgentRedisCoordinator` 的现有状态约束。"""
            return values.get(name.encode("utf-8"), values.get(name))

        operation = self._decode(field("operation"))
        persisted = self._decode(field("persisted")) == "1"
        return IdempotencyRecord(
            idempotency_key=idempotency_key,
            operation=operation,
            persisted=persisted,
            status=self._decode(field("status")),
            result=(
                json.loads(self._decode(field("result")))
                if field("result")
                else None
            ),
            reason=self._decode(field("reason")) or None,
        )

    async def _transition_idempotency(
        self,
        lease: LeaseHandle,
        idempotency_key: str,
        target: IdempotencyStatus,
        *,
        result: dict[str, JsonValue] | None = None,
        reason: str | None = None,
    ) -> IdempotencyRecord:
        """转换幂等记录，并遵循现有调用契约。

        参数:
            `lease`：沿用签名中 `LeaseHandle` 类型约束的输入。
            `idempotency_key`：沿用签名中 `str` 类型约束的输入。
            `target`：沿用签名中 `IdempotencyStatus` 类型约束的输入。
            `result`：沿用签名中 `dict[str, JsonValue] | None` 类型约束的输入。
            `reason`：沿用签名中 `str | None` 类型约束的输入。

        返回:
            `IdempotencyRecord`，内容保持现有调用方契约。

        异常:
            `ValueError, LeaseLostError`：输入、状态或下游结果不满足现有约束时抛出。

        副作用:
            可能按照既有键空间读写 Redis 中的 Agent 协调状态。

        不变量:
            租约、幂等记录、审批凭据和事件游标必须保持原有归属约束。"""
        key = self._idempotency_key(lease, idempotency_key)
        current = await self.redis.hgetall(key)
        if not current:
            raise ValueError("idempotency reservation does not exist")
        operation = self._decode(current.get(b"operation"))
        persisted = self._decode(current.get(b"persisted")) == "1"
        result_json = (
            json.dumps(result, sort_keys=True, separators=(",", ":"))
            if result is not None
            else ""
        )
        values = await self.redis.eval(
            _TRANSITION_IDEMPOTENCY,
            2,
            self._lease_key(lease),
            key,
            lease.value,
            self.settings.idempotency_ttl,
            target.value,
            result_json,
            reason or "",
        )
        code = int(values[0])
        if code == -1:
            raise LeaseLostError("lease fence no longer owns the thread")
        if code == -2:
            raise ValueError("idempotency reservation does not exist")
        if code == -3:
            current_status = self._decode(values[1])
            raise ValueError(
                f"cannot transition idempotency from {current_status} to {target.value}"
            )
        if code == -4:
            raise ValueError("completed idempotency result cannot be changed")
        return self._record(idempotency_key, operation, persisted, values)

    async def mark_idempotency_started(
        self, lease: LeaseHandle, idempotency_key: str
    ) -> IdempotencyRecord:
        """标记幂等记录started，并遵循现有调用契约。"""
        return await self._transition_idempotency(
            lease, idempotency_key, IdempotencyStatus.STARTED
        )

    async def complete_idempotency(
        self,
        lease: LeaseHandle,
        idempotency_key: str,
        result: dict[str, JsonValue],
    ) -> IdempotencyRecord:
        """完成幂等记录，并遵循现有调用契约。"""
        return await self._transition_idempotency(
            lease,
            idempotency_key,
            IdempotencyStatus.COMPLETED,
            result=result,
        )

    async def mark_outcome_unknown(
        self, lease: LeaseHandle, idempotency_key: str, reason: str
    ) -> IdempotencyRecord:
        """标记结果未知，并遵循现有调用契约。

        参数:
            `lease`：沿用签名中 `LeaseHandle` 类型约束的输入。
            `idempotency_key`：沿用签名中 `str` 类型约束的输入。
            `reason`：沿用签名中 `str` 类型约束的输入。

        返回:
            `IdempotencyRecord`，内容保持现有调用方契约。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        if not reason or len(reason) > 128:
            raise ValueError("outcome_unknown requires a bounded reason")
        return await self._transition_idempotency(
            lease,
            idempotency_key,
            IdempotencyStatus.OUTCOME_UNKNOWN,
            reason=reason,
        )

    async def request_cancel(self, lease: LeaseHandle) -> None:
        """请求取消标记，并遵循现有调用契约。

        参数:
            `lease`：沿用签名中 `LeaseHandle` 类型约束的输入。

        异常:
            `LeaseLostError`：输入、状态或下游结果不满足现有约束时抛出。

        副作用:
            可能按照既有键空间读写 Redis 中的 Agent 协调状态。

        不变量:
            租约、幂等记录、审批凭据和事件游标必须保持原有归属约束。"""
        if not await self.renew_lease(lease):
            raise LeaseLostError("lease fence no longer owns the thread")
        await self.redis.set(
            self._key("cancel", lease.storage_id),
            "1",
            ex=self.settings.cancel_ttl,
        )

    async def request_cancel_by_identity(
        self, scope_hash: str, graph_version: str, thread_id: str
    ) -> None:
        """按身份读取或计算请求取消标记。

        参数:
            `scope_hash`：沿用签名中 `str` 类型约束的输入。
            `graph_version`：沿用签名中 `str` 类型约束的输入。
            `thread_id`：Agent 运行线程 ID。

        副作用:
            可能按照既有键空间读写 Redis 中的 Agent 协调状态。

        不变量:
            租约、幂等记录、审批凭据和事件游标必须保持原有归属约束。"""
        storage_id = self._storage_id(scope_hash, graph_version, thread_id)
        await self.redis.set(
            self._key("cancel", storage_id),
            "1",
            ex=self.settings.cancel_ttl,
        )

    async def is_cancelled(self, lease: LeaseHandle) -> bool:
        """判断取消状态是否满足现有约束。

        参数:
            `lease`：沿用签名中 `LeaseHandle` 类型约束的输入。

        返回:
            `bool`，内容保持现有调用方契约。

        副作用:
            可能按照既有键空间读写 Redis 中的 Agent 协调状态。

        不变量:
            租约、幂等记录、审批凭据和事件游标必须保持原有归属约束。"""
        self._validate_lease(lease)
        return bool(await self.redis.exists(self._key("cancel", lease.storage_id)))

    async def is_cancelled_by_identity(
        self, scope_hash: str, graph_version: str, thread_id: str
    ) -> bool:
        """判断取消状态按身份是否满足现有约束。

        参数:
            `scope_hash`：沿用签名中 `str` 类型约束的输入。
            `graph_version`：沿用签名中 `str` 类型约束的输入。
            `thread_id`：Agent 运行线程 ID。

        返回:
            `bool`，内容保持现有调用方契约。

        副作用:
            可能按照既有键空间读写 Redis 中的 Agent 协调状态。

        不变量:
            租约、幂等记录、审批凭据和事件游标必须保持原有归属约束。"""
        storage_id = self._storage_id(scope_hash, graph_version, thread_id)
        return bool(await self.redis.exists(self._key("cancel", storage_id)))

    def _nonce_key(self, lease: LeaseHandle, nonce: str) -> str:
        """构造一次性凭据键，并保持现有命名空间格式。

        参数:
            `lease`：沿用签名中 `LeaseHandle` 类型约束的输入。
            `nonce`：沿用签名中 `str` 类型约束的输入。

        返回:
            `str`，内容保持现有调用方契约。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        if not nonce or len(nonce) > 256:
            raise ValueError("approval nonce must be bounded")
        digest = hashlib.sha256(nonce.encode("utf-8")).hexdigest()
        return self._key("approval", f"{lease.storage_id}:{digest}")

    async def issue_approval_nonce(self, lease: LeaseHandle, nonce: str) -> bool:
        """签发审批一次性凭据，并遵循现有调用契约。

        参数:
            `lease`：沿用签名中 `LeaseHandle` 类型约束的输入。
            `nonce`：沿用签名中 `str` 类型约束的输入。

        返回:
            `bool`，内容保持现有调用方契约。

        异常:
            `LeaseLostError`：输入、状态或下游结果不满足现有约束时抛出。

        副作用:
            可能按照既有键空间读写 Redis 中的 Agent 协调状态。

        不变量:
            审批结果必须继续绑定当前项目、revision、plan hash 与一次性凭据。"""
        if not await self.renew_lease(lease):
            raise LeaseLostError("lease fence no longer owns the thread")
        return bool(
            await self.redis.set(
                self._nonce_key(lease, nonce),
                "issued",
                ex=self.settings.state_ttl_seconds,
                nx=True,
            )
        )

    async def consume_approval_nonce(self, lease: LeaseHandle, nonce: str) -> bool:
        """消费审批一次性凭据，并遵循现有调用契约。

        参数:
            `lease`：沿用签名中 `LeaseHandle` 类型约束的输入。
            `nonce`：沿用签名中 `str` 类型约束的输入。

        返回:
            `bool`，内容保持现有调用方契约。

        异常:
            `LeaseLostError`：输入、状态或下游结果不满足现有约束时抛出。

        副作用:
            可能按照既有键空间读写 Redis 中的 Agent 协调状态。

        不变量:
            审批结果必须继续绑定当前项目、revision、plan hash 与一次性凭据。"""
        result = int(
            await self.redis.eval(
                _CONSUME_NONCE,
                2,
                self._lease_key(lease),
                self._nonce_key(lease, nonce),
                lease.value,
            )
        )
        if result == -1:
            raise LeaseLostError("lease fence no longer owns the thread")
        return result == 1

    async def claim_approval_nonce(
        self,
        lease: LeaseHandle,
        nonce: str,
        claim_id: str,
    ) -> bool:
        """认领审批一次性凭据，并遵循现有调用契约。

        参数:
            `lease`：沿用签名中 `LeaseHandle` 类型约束的输入。
            `nonce`：沿用签名中 `str` 类型约束的输入。
            `claim_id`：沿用签名中 `str` 类型约束的输入。

        返回:
            `bool`，内容保持现有调用方契约。

        异常:
            `ValueError, LeaseLostError`：输入、状态或下游结果不满足现有约束时抛出。

        副作用:
            可能按照既有键空间读写 Redis 中的 Agent 协调状态。

        不变量:
            审批结果必须继续绑定当前项目、revision、plan hash 与一次性凭据。"""
        if not claim_id or len(claim_id) > 128:
            raise ValueError("approval nonce claim ID must be bounded")
        result = int(
            await self.redis.eval(
                _CLAIM_NONCE,
                2,
                self._lease_key(lease),
                self._nonce_key(lease, nonce),
                lease.value,
                claim_id,
                self.settings.state_ttl_seconds,
            )
        )
        if result == -1:
            raise LeaseLostError("lease fence no longer owns the thread")
        return result == 1

    async def finalize_approval_nonce(
        self,
        lease: LeaseHandle,
        nonce: str,
        claim_id: str,
    ) -> bool:
        """完成并固化审批一次性凭据，并保持现有契约。

        参数:
            `lease`：沿用签名中 `LeaseHandle` 类型约束的输入。
            `nonce`：沿用签名中 `str` 类型约束的输入。
            `claim_id`：沿用签名中 `str` 类型约束的输入。

        返回:
            `bool`，内容保持现有调用方契约。

        异常:
            `LeaseLostError`：输入、状态或下游结果不满足现有约束时抛出。

        副作用:
            可能按照既有键空间读写 Redis 中的 Agent 协调状态。

        不变量:
            审批结果必须继续绑定当前项目、revision、plan hash 与一次性凭据。"""
        result = int(
            await self.redis.eval(
                _FINALIZE_NONCE,
                2,
                self._lease_key(lease),
                self._nonce_key(lease, nonce),
                lease.value,
                claim_id,
            )
        )
        if result == -1:
            raise LeaseLostError("lease fence no longer owns the thread")
        return result == 1

    async def append_event(
        self,
        lease: LeaseHandle,
        kind: str,
        data: JsonValue,
    ) -> int:
        """追加事件，并遵循现有调用契约。

        参数:
            `lease`：沿用签名中 `LeaseHandle` 类型约束的输入。
            `kind`：沿用签名中 `str` 类型约束的输入。
            `data`：沿用签名中 `JsonValue` 类型约束的输入。

        返回:
            `int`，内容保持现有调用方契约。

        异常:
            `ValueError, LeaseLostError`：输入、状态或下游结果不满足现有约束时抛出。

        副作用:
            可能按照既有键空间读写 Redis 中的 Agent 协调状态。

        不变量:
            租约、幂等记录、审批凭据和事件游标必须保持原有归属约束。"""
        if not kind or len(kind) > 64:
            raise ValueError("event kind must be bounded")
        encoded = json.dumps(data, sort_keys=True, separators=(",", ":"))
        sequence = int(
            await self.redis.eval(
                _APPEND_EVENT,
                3,
                self._lease_key(lease),
                self._key("event-sequence", lease.storage_id),
                self._key("events", lease.storage_id),
                lease.value,
                self.settings.event_max_length,
                kind,
                encoded,
                self.settings.event_ttl_seconds,
            )
        )
        if sequence == -1:
            raise LeaseLostError("lease fence no longer owns the thread")
        return sequence

    async def replay_events(
        self, lease: LeaseHandle, after_sequence: int
    ) -> list[ReplayEvent]:
        """回放事件，并遵循现有调用契约。

        参数:
            `lease`：沿用签名中 `LeaseHandle` 类型约束的输入。
            `after_sequence`：沿用签名中 `int` 类型约束的输入。

        返回:
            `list[ReplayEvent]`，内容保持现有调用方契约。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。

        副作用:
            可能按照既有键空间读写 Redis 中的 Agent 协调状态。

        不变量:
            租约、幂等记录、审批凭据和事件游标必须保持原有归属约束。"""
        self._validate_lease(lease)
        if after_sequence < 0:
            raise ValueError("after_sequence cannot be negative")
        entries = await self.redis.xrange(
            self._key("events", lease.storage_id),
            min=f"({after_sequence}-0",
            max="+",
            count=self.settings.event_max_length,
        )
        events: list[ReplayEvent] = []
        for stream_id, fields in entries:
            identifier = self._decode(stream_id)
            events.append(
                ReplayEvent(
                    sequence=int(identifier.split("-", 1)[0]),
                    kind=self._decode(fields[b"kind"]),
                    data=json.loads(self._decode(fields[b"data"])),
                )
            )
        return events

    async def replay_events_by_identity(
        self,
        scope_hash: str,
        graph_version: str,
        thread_id: str,
        after_sequence: int,
    ) -> list[ReplayEvent]:
        """按身份读取或计算replay事件。"""
        storage_id = self._storage_id(scope_hash, graph_version, thread_id)
        synthetic = LeaseHandle(self.settings.prefix, storage_id, "read-only", 1)
        return await self.replay_events(synthetic, after_sequence)

    @property
    def command_stream_key(self) -> str:
        """返回当前命令流键。"""
        return self._key("commands")

    async def ensure_command_group(self, group: str) -> None:
        """确保命令消费组，并遵循现有调用契约。

        参数:
            `group`：沿用签名中 `str` 类型约束的输入。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。

        副作用:
            可能按照既有键空间读写 Redis 中的 Agent 协调状态。

        不变量:
            租约、幂等记录、审批凭据和事件游标必须保持原有归属约束。"""
        if not group or len(group) > 128:
            raise ValueError("command group must be bounded")
        try:
            await self.redis.xgroup_create(
                self.command_stream_key, group, id="0", mkstream=True
            )
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def enqueue_command(
        self,
        *,
        scope_hash: str,
        graph_version: str,
        thread_id: str,
        command_id: str,
        kind: Literal["start", "resume", "recover"],
        traceparent: str | None = None,
    ) -> str:
        """入队命令，并遵循现有调用契约。

        参数:
            `scope_hash`：沿用签名中 `str` 类型约束的输入。
            `graph_version`：沿用签名中 `str` 类型约束的输入。
            `thread_id`：Agent 运行线程 ID。
            `command_id`：沿用签名中 `str` 类型约束的输入。
            `kind`：沿用签名中 `Literal['start', 'resume', 'recover']` 类型约束的输入。
            `traceparent`：沿用签名中 `str | None` 类型约束的输入。

        返回:
            `str`，内容保持现有调用方契约。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。

        副作用:
            可能按照既有键空间读写 Redis 中的 Agent 协调状态。

        不变量:
            租约、幂等记录、审批凭据和事件游标必须保持原有归属约束。"""
        if not command_id or len(command_id) > 128:
            raise ValueError("command ID must be bounded")
        storage_id = self._storage_id(scope_hash, graph_version, thread_id)
        if traceparent is not None:
            TraceCarrier(traceparent=traceparent)
        dedup = self._key(
            "command-dedup",
            hashlib.sha256(command_id.encode("utf-8")).hexdigest(),
        )
        result = await self.redis.eval(
            _ENQUEUE_COMMAND,
            2,
            self.command_stream_key,
            dedup,
            command_id,
            scope_hash,
            graph_version,
            thread_id,
            kind,
            traceparent or "",
            self.settings.state_ttl_seconds,
        )
        del storage_id  # validation and canonical scope binding are intentional.
        return self._decode(result)

    async def read_commands(
        self,
        group: str,
        consumer: str,
        *,
        count: int = 1,
        block_ms: int = 1_000,
    ) -> list[AgentCommand]:
        """读取命令，并遵循现有调用契约。

        参数:
            `group`：沿用签名中 `str` 类型约束的输入。
            `consumer`：沿用签名中 `str` 类型约束的输入。
            `count`：沿用签名中 `int` 类型约束的输入。
            `block_ms`：沿用签名中 `int` 类型约束的输入。

        返回:
            `list[AgentCommand]`，内容保持现有调用方契约。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。

        副作用:
            可能按照既有键空间读写 Redis 中的 Agent 协调状态。

        不变量:
            租约、幂等记录、审批凭据和事件游标必须保持原有归属约束。"""
        if not consumer or len(consumer) > 128:
            raise ValueError("consumer must be bounded")
        messages = await self.redis.xreadgroup(
            group,
            consumer,
            {self.command_stream_key: ">"},
            count=count,
            block=block_ms,
        )
        commands: list[AgentCommand] = []
        for _, entries in messages:
            for stream_id, fields in entries:
                commands.append(
                    AgentCommand(
                        stream_id=self._decode(stream_id),
                        command_id=self._decode(fields[b"command_id"]),
                        scope_hash=self._decode(fields[b"scope_hash"]),
                        graph_version=self._decode(fields[b"graph_version"]),
                        thread_id=self._decode(fields[b"thread_id"]),
                        kind=self._decode(fields[b"kind"]),
                        traceparent=(
                            self._decode(fields.get(b"traceparent", b"")) or None
                        ),
                    )
                )
        return commands

    async def claim_commands(
        self,
        group: str,
        consumer: str,
        *,
        count: int = 1,
    ) -> list[AgentCommand]:
        """认领命令，并遵循现有调用契约。

        参数:
            `group`：沿用签名中 `str` 类型约束的输入。
            `consumer`：沿用签名中 `str` 类型约束的输入。
            `count`：沿用签名中 `int` 类型约束的输入。

        返回:
            `list[AgentCommand]`，内容保持现有调用方契约。

        副作用:
            可能按照既有键空间读写 Redis 中的 Agent 协调状态。

        不变量:
            租约、幂等记录、审批凭据和事件游标必须保持原有归属约束。"""
        result = await self.redis.xautoclaim(
            self.command_stream_key,
            group,
            consumer,
            min_idle_time=self.settings.command_claim_seconds * 1_000,
            start_id="0-0",
            count=count,
        )
        entries = result[1]
        commands: list[AgentCommand] = []
        for stream_id, fields in entries:
            commands.append(
                AgentCommand(
                    stream_id=self._decode(stream_id),
                    command_id=self._decode(fields[b"command_id"]),
                    scope_hash=self._decode(fields[b"scope_hash"]),
                    graph_version=self._decode(fields[b"graph_version"]),
                    thread_id=self._decode(fields[b"thread_id"]),
                    kind=self._decode(fields[b"kind"]),
                    traceparent=(
                        self._decode(fields.get(b"traceparent", b"")) or None
                    ),
                )
            )
        return commands

    async def ack_command(self, group: str, stream_id: str) -> int:
        """确认消费命令，并遵循现有调用契约。

        参数:
            `group`：沿用签名中 `str` 类型约束的输入。
            `stream_id`：沿用签名中 `str` 类型约束的输入。

        返回:
            `int`，内容保持现有调用方契约。

        副作用:
            可能按照既有键空间读写 Redis 中的 Agent 协调状态。

        不变量:
            租约、幂等记录、审批凭据和事件游标必须保持原有归属约束。"""
        return int(await self.redis.xack(self.command_stream_key, group, stream_id))

    async def aclose(self) -> None:
        """异步关闭当前资源并保持重复关闭安全。

        副作用:
            可能按照既有键空间读写 Redis 中的 Agent 协调状态。

        不变量:
            租约、幂等记录、审批凭据和事件游标必须保持原有归属约束。"""
        await self.redis.aclose()

    async def delete_test_namespace(self) -> None:
        """删除测试命名空间，并遵循现有调用契约。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。

        副作用:
            可能按照既有键空间读写 Redis 中的 Agent 协调状态。

        不变量:
            租约、幂等记录、审批凭据和事件游标必须保持原有归属约束。"""

        if ":test:" not in self.settings.prefix:
            raise ValueError("namespace cleanup is restricted to explicit test prefixes")
        batch: list[bytes] = []
        async for key in self.redis.scan_iter(match=f"{self.settings.prefix}:*"):
            batch.append(key)
            if len(batch) == 100:
                await self.redis.delete(*batch)
                batch.clear()
        if batch:
            await self.redis.delete(*batch)
