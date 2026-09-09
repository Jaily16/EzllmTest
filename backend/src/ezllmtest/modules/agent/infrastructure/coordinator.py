# 固定 Redis 命令和 Lua 协调租约、fencing、幂等与重放，调用必须携带项目和运行作用域。
"""Redis coordination primitives for the internal Aspect 3 Agent worker.

Only fixed commands and Lua scripts are exposed.  Callers operate on a
project/graph/thread-derived storage identity and must hold the current fenced
lease before mutating thread state.
"""

from __future__ import annotations
from ezllmtest.modules.agent.ports.coordination import AgentCommand, AgentRedisError, AgentRedisSettings, IdempotencyRecord, IdempotencyStatus, LeaseHandle, LeaseLostError, ReplayEvent, _RedisModel

import hashlib
import json
import os
from ezllmtest.platform import configuration as runtime_values
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue
from redis.asyncio import Redis
from redis.exceptions import ResponseError
from ezllmtest.platform.telemetry.agent_telemetry import TraceCarrier


















def agent_redis_settings_from_environment() -> AgentRedisSettings:
    """从已装配快照解析协调器设置，名称沿用历史 API，但不搜索操作系统 .env。"""

    def integer(name: str, default: int) -> int:
        """对协调 TTL 和轮询设置解析整数，非法配置不能进入队列运行。"""
        raw = runtime_values.get(name)
        if raw is None:
            return default
        try:
            return int(raw)
        except ValueError as exc:
            raise ValueError(f"{name} must be an integer") from exc

    return AgentRedisSettings(
        url=runtime_values.get("AGENT_REDIS_URL", "redis://127.0.0.1:6379/0"),
        prefix=runtime_values.get("AGENT_REDIS_PREFIX", "ezllm:agent:v1"),
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
        """接收可替换 Redis 客户端或按显式设置创建客户端；使用字节响应以便严格解码协调状态。"""
        self.settings = settings
        self.redis = redis or Redis.from_url(settings.url, decode_responses=False)

    def _storage_id(
        self, scope_hash: str, graph_version: str, thread_id: str
    ) -> str:
        """规范化 scope 和 thread 身份后生成存储标识，使租约、幂等和事件共享同一隔离边界。"""
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
        """由 scope 与 thread 派生隔离存储身份，调用方不得直接用未核验项目标识拼接控制键。"""
        return self._storage_id(scope_hash, graph_version, thread_id)

    def _key(self, kind: str, storage_id: str | None = None) -> str:
        """在已配置前缀下组合固定协调键，避免调用方直接提供完整 Redis 键。"""
        base = f"{self.settings.prefix}:{kind}"
        return f"{base}:{storage_id}" if storage_id else base

    def _validate_lease(self, lease: LeaseHandle) -> None:
        """核验租约句柄的身份与必要字段，后续带副作用的 Redis 操作仍需验证当前 fence。"""
        if lease.namespace != self.settings.prefix:
            raise LeaseLostError("lease belongs to a different Redis namespace")

    def _lease_key(self, lease: LeaseHandle) -> str:
        """把可信存储身份放入租约命名空间，供持有者与 fence 一起核验。"""
        self._validate_lease(lease)
        return self._key("lease", lease.storage_id)

    async def acquire_lease(
        self,
        scope_hash: str,
        graph_version: str,
        thread_id: str,
        owner: str,
    ) -> LeaseHandle | None:
        """原子争取线程执行租约并取得 fence，只有成功持有者可以继续处理该线程副作用。"""
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
        """只为当前持有者续租；失败返回失租约结果，执行层据此取消任务。"""
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
        """只释放与句柄身份相符的租约，防止旧 worker 删除新持有者的执行权。"""
        return bool(
            await self.redis.eval(
                _RELEASE_LEASE,
                1,
                self._lease_key(lease),
                lease.value,
            )
        )

    def _idempotency_key(self, lease: LeaseHandle, value: str) -> str:
        """将调用幂等身份限定到租约所属运行，避免不同项目或线程共享执行结果。"""
        if not value or len(value) > 256:
            raise ValueError("idempotency key must be bounded")
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
        return self._key("idempotency", f"{lease.storage_id}:{digest}")

    @staticmethod
    def _decode(value: bytes | str | None) -> str:
        """将 Redis 字节值解码为文本，其他响应按已有类型保留。"""
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
        """把 Redis 幂等响应转换为带状态的记录，不把缺失或无法证明的结果解释为成功。"""
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
        """在租约保护下原子预留调用身份；重复调用应读取既有状态，不再次产生付费副作用。"""
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
        """读取调用身份对应的幂等记录，供执行层判断可恢复结果或 outcome_unknown。"""

        self._validate_lease(lease)
        values = await self.redis.hgetall(
            self._idempotency_key(lease, idempotency_key)
        )
        if not values:
            return None

        def field(name: str):
            """兼容 Redis 字节键和文本键的字段读取，不改变幂等记录状态。"""
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
        """按租约和允许的前态原子迁移幂等记录，禁止旧执行者覆盖更新后的状态。"""
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
        """在实际调用前记录副作用即将开始；崩溃恢复据此区分从未执行与结果无法证明。"""
        return await self._transition_idempotency(
            lease, idempotency_key, IdempotencyStatus.STARTED
        )

    async def complete_idempotency(
        self,
        lease: LeaseHandle,
        idempotency_key: str,
        result: dict[str, JsonValue],
    ) -> IdempotencyRecord:
        """在持有有效租约时登记已完成结果，使重试能够返回既有结果而不重复调用。"""
        return await self._transition_idempotency(
            lease,
            idempotency_key,
            IdempotencyStatus.COMPLETED,
            result=result,
        )

    async def mark_outcome_unknown(
        self, lease: LeaseHandle, idempotency_key: str, reason: str
    ) -> IdempotencyRecord:
        """记录副作用结果无法证明的状态，阻止恢复流程自动再次执行可能已付费的调用。"""
        if not reason or len(reason) > 128:
            raise ValueError("outcome_unknown requires a bounded reason")
        return await self._transition_idempotency(
            lease,
            idempotency_key,
            IdempotencyStatus.OUTCOME_UNKNOWN,
            reason=reason,
        )

    async def request_cancel(self, lease: LeaseHandle) -> None:
        """在租约对应的线程设置取消意图，由执行边界观察并终止后续操作。"""
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
        """按可信 scope 与 thread 设置取消意图，使 API 无需取得执行租约即可请求停止。"""
        storage_id = self._storage_id(scope_hash, graph_version, thread_id)
        await self.redis.set(
            self._key("cancel", storage_id),
            "1",
            ex=self.settings.cancel_ttl,
        )

    async def is_cancelled(self, lease: LeaseHandle) -> bool:
        """读取当前租约所属线程的取消标记，调用方仍须在实际副作用前检查。"""
        self._validate_lease(lease)
        return bool(await self.redis.exists(self._key("cancel", lease.storage_id)))

    async def is_cancelled_by_identity(
        self, scope_hash: str, graph_version: str, thread_id: str
    ) -> bool:
        """按可信运行身份检查取消意图，不认领队列命令或改变执行权。"""
        storage_id = self._storage_id(scope_hash, graph_version, thread_id)
        return bool(await self.redis.exists(self._key("cancel", storage_id)))

    def _nonce_key(self, lease: LeaseHandle, nonce: str) -> str:
        """把审批 nonce 限定到当前运行身份，防止其他运行复用审批令牌。"""
        if not nonce or len(nonce) > 256:
            raise ValueError("approval nonce must be bounded")
        digest = hashlib.sha256(nonce.encode("utf-8")).hexdigest()
        return self._key("approval", f"{lease.storage_id}:{digest}")

    async def issue_approval_nonce(self, lease: LeaseHandle, nonce: str) -> bool:
        """登记一次性审批 nonce 及有效期，使恢复命令能验证审批的新鲜性。"""
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
        """消费指定审批 nonce，重复请求不能无条件复用已消费的审批授权。"""
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
        """为本次审批处理认领 nonce，避免并发请求重复推进同一次批准。"""
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
        """完成已认领 nonce 的处理，保持审批状态与命令恢复的一次性边界。"""
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
        """在运行身份和租约约束下追加有序事件，供 SSE 使用稳定游标恢复。"""
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
        """从指定游标读取已存在的运行事件，不执行工具或重新生成结果。"""
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
        """按可信 scope 与 thread 重放事件，读接口不需要冒充当前执行租约。"""
        storage_id = self._storage_id(scope_hash, graph_version, thread_id)
        synthetic = LeaseHandle(self.settings.prefix, storage_id, "read-only", 1)
        return await self.replay_events(synthetic, after_sequence)

    @property
    def command_stream_key(self) -> str:
        """返回本协调器的命令流位置，消费组操作必须继续通过协调端口。"""
        return self._key("commands")

    async def ensure_command_group(self, group: str) -> None:
        """为普通 worker 显式建立消费组；不消费验收路径不得调用此操作。"""
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
        """把已校验的运行命令加入 Redis Stream，入队不等同于模型或工具已经执行。"""
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
        """按消费组读取可处理命令；该操作会参与队列消费，不属于只读验收。"""
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
        """认领允许恢复的命令并返回给 worker；执行仍须重新验证租约和幂等状态。"""
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
        """确认已处理的流命令，调用方须遵守执行与错误恢复的确认边界。"""
        return int(await self.redis.xack(self.command_stream_key, group, stream_id))

    async def aclose(self) -> None:
        """关闭当前协调器的 Redis 连接，不清理项目数据、控制状态或其他 worker。"""
        await self.redis.aclose()

    async def delete_test_namespace(self) -> None:
        """供隔离测试清理其命名空间；产品启动和普通退出不得调用此测试清理入口。"""

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


    async def put_control(self, key: str, value: Any, **options: Any) -> Any:
        """在租约保护下保存严格序列化的运行控制数据，不能把任意对象交给 Redis。"""
        return await self.redis.set(key, value, **options)

    async def get_control(self, key: str) -> Any:
        """读取指定运行控制记录，类型和内容校验由严格序列化层继续执行。"""
        return await self.redis.get(key)

    async def has_control(self, key: str) -> Any:
        """检查指定控制记录是否存在，不将存在性解释为当前执行成功。"""
        return await self.redis.exists(key)

    async def remove_control(self, key: str) -> Any:
        """在协调边界内移除指定控制记录，不扩大为项目或命名空间清理。"""
        return await self.redis.delete(key)

    def control_key(self, kind: str, storage_id: str) -> str:
        """按运行身份生成控制记录键，保持状态保存与恢复定位一致。"""
        return self._key(kind, storage_id)
