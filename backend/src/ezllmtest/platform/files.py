"""将历史相对文档路径锚定到显式数据根，不依赖终端工作目录。"""
from pathlib import Path
from ezllmtest.platform.configuration import backend_root

def document_path(value: str | Path) -> Path:
    """将相对路径锚定到显式 backend 根；规范化后必须位于 static/projects 内，并拒绝路径祖先中的 reparse point。"""
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = backend_root() / candidate
    resolved = candidate.resolve()
    boundary = (backend_root() / "static" / "projects").resolve()
    if not resolved.is_relative_to(boundary):
        raise ValueError("project_path:outside_data_boundary")
    for item in (candidate, *candidate.parents):
        if item.exists() and (item.is_symlink() or getattr(item.stat(), "st_file_attributes", 0) & 0x400):
            raise ValueError("project_path:reparse_point")
    return resolved
