"""人工 IPC 验证：不启动 HTTP，不读取真实配置，不输出测试 token。"""

import hmac
import time
import pytest

from ezllmtest.platform.security.session_token import SessionTokenProvider, SessionTokenServer, TokenIPCError


def test_session_exchange_rotation_and_close(tmp_path):
    """同会话可取凭据；实例冲突拒绝；重启使旧凭据失效；关闭后无通道。"""
    endpoint = "http://127.0.0.1:49990"
    server = SessionTokenServer(tmp_path, endpoint)
    client = SessionTokenProvider(tmp_path, endpoint)
    server.start()
    try:
        received = client.get()
        matched = bool(received) and hmac.compare_digest(received, server.token)
        assert matched, "same-session credential exchange failed"
        competing = SessionTokenServer(tmp_path, endpoint)
        with pytest.raises(TokenIPCError, match="telemetry_ipc:channel_unavailable"):
            competing.start()
    finally:
        server.close()
    client.invalidate()
    time.sleep(1.05)
    missing = not client.get()
    assert missing, "closed channel must not issue credentials"
    replacement = SessionTokenServer(tmp_path, endpoint)
    replacement.start()
    try:
        time.sleep(1.05)
        updated = client.get()
        changed = bool(updated) and not hmac.compare_digest(received, updated)
        assert changed, "restart must rotate the in-memory credential"
    finally:
        replacement.close()

def test_cross_process_and_scope_isolation(tmp_path):
    """独立 Python 子进程可获取同会话凭据；不同根和伪造协议身份不能获取。"""
    import subprocess
    import sys
    import os
    endpoint = "http://127.0.0.1:49989"
    server = SessionTokenServer(tmp_path, endpoint)
    server.start()
    try:
        code = "from pathlib import Path; import sys; from ezllmtest.platform.security.session_token import SessionTokenProvider; print(bool(SessionTokenProvider(Path(sys.argv[1]),sys.argv[2]).get()))"
        result = subprocess.run([sys.executable, "-B", "-c", code, str(tmp_path), endpoint],
            capture_output=True, text=True, timeout=10, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        assert result.returncode == 0 and result.stdout.strip() == "True"
        assert not SessionTokenProvider(tmp_path/"other-root", endpoint).get()
        assert not SessionTokenProvider(tmp_path, "http://127.0.0.1:49988").get()
        altered = SessionTokenProvider(tmp_path, endpoint)
        altered.scope = "incorrect-protocol-identity"
        assert not altered.get()
    finally:
        server.close()

def test_idle_pipe_shutdown_is_bounded(tmp_path):
    """没有客户端时也可取消正在等待的连接，不留下 IPC 线程。"""
    server=SessionTokenServer(tmp_path,"http://127.0.0.1:49987")
    server.start()
    begin=time.monotonic()
    server.close()
    assert time.monotonic()-begin < 3
