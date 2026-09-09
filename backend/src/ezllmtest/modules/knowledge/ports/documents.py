"""documents端口：由 bootstrap 注入实现，不加载 SDK 或数据。"""
from __future__ import annotations

_adapter = None

def bind(adapter):
    """仅由进程装配层绑定具体实现。"""
    global _adapter
    _adapter = adapter

def _require():
    """通过装配的端口实现调用；要求观测连接已打开，未进入生命周期时明确失败而不隐式初始化。"""
    if _adapter is None:
        raise RuntimeError("runtime_dependencies:documents_unbound")
    return _adapter

def load_document(filepath):
    """装配端口：将显式文件路径锚定到数据边界后按扩展名选择加载器，不支持的格式返回 False。"""
    return _require().load_document(filepath)
