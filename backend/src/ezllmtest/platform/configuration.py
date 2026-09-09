"""进程内配置快照；只有 bootstrap 写入，不搜索或读取操作系统环境。"""

from pathlib import Path
from types import MappingProxyType
from collections.abc import Mapping

_values: Mapping[str, str] = MappingProxyType({})
_repo_root: Path | None = None


def install(values: Mapping[str, str], repo_root: Path) -> None:
    """复制并冻结已校验配置和显式数据根，同时清除 settings 缓存，避免后续读取沿用上一轮快照。"""
    global _values, _repo_root
    _values = MappingProxyType(dict(values))
    _repo_root = repo_root
    from ezllmtest.platform.settings import get_settings
    get_settings.cache_clear()


def get(name: str, default: str | None = None) -> str | None:
    """读取装配快照，不回退到父终端中的同名配置。"""
    return _values.get(name, default)


def repo_root() -> Path:
    """只返回 bootstrap 安装的数据根；未装配时明确失败，不猜测源码层级或当前工作目录。"""
    if _repo_root is None:
        raise RuntimeError("runtime_config:repo_root_required")
    return _repo_root


def backend_root() -> Path:
    """数据的后端根始终位于原工作目录，源码迁移不移动用户资料。"""
    return repo_root() / "backend"
