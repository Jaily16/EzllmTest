"""indexes端口：由 bootstrap 注入实现，不加载 SDK 或数据。"""
from __future__ import annotations

_adapter = None

def bind(adapter):
    """仅由进程装配层绑定具体实现。"""
    global _adapter
    _adapter = adapter

def _require():
    """通过装配的端口实现调用；要求观测连接已打开，未进入生命周期时明确失败而不隐式初始化。"""
    if _adapter is None:
        raise RuntimeError("runtime_dependencies:indexes_unbound")
    return _adapter

def invalidate_project_indexes(pid):
    """通过装配的端口实现调用；使指定项目的进程内索引失效，来源变化后后续检索重新建立正确身份。"""
    return _require().invalidate_project_indexes(pid)
