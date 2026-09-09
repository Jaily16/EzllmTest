"""artifact_store端口：由 bootstrap 注入实现，不加载 SDK 或数据。"""
from __future__ import annotations

_adapter = None

def bind(adapter):
    """仅由进程装配层绑定具体实现。"""
    global _adapter
    _adapter = adapter

def _require():
    """通过装配的端口实现调用；要求观测连接已打开，未进入生命周期时明确失败而不隐式初始化。"""
    if _adapter is None:
        raise RuntimeError("runtime_dependencies:artifact_store_unbound")
    return _adapter

def get_fresh_artifact(project_id, artifact_key, source_revision, input_hash, prompt_version, model_label):
    """通过装配的端口实现调用；按产物身份读取有效记录并转换为快照；无论成功或异常均关闭本次会话。"""
    return _require().get_fresh_artifact(project_id, artifact_key, source_revision, input_hash, prompt_version, model_label)

def invalidate_project_artifacts(project_id, source_revision):
    """通过装配的端口实现调用；仅将指定项目产物标记为过期并维护元数据，不把来源变化解释为删除历史有效结果。"""
    return _require().invalidate_project_artifacts(project_id, source_revision)

def save_artifact(record, artifact_key=None, source_revision=None, input_hash=None, prompt_version=None, model_label=None, content=None, metadata=None):
    """通过装配的端口实现调用；校验类型与元数据后在独立会话内新增或替换有效产物，提交失败回滚并关闭会话。"""
    return _require().save_artifact(record, artifact_key, source_revision, input_hash, prompt_version, model_label, content, metadata)
