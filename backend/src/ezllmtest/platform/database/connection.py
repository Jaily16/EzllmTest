"""延迟创建连接池，导入本模块不解析秘密、不连接数据库。"""

from threading import RLock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from ezllmtest.platform.settings import get_settings

_engine = None
_session_factory = None
_lock = RLock()


def get_engine():
    """首次请求时在锁内创建 engine 与会话工厂，后续共享连接池；导入模块不会创建引擎或执行建表。"""
    global _engine, _session_factory
    with _lock:
        if _engine is None:
            _engine = create_engine(get_settings().database_url, pool_pre_ping=True)
            _session_factory = sessionmaker(bind=_engine)
        return _engine


def Session():
    """确保延迟引擎已创建后返回独立会话；提交、回滚与关闭仍由业务仓储负责。"""
    get_engine()
    return _session_factory()


def close() -> None:
    """持锁释放连接池并清空工厂引用，使进程关闭后的下一次显式装配可以重新创建资源。"""
    global _engine, _session_factory
    with _lock:
        if _engine is not None:
            _engine.dispose()
        _engine = _session_factory = None
