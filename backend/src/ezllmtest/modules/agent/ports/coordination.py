"""协调状态和值对象；应用层只依赖协议，不导入 Redis SDK。"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal, Protocol
from pydantic import BaseModel, ConfigDict, Field, JsonValue
from ezllmtest.platform.telemetry.agent_telemetry import TraceCarrier

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
        """从命令携带的 traceparent 与 tracestate 构造传播载体，不附带任务正文。"""
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
        """核验命名空间、租约和队列时间参数的约束，避免无效配置进入协调层。"""
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
        """幂等记录使用显式 TTL 或状态 TTL，保证重复调用窗口与配置一致。"""
        return self.idempotency_ttl_seconds or self.state_ttl_seconds

    @property
    def cancel_ttl(self) -> int:
        """取消标记使用显式 TTL 或状态 TTL，避免永久遗留控制键。"""
        return self.cancel_ttl_seconds or self.state_ttl_seconds


@dataclass(frozen=True)
# fence token 是 Redis 租约的单调代际号；释放或续租只能作用于当前 owner。
class LeaseHandle:
    namespace: str
    storage_id: str
    owner: str
    fence: int

    @property
    def value(self) -> str:
        """把租约 owner 与 fence 编码为比较值，旧持有者不能冒充新租约。"""
        return f"{self.owner}:{self.fence}"


class Coordinator(Protocol):
    """租约、命令与控制状态的应用接口；Redis 留在 adapter 内。"""
    settings: AgentRedisSettings
    # 由 scope 与 thread 派生隔离存储身份，调用方不得直接用未核验项目标识拼接控制键。
    def storage_id(self, scope_hash: str, graph_version: str, thread_id: str) -> Any: ...
    # 原子争取线程执行租约并取得 fence，只有成功持有者可以继续处理该线程副作用。
    async def acquire_lease(self, scope_hash: str, graph_version: str, thread_id: str, owner: str) -> Any: ...
    # 只为当前持有者续租；失败返回失租约结果，执行层据此取消任务。
    async def renew_lease(self, lease: LeaseHandle) -> Any: ...
    # 只释放与句柄身份相符的租约，防止旧 worker 删除新持有者的执行权。
    async def release_lease(self, lease: LeaseHandle) -> Any: ...
    # 在租约保护下原子预留调用身份；重复调用应读取既有状态，不再次产生付费副作用。
    async def reserve_idempotency(self, lease: LeaseHandle, *, idempotency_key: str, operation: str, persisted: bool) -> Any: ...
    # 读取调用身份对应的幂等记录，供执行层判断可恢复结果或 outcome_unknown。
    async def get_idempotency(self, lease: LeaseHandle, *, idempotency_key: str) -> Any: ...
    # 在实际调用前记录副作用即将开始；崩溃恢复据此区分从未执行与结果无法证明。
    async def mark_idempotency_started(self, lease: LeaseHandle, idempotency_key: str) -> Any: ...
    # 在持有有效租约时登记已完成结果，使重试能够返回既有结果而不重复调用。
    async def complete_idempotency(self, lease: LeaseHandle, idempotency_key: str, result: dict[str, JsonValue]) -> Any: ...
    # 记录副作用结果无法证明的状态，阻止恢复流程自动再次执行可能已付费的调用。
    async def mark_outcome_unknown(self, lease: LeaseHandle, idempotency_key: str, reason: str) -> Any: ...
    # 在租约对应的线程设置取消意图，由执行边界观察并终止后续操作。
    async def request_cancel(self, lease: LeaseHandle) -> Any: ...
    # 按可信 scope 与 thread 设置取消意图，使 API 无需取得执行租约即可请求停止。
    async def request_cancel_by_identity(self, scope_hash: str, graph_version: str, thread_id: str) -> Any: ...
    # 读取当前租约所属线程的取消标记，调用方仍须在实际副作用前检查。
    async def is_cancelled(self, lease: LeaseHandle) -> Any: ...
    # 按可信运行身份检查取消意图，不认领队列命令或改变执行权。
    async def is_cancelled_by_identity(self, scope_hash: str, graph_version: str, thread_id: str) -> Any: ...
    # 登记一次性审批 nonce 及有效期，使恢复命令能验证审批的新鲜性。
    async def issue_approval_nonce(self, lease: LeaseHandle, nonce: str) -> Any: ...
    # 消费指定审批 nonce，重复请求不能无条件复用已消费的审批授权。
    async def consume_approval_nonce(self, lease: LeaseHandle, nonce: str) -> Any: ...
    # 为本次审批处理认领 nonce，避免并发请求重复推进同一次批准。
    async def claim_approval_nonce(self, lease: LeaseHandle, nonce: str, claim_id: str) -> Any: ...
    # 完成已认领 nonce 的处理，保持审批状态与命令恢复的一次性边界。
    async def finalize_approval_nonce(self, lease: LeaseHandle, nonce: str, claim_id: str) -> Any: ...
    # 在运行身份和租约约束下追加有序事件，供 SSE 使用稳定游标恢复。
    async def append_event(self, lease: LeaseHandle, kind: str, data: JsonValue) -> Any: ...
    # 从指定游标读取已存在的运行事件，不执行工具或重新生成结果。
    async def replay_events(self, lease: LeaseHandle, after_sequence: int) -> Any: ...
    # 按可信 scope 与 thread 重放事件，读接口不需要冒充当前执行租约。
    async def replay_events_by_identity(self, scope_hash: str, graph_version: str, thread_id: str, after_sequence: int) -> Any: ...
    # 返回本协调器的命令流位置，消费组操作必须继续通过协调端口。
    def command_stream_key(self) -> Any: ...
    # 为普通 worker 显式建立消费组；不消费验收路径不得调用此操作。
    async def ensure_command_group(self, group: str) -> Any: ...
    # 把已校验的运行命令加入 Redis Stream，入队不等同于模型或工具已经执行。
    async def enqueue_command(self, *, scope_hash: str, graph_version: str, thread_id: str, command_id: str, kind: Literal['start', 'resume', 'recover'], traceparent: str | None=None) -> Any: ...
    # 按消费组读取可处理命令；该操作会参与队列消费，不属于只读验收。
    async def read_commands(self, group: str, consumer: str, *, count: int=1, block_ms: int=1000) -> Any: ...
    # 认领允许恢复的命令并返回给 worker；执行仍须重新验证租约和幂等状态。
    async def claim_commands(self, group: str, consumer: str, *, count: int=1) -> Any: ...
    # 确认已处理的流命令，调用方须遵守执行与错误恢复的确认边界。
    async def ack_command(self, group: str, stream_id: str) -> Any: ...
    # 关闭当前协调器的 Redis 连接，不清理项目数据、控制状态或其他 worker。
    async def aclose(self) -> Any: ...
    # 供隔离测试清理其命名空间；产品启动和普通退出不得调用此测试清理入口。
    async def delete_test_namespace(self) -> Any: ...
    # 在租约保护下保存严格序列化的运行控制数据，不能把任意对象交给 Redis。
    async def put_control(self, key: str, value: Any, **options: Any) -> Any: ...
    # 读取指定运行控制记录，类型和内容校验由严格序列化层继续执行。
    async def get_control(self, key: str) -> Any: ...
    # 检查指定控制记录是否存在，不将存在性解释为当前执行成功。
    async def has_control(self, key: str) -> Any: ...
    # 在协调边界内移除指定控制记录，不扩大为项目或命名空间清理。
    async def remove_control(self, key: str) -> Any: ...
    # 按运行身份生成控制记录键，保持状态保存与恢复定位一致。
    def control_key(self, kind: str, storage_id: str) -> str: ...
