"""projects 的稳定内部接口；只暴露实际消费者需要的操作和 DTO。"""
from __future__ import annotations

from ezllmtest.modules.projects.domain.info_type import InfoType
from ezllmtest.modules.projects.schemas.setup import ProjectSetupError
def add_project_info(pid, info_type, info):
    """供其他域调用的稳定内部接口；新增指定项目信息记录，提交与回滚由本仓储会话负责。"""
    from ezllmtest.modules.projects.ports.repository import add_project_info as implementation
    return implementation(pid, info_type, info)

def artifact_input_hash(operation, payload):
    """供其他域调用的稳定内部接口；对操作、规范化选择及输入身份生成稳定摘要，防止不同选择误用同一产物。"""
    from ezllmtest.modules.projects.application.revision import artifact_input_hash as implementation
    return implementation(operation, payload)

def collect_project_test_evidence(documents):
    """跨域内部接口：对已提供文档使用固定模式提取单元、集成和关系信号，不调用模型。"""
    from ezllmtest.modules.projects.application.test_evidence import collect_project_test_evidence as implementation
    return implementation(documents)

def compute_project_source_revision(pid):
    """供其他域调用的稳定内部接口；从项目当前来源记录和文件内容建立 revision，供缓存、准备状态和审批绑定使用。"""
    from ezllmtest.modules.projects.application.revision import compute_project_source_revision as implementation
    return implementation(pid)

def docs_to_meaningful_strings(docs):
    """跨域内部接口：按文档顺序附加编号与可用引用 ID，保留来源提示后拼接正文。"""
    from ezllmtest.modules.projects.application.documents import docs_to_meaningful_strings as implementation
    return implementation(docs)

def docs_to_string(docs):
    """跨域内部接口：按统一文档格式拼接内容；有引用 ID 时保留引用前缀供生成结果关联来源。"""
    from ezllmtest.modules.projects.application.documents import docs_to_string as implementation
    return implementation(docs)

def find_project(pid):
    """跨域内部接口：按项目 ID 查询并返回不带 ORM 会话的只读快照；不存在与查询失败分别返回 None 和 False。"""
    from ezllmtest.modules.projects.ports.repository import find_project as implementation
    return implementation(pid)

def generate_all_testdocs_docs(pid):
    """跨域内部接口：汇集项目需求与设计 Document 对象，供完整语料分析使用。"""
    from ezllmtest.modules.projects.application.documents import generate_all_testdocs_docs as implementation
    return implementation(pid)

def generate_design_testdocs_docs(pid):
    """跨域内部接口：按项目登记加载设计 Document 集合，保留文档元数据。"""
    from ezllmtest.modules.projects.application.documents import generate_design_testdocs_docs as implementation
    return implementation(pid)

def generate_design_testdocs_str(pid):
    """跨域内部接口：仅加载当前项目设计资料并按顺序拼接，不把知识文档混入设计输入。"""
    from ezllmtest.modules.projects.application.documents import generate_design_testdocs_str as implementation
    return implementation(pid)

def generate_knowledge_docs(pid):
    """跨域内部接口：加载当前项目知识文档集合，检索层据此建立项目内索引。"""
    from ezllmtest.modules.projects.application.documents import generate_knowledge_docs as implementation
    return implementation(pid)

def generate_require_testdocs_docs(pid):
    """跨域内部接口：按项目登记加载需求 Document 集合，加载失败不伪造空的成功结果。"""
    from ezllmtest.modules.projects.application.documents import generate_require_testdocs_docs as implementation
    return implementation(pid)

def generate_require_testdocs_str(pid):
    """跨域内部接口：仅加载当前项目需求资料并按顺序拼接，文件路径来自项目登记。"""
    from ezllmtest.modules.projects.application.documents import generate_require_testdocs_str as implementation
    return implementation(pid)

def get_project_info(pid, info_type):
    """供其他域调用的稳定内部接口；读取指定项目和信息类型的记录，返回数据快照而非开放数据库会话。"""
    from ezllmtest.modules.projects.ports.repository import get_project_info as implementation
    return implementation(pid, info_type)

def get_project_type(pid):
    """跨域内部接口：读取项目类型并返回独立快照，缺失与存储异常使用不同返回值。"""
    from ezllmtest.modules.projects.ports.repository import get_project_type as implementation
    return implementation(pid)

def get_project_workflow_status(pid):
    """跨域内部接口：把准备状态、当前 revision 和有效产物合成统一阶段；旧产物失效与已完成清单分别返回。"""
    from ezllmtest.modules.projects.application.workflow_status import get_project_workflow_status as implementation
    return implementation(pid)

def get_status(pid):
    """供其他域调用的稳定内部接口；依据当前登记资料和已存准备记录推导状态，不通过查询自动调用模型。"""
    from ezllmtest.modules.projects.application.setup import get_status as implementation
    return implementation(pid)

def num_tokens_from_string(text_str):
    """跨域内部接口：按固定 gpt-3.5-turbo tokenizer 离线估算 token，保持历史预算计数口径。"""
    from ezllmtest.platform.ai.tokens import num_tokens_from_string as implementation
    return implementation(text_str)

def reconcile_test_menu(candidate, evidence):
    """跨域内部接口：达到单元或集成结构证据阈值时补开菜单项，不因候选模型遗漏而丢失可验证测试类型。"""
    from ezllmtest.modules.projects.application.test_evidence import reconcile_test_menu as implementation
    return implementation(candidate, evidence)

def save_project_analysis_artifact_bundle(pid, summary, plan, menu_json, *, artifact_key, input_hash, source_revision, prompt_version, model_label, artifact_content, metadata_json):
    """供其他域调用的稳定内部接口；在同一事务保存分析信息和 revision 产物记录，使恢复身份与有效结果一致。"""
    from ezllmtest.modules.projects.ports.repository import save_project_analysis_artifact_bundle as implementation
    return implementation(pid, summary, plan, menu_json, artifact_key=artifact_key, input_hash=input_hash, source_revision=source_revision, prompt_version=prompt_version, model_label=model_label, artifact_content=artifact_content, metadata_json=metadata_json)

def update_project_info(pid, info_type, info):
    """供其他域调用的稳定内部接口；更新当前项目对应类型的信息，异常回滚并关闭会话。"""
    from ezllmtest.modules.projects.ports.repository import update_project_info as implementation
    return implementation(pid, info_type, info)
