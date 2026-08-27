import base64
import asyncio
import dataclasses
import json
import math
import os
import uuid

import pytest
from pydantic import BaseModel

from langgraph.types import Interrupt, Send
from service.agentCheckpoint import (
    AsyncAgentRedisCheckpointSaver,
    CHECKPOINT_CONTENT_TYPE,
    StrictAgentCheckpointSerializer,
    UnsafeCheckpointDataError,
    derive_agent_scope_hash,
    derive_storage_thread_id,
)
from service.agentContracts import TrustedProjectScope


def _interrupt(value):
    fields = {field.name for field in dataclasses.fields(Interrupt)}
    kwargs = {"value": value}
    if "id" in fields:
        kwargs["id"] = "interrupt-1"
    return Interrupt(**kwargs)


def test_strict_serializer_round_trips_only_explicit_safe_types():
    serializer = StrictAgentCheckpointSerializer()
    value = {
        "none": None,
        "boolean": True,
        "integer": 7,
        "float": 1.25,
        "text": "safe",
        "bytes": b"abc",
        "bytearray": bytearray(b"def"),
        "list": [1, "two"],
        "tuple": (3, "four"),
        "interrupt": _interrupt({"approval_request": "step-1"}),
        "send": Send("execute", {"step": 1}),
    }

    encoded = serializer.dumps_typed(value)
    decoded = serializer.loads_typed(encoded)

    assert encoded[0] == CHECKPOINT_CONTENT_TYPE
    assert decoded["none"] is None
    assert decoded["bytes"] == b"abc"
    assert decoded["bytearray"] == bytearray(b"def")
    assert decoded["tuple"] == (3, "four")
    assert isinstance(decoded["interrupt"], Interrupt)
    assert decoded["interrupt"].value == {"approval_request": "step-1"}
    assert isinstance(decoded["send"], Send)
    assert decoded["send"].node == "execute"
    assert decoded["send"].arg == {"step": 1}


@pytest.mark.parametrize(
    "value",
    [
        {"lc": 2, "type": "constructor", "id": ["os", "system"]},
        {"nested": {"lc": 1, "type": "constructor", "id": ["x", "Y"]}},
        {"prompt": "hidden"},
        {"reasoning": "hidden"},
        {"api_key": "secret"},
        {"value": {1: "non-string-key"}},
        {"bad": float("nan")},
        {"bad": float("inf")},
        {"bad": {1, 2}},
    ],
)
def test_strict_serializer_rejects_forbidden_or_ambiguous_values(value):
    serializer = StrictAgentCheckpointSerializer()
    with pytest.raises(UnsafeCheckpointDataError):
        serializer.dumps_typed(value)


def test_strict_serializer_never_constructs_arbitrary_dataclasses():
    side_effects = []

    @dataclasses.dataclass
    class Evil:
        value: int

        def __post_init__(self):
            side_effects.append(self.value)

    serializer = StrictAgentCheckpointSerializer()
    side_effects.clear()

    with pytest.raises(UnsafeCheckpointDataError):
        serializer.dumps_typed(Evil(7))

    assert side_effects == [7]
    side_effects.clear()

    malicious_ast = {
        "schema": 1,
        "root": {
            "t": "dict",
            "v": [
                ["lc", {"t": "int", "v": 2}],
                ["type", {"t": "str", "v": "constructor"}],
                [
                    "id",
                    {
                        "t": "list",
                        "v": [
                            {"t": "str", "v": "__main__"},
                            {"t": "str", "v": "Evil"},
                        ],
                    },
                ],
            ],
        },
    }
    with pytest.raises(UnsafeCheckpointDataError):
        serializer.loads_typed(
            (CHECKPOINT_CONTENT_TYPE, json.dumps(malicious_ast).encode("utf-8"))
        )

    assert side_effects == []


class _PydanticState(BaseModel):
    value: int


def test_strict_serializer_requires_pydantic_to_be_dumped_first():
    with pytest.raises(UnsafeCheckpointDataError):
        StrictAgentCheckpointSerializer().dumps_typed(_PydanticState(value=1))


@pytest.mark.parametrize("content_type", ["pickle", "msgpack", "json", "unknown"])
def test_strict_serializer_rejects_all_unapproved_content_types(content_type):
    with pytest.raises(UnsafeCheckpointDataError):
        StrictAgentCheckpointSerializer().loads_typed((content_type, b"{}"))


def test_strict_serializer_rejects_excessive_depth_and_size():
    serializer = StrictAgentCheckpointSerializer(max_depth=8, max_bytes=256)
    nested = "leaf"
    for _ in range(10):
        nested = [nested]

    with pytest.raises(UnsafeCheckpointDataError):
        serializer.dumps_typed(nested)
    with pytest.raises(UnsafeCheckpointDataError):
        serializer.dumps_typed("x" * 300)


