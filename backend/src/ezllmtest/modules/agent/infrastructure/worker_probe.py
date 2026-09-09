"""验收 Redis adapter：不创建消费组，不注册为正常可用 worker。"""
from redis.asyncio import Redis
from ezllmtest.platform import configuration


class RedisWorkerProbe:
    """连接使用角色配置；单独的验收键不会匹配正常 worker 集合。"""

    # 为验收建立带超时的 Redis 客户端，键名使用独立 acceptance-worker 命名空间，避免冒充可消费 worker。
    def __init__(self, consumer: str, *, redis=None) -> None:
        self.redis = redis if redis is not None else Redis.from_url(
            configuration.get("AGENT_REDIS_URL"),
            socket_connect_timeout=3, socket_timeout=3,
        )
        self.key = f"{configuration.get('AGENT_REDIS_PREFIX')}:workbench:acceptance-worker:{consumer}"

    async def ping(self) -> bool:
        """只发送 Redis PING，不探测消费组或读取命令流。"""
        return bool(await self.redis.ping())

    async def heartbeat(self, ttl_seconds: int) -> None:
        """仅写入本验收 consumer 的 no-consume 标记并设置过期时间，不加入正常 worker 集合。"""
        await self.redis.set(self.key, "no-consume", ex=ttl_seconds)

    async def close(self) -> None:
        """释放本 adapter 的异步 Redis 客户端；验收心跳靠 TTL 自然消失。"""
        await self.redis.aclose()
