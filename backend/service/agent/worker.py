"""Redis Stream worker for internal Aspect 3 Agent commands."""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys

from service.agent.factory import build_default_runtime_service
from service.agent.runtime import AgentRuntimeService
from infrastructure.observability.agent_telemetry import get_agent_telemetry
from infrastructure.observability.logging import build_safe_logger


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
        """初始化实例并保存后续操作所需的依赖与状态。

        参数:
            `service`：沿用签名中 `AgentRuntimeService` 类型约束的输入。
            `group`：沿用签名中 `str` 类型约束的输入。
            `consumer`：沿用签名中 `str` 类型约束的输入。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        if not _CONSUMER.fullmatch(consumer):
            raise ValueError("worker consumer name is invalid")
        if not _CONSUMER.fullmatch(group):
            raise ValueError("worker group name is invalid")
        self.service = service
        self.coordinator = service.coordinator
        self.group = group
        self.consumer = consumer

    async def run_once(self, *, block_ms: int = 1_000) -> bool:
        """执行ONCE，并遵循现有调用契约。

        参数:
            `block_ms`：沿用签名中 `int` 类型约束的输入。

        返回:
            `bool`，内容保持现有调用方契约。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        workbench_store = getattr(self.service, "workbench_store", None)
        heartbeat_ttl = 30
        if workbench_store is not None:
            raw_ttl = os.environ.get(
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
            """处理KEEP心跳，并保持 `AgentCommandWorker` 的现有状态约束。"""
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
        """执行forever，并遵循现有调用契约。"""
        while True:
            await self.run_once(block_ms=1_000)


def build_parser() -> argparse.ArgumentParser:
    """构建当前命令行入口的参数解析器。"""
    parser = argparse.ArgumentParser(description="EzLLM internal Agent worker")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--consumer", required=True)
    return parser


async def _run(args: argparse.Namespace) -> int:
    """执行当前组件封装的单次内部任务。

    参数:
        `args`：沿用签名中 `argparse.Namespace` 类型约束的输入。

    返回:
        `int`，内容保持现有调用方契约。"""
    service = build_default_runtime_service()
    group = os.environ.get("AGENT_WORKER_GROUP", "ezllm-agent-workers")
    worker = AgentCommandWorker(
        service, group=group, consumer=args.consumer
    )
    try:
        if args.once:
            await worker.run_once()
        else:
            await worker.run_forever()
        return 0
    except (KeyboardInterrupt, asyncio.CancelledError):
        return 130
    except Exception:
        # Do not print tracebacks, Redis URLs, project data, or provider errors.
        print("Agent worker stopped after a safe execution error", file=sys.stderr)
        return 1
    finally:
        await service.coordinator.aclose()


def main(argv: list[str] | None = None) -> int:
    """解析命令行参数并执行当前模块的本地入口。"""
    args = build_parser().parse_args(argv)
    return asyncio.run(_run(args))
