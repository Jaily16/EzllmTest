"""不消费验收：端口仅允许连接检查和独立 TTL 心跳，不暴露队列能力。"""
from __future__ import annotations

import asyncio
import re
from typing import Protocol


class WorkerProbe(Protocol):
    """验收所需最小能力；与正常 worker 注册和命令消费分离。"""

    # 验证 Redis 连接是否可用；协议不暴露任何队列或模型能力。
    async def ping(self) -> bool: ...
    # 刷新独立验收键的有界 TTL，不注册正常 worker，也不改变业务就绪判断。
    async def heartbeat(self, ttl_seconds: int) -> None: ...
    # 关闭本次验收持有的连接，不删除其他 worker 或队列键。
    async def close(self) -> None: ...


def validated_probe(consumer: str, raw_ttl: str) -> int:
    """约束 consumer 的字符与长度，并将 TTL 限制在 1–300 秒，防止验收键无法自然过期。"""
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", consumer):
        raise ValueError("worker consumer name is invalid")
    try:
        ttl = int(raw_ttl)
    except (ValueError, TypeError) as exc:
        raise ValueError("AGENT_WORKER_HEARTBEAT_TTL_SECONDS must be an integer") from exc
    if not 1 <= ttl <= 300:
        raise ValueError("AGENT_WORKER_HEARTBEAT_TTL_SECONDS must be between 1 and 300")
    return ttl


async def run_probe(probe: WorkerProbe, *, ttl_seconds: int, once: bool) -> None:
    """每轮先 PING 再刷新独立心跳；单次模式立即返回，持续模式按 TTL 的三分之一等待，取消由调用方关闭连接。"""
    if not 1 <= ttl_seconds <= 300:
        raise ValueError("worker probe TTL is invalid")
    while True:
        if not await probe.ping():
            raise ConnectionError("worker probe Redis unavailable")
        await probe.heartbeat(ttl_seconds)
        if once:
            return
        await asyncio.sleep(ttl_seconds / 3)
