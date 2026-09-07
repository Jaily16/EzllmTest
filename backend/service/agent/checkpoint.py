"""Strict checkpoint serialization and the Aspect 3 Redis saver.

The codec is intentionally independent of LangGraph's JsonPlusSerializer.  It
never imports a module named by persisted data and it has no pickle or msgpack
fallback.  The Redis saver later in this module implements only the public
``BaseCheckpointSaver`` protocol required by the single-Agent runtime.
"""

from __future__ import annotations

import base64
import dataclasses
import hashlib
import json
import math
import re
import time
from collections.abc import AsyncIterator, Sequence
from typing import Any, cast

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    WRITES_IDX_MAP,
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)
from langgraph.checkpoint.serde.types import TASKS
from langgraph.types import Interrupt, Send
from redis.asyncio import Redis
from redis.exceptions import ResponseError

from service.agent.contracts import TrustedProjectScope
from infrastructure.observability.agent_telemetry import agent_span, get_agent_telemetry


CHECKPOINT_CONTENT_TYPE = "ezllm-safe-json-v1"


class UnsafeCheckpointDataError(ValueError):
    """Raised when checkpoint data is outside the explicit safe subset."""


def _instrument_checkpoint(kind: str):
    """包装并观测检查点，并保持现有契约。

    参数:
        `kind`：沿用签名中 `str` 类型约束的输入。"""
    def decorate(function):
        """包装内部逻辑，并遵循现有调用契约。

        参数:
            `function`：调用方传入的现有参数。"""
        async def wrapped(*args, **kwargs):
            """执行被包装的调用，并在前后应用当前装饰器的保护逻辑。

            参数:
                `args`：调用方传入的现有参数。
                `kwargs`：调用方传入的现有参数。"""
            started = time.perf_counter()
            telemetry = get_agent_telemetry()
            status = "error"
            try:
                with agent_span(
                    "agent.checkpoint",
                    {"agent.checkpoint.kind": kind},
                ):
                    result = await function(*args, **kwargs)
                status = "success"
                return result
            finally:
                telemetry.counter(
                    "ezllm.agent.checkpoint.operations",
                    labels={"checkpoint_kind": kind, "status": status},
                )
                telemetry.histogram(
                    "ezllm.agent.checkpoint.duration",
                    (time.perf_counter() - started) * 1_000,
                    {"checkpoint_kind": kind, "status": status},
                )

        return wrapped

    return decorate


def _instrument_checkpoint_stream(kind: str):
    """包装并观测检查点流，并保持现有契约。

    参数:
        `kind`：沿用签名中 `str` 类型约束的输入。"""
    def decorate(function):
        """包装内部逻辑，并遵循现有调用契约。

        参数:
            `function`：调用方传入的现有参数。"""
        async def wrapped(*args, **kwargs):
            """执行被包装的调用，并在前后应用当前装饰器的保护逻辑。

            参数:
                `args`：调用方传入的现有参数。
                `kwargs`：调用方传入的现有参数。"""
            started = time.perf_counter()
            telemetry = get_agent_telemetry()
            status = "error"
            try:
                with agent_span(
                    "agent.checkpoint",
                    {"agent.checkpoint.kind": kind},
                ):
                    async for item in function(*args, **kwargs):
                        yield item
                status = "success"
            finally:
                telemetry.counter(
                    "ezllm.agent.checkpoint.operations",
                    labels={"checkpoint_kind": kind, "status": status},
                )
                telemetry.histogram(
                    "ezllm.agent.checkpoint.duration",
                    (time.perf_counter() - started) * 1_000,
                    {"checkpoint_kind": kind, "status": status},
                )

        return wrapped

    return decorate


_FORBIDDEN_STATE_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "chain_of_thought",
        "completion",
        "cookie",
        "credential",
        "credentials",
        "document_body",
        "document_content",
        "password",
        "passwd",
        "prompt",
        "raw_document",
        "reasoning",
        "reasoning_content",
        "scratchpad",
        "secret",
        "traceback",
    }
)


def _is_constructor_envelope(value: dict[str, Any]) -> bool:
    """判断constructor响应信封是否满足现有约束。"""
    return (
        value.get("lc") in (1, 2)
        and value.get("type") == "constructor"
        and "id" in value
    )


