"""artifacts端口：由 bootstrap 注入实现，不加载 SDK 或数据。"""
from __future__ import annotations
from ezllmtest.modules.generation.schemas.artifacts import WorkflowArtifactLookup

_adapter = None

def bind(adapter):
    """仅由进程装配层绑定具体实现。"""
    global _adapter
    _adapter = adapter

def _require():
    """通过装配的端口实现调用；要求观测连接已打开，未进入生命周期时明确失败而不隐式初始化。"""
    if _adapter is None:
        raise RuntimeError("runtime_dependencies:artifacts_unbound")
    return _adapter

def build_workflow_artifact_key(pid, definition, payload, model_label):
    """通过装配的端口实现调用；结合项目来源 revision、操作、模型、提示词版本和选择输入建立缓存身份，避免跨版本复用。"""
    return _require().build_workflow_artifact_key(pid, definition, payload, model_label)

def list_artifact_history(project_id, artifact_key=None):
    """通过装配的端口实现调用；按项目和可选产物条件读取历史快照并按更新时间排序，关闭会话后返回不可变记录。"""
    return _require().list_artifact_history(project_id, artifact_key)

def lookup_workflow_artifact(pid, definition, payload, model_label):
    """通过装配的端口实现调用；先匹配完整产物身份，再区分精确缓存、其他模型和历史过期结果；返回查找状态而不自动生成。"""
    return _require().lookup_workflow_artifact(pid, definition, payload, model_label)

def normalized_selection(definition, payload):
    """通过装配的端口实现调用；按稳定键序规范化用户选择，保证相同选择产生相同输入身份。"""
    return _require().normalized_selection(definition, payload)

def save_workflow_artifact(pid, definition, key, payload, result, pending_info, *, call_count):
    """通过装配的端口实现调用；将最终产物与关联 pending_info 放入同一事务；任何异常回滚，失败执行不能部分覆盖旧有效数据。"""
    return _require().save_workflow_artifact(pid, definition, key, payload, result, pending_info, call_count=call_count)

def validate_workflow_prerequisites(pid, definition, payload, source_revision):
    """通过装配的端口实现调用；按 workflow 定义验证选择字段与前置产物，失败时阻止下游调用并关闭只读会话。"""
    return _require().validate_workflow_prerequisites(pid, definition, payload, source_revision)
