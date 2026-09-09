"""不消费验收的副作用边界、CLI 分流与正常消费回归。"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
import pytest

from ezllmtest.bootstrap import app_factory, worker
from ezllmtest.modules.agent.application.worker_probe import run_probe, validated_probe
from ezllmtest.modules.agent.infrastructure.worker_probe import RedisWorkerProbe
from ezllmtest.platform import configuration


class MemoryRedis:
    """仅提供批准的 Redis 操作；任何队列或集合访问都会直接失败。"""
    # 初始化人工时钟和键表，用可控时间验证验收心跳的 TTL。
    def __init__(self):
        self.now = 0
        self.entries = {}
        self.closed = False

    # 模拟 Redis 连接成功，不执行网络访问。
    async def ping(self):
        return True

    # 仅在内存记录验收心跳与到期时间，供 TTL 过期断言使用。
    async def set(self, key, value, *, ex):
        self.entries[key] = (value, self.now + ex)

    # 记录人工连接已关闭，验证 worker 正常退出会释放连接。
    async def aclose(self):
        self.closed = True

    # 对任何未获准的 Redis 方法立即报错，证明不消费模式没有碰触消费组或队列。
    def __getattr__(self, name):
        raise AssertionError("forbidden Redis operation: " + name)


# 验证 no-consume 仅写独立 TTL 键，且不会使普通 worker 被判为可用。
def test_probe_uses_only_isolated_expiring_key(tmp_path):
    configuration.install({"AGENT_REDIS_PREFIX": "offline:probe"}, tmp_path)
    redis = MemoryRedis()
    probe = RedisWorkerProbe("aspect3-test", redis=redis)
    asyncio.run(run_probe(probe, ttl_seconds=3, once=True))
    assert redis.entries == {"offline:probe:workbench:acceptance-worker:aspect3-test": ("no-consume", 3)}
    assert "offline:probe:workbench:workers" not in redis.entries
    redis.now = 4
    assert not any(expiry > redis.now for _, expiry in redis.entries.values())
    asyncio.run(probe.close())
    assert redis.closed


# 以受控时钟验证持续验收刷新和取消，禁止进入正常消费循环。
def test_continuous_probe_refresh_and_cancel(monkeypatch):
    probe = SimpleNamespace(ping=AsyncMock(return_value=True), heartbeat=AsyncMock())
    sleep = AsyncMock(side_effect=[None, asyncio.CancelledError()])
    monkeypatch.setattr("ezllmtest.modules.agent.application.worker_probe.asyncio.sleep", sleep)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run_probe(probe, ttl_seconds=6, once=False))
    assert probe.heartbeat.await_count == 2
    assert [c.args for c in sleep.await_args_list] == [(2.0,), (2.0,)]


# 覆盖 consumer 和 TTL 非法值，确认在 Redis 副作用前拒绝输入。
@pytest.mark.parametrize("consumer,ttl", [("bad/name", "30"), ("", "30"), ("ok", "0"), ("ok", "301"), ("ok", "bad")])
def test_invalid_probe_configuration(consumer, ttl):
    with pytest.raises(ValueError):
        validated_probe(consumer, ttl)


# 模拟 PING 失败，证明未刷新心跳或调用任何队列能力。
def test_connection_failure_never_writes():
    probe = SimpleNamespace(ping=AsyncMock(return_value=False), heartbeat=AsyncMock())
    with pytest.raises(ConnectionError):
        asyncio.run(run_probe(probe, ttl_seconds=30, once=True))
    probe.heartbeat.assert_not_awaited()


# 模拟验收成功、取消或失败，验证连接关闭和错误输出脱敏。
@pytest.mark.parametrize("error,expected", [(ConnectionError("synthetic secret"), 1), (asyncio.CancelledError(), 130)])
def test_entrypoint_closes_probe_and_sanitizes(monkeypatch, capsys, error, expected):
    probe = SimpleNamespace(ping=AsyncMock(side_effect=error), heartbeat=AsyncMock(), close=AsyncMock())
    monkeypatch.setattr("ezllmtest.modules.agent.infrastructure.worker_probe.RedisWorkerProbe", lambda _: probe)
    monkeypatch.setattr("ezllmtest.bootstrap.agent.build_default_runtime_service", Mock(side_effect=AssertionError("model assembly forbidden")))
    result = asyncio.run(worker._run(SimpleNamespace(no_consume=True, once=True, consumer="probe")))
    assert result == expected
    probe.close.assert_awaited_once()
    probe.heartbeat.assert_not_awaited()
    output = capsys.readouterr()
    assert "synthetic secret" not in output.out + output.err


# 用会报错的装配替身证明 --no-consume 不构造模型执行服务。
def test_cli_skips_application_assembly(monkeypatch):
    config = object()
    load = Mock(return_value=config)
    monkeypatch.setattr(app_factory, "load_process", load)
    activate = Mock()
    monkeypatch.setattr(app_factory, "activate", activate)
    monkeypatch.setattr(app_factory, "create_app", Mock(side_effect=AssertionError("assembly forbidden")))
    run = AsyncMock(return_value=0)
    monkeypatch.setattr(worker, "_run", run)
    assert app_factory.main("worker", ["--repo-root", "synthetic", "--backend-env-file", "backend", "--observability-env-file", "observability", "--consumer", "probe", "--once", "--no-consume"]) == 0
    activate.assert_called_once_with(config)
    args = run.await_args.args[0]
    assert args.no_consume and args.once
    assert load.call_args.kwargs["frontend"] is None
    with pytest.raises(SystemExit):
        app_factory.main("product-api", ["--repo-root", "synthetic", "--backend-env-file", "backend", "--frontend-env-file", "frontend", "--no-consume"])
    assert load.call_count == 1


# 验证不带新参数时仍使用既有普通消费路径，不把验收模式误设为默认。
def test_normal_worker_still_consumes(monkeypatch):
    service = SimpleNamespace(coordinator=SimpleNamespace(aclose=AsyncMock()))
    build = Mock(return_value=service)
    monkeypatch.setattr("ezllmtest.bootstrap.agent.build_default_runtime_service", build)
    command_worker = SimpleNamespace(run_once=AsyncMock(), run_forever=AsyncMock())
    monkeypatch.setattr("ezllmtest.modules.agent.application.worker.AgentCommandWorker", lambda *a, **kw: command_worker)
    assert asyncio.run(worker._run(SimpleNamespace(no_consume=False, once=True, consumer="normal"))) == 0
    build.assert_called_once()
    command_worker.run_once.assert_awaited_once()
    command_worker.run_forever.assert_not_awaited()
    service.coordinator.aclose.assert_awaited_once()


# 模拟关闭失败，确认只输出稳定类别而不泄露连接异常细节。
def test_probe_close_failure_is_sanitized(monkeypatch, capsys):
    probe = SimpleNamespace(ping=AsyncMock(return_value=True), heartbeat=AsyncMock(), close=AsyncMock(side_effect=ConnectionError("synthetic secret")))
    monkeypatch.setattr("ezllmtest.modules.agent.infrastructure.worker_probe.RedisWorkerProbe", lambda _: probe)
    assert asyncio.run(worker._run(SimpleNamespace(no_consume=True, once=True, consumer="probe"))) == 1
    output = capsys.readouterr()
    assert "close_failed" in output.err
    assert "synthetic secret" not in output.out + output.err
