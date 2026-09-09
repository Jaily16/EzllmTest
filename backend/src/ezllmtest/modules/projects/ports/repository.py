"""repository端口：由 bootstrap 注入实现，不加载 SDK 或数据。"""
from __future__ import annotations

_adapter = None

def bind(adapter):
    """仅由进程装配层绑定具体实现。"""
    global _adapter
    _adapter = adapter

def _require():
    """通过装配的端口实现调用；要求观测连接已打开，未进入生命周期时明确失败而不隐式初始化。"""
    if _adapter is None:
        raise RuntimeError("runtime_dependencies:repository_unbound")
    return _adapter

def add_project(name):
    """装配端口：创建并保存项目 ID，明确属于业务写入接口。"""
    return _require().add_project(name)

def add_project_design_testdoc(pid, path):
    """装配端口：通过统一登记函数添加设计资料路径，不执行文档解析或索引。"""
    return _require().add_project_design_testdoc(pid, path)

def add_project_info(pid, info_type, info):
    """通过装配的端口实现调用；新增指定项目信息记录，提交与回滚由本仓储会话负责。"""
    return _require().add_project_info(pid, info_type, info)

def add_project_knowledge(pid, path):
    """装配端口：通过统一登记函数添加知识文档路径，不在仓储内读取文件正文。"""
    return _require().add_project_knowledge(pid, path)

def add_project_requirement_testdoc(pid, path):
    """装配端口：通过统一登记函数添加需求资料路径，文件上传由应用层负责。"""
    return _require().add_project_requirement_testdoc(pid, path)

def add_project_type(pid, overflow):
    """通过装配的端口实现调用；保存项目类型信息并提交本次事务，失败不留下半份类型判断。"""
    return _require().add_project_type(pid, overflow)

def find_project(pid):
    """装配端口：按项目 ID 查询并返回不带 ORM 会话的只读快照；不存在与查询失败分别返回 None 和 False。"""
    return _require().find_project(pid)

def find_project_design_testdoc_list(pid):
    """装配端口：查询项目设计资料的路径快照，不把 ORM 对象传出仓储。"""
    return _require().find_project_design_testdoc_list(pid)

def find_project_knowledge_list(pid):
    """装配端口：查询项目知识文档路径并转换为 DocumentRecord，离开函数前关闭数据库会话。"""
    return _require().find_project_knowledge_list(pid)

def find_project_requirement_testdoc_list(pid):
    """装配端口：查询项目需求资料路径并返回会话外可用的文档快照。"""
    return _require().find_project_requirement_testdoc_list(pid)

def get_project_info(pid, info_type):
    """通过装配的端口实现调用；读取指定项目和信息类型的记录，返回数据快照而非开放数据库会话。"""
    return _require().get_project_info(pid, info_type)

def get_project_setup_documents(pid):
    """装配端口：项目存在时读取三组已登记路径，供准备服务核对资料完整性。"""
    return _require().get_project_setup_documents(pid)

def get_project_type(pid):
    """装配端口：读取项目类型并返回独立快照，缺失与存储异常使用不同返回值。"""
    return _require().get_project_type(pid)

def save_project_analysis_artifact_bundle(pid, summary, plan, menu_json, *, artifact_key, input_hash, source_revision, prompt_version, model_label, artifact_content, metadata_json):
    """通过装配的端口实现调用；在同一事务保存分析信息和 revision 产物记录，使恢复身份与有效结果一致。"""
    return _require().save_project_analysis_artifact_bundle(pid, summary, plan, menu_json, artifact_key=artifact_key, input_hash=input_hash, source_revision=source_revision, prompt_version=prompt_version, model_label=model_label, artifact_content=artifact_content, metadata_json=metadata_json)

def update_project_info(pid, info_type, info):
    """通过装配的端口实现调用；更新当前项目对应类型的信息，异常回滚并关闭会话。"""
    return _require().update_project_info(pid, info_type, info)
