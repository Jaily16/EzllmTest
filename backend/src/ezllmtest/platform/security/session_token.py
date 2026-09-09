"""当前 Windows 登录会话内的凭据交接；token 只存在于内存和受限管道中。"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import threading
import time
from pathlib import Path

if os.name == "nt":
    from pywintypes import error as Win32Error
else:
    class Win32Error(Exception):
        """非 Windows 平台的异常类型占位，不提供 IPC 实现。"""


class TokenIPCError(RuntimeError):
    """可安全展示的 IPC 错误，不包含系统异常正文或凭据。"""

_PROVIDER = None
_MAX_MESSAGE = 2048


def _windows():
    """仅在 Windows 延迟导入 pywin32；其他平台明确拒绝会话管道共享，不能降级为无鉴权传输。"""
    if os.name != "nt":
        raise RuntimeError("telemetry_ipc:windows_required")
    import pywintypes
    import win32api
    import win32con
    import win32event
    import win32file
    import win32pipe
    import win32security
    return pywintypes, win32api, win32con, win32event, win32file, win32pipe, win32security


def _identity():
    """读取当前进程的用户 SID 与登录会话 SID，并立即关闭访问令牌句柄；用于隔离同机不同会话。"""
    _, api, con, _, _, _, security = _windows()
    token = security.OpenProcessToken(api.GetCurrentProcess(), con.TOKEN_QUERY)
    try:
        user = security.GetTokenInformation(token, security.TokenUser)[0]
        groups = security.GetTokenInformation(token, security.TokenGroups)
        login = next(sid for sid, flags in groups if flags & 0xC0000000 == 0xC0000000)
        return user, login
    finally:
        token.Close()


def _address(root: Path, endpoint: str):
    """以规范化工作目录、观测端点和登录会话派生管道定位标识；该摘要不包含实际观测 token。"""
    *_, security = _windows()
    user, login = _identity()
    scope = hashlib.sha256((os.path.normcase(str(root.resolve())) + "\0" +
        endpoint.rstrip("/") + "\0" + security.ConvertSidToStringSid(login)).encode()).hexdigest()
    return "\\\\.\\pipe\\ezllmtest-observation-" + scope, scope, user, login


def _overlapped():
    """为单次异步管道操作分配独立完成事件，由 _finish 收尾关闭，避免退出时遗留句柄。"""
    types, _, _, event, _, _, _ = _windows()
    value = types.OVERLAPPED()
    value.hEvent = event.CreateEvent(None, True, False, None)
    return value


def _finish(handle, operation, timeout_ms: int, stop=None):
    """以短轮询检查 IO 完成、超时和停止信号；取消后等待操作收尾再关闭事件，避免后台永久阻塞。"""
    _, _, con, event, files, _, _ = _windows()
    deadline = time.monotonic() + timeout_ms / 1000
    try:
        while event.WaitForSingleObject(operation.hEvent, 25) == con.WAIT_TIMEOUT:
            if time.monotonic() >= deadline or (stop is not None and stop.is_set()):
                files.CancelIo(handle)
                raise TimeoutError("telemetry_ipc:timeout")
        return files.GetOverlappedResult(handle, operation, False)
    finally:
        # 取消后先收束内核操作，再释放 OVERLAPPED 使用的事件。
        try:
            files.GetOverlappedResult(handle, operation, True)
        except (OSError, Win32Error):
            pass
        operation.hEvent.Close()


class SessionTokenServer:
    """观测 lifespan 拥有的单实例管道，不启动 HTTP 或独立常驻服务。"""

    # 为该工作目录和会话生成仅存于内存的新 token；实例重建会轮换凭据，但此时尚未创建管道。
    def __init__(self, root: Path, endpoint: str):
        self.name, self.scope, self.user, self.login = _address(root, endpoint)
        self.token = secrets.token_urlsafe(32)
        self._stop = threading.Event()
        self._thread = None
        self._handle = None

    def start(self):
        """显式 DACL 只授权当前登录会话，拒绝远程客户端并要求首个管道实例；创建失败不接管同名通道。"""
        types, _, _, _, files, pipes, security = _windows()
        descriptor = security.SECURITY_DESCRIPTOR()
        acl = security.ACL()
        # 登录 SID 持有管道；不授权 Everyone、匿名或其他登录会话。
        acl.AddAccessAllowedAce(security.ACL_REVISION, 0x001F01FF, self.login)
        descriptor.SetSecurityDescriptorDacl(1, acl, 0)
        descriptor.SetSecurityDescriptorOwner(self.user, 0)
        attrs = types.SECURITY_ATTRIBUTES()
        attrs.SECURITY_DESCRIPTOR = descriptor
        attrs.bInheritHandle = False
        try:
            self._handle = pipes.CreateNamedPipe(
                self.name, pipes.PIPE_ACCESS_DUPLEX | files.FILE_FLAG_OVERLAPPED | 0x00080000,
                pipes.PIPE_TYPE_MESSAGE | pipes.PIPE_READMODE_MESSAGE | pipes.PIPE_WAIT |
                pipes.PIPE_REJECT_REMOTE_CLIENTS,
                1, _MAX_MESSAGE, _MAX_MESSAGE, 2000, attrs)
        except (OSError, Win32Error):
            raise TokenIPCError("telemetry_ipc:channel_unavailable") from None
        self._thread = threading.Thread(target=self._serve, name="ezllmtest-token-ipc", daemon=True)
        self._thread.start()

    def _serve(self):
        """发送有界凭据报文后等待客户端确认再断开，给客户端保留核验服务端身份的窗口；每轮失败只回收本次连接。"""
        _, _, _, event, files, pipes, _ = _windows()
        payload = json.dumps({"version": 1, "scope": self.scope, "token": self.token}).encode()
        try:
            while not self._stop.is_set():
                operation = _overlapped()
                try:
                    try:
                        pipes.ConnectNamedPipe(self._handle, operation)
                    except (OSError, Win32Error) as exc:
                        if exc.winerror == 535:
                            event.SetEvent(operation.hEvent)
                        elif exc.winerror != 997:
                            operation.hEvent.Close()
                            raise
                    _finish(self._handle, operation, 1000, self._stop)
                    operation = _overlapped()
                    try:
                        files.WriteFile(self._handle, payload, operation)
                    except (OSError, Win32Error):
                        operation.hEvent.Close()
                        raise
                    _finish(self._handle, operation, 2000, self._stop)
                    # WriteFile 完成只表示已入内核缓冲；等待客户端确认，避免身份核验前断开。
                    operation = _overlapped()
                    try:
                        _, acknowledgement = files.ReadFile(self._handle, 16, operation)
                    except (OSError, Win32Error):
                        operation.hEvent.Close()
                        raise
                    length = _finish(self._handle, operation, 2000, self._stop)
                    if bytes(acknowledgement[:length]) != b"received":
                        continue
                except (OSError, Win32Error, TimeoutError):
                    pass
                finally:
                    try:
                        pipes.DisconnectNamedPipe(self._handle)
                    except (OSError, Win32Error):
                        pass
        finally:
            self._handle.Close()
            self._handle = None

    def close(self):
        """通知服务线程取消有界 IO 并等待退出；超时明确失败，正常结束后清空服务端 token。"""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(5)
            if self._thread.is_alive():
                raise RuntimeError("telemetry_ipc:shutdown_timeout")
        self.token = ""


class SessionTokenProvider:
    """生产者按需读取内存凭据，失败冷却，不把观测故障传播给业务。"""

    # 记录管道身份并建立进程内缓存和锁，首次获取前不请求或持久化凭据。
    def __init__(self, root: Path, endpoint: str):
        self.name, self.scope, self.user, self.login = _address(root, endpoint)
        self._token = ""
        self._retry_at = 0.0
        self._lock = threading.Lock()

    def invalidate(self):
        """鉴权失效时清空本进程缓存并设置短暂重取间隔，避免旧 token 被反复发送。"""
        with self._lock:
            self._token = ""
            self._retry_at = time.monotonic() + 1.0

    def get(self) -> str:
        """缓存未命中时验证管道所有者、精确 DACL、服务进程会话和报文 scope；失败返回空值供遥测 fail-open，不放宽 ingestion 鉴权。"""
        with self._lock:
            if self._token:
                return self._token
            if time.monotonic() < self._retry_at:
                return ""
            self._retry_at = time.monotonic() + 1.0
            handle = None
            try:
                _, api, con, _, files, pipes, security = _windows()
                handle = files.CreateFile(self.name, con.GENERIC_READ | con.GENERIC_WRITE | con.READ_CONTROL,
                    0, None, con.OPEN_EXISTING, files.FILE_FLAG_OVERLAPPED, None)
                owner = security.GetSecurityInfo(handle, security.SE_KERNEL_OBJECT,
                    security.OWNER_SECURITY_INFORMATION | security.DACL_SECURITY_INFORMATION)
                if owner.GetSecurityDescriptorOwner() != self.user:
                    return ""
                acl = owner.GetSecurityDescriptorDacl()
                if (acl is None or acl.GetAceCount() != 1 or acl.GetAce(0)[2] != self.login
                    or acl.GetAce(0)[0] != (0, 0) or acl.GetAce(0)[1] != 0x001F01FF):
                    return ""
                pid = pipes.GetNamedPipeServerProcessId(handle)
                process = api.OpenProcess(con.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
                try:
                    token = security.OpenProcessToken(process, con.TOKEN_QUERY)
                    try:
                        groups = security.GetTokenInformation(token, security.TokenGroups)
                        if security.GetTokenInformation(token, security.TokenUser)[0] != self.user:
                            return ""
                        if not any(sid == self.login and flags & 0xC0000000 == 0xC0000000 for sid, flags in groups):
                            return ""
                    finally:
                        token.Close()
                finally:
                    process.Close()
                operation = _overlapped()
                try:
                    _, buffer = files.ReadFile(handle, _MAX_MESSAGE, operation)
                except (OSError, Win32Error):
                    operation.hEvent.Close()
                    raise
                length = _finish(handle, operation, 2000)
                message = json.loads(bytes(buffer[:length]))
                if not isinstance(message, dict):
                    return ""
                value = message.get("token", "")
                if set(message) != {"version", "scope", "token"} or message["version"] != 1 or message["scope"] != self.scope:
                    return ""
                if not isinstance(value, str) or not 32 <= len(value) <= 128 or any(c.isspace() for c in value):
                    return ""
                operation = _overlapped()
                try:
                    files.WriteFile(handle, b"received", operation)
                except (OSError, Win32Error):
                    operation.hEvent.Close()
                    raise
                _finish(handle, operation, 500)
                self._token = value
                return value
            except (OSError, Win32Error, ValueError, TypeError, RuntimeError):
                return ""
            finally:
                if handle is not None:
                    handle.Close()


def configure_provider(root: Path, endpoint: str):
    """为当前生产者进程安装共享凭据提供者；配置中只携带定位信息，不将 token 写入环境变量。"""
    global _PROVIDER
    _PROVIDER = SessionTokenProvider(root, endpoint)


def provider():
    """返回进程内凭据提供者；未启用遥测时为空。"""
    return _PROVIDER
