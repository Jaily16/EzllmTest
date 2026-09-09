"""离线回归的硬边界：禁止网络连接及读取工作树中的受保护资料。"""
import os
import sys
import socket
from pathlib import Path
import pytest

_REAL_ROOT = Path(__file__).resolve().parents[2]
_PROTECTED = [_REAL_ROOT / "backend/static/projects", _REAL_ROOT / "observability/data"]
# 阻止离线用例访问真实网络和受保护资料；仅放行 Windows asyncio 内部 socketpair 的临时回环。
def _guard(event, args):
    if event in {"socket.connect", "socket.bind"}:
        # Windows asyncio 用标准库 socketpair 唤醒 IO 线程；仅放行该函数的临时回环。
        caller = sys._getframe(1).f_code
        address = args[1]
        internal_pair = (caller is getattr(socket.socketpair, "__code__", None)
            and address[0] in {"127.0.0.1", "::1"} and address[1] not in {8140,8180,8230,8231})
        if not internal_pair:
            raise RuntimeError("offline_network_forbidden")
    if event in {"open", "os.listdir", "os.scandir"} and isinstance(args[0], (str, bytes, os.PathLike)):
        path = Path(os.fsdecode(args[0])).absolute()
        if path.is_relative_to(_REAL_ROOT) and (path.name == ".env" or any(path == p or path.is_relative_to(p) for p in _PROTECTED)):
            raise RuntimeError("protected_asset_access_forbidden")
sys.addaudithook(_guard)

@pytest.fixture(autouse=True)
def isolated_runtime(monkeypatch, tmp_path):
    """人工配置覆盖进程快照，恢复测试前的配置且不发现本地文件。"""
    from ezllmtest.platform import configuration
    previous_values, previous_root = configuration._values, configuration._repo_root
    for name in tuple(os.environ):
        if name.startswith(("AGENT_", "DATABASE_", "EZLLMTEST_", "OBSERVABILITY_", "OTEL_", "LANGSMITH_", "LANGCHAIN_")) or any(x in name for x in ("TOKEN", "SECRET", "PASSWORD", "API_KEY")):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "true")
    configuration.install({"DATABASE_URL": "sqlite:///:memory:", "AGENT_TELEMETRY_ENABLED": "false"}, tmp_path)
    yield
    configuration._values, configuration._repo_root = previous_values, previous_root