# checkpoint 只允许可枚举的 JSON 值，拒绝 pickle/msgpack 以保持跨版本安全恢复。
class StrictAgentCheckpointSerializer:
    """Serialize an explicit safe value algebra to deterministic JSON bytes."""

    def __init__(
        self,
        *,
        max_depth: int = 64,
        max_bytes: int = 1_048_576,
        max_nodes: int = 20_000,
    ) -> None:
        """初始化实例并保存后续操作所需的依赖与状态。

        参数:
            `max_depth`：沿用签名中 `int` 类型约束的输入。
            `max_bytes`：沿用签名中 `int` 类型约束的输入。
            `max_nodes`：沿用签名中 `int` 类型约束的输入。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        if max_depth < 1 or max_bytes < 64 or max_nodes < 1:
            raise ValueError("checkpoint serializer limits must be positive")
        self.max_depth = max_depth
        self.max_bytes = max_bytes
        self.max_nodes = max_nodes

    def dumps_typed(self, obj: Any) -> tuple[str, bytes]:
        """序列化typed，并遵循现有调用契约。

        参数:
            `obj`：沿用签名中 `Any` 类型约束的输入。

        返回:
            `tuple[str, bytes]`，内容保持现有调用方契约。

        异常:
            `UnsafeCheckpointDataError`：输入、状态或下游结果不满足现有约束时抛出。"""
        counter = [0]
        root = self._encode(obj, depth=0, counter=counter)
        data = json.dumps(
            {"schema": 1, "root": root},
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        if len(data) > self.max_bytes:
            raise UnsafeCheckpointDataError("checkpoint exceeds the byte limit")
        return CHECKPOINT_CONTENT_TYPE, data

    def loads_typed(self, data: tuple[str, bytes]) -> Any:
        """反序列化typed，并遵循现有调用契约。

        参数:
            `data`：沿用签名中 `tuple[str, bytes]` 类型约束的输入。

        返回:
            `Any`，内容保持现有调用方契约。

        异常:
            `UnsafeCheckpointDataError`：输入、状态或下游结果不满足现有约束时抛出。"""
        content_type, payload = data
        if content_type != CHECKPOINT_CONTENT_TYPE:
            raise UnsafeCheckpointDataError(
                f"unsupported checkpoint content type: {content_type}"
            )
        if not isinstance(payload, bytes) or len(payload) > self.max_bytes:
            raise UnsafeCheckpointDataError("checkpoint payload is invalid or too large")
        try:
            document = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise UnsafeCheckpointDataError("checkpoint JSON is invalid") from exc
        if (
            not isinstance(document, dict)
            or set(document) != {"schema", "root"}
            or document.get("schema") != 1
        ):
            raise UnsafeCheckpointDataError("checkpoint envelope is invalid")
        counter = [0]
        return self._decode(document["root"], depth=0, counter=counter)

    def _visit(self, depth: int, counter: list[int]) -> None:
        """处理visit，并保持 `StrictAgentCheckpointSerializer` 的现有状态约束。

        参数:
            `depth`：沿用签名中 `int` 类型约束的输入。
            `counter`：沿用签名中 `list[int]` 类型约束的输入。

        异常:
            `UnsafeCheckpointDataError`：输入、状态或下游结果不满足现有约束时抛出。"""
        if depth > self.max_depth:
            raise UnsafeCheckpointDataError("checkpoint exceeds the depth limit")
        counter[0] += 1
        if counter[0] > self.max_nodes:
            raise UnsafeCheckpointDataError("checkpoint exceeds the node limit")

    def _encode(self, value: Any, *, depth: int, counter: list[int]) -> dict[str, Any]:
        """将当前值编码为稳定存储格式。

        参数:
            `value`：待处理的值。
            `depth`：沿用签名中 `int` 类型约束的输入。
            `counter`：沿用签名中 `list[int]` 类型约束的输入。

        返回:
            `dict[str, Any]`，内容保持现有调用方契约。

        异常:
            `UnsafeCheckpointDataError`：输入、状态或下游结果不满足现有约束时抛出。"""
        self._visit(depth, counter)
        if value is None:
            return {"t": "null"}
        if type(value) is bool:
            return {"t": "bool", "v": value}
        if type(value) is int:
            return {"t": "int", "v": value}
        if type(value) is float:
            if not math.isfinite(value):
                raise UnsafeCheckpointDataError("checkpoint floats must be finite")
            return {"t": "float", "v": value}
        if type(value) is str:
            return {"t": "str", "v": value}
        if type(value) is bytes:
            return {
                "t": "bytes",
                "v": base64.b64encode(value).decode("ascii"),
            }
        if type(value) is bytearray:
            return {
                "t": "bytearray",
                "v": base64.b64encode(bytes(value)).decode("ascii"),
            }
        if type(value) is list:
            return {
                "t": "list",
                "v": [
                    self._encode(item, depth=depth + 1, counter=counter)
                    for item in value
                ],
            }
        if type(value) is tuple:
            return {
                "t": "tuple",
                "v": [
                    self._encode(item, depth=depth + 1, counter=counter)
                    for item in value
                ],
            }
        if type(value) is dict:
            self._validate_plain_dict(value)
            return {
                "t": "dict",
                "v": [
                    [
                        key,
                        self._encode(value[key], depth=depth + 1, counter=counter),
                    ]
                    for key in sorted(value)
                ],
            }
        if type(value) is Interrupt:
            fields = {field.name for field in dataclasses.fields(Interrupt)}
            encoded: dict[str, Any] = {
                "t": "interrupt",
                "value": self._encode(
                    value.value, depth=depth + 1, counter=counter
                ),
            }
            if "id" in fields:
                interrupt_id = getattr(value, "id", None)
                if not isinstance(interrupt_id, str):
                    raise UnsafeCheckpointDataError("interrupt id must be text")
                encoded["id"] = interrupt_id
            return encoded
        if type(value) is Send:
            if getattr(value, "timeout", None) is not None:
                raise UnsafeCheckpointDataError("Send timeout is not checkpointable")
            if not isinstance(value.node, str):
                raise UnsafeCheckpointDataError("Send node must be text")
            return {
                "t": "send",
                "node": value.node,
                "arg": self._encode(value.arg, depth=depth + 1, counter=counter),
            }
        raise UnsafeCheckpointDataError(
            f"unsupported checkpoint value type: {type(value).__name__}"
        )

    def _validate_plain_dict(self, value: dict[Any, Any]) -> None:
        """校验普通DICT，并保持现有契约。

        参数:
            `value`：待处理的值。

        异常:
            `UnsafeCheckpointDataError`：输入、状态或下游结果不满足现有约束时抛出。"""
        if any(type(key) is not str for key in value):
            raise UnsafeCheckpointDataError("checkpoint object keys must be text")
        if _is_constructor_envelope(value):
            raise UnsafeCheckpointDataError("constructor envelopes are forbidden")
        for key in value:
            if key.strip().lower() in _FORBIDDEN_STATE_KEYS:
                raise UnsafeCheckpointDataError(
                    f"forbidden checkpoint field: {key}"
                )

    def _decode(self, node: Any, *, depth: int, counter: list[int]) -> Any:
        """解码并校验当前存储值。

        参数:
            `node`：沿用签名中 `Any` 类型约束的输入。
            `depth`：沿用签名中 `int` 类型约束的输入。
            `counter`：沿用签名中 `list[int]` 类型约束的输入。

        返回:
            `Any`，内容保持现有调用方契约。

        异常:
            `UnsafeCheckpointDataError`：输入、状态或下游结果不满足现有约束时抛出。"""
        self._visit(depth, counter)
        if not isinstance(node, dict) or not isinstance(node.get("t"), str):
            raise UnsafeCheckpointDataError("checkpoint AST node is invalid")
        tag = node["t"]
        if tag == "null" and set(node) == {"t"}:
            return None
        if tag == "bool" and set(node) == {"t", "v"} and type(node["v"]) is bool:
            return node["v"]
        if tag == "int" and set(node) == {"t", "v"} and type(node["v"]) is int:
            return node["v"]
        if tag == "float" and set(node) == {"t", "v"} and type(node["v"]) in (int, float):
            value = float(node["v"])
            if not math.isfinite(value):
                raise UnsafeCheckpointDataError("checkpoint floats must be finite")
            return value
        if tag == "str" and set(node) == {"t", "v"} and type(node["v"]) is str:
            return node["v"]
        if tag in {"bytes", "bytearray"} and set(node) == {"t", "v"}:
            if type(node["v"]) is not str:
                raise UnsafeCheckpointDataError("checkpoint binary marker is invalid")
            try:
                decoded = base64.b64decode(node["v"], validate=True)
            except (ValueError, TypeError) as exc:
                raise UnsafeCheckpointDataError(
                    "checkpoint binary value is invalid"
                ) from exc
            return decoded if tag == "bytes" else bytearray(decoded)
        if tag in {"list", "tuple"} and set(node) == {"t", "v"}:
            if not isinstance(node["v"], list):
                raise UnsafeCheckpointDataError("checkpoint sequence is invalid")
            value = [
                self._decode(item, depth=depth + 1, counter=counter)
                for item in node["v"]
            ]
            return value if tag == "list" else tuple(value)
        if tag == "dict" and set(node) == {"t", "v"}:
            if not isinstance(node["v"], list):
                raise UnsafeCheckpointDataError("checkpoint object is invalid")
            value: dict[str, Any] = {}
            for pair in node["v"]:
                if (
                    not isinstance(pair, list)
                    or len(pair) != 2
                    or type(pair[0]) is not str
                    or pair[0] in value
                ):
                    raise UnsafeCheckpointDataError("checkpoint object entry is invalid")
                value[pair[0]] = self._decode(
                    pair[1], depth=depth + 1, counter=counter
                )
            self._validate_plain_dict(value)
            return value
        if tag == "interrupt":
            allowed = {"t", "value", "id"}
            if not set(node).issubset(allowed) or "value" not in node:
                raise UnsafeCheckpointDataError("interrupt marker is invalid")
            fields = {field.name for field in dataclasses.fields(Interrupt)}
            kwargs = {
                "value": self._decode(
                    node["value"], depth=depth + 1, counter=counter
                )
            }
            if "id" in fields:
                interrupt_id = node.get("id", "placeholder-id")
                if type(interrupt_id) is not str:
                    raise UnsafeCheckpointDataError("interrupt id must be text")
                kwargs["id"] = interrupt_id
            elif "id" in node:
                raise UnsafeCheckpointDataError("unexpected interrupt id")
            return Interrupt(**kwargs)
        if tag == "send" and set(node) == {"t", "node", "arg"}:
            if type(node["node"]) is not str:
                raise UnsafeCheckpointDataError("Send node must be text")
            return Send(
                node["node"],
                self._decode(node["arg"], depth=depth + 1, counter=counter),
            )
        raise UnsafeCheckpointDataError(f"unknown checkpoint AST tag: {tag}")


_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_CHECKPOINT_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def derive_agent_scope_hash(
    scope: TrustedProjectScope,
    graph_version: str,
) -> str:
    """计算derive agent作用域的稳定哈希。

    参数:
        `scope`：沿用签名中 `TrustedProjectScope` 类型约束的输入。
        `graph_version`：沿用签名中 `str` 类型约束的输入。

    返回:
        `str`，内容保持现有调用方契约。

    异常:
        `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
    if not graph_version or len(graph_version) > 128:
        raise ValueError("graph_version is invalid")
    canonical = json.dumps(
        {
            "graph_version": graph_version,
            "scope": scope.model_dump(mode="json"),
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


# 存储线程 ID 绑定可信项目 scope，防止同一个外部线程跨项目复用 Redis 状态。
def derive_storage_thread_id(scope_hash: str, external_thread_id: str) -> str:
    """返回当前derive存储线程ID。

    参数:
        `scope_hash`：沿用签名中 `str` 类型约束的输入。
        `external_thread_id`：沿用签名中 `str` 类型约束的输入。

    返回:
        `str`，内容保持现有调用方契约。

    异常:
        `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
    if not _HEX_64.fullmatch(scope_hash):
        raise ValueError("scope_hash must be a lowercase SHA-256 digest")
    if not external_thread_id or len(external_thread_id) > 128:
        raise ValueError("external_thread_id is invalid")
    return hashlib.sha256(
        f"{scope_hash}\0{external_thread_id}".encode("utf-8")
    ).hexdigest()


