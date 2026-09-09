"""generation 的稳定内部接口；只暴露实际消费者需要的操作和 DTO。"""
from __future__ import annotations

from ezllmtest.modules.generation.schemas.history import ArtifactHistoryRow
from ezllmtest.modules.generation.schemas.requests import InfoModel
from ezllmtest.modules.generation.schemas.analysis import ProjectTestEvidence
from ezllmtest.modules.generation.schemas.analysis import TestMenu
from ezllmtest.modules.generation.schemas.errors import TestPlanStreamError
from ezllmtest.modules.generation.schemas.artifact_record import WorkflowArtifactRecord
from ezllmtest.modules.generation.schemas.errors import WorkflowStreamError
def get_fresh_artifact(project_id, artifact_key, source_revision, input_hash, prompt_version, model_label):
    """供其他域调用的稳定内部接口；按产物身份读取有效记录并转换为快照；无论成功或异常均关闭本次会话。"""
    from ezllmtest.modules.generation.ports.artifact_store import get_fresh_artifact as implementation
    return implementation(project_id, artifact_key, source_revision, input_hash, prompt_version, model_label)

def get_project_analysis_status(pid):
    """跨域内部接口：并发读取摘要、计划和菜单，仅三者均有效才返回整体 ready。"""
    from ezllmtest.modules.generation.application.test_plan_stream import get_project_analysis_status as implementation
    return implementation(pid)

def get_workflow_definition(operation):
    """跨域内部接口：从不可变操作索引获取工作流定义，未知 operation 直接失败。"""
    from ezllmtest.modules.generation.domain.catalog import get_workflow_definition as implementation
    return implementation(operation)

def invalidate_project_artifacts(project_id, source_revision):
    """供其他域调用的稳定内部接口；仅将指定项目产物标记为过期并维护元数据，不把来源变化解释为删除历史有效结果。"""
    from ezllmtest.modules.generation.ports.artifact_store import invalidate_project_artifacts as implementation
    return implementation(project_id, source_revision)

def list_artifact_history(project_id, artifact_key=None):
    """供其他域调用的稳定内部接口；按项目和可选产物条件读取历史快照并按更新时间排序，关闭会话后返回不可变记录。"""
    from ezllmtest.modules.generation.ports.artifacts import list_artifact_history as implementation
    return implementation(project_id, artifact_key)

def list_workflow_definitions():
    """跨域内部接口：返回完整不可变工作流元组，19 workflows 的顺序以此为准。"""
    from ezllmtest.modules.generation.domain.catalog import list_workflow_definitions as implementation
    return implementation()

def profile_for(operation, stage='final'):
    """供其他域调用的稳定内部接口；按 operation 和调用阶段取得预算配置，避免把中间抽取与最终产物共用不合适的上限。"""
    from ezllmtest.modules.generation.domain.budget import profile_for as implementation
    return implementation(operation, stage)

def save_artifact(record, artifact_key=None, source_revision=None, input_hash=None, prompt_version=None, model_label=None, content=None, metadata=None):
    """供其他域调用的稳定内部接口；校验类型与元数据后在独立会话内新增或替换有效产物，提交失败回滚并关闭会话。"""
    from ezllmtest.modules.generation.ports.artifact_store import save_artifact as implementation
    return implementation(record, artifact_key, source_revision, input_hash, prompt_version, model_label, content, metadata)

def stream_llm_workflow(operation, pid, llm_name, payload, regenerate=False, *, is_disconnected=None):
    """供其他域调用的稳定内部接口；统一执行前置检查、revision 缓存恢复和分析/用例分派；只在完整有效结果与连接检查通过后提交持久化，失败或截断保留旧结果。"""
    from ezllmtest.modules.generation.application.stream import stream_llm_workflow as implementation
    return implementation(operation, pid, llm_name, payload, regenerate, is_disconnected=is_disconnected)

def stream_test_plan(pid, llm_name, regenerate, *, is_disconnected=None):
    """供其他域调用的稳定内部接口；先检查可恢复缓存，再从同一摘要形成菜单和计划；完整校验且连接仍有效时原子保存联合结果。"""
    from ezllmtest.modules.generation.application.test_plan_stream import stream_test_plan as implementation
    return implementation(pid, llm_name, regenerate, is_disconnected=is_disconnected)
