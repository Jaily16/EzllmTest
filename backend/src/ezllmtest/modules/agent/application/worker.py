# 消费 Redis 命令并管理运行任务；确认、取消和关闭连接都受 worker 生命周期约束。
"""Redis Stream worker for internal Aspect 3 Agent commands."""

from __future__ import annotations

import argparse
import asyncio
import os
from ezllmtest.platform import configuration as runtime_values
import re
import sys

from ezllmtest.modules.agent.application.runtime import AgentRuntimeService
from ezllmtest.platform.telemetry.agent_telemetry import get_agent_telemetry
from ezllmtest.platform.telemetry.logging import build_safe_logger


_CONSUMER = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_LOGGER = build_safe_logger("ezllm-agent-worker")


class AgentCommandWorker:
    def __init__(
        self,
        service: AgentRuntimeService,
        *,
        group: str = "ezllm-agent-workers",
        consumer: str,
    ) -> None:
        """绑定运行服务与协调器，并验证消费组和 consumer 标识；该类仅用于普通消费模式。"""
        if not _CONSUMER.fullmatch(consumer):
            raise ValueError("worker consumer name is invalid")
        if not _CONSUMER.fullmatch(group):
            raise ValueError("worker group name is invalid")
        self.service = service
        self.coordinator = service.coordinator
        self.group = group
        self.consumer = consumer

    async def run_once(self, *, block_ms: int = 1_000) -> bool:
        """建立消费组并认领一批命令，处理期间刷新普通 worker 心跳；命令确认与异常路径由本轮执行结果决定。"""
        workbench_store = getattr(self.service, "workbench_store", None)
        heartbeat_ttl = 30
        if workbench_store is not None:
            raw_ttl = runtime_values.get(
                "AGENT_WORKER_HEARTBEAT_TTL_SECONDS", "30"
            )
            try:
                heartbeat_ttl = int(raw_ttl)
            except ValueError as exc:
                raise ValueError(
                    "AGENT_WORKER_HEARTBEAT_TTL_SECONDS must be an integer"
                ) from exc
            if not 1 <= heartbeat_ttl <= 300:
                raise ValueError(
                    "AGENT_WORKER_HEARTBEAT_TTL_SECONDS must be between 1 and 300"
                )
            await workbench_store.heartbeat_worker(
                self.consumer, ttl_seconds=heartbeat_ttl
            )
        await self.coordinator.ensure_command_group(self.group)
        commands = await self.coordinator.claim_commands(
            self.group, self.consumer, count=1
        )
        source = "reclaimed" if commands else "queued"
        if not commands:
            commands = await self.coordinator.read_commands(
                self.group,
                self.consumer,
                count=1,
                block_ms=block_ms,
            )
        if not commands:
            return False
        command = commands[0]
        get_agent_telemetry().counter(
            "ezllm.agent.commands.received",
            labels={
                "command_kind": getattr(command, "kind", "unknown"),
                "status": source,
            },
        )
        heartbeat_stop = asyncio.Event()

        async def keep_heartbeat() -> None:
            """消费执行期间按配置刷新普通 worker 存活标记；与独立 no-consume 验收键分离。"""
            if workbench_store is None:
                return
            interval = max(1.0, heartbeat_ttl / 3)
            while True:
                try:
                    await asyncio.wait_for(heartbeat_stop.wait(), timeout=interval)
                    return
                except TimeoutError:
                    await workbench_store.heartbeat_worker(
                        self.consumer, ttl_seconds=heartbeat_ttl
                    )

        heartbeat_task = asyncio.create_task(keep_heartbeat())
        try:
            await self.service.process_command(command, owner=self.consumer)
        finally:
            heartbeat_stop.set()
            await heartbeat_task
        await self.coordinator.ack_command(self.group, command.stream_id)
        _LOGGER.info(
            "agent.command.acknowledged",
            status="success",
        )
        return True

    async def run_forever(self) -> None:
        """连续调用单轮消费，取消和异常向外传播，由入口统一关闭连接。"""
        while True:
            await self.run_once(block_ms=1_000)