_PUT_CHECKPOINT_SCRIPT = r"""
if redis.call('GET', KEYS[5]) ~= ARGV[1] .. ':' .. ARGV[2] then
  return redis.error_reply('LEASE_FENCE_MISMATCH')
end
local sequence = redis.call('INCR', KEYS[3])
redis.call('HSET', KEYS[1],
  'content_type', ARGV[5],
  'checkpoint', ARGV[6],
  'metadata_type', ARGV[7],
  'metadata', ARGV[8],
  'parent_checkpoint_id', ARGV[9],
  'checkpoint_ns', ARGV[10],
  'scope_hash', ARGV[11],
  'graph_version', ARGV[12],
  'storage_thread_id', ARGV[13],
  'checkpoint_id', ARGV[4],
  'sequence', tostring(sequence))
redis.call('ZADD', KEYS[2], sequence, ARGV[4])
redis.call('SADD', KEYS[4], KEYS[1], KEYS[2], KEYS[3], KEYS[5])
local ttl = tonumber(ARGV[3])
redis.call('EXPIRE', KEYS[1], ttl)
redis.call('EXPIRE', KEYS[2], ttl)
redis.call('EXPIRE', KEYS[3], ttl)
redis.call('EXPIRE', KEYS[4], ttl)
return sequence
"""


