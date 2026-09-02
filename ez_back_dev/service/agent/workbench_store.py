"""Bounded Redis storage for the local Agent workbench projection."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from service.agent.checkpoint import StrictAgentCheckpointSerializer
from service.agent.coordinator import AgentRedisCoordinator
from service.agent.runtime_contracts import AGENT_GRAPH_VERSION
from service.agent.workbench_contracts import (
    AgentBudgetPreset,
    AgentStepEvidence,
    AgentTimelineEvent,
)


_RESERVE_ACTIVE = """
if redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2], 'NX') then
  return 1
end
return 0
"""

_COMMIT_ACTIVE = """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then
  return 0
end
redis.call('SET', KEYS[1], ARGV[2], 'EX', ARGV[3])
return 1
"""

_RELEASE_ACTIVE = """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then
  return 0
end
return redis.call('DEL', KEYS[1])
"""

_REGISTER_RUN = """
local sequence = redis.call('INCR', KEYS[1])
redis.call('ZADD', KEYS[2], sequence, ARGV[1])
redis.call('EXPIRE', KEYS[1], ARGV[2])
redis.call('EXPIRE', KEYS[2], ARGV[2])
redis.call('SET', KEYS[3], ARGV[3], 'EX', ARGV[2])
return sequence
"""

_APPEND_TIMELINE = """
local existing = redis.call('GET', KEYS[3])
if existing then
  return tonumber(existing)
end
local sequence = redis.call('INCR', KEYS[2])
redis.call('XADD', KEYS[1], tostring(sequence) .. '-0', 'payload', ARGV[1])
redis.call('XTRIM', KEYS[1], 'MAXLEN', '~', ARGV[2])
redis.call('EXPIRE', KEYS[1], ARGV[3])
redis.call('EXPIRE', KEYS[2], ARGV[3])
redis.call('SET', KEYS[3], sequence, 'EX', ARGV[3], 'NX')
return sequence
"""

_ACCEPT_PROGRESS = """
local previous = redis.call('HGET', KEYS[1], ARGV[1])
if previous and tonumber(previous) >= tonumber(ARGV[2]) then
  return 0