def test_strict_serializer_emits_deterministic_json_without_constructor_markers():
    serializer = StrictAgentCheckpointSerializer()
    first = serializer.dumps_typed({"z": 1, "a": b"x"})
    second = serializer.dumps_typed({"a": b"x", "z": 1})

    assert first == second
    payload = first[1].decode("utf-8")
    assert "pickle" not in payload.lower()
    assert "constructor" not in payload.lower()
    assert base64.b64encode(b"x").decode("ascii") in payload
    assert math.isfinite(float(1.0))


def test_storage_thread_identity_is_project_and_graph_scoped():
    first = TrustedProjectScope(
        project_id="project-a", actor_id="actor", scope_version="1"
    )
    second = first.model_copy(update={"project_id": "project-b"})
    first_hash = derive_agent_scope_hash(first, "iteration4-aspect3-v1")
    second_hash = derive_agent_scope_hash(second, "iteration4-aspect3-v1")

    assert len(first_hash) == 64
    assert first_hash != second_hash
    assert derive_storage_thread_id(first_hash, "run-1") == derive_storage_thread_id(
        first_hash, "run-1"
    )
    assert derive_storage_thread_id(first_hash, "run-1") != derive_storage_thread_id(
        second_hash, "run-1"
    )


def test_safe_redis_saver_checkpoint_and_pending_write_round_trip():
    redis_url = os.getenv("EZLLM_TEST_REDIS_URL")
    if not redis_url:
        pytest.skip("local Redis integration gate is not enabled")

    async def scenario():
        from redis.asyncio import Redis

        client = Redis.from_url(redis_url, decode_responses=False)
        scope = TrustedProjectScope(
            project_id="project-a", actor_id="actor", scope_version="1"
        )
        graph_version = "iteration4-aspect3-v1"
        scope_hash = derive_agent_scope_hash(scope, graph_version)
        thread_id = derive_storage_thread_id(scope_hash, "run-checkpoint")
        prefix = f"ezllm:test:{uuid.uuid4().hex}"
        saver = AsyncAgentRedisCheckpointSaver(
            client,
            scope_hash=scope_hash,
            graph_version=graph_version,
            lease_owner="worker-a",
            fence_token=7,
            prefix=prefix,
            ttl_seconds=60,
        )
        config = saver.runtime_config(thread_id)
        await client.set(saver.lease_key(thread_id), b"worker-a:7", ex=60)
        checkpoint = {
            "v": 2,
            "id": "00000000-0000-6000-8000-000000000001",
            "ts": "2026-08-27T00:00:00+00:00",
            "channel_values": {"state": {"status": "planning"}},
            "channel_versions": {"state": "1"},
            "versions_seen": {"__input__": {}},
            "pending_sends": [],
            "updated_channels": ["state"],
        }
        saved = await saver.aput(config, checkpoint, {"source": "input"}, {})
        await saver.aput_writes(
            saved,
            [("agent_result", {"ok": True})],
            "task-1",
            "path-1",
        )

        loaded = await saver.aget_tuple(saved)
        assert loaded is not None
        assert loaded.checkpoint["channel_values"] == checkpoint["channel_values"]
        assert loaded.metadata == {"source": "input"}
        assert loaded.pending_writes == [("task-1", "agent_result", {"ok": True})]
        assert await client.ttl(saver.checkpoint_key(saved)) > 0

        listed = [item async for item in saver.alist(config, limit=10)]
        assert [item.config["configurable"]["checkpoint_id"] for item in listed] == [
            checkpoint["id"]
        ]

        await saver.adelete_thread(thread_id)
        assert await saver.aget_tuple(saved) is None
        await client.aclose()

    asyncio.run(scenario())


def test_safe_redis_saver_rejects_stale_fence_before_writing():
    redis_url = os.getenv("EZLLM_TEST_REDIS_URL")
    if not redis_url:
        pytest.skip("local Redis integration gate is not enabled")

    async def scenario():
        from redis.asyncio import Redis

        client = Redis.from_url(redis_url, decode_responses=False)
        scope = TrustedProjectScope(
            project_id="project-a", actor_id="actor", scope_version="1"
        )
        graph_version = "iteration4-aspect3-v1"
        scope_hash = derive_agent_scope_hash(scope, graph_version)
        thread_id = derive_storage_thread_id(scope_hash, "run-fence")
        saver = AsyncAgentRedisCheckpointSaver(
            client,
            scope_hash=scope_hash,
            graph_version=graph_version,
            lease_owner="worker-old",
            fence_token=1,
            prefix=f"ezllm:test:{uuid.uuid4().hex}",
            ttl_seconds=60,
        )
        await client.set(saver.lease_key(thread_id), b"worker-new:2", ex=60)
        checkpoint = {
            "v": 2,
            "id": "00000000-0000-6000-8000-000000000002",
            "ts": "2026-08-27T00:00:00+00:00",
            "channel_values": {},
            "channel_versions": {},
            "versions_seen": {},
            "pending_sends": [],
            "updated_channels": None,
        }
        with pytest.raises(PermissionError, match="lease fence"):
            await saver.aput(saver.runtime_config(thread_id), checkpoint, {}, {})
        await saver.adelete_thread(thread_id)
        await client.aclose()

    asyncio.run(scenario())