_PUT_WRITES_SCRIPT = r"""
if redis.call('GET', KEYS[3]) ~= ARGV[1] .. ':' .. ARGV[2] then
  return redis.error_reply('LEASE_FENCE_MISMATCH')
end
local count = tonumber(ARGV[4])
local offset = 5
for index = 1, count do
  local field = ARGV[offset]
  local value = ARGV[offset + 1]
  local overwrite = ARGV[offset + 2]
  if overwrite == '1' then
    redis.call('HSET', KEYS[1], field, value)
  else
    redis.call('HSETNX', KEYS[1], field, value)
  end
  offset = offset + 3
end
redis.call('SADD', KEYS[2], KEYS[1], KEYS[3])
local ttl = tonumber(ARGV[3])
redis.call('EXPIRE', KEYS[1], ttl)
redis.call('EXPIRE', KEYS[2], ttl)
return count
"""


# checkpoint 写入必须经过租约 fence 和幂等序列，避免失租约 worker 覆盖新运行状态。
class AsyncAgentRedisCheckpointSaver(BaseCheckpointSaver[str]):
    """Scope-bound Redis implementation of LangGraph's public async protocol."""

    def __init__(
        self,
        redis_client: Redis,
        *,
        scope_hash: str,
        graph_version: str,
        lease_owner: str,
        fence_token: int,
        prefix: str = "ezllm:agent:v1:checkpoint",
        coordination_prefix: str = "ezllm:agent:v1",
        ttl_seconds: int = 7 * 24 * 60 * 60,
        serializer: StrictAgentCheckpointSerializer | None = None,
    ) -> None:
        """初始化实例并保存后续操作所需的依赖与状态。

        参数:
            `redis_client`：沿用签名中 `Redis` 类型约束的输入。
            `scope_hash`：沿用签名中 `str` 类型约束的输入。
            `graph_version`：沿用签名中 `str` 类型约束的输入。
            `lease_owner`：沿用签名中 `str` 类型约束的输入。
            `fence_token`：沿用签名中 `int` 类型约束的输入。
            `prefix`：沿用签名中 `str` 类型约束的输入。
            `coordination_prefix`：沿用签名中 `str` 类型约束的输入。
            `ttl_seconds`：沿用签名中 `int` 类型约束的输入。
            `serializer`：沿用签名中 `StrictAgentCheckpointSerializer | None` 类型约束的输入。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        if not _HEX_64.fullmatch(scope_hash):
            raise ValueError("scope_hash must be a lowercase SHA-256 digest")
        if not graph_version or len(graph_version) > 128:
            raise ValueError("graph_version is invalid")
        if not lease_owner or len(lease_owner) > 128:
            raise ValueError("lease_owner is invalid")
        if isinstance(fence_token, bool) or fence_token < 1:
            raise ValueError("fence_token must be a positive integer")
        if not prefix or len(prefix) > 160:
            raise ValueError("checkpoint prefix is invalid")
        if ttl_seconds < 60:
            raise ValueError("checkpoint TTL must be at least 60 seconds")
        self.redis = redis_client
        self.scope_hash = scope_hash
        self.graph_version = graph_version
        self.graph_hash = hashlib.sha256(graph_version.encode("utf-8")).hexdigest()[:32]
        self.lease_owner = lease_owner
        self.fence_token = fence_token
        self.prefix = prefix.rstrip(":")
        self.coordination_prefix = coordination_prefix.rstrip(":")
        self.ttl_seconds = ttl_seconds
        super().__init__(serde=serializer or StrictAgentCheckpointSerializer())

    def runtime_config(
        self,
        storage_thread_id: str,
        *,
        checkpoint_id: str | None = None,
        checkpoint_ns: str = "",
    ) -> RunnableConfig:
        """处理运行时配置，并保持 `AsyncAgentRedisCheckpointSaver` 的现有状态约束。

        参数:
            `storage_thread_id`：沿用签名中 `str` 类型约束的输入。
            `checkpoint_id`：检查点 ID。
            `checkpoint_ns`：沿用签名中 `str` 类型约束的输入。

        返回:
            `RunnableConfig`，内容保持现有调用方契约。"""
        self._validate_thread_id(storage_thread_id)
        configurable: dict[str, Any] = {
            "thread_id": storage_thread_id,
            "checkpoint_ns": checkpoint_ns,
            "agent_scope_hash": self.scope_hash,
            "agent_graph_version": self.graph_version,
            "agent_fence": self.fence_token,
        }
        if checkpoint_id is not None:
            self._validate_checkpoint_id(checkpoint_id)
            configurable["checkpoint_id"] = checkpoint_id
        return {"configurable": configurable}

    def lease_key(self, storage_thread_id: str) -> str:
        """构造租约键，并保持现有命名空间格式。"""
        self._validate_thread_id(storage_thread_id)
        return f"{self.coordination_prefix}:lease:{storage_thread_id}"

    def checkpoint_key(self, config: RunnableConfig) -> str:
        """构造检查点键，并保持现有命名空间格式。"""
        values = self._validated_config(config, require_checkpoint=True)
        return self._checkpoint_key(
            values["thread_id"], values["checkpoint_ns"], values["checkpoint_id"]
        )

    def _base(self, storage_thread_id: str, checkpoint_ns: str) -> str:
        """处理基础，并保持 `AsyncAgentRedisCheckpointSaver` 的现有状态约束。"""
        namespace_hash = hashlib.sha256(checkpoint_ns.encode("utf-8")).hexdigest()[:32]
        return (
            f"{self.prefix}:{self.scope_hash}:{self.graph_hash}:"
            f"{storage_thread_id}:{namespace_hash}"
        )

    def _checkpoint_key(
        self, storage_thread_id: str, checkpoint_ns: str, checkpoint_id: str
    ) -> str:
        """构造检查点键，并保持现有命名空间格式。"""
        return f"{self._base(storage_thread_id, checkpoint_ns)}:cp:{checkpoint_id}"

    def _timeline_key(self, storage_thread_id: str, checkpoint_ns: str) -> str:
        """构造时间线键，并保持现有命名空间格式。"""
        return f"{self._base(storage_thread_id, checkpoint_ns)}:timeline"

    def _sequence_key(self, storage_thread_id: str, checkpoint_ns: str) -> str:
        """构造sequence键，并保持现有命名空间格式。"""
        return f"{self._base(storage_thread_id, checkpoint_ns)}:sequence"

    def _writes_key(
        self, storage_thread_id: str, checkpoint_ns: str, checkpoint_id: str
    ) -> str:
        """构造写入记录键，并保持现有命名空间格式。"""
        return f"{self._base(storage_thread_id, checkpoint_ns)}:writes:{checkpoint_id}"

    def _registry_key(self, storage_thread_id: str) -> str:
        """构造注册表键，并保持现有命名空间格式。"""
        return (
            f"{self.prefix}:registry:{self.scope_hash}:{self.graph_hash}:"
            f"{storage_thread_id}"
        )

    @staticmethod
    def _validate_thread_id(storage_thread_id: str) -> None:
        """校验线程ID，并保持现有契约。

        参数:
            `storage_thread_id`：沿用签名中 `str` 类型约束的输入。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        if not isinstance(storage_thread_id, str) or not _HEX_64.fullmatch(
            storage_thread_id
        ):
            raise ValueError("storage thread id is invalid")

    @staticmethod
    def _validate_checkpoint_id(checkpoint_id: str) -> None:
        """校验检查点ID，并保持现有契约。

        参数:
            `checkpoint_id`：检查点 ID。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        if not isinstance(checkpoint_id, str) or not _SAFE_CHECKPOINT_ID.fullmatch(
            checkpoint_id
        ):
            raise ValueError("checkpoint id is invalid")

    def _validated_config(
        self, config: RunnableConfig, *, require_checkpoint: bool
    ) -> dict[str, Any]:
        """返回经过现有约束校验的配置。

        参数:
            `config`：显式运行配置。
            `require_checkpoint`：沿用签名中 `bool` 类型约束的输入。

        返回:
            `dict[str, Any]`，内容保持现有调用方契约。

        异常:
            `ValueError, PermissionError`：输入、状态或下游结果不满足现有约束时抛出。"""
        if not isinstance(config, dict) or not isinstance(
            config.get("configurable"), dict
        ):
            raise ValueError("checkpoint config is invalid")
        values = cast(dict[str, Any], config["configurable"])
        thread_id = values.get("thread_id")
        self._validate_thread_id(thread_id)
        checkpoint_ns = values.get("checkpoint_ns", "")
        if not isinstance(checkpoint_ns, str) or len(checkpoint_ns) > 512:
            raise ValueError("checkpoint namespace is invalid")
        if values.get("agent_scope_hash") != self.scope_hash:
            raise PermissionError("checkpoint project scope does not match")
        if values.get("agent_graph_version") != self.graph_version:
            raise PermissionError("checkpoint graph version does not match")
        if values.get("agent_fence") != self.fence_token:
            raise PermissionError("checkpoint lease fence does not match")
        checkpoint_id = values.get("checkpoint_id")
        if require_checkpoint and checkpoint_id is None:
            raise ValueError("checkpoint id is required")
        if checkpoint_id is not None:
            self._validate_checkpoint_id(checkpoint_id)
        return {
            "thread_id": thread_id,
            "checkpoint_ns": checkpoint_ns,
            "checkpoint_id": checkpoint_id,
        }

    @staticmethod
    def _field(row: dict[bytes, bytes], name: str) -> bytes | None:
        """读取并校验指定字段。"""
        return row.get(name.encode("utf-8"))

    @staticmethod
    def _text(value: bytes | None) -> str:
        """处理文本，并保持 `AsyncAgentRedisCheckpointSaver` 的现有状态约束。"""
        return value.decode("utf-8") if value else ""

    def _config_with_checkpoint(
        self, config: RunnableConfig, checkpoint_id: str
    ) -> RunnableConfig:
        """基于检查点构造配置。"""
        configurable = dict(cast(dict[str, Any], config["configurable"]))
        configurable["checkpoint_id"] = checkpoint_id
        return {**config, "configurable": configurable}

    @_instrument_checkpoint("put")
    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """异步保存 LangGraph 检查点，并维持线程与 checkpoint 绑定。

        参数:
            `config`：显式运行配置。
            `checkpoint`：沿用签名中 `Checkpoint` 类型约束的输入。
            `metadata`：沿用签名中 `CheckpointMetadata` 类型约束的输入。
            `new_versions`：沿用签名中 `ChannelVersions` 类型约束的输入。

        返回:
            `RunnableConfig`，内容保持现有调用方契约。

        异常:
            `PermissionError`：输入、状态或下游结果不满足现有约束时抛出。

        副作用:
            可能按照既有键空间读写 Redis 中的 Agent 协调状态。

        不变量:
            检查点必须绑定既有运行身份，恢复不得跨项目或跨 revision。"""
        del new_versions
        values = self._validated_config(config, require_checkpoint=False)
        checkpoint_id = checkpoint.get("id")
        self._validate_checkpoint_id(checkpoint_id)
        checkpoint_to_store = dict(checkpoint)
        checkpoint_to_store["pending_sends"] = []
        checkpoint_type, checkpoint_data = self.serde.dumps_typed(
            checkpoint_to_store
        )
        metadata_type, metadata_data = self.serde.dumps_typed(dict(metadata))
        parent_id = values["checkpoint_id"] or ""
        checkpoint_key = self._checkpoint_key(
            values["thread_id"], values["checkpoint_ns"], checkpoint_id
        )
        keys = (
            checkpoint_key,
            self._timeline_key(values["thread_id"], values["checkpoint_ns"]),
            self._sequence_key(values["thread_id"], values["checkpoint_ns"]),
            self._registry_key(values["thread_id"]),
            self.lease_key(values["thread_id"]),
        )
        args: tuple[Any, ...] = (
            self.lease_owner,
            str(self.fence_token),
            str(self.ttl_seconds),
            checkpoint_id,
            checkpoint_type,
            checkpoint_data,
            metadata_type,
            metadata_data,
            parent_id,
            values["checkpoint_ns"],
            self.scope_hash,
            self.graph_version,
            values["thread_id"],
        )
        try:
            await self.redis.eval(_PUT_CHECKPOINT_SCRIPT, len(keys), *keys, *args)
        except ResponseError as exc:
            if "LEASE_FENCE_MISMATCH" in str(exc):
                raise PermissionError("checkpoint lease fence does not match") from None
            raise
        return self._config_with_checkpoint(config, checkpoint_id)

    @_instrument_checkpoint("put_writes")
    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        """异步保存检查点的待处理写入记录。

        参数:
            `config`：显式运行配置。
            `writes`：沿用签名中 `Sequence[tuple[str, Any]]` 类型约束的输入。
            `task_id`：沿用签名中 `str` 类型约束的输入。
            `task_path`：沿用签名中 `str` 类型约束的输入。

        异常:
            `ValueError, UnsafeCheckpointDataError, PermissionError`：输入、状态或下游结果不满足现有约束时抛出。

        副作用:
            可能按照既有键空间读写 Redis 中的 Agent 协调状态。

        不变量:
            检查点必须绑定既有运行身份，恢复不得跨项目或跨 revision。"""
        values = self._validated_config(config, require_checkpoint=True)
        if not task_id or len(task_id) > 256 or len(task_path) > 512:
            raise ValueError("checkpoint task identity is invalid")
        serialized: list[Any] = []
        for position, (channel, value) in enumerate(writes):
            if not isinstance(channel, str) or not channel:
                raise ValueError("checkpoint write channel is invalid")
            index = WRITES_IDX_MAP.get(channel, position)
            identity = hashlib.sha256(
                f"{task_id}\0{task_path}\0{index}".encode("utf-8")
            ).hexdigest()
            content_type, payload = self.serde.dumps_typed(
                (task_id, task_path, index, channel, value)
            )
            if content_type != CHECKPOINT_CONTENT_TYPE:
                raise UnsafeCheckpointDataError("unexpected write content type")
            serialized.extend(
                [identity, payload, "1" if channel in WRITES_IDX_MAP else "0"]
            )
        keys = (
            self._writes_key(
                values["thread_id"],
                values["checkpoint_ns"],
                values["checkpoint_id"],
            ),
            self._registry_key(values["thread_id"]),
            self.lease_key(values["thread_id"]),
        )
        args: list[Any] = [
            self.lease_owner,
            str(self.fence_token),
            str(self.ttl_seconds),
            str(len(writes)),
            *serialized,
        ]
        try:
            await self.redis.eval(_PUT_WRITES_SCRIPT, len(keys), *keys, *args)
        except ResponseError as exc:
            if "LEASE_FENCE_MISMATCH" in str(exc):
                raise PermissionError("checkpoint lease fence does not match") from None
            raise

    async def _pending_writes(
        self, storage_thread_id: str, checkpoint_ns: str, checkpoint_id: str
    ) -> list[tuple[str, str, Any]]:
        """处理待处理写入记录，并保持 `AsyncAgentRedisCheckpointSaver` 的现有状态约束。

        参数:
            `storage_thread_id`：沿用签名中 `str` 类型约束的输入。
            `checkpoint_ns`：沿用签名中 `str` 类型约束的输入。
            `checkpoint_id`：检查点 ID。

        返回:
            `list[tuple[str, str, Any]]`，内容保持现有调用方契约。

        异常:
            `UnsafeCheckpointDataError`：输入、状态或下游结果不满足现有约束时抛出。

        副作用:
            可能按照既有键空间读写 Redis 中的 Agent 协调状态。

        不变量:
            检查点必须绑定既有运行身份，恢复不得跨项目或跨 revision。"""
        row = await self.redis.hgetall(
            self._writes_key(storage_thread_id, checkpoint_ns, checkpoint_id)
        )
        decoded: list[tuple[str, str, int, str, Any]] = []
        for payload in row.values():
            value = self.serde.loads_typed((CHECKPOINT_CONTENT_TYPE, payload))
            if (
                not isinstance(value, tuple)
                or len(value) != 5
                or not isinstance(value[0], str)
                or not isinstance(value[1], str)
                or type(value[2]) is not int
                or not isinstance(value[3], str)
            ):
                raise UnsafeCheckpointDataError("pending write is invalid")
            decoded.append(value)
        decoded.sort(key=lambda item: (item[0], item[1], item[2]))
        return [(task_id, channel, value) for task_id, _, _, channel, value in decoded]

    @_instrument_checkpoint("get")
    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        """异步读取指定配置对应的检查点元组。

        参数:
            `config`：显式运行配置。

        返回:
            `CheckpointTuple | None`，内容保持现有调用方契约。

        异常:
            `PermissionError, UnsafeCheckpointDataError`：输入、状态或下游结果不满足现有约束时抛出。

        副作用:
            可能按照既有键空间读写 Redis 中的 Agent 协调状态。

        不变量:
            检查点必须绑定既有运行身份，恢复不得跨项目或跨 revision。"""
        values = self._validated_config(config, require_checkpoint=False)
        checkpoint_id = values["checkpoint_id"]
        if checkpoint_id is None:
            latest = await self.redis.zrevrange(
                self._timeline_key(values["thread_id"], values["checkpoint_ns"]),
                0,
                0,
            )
            if not latest:
                return None
            checkpoint_id = self._text(latest[0])
            self._validate_checkpoint_id(checkpoint_id)
        row = await self.redis.hgetall(
            self._checkpoint_key(
                values["thread_id"], values["checkpoint_ns"], checkpoint_id
            )
        )
        if not row:
            return None
        if (
            self._text(self._field(row, "scope_hash")) != self.scope_hash
            or self._text(self._field(row, "graph_version")) != self.graph_version
            or self._text(self._field(row, "storage_thread_id"))
            != values["thread_id"]
        ):
            raise PermissionError("stored checkpoint authority does not match")
        checkpoint = self.serde.loads_typed(
            (
                self._text(self._field(row, "content_type")),
                self._field(row, "checkpoint") or b"",
            )
        )
        metadata = self.serde.loads_typed(
            (
                self._text(self._field(row, "metadata_type")),
                self._field(row, "metadata") or b"",
            )
        )
        if not isinstance(checkpoint, dict) or not isinstance(metadata, dict):
            raise UnsafeCheckpointDataError("stored checkpoint record is invalid")
        parent_id = self._text(self._field(row, "parent_checkpoint_id"))
        if parent_id:
            parent_writes = await self._pending_writes(
                values["thread_id"], values["checkpoint_ns"], parent_id
            )
            checkpoint["pending_sends"] = [
                item for _, channel, item in parent_writes if channel == TASKS
            ]
        else:
            checkpoint["pending_sends"] = []
        result_config = self._config_with_checkpoint(config, checkpoint_id)
        parent_config = (
            self._config_with_checkpoint(config, parent_id) if parent_id else None
        )
        pending_writes = await self._pending_writes(
            values["thread_id"], values["checkpoint_ns"], checkpoint_id
        )
        return CheckpointTuple(
            result_config,
            cast(Checkpoint, checkpoint),
            cast(CheckpointMetadata, metadata),
            parent_config,
            pending_writes,
        )

    @_instrument_checkpoint_stream("list")
    async def alist(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        """按过滤与分页约束异步列出检查点。

        参数:
            `config`：显式运行配置。
            `filter`：沿用签名中 `dict[str, Any] | None` 类型约束的输入。
            `before`：分页游标上界。
            `limit`：结果数量上限。

        返回:
            `AsyncIterator[CheckpointTuple]`，内容保持现有调用方契约。

        异常:
            `ValueError, PermissionError`：输入、状态或下游结果不满足现有约束时抛出。

        副作用:
            可能按照既有键空间读写 Redis 中的 Agent 协调状态。

        不变量:
            检查点必须绑定既有运行身份，恢复不得跨项目或跨 revision。"""
        if config is None:
            raise ValueError("scope-bound checkpoint listing requires config")
        values = self._validated_config(config, require_checkpoint=False)
        if limit is not None and limit < 1:
            return
        checkpoint_ids = [
            self._text(item)
            for item in await self.redis.zrevrange(
                self._timeline_key(values["thread_id"], values["checkpoint_ns"]),
                0,
                -1,
            )
        ]
        if before is not None:
            before_values = self._validated_config(before, require_checkpoint=True)
            if (
                before_values["thread_id"] != values["thread_id"]
                or before_values["checkpoint_ns"] != values["checkpoint_ns"]
            ):
                raise PermissionError("before checkpoint scope does not match")
            try:
                checkpoint_ids = checkpoint_ids[
                    checkpoint_ids.index(before_values["checkpoint_id"]) + 1 :
                ]
            except ValueError:
                checkpoint_ids = []
        yielded = 0
        for checkpoint_id in checkpoint_ids:
            item = await self.aget_tuple(
                self.runtime_config(
                    values["thread_id"],
                    checkpoint_id=checkpoint_id,
                    checkpoint_ns=values["checkpoint_ns"],
                )
            )
            if item is None:
                continue
            if filter and any(item.metadata.get(key) != value for key, value in filter.items()):
                continue
            yield item
            yielded += 1
            if limit is not None and yielded >= limit:
                break

    @_instrument_checkpoint("delete_thread")
    async def adelete_thread(self, thread_id: str) -> None:
        """异步删除指定测试命名空间中的检查点线程数据。

        参数:
            `thread_id`：Agent 运行线程 ID。

        副作用:
            可能按照既有键空间读写 Redis 中的 Agent 协调状态。

        不变量:
            检查点必须绑定既有运行身份，恢复不得跨项目或跨 revision。"""
        self._validate_thread_id(thread_id)
        registry = self._registry_key(thread_id)
        keys = list(await self.redis.smembers(registry))
        decoded = [self._text(item) for item in keys]
        if decoded:
            await self.redis.delete(*decoded)
        await self.redis.delete(registry, self.lease_key(thread_id))
