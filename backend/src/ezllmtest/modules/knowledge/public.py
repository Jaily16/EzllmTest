"""knowledge 的稳定内部接口；只暴露实际消费者需要的操作和 DTO。"""
from __future__ import annotations

from ezllmtest.modules.knowledge.schemas.contracts import RetrievalCitation
from ezllmtest.modules.knowledge.schemas.contracts import RetrievalQueryEvidence
from ezllmtest.modules.knowledge.schemas.contracts import ToolRetrievalEvidence
def api_retriever(documents, *, embedding_model=None):
    """供其他域调用的稳定内部接口；为接口相关资料选择检索器，避免无关文档扩展上下文。"""
    from ezllmtest.modules.knowledge.ports.retrieval import api_retriever as implementation
    return implementation(documents, embedding_model=embedding_model)

def design_retriever(documents, *, embedding_model=None):
    """供其他域调用的稳定内部接口；为设计资料选择检索器，保留该资料类别的策略和数量约束。"""
    from ezllmtest.modules.knowledge.ports.retrieval import design_retriever as implementation
    return implementation(documents, embedding_model=embedding_model)

def get_project_retriever(pid, corpus, source_revision, documents, *, embedding_model=None, policy=None):
    """供其他域调用的稳定内部接口；按可信项目、资料类别、revision 和检索策略装配索引检索器。"""
    from ezllmtest.modules.knowledge.ports.retrieval import get_project_retriever as implementation
    return implementation(pid, corpus, source_revision, documents, embedding_model=embedding_model, policy=policy)

def invalidate_project_indexes(pid):
    """供其他域调用的稳定内部接口；使指定项目的进程内索引失效，来源变化后后续检索重新建立正确身份。"""
    from ezllmtest.modules.knowledge.ports.indexes import invalidate_project_indexes as implementation
    return implementation(pid)

def knowledge_retriever(documents, *, embedding_model=None):
    """供其他域调用的稳定内部接口；为知识资料选择检索器，供测试方法和用例构造使用。"""
    from ezllmtest.modules.knowledge.ports.retrieval import knowledge_retriever as implementation
    return implementation(documents, embedding_model=embedding_model)

def load_document(filepath):
    """跨域内部接口：将显式文件路径锚定到数据边界后按扩展名选择加载器，不支持的格式返回 False。"""
    from ezllmtest.modules.knowledge.ports.documents import load_document as implementation
    return implementation(filepath)

def nfunctional_retriever(documents, *, embedding_model=None):
    """供其他域调用的稳定内部接口；为非功能测试相关资料选择检索器，保持目标方法的证据边界。"""
    from ezllmtest.modules.knowledge.ports.retrieval import nfunctional_retriever as implementation
    return implementation(documents, embedding_model=embedding_model)

def require_retriever(documents, *, embedding_model=None):
    """供其他域调用的稳定内部接口；为需求资料选择检索器，不混用其他项目或类别的索引。"""
    from ezllmtest.modules.knowledge.ports.retrieval import require_retriever as implementation
    return implementation(documents, embedding_model=embedding_model)

from ezllmtest.modules.knowledge.ports.splitters import testdoc_text_splitter_for_acceptance
from ezllmtest.modules.knowledge.ports.splitters import testdoc_text_splitter_for_db
from ezllmtest.modules.knowledge.ports.splitters import testdoc_text_splitter_for_integration
from ezllmtest.modules.knowledge.ports.splitters import testdoc_text_splitter_for_menu
from ezllmtest.modules.knowledge.ports.splitters import testdoc_text_splitter_for_ui
from ezllmtest.modules.knowledge.ports.splitters import testdoc_text_splitter_for_unit
from ezllmtest.modules.knowledge.ports.splitters import testdoc_text_splitter_for_use_case
def use_agent_retrieval(scope, *, strategy="dense_v1"):
    """跨域内部接口：为可信 scope 建立临时检索会话，退出时恢复原上下文，隔离并发 Agent 调用。"""
    from ezllmtest.modules.knowledge.application.agent import use_agent_retrieval as implementation
    return implementation(scope, strategy=strategy)