end
redis.call('HSET', KEYS[1], ARGV[1], ARGV[2])
redis.call('EXPIRE', KEYS[1], ARGV[3])
return 1
"""


class _RunMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    budget_preset: AgentBudgetPreset
    created_at: datetime
    index_sequence: int = Field(ge=1)


class AgentWorkbenchStore:
    def __init__(self, coordinator: AgentRedisCoordinator) -> None:
        self.coordinator = coordinator
        self.redis = coordinator.redis
        self.ttl = coordinator.settings.state_ttl_seconds
        self.event_ttl = coordinator.settings.event_ttl_seconds
        self.serializer = StrictAgentCheckpointSerializer(
            max_bytes=4 * 1_024 * 1_024,
            max_nodes=50_000,
        )

    def _scope_key(self, kind: str, scope_hash: str) -> str:
        if not scope_hash or len(scope_hash) > 256:
            raise ValueError("scope hash must be bounded")
        return f"{self.coordinator.settings.prefix}:workbench:{kind}:{scope_hash}"

    def _storage_id(self, scope_hash: str, thread_id: str) -> str:
        return self.coordinator.storage_id(
            scope_hash, AGENT_GRAPH_VERSION, thread_id
        )

    def _run_key(self, kind: str, scope_hash: str, thread_id: str) -> str:
        return (
            f"{self.coordinator.settings.prefix}:workbench:{kind}:"
            f"{self._storage_id(scope_hash, thread_id)}"
        )

    @staticmethod
    def _text(value: bytes | str | None) -> str | None:
        if value is None:
            return None
        return value.decode("utf-8") if isinstance(value, bytes) else value

    def _dump(self, value: Any) -> bytes:
        content_type, payload = self.serializer.dumps_typed(value)
        if content_type != "ezllm-safe-json-v1":
            raise ValueError("unexpected workbench serializer content type")
        return payload

    def _load(self, payload: bytes) -> Any:
        return self.serializer.loads_typed(("ezllm-safe-json-v1", payload))

    async def reserve_active(self, scope_hash: str, reservation_id: str) -> bool:
        if not reservation_id or len(reservation_id) > 128:
            raise ValueError("reservation ID must be bounded")
        return bool(
            await self.redis.eval(
                _RESERVE_ACTIVE,
                1,
                self._scope_key("active", scope_hash),
                reservation_id,
                self.ttl,
            )
        )

    async def commit_active(
        self, scope_hash: str, reservation_id: str, thread_id: str
    ) -> bool:
        if not thread_id or len(thread_id) > 128:
            raise ValueError("thread ID must be bounded")
        return bool(
            await self.redis.eval(
                _COMMIT_ACTIVE,
                1,
                self._scope_key("active", scope_hash),
                reservation_id,
                thread_id,
                self.ttl,
            )
        )

    async def release_active(self, scope_hash: str, expected: str) -> bool:
        return bool(
            await self.redis.eval(
                _RELEASE_ACTIVE,
                1,
                self._scope_key("active", scope_hash),
                expected,
            )
        )

    async def active_thread(self, scope_hash: str) -> str | None:
        return self._text(
            await self.redis.get(self._scope_key("active", scope_hash))
        )

    async def register_run(
        self,
        scope_hash: str,
        thread_id: str,
        budget_preset: AgentBudgetPreset | str,
        created_at: datetime,
    ) -> int:
        preset = AgentBudgetPreset(budget_preset)
        sequence_key = self._scope_key("run-sequence", scope_hash)
        index_key = self._scope_key("run-index", scope_hash)
        metadata_key = self._run_key("metadata", scope_hash, thread_id)
        placeholder = _RunMetadata(
            budget_preset=preset,
            created_at=created_at,
            index_sequence=1,
        )
        sequence = int(
            await self.redis.eval(
                _REGISTER_RUN,
                3,
                sequence_key,
                index_key,
                metadata_key,
                thread_id,
                self.ttl,
                self._dump(placeholder.model_dump(mode="json")),
            )
        )
        metadata = placeholder.model_copy(update={"index_sequence": sequence})
        await self.redis.set(metadata_key, self._dump(metadata.model_dump(mode="json")), ex=self.ttl)
        return sequence

    async def run_metadata(
        self, scope_hash: str, thread_id: str
    ) -> _RunMetadata | None:
        payload = await self.redis.get(
            self._run_key("metadata", scope_hash, thread_id)
        )
        if payload is None:
            return None
        return _RunMetadata.model_validate(self._load(payload))

    async def list_run_threads(
        self,
        scope_hash: str,
        *,
        limit: int = 20,
        before: int | None = None,
    ) -> tuple[tuple[str, ...], int | None]:
        if not 1 <= limit <= 50:
            raise ValueError("run list limit must be between 1 and 50")
        maximum: int | str = before - 1 if before is not None else "+inf"
        rows = await self.redis.zrevrangebyscore(
            self._scope_key("run-index", scope_hash),
            maximum,
            "-inf",
            start=0,
            num=limit + 1,
            withscores=True,
        )
        visible = rows[:limit]
        threads = tuple(self._text(member) or "" for member, _ in visible)
        next_cursor = int(visible[-1][1]) if len(rows) > limit and visible else None
        return threads, next_cursor

    async def put_evidence(
        self,
        scope_hash: str,
        thread_id: str,
        evidence: AgentStepEvidence,
    ) -> None:
        key = self._run_key("evidence", scope_hash, thread_id)
        await self.redis.hset(
            key,
            evidence.step_id,
            self._dump(evidence.model_dump(mode="json")),
        )
        await self.redis.expire(key, self.ttl)

    async def get_evidence(
        self, scope_hash: str, thread_id: str
    ) -> tuple[AgentStepEvidence, ...]:
        values = await self.redis.hgetall(
            self._run_key("evidence", scope_hash, thread_id)
        )
        evidence = [
            AgentStepEvidence.model_validate(self._load(payload))
            for payload in values.values()
        ]
        return tuple(sorted(evidence, key=lambda item: item.step_id))

    def _timeline_keys(
        self, scope_hash: str, thread_id: str, event_id: str
    ) -> tuple[str, str, str]:
        storage_id = self._storage_id(scope_hash, thread_id)
        digest = hashlib.sha256(event_id.encode("utf-8")).hexdigest()
        base = f"{self.coordinator.settings.prefix}:workbench"
        return (
            f"{base}:timeline:{storage_id}",
            f"{base}:timeline-sequence:{storage_id}",
            f"{base}:timeline-dedup:{storage_id}:{digest}",
        )

    async def append_timeline_event(
        self,
        scope_hash: str,
        thread_id: str,
        event_id: str,
        payload: dict[str, Any],
    ) -> int:
        if not event_id or len(event_id) > 256:
            raise ValueError("event ID must be bounded")
        timeline, sequence, dedup = self._timeline_keys(
            scope_hash, thread_id, event_id
        )
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return int(
            await self.redis.eval(
                _APPEND_TIMELINE,
                3,
                timeline,
                sequence,
                dedup,
                encoded,
                self.coordinator.settings.event_max_length,
                self.event_ttl,
            )
        )

    async def replay_timeline(
        self, scope_hash: str, thread_id: str, after_sequence: int
    ) -> tuple[AgentTimelineEvent, ...]:
        if after_sequence < 0:
            raise ValueError("after_sequence cannot be negative")
        timeline = self._timeline_keys(scope_hash, thread_id, "read")[0]
        rows = await self.redis.xrange(
            timeline,
            min=f"({after_sequence}-0",
            max="+",
            count=self.coordinator.settings.event_max_length,
        )
        events: list[AgentTimelineEvent] = []
        for stream_id, fields in rows:
            identifier = self._text(stream_id) or "0-0"
            raw = fields.get(b"payload", fields.get("payload"))
            if raw is None:
                continue
            payload = json.loads(self._text(raw) or "{}")
            payload["sequence"] = int(identifier.split("-", 1)[0])
            events.append(AgentTimelineEvent.model_validate(payload))
        return tuple(events)

    async def accept_progress(
        self,
        scope_hash: str,
        thread_id: str,
        step_stage: str,
        bucket: int,
    ) -> bool:
        if not step_stage or len(step_stage) > 256 or not 0 <= bucket <= 100:
            raise ValueError("progress identity or bucket is invalid")
        return bool(
            await self.redis.eval(
                _ACCEPT_PROGRESS,
                1,
                self._run_key("progress", scope_hash, thread_id),
                step_stage,
                bucket,
                self.event_ttl,
            )
        )

    async def timeline_bounds(
        self, scope_hash: str, thread_id: str
    ) -> tuple[int, int] | None:
        timeline = self._timeline_keys(scope_hash, thread_id, "read")[0]
        first = await self.redis.xrange(timeline, min="-", max="+", count=1)
        last = await self.redis.xrevrange(timeline, max="+", min="-", count=1)
        if not first or not last:
            return None
        first_id = self._text(first[0][0]) or "0-0"
        last_id = self._text(last[0][0]) or "0-0"
        return int(first_id.split("-", 1)[0]), int(last_id.split("-", 1)[0])

    async def heartbeat_worker(
        self, consumer: str, *, ttl_seconds: int = 30
    ) -> None:
        if not consumer or len(consumer) > 64 or ttl_seconds <= 0:
            raise ValueError("worker heartbeat values are invalid")
        await self.redis.set(
            f"{self.coordinator.settings.prefix}:workbench:worker:{consumer}",
            "1",
            ex=ttl_seconds,
        )
        workers = f"{self.coordinator.settings.prefix}:workbench:workers"
        await self.redis.sadd(workers, consumer)
        await self.redis.expire(workers, self.ttl)

    async def worker_available(self) -> bool:
        workers = f"{self.coordinator.settings.prefix}:workbench:workers"
        members = await self.redis.smembers(workers)
        for member in members:
            consumer = self._text(member)
            if consumer and await self.redis.exists(
                f"{self.coordinator.settings.prefix}:workbench:worker:{consumer}"
            ):
                return True
        return False
