"""retrieval端口：由 bootstrap 注入实现，不加载 SDK 或数据。"""
from __future__ import annotations

_adapter = None

def bind(adapter):
    """仅由进程装配层绑定具体实现。"""
    global _adapter
    _adapter = adapter

def _require():
    """通过装配的端口实现调用；要求观测连接已打开，未进入生命周期时明确失败而不隐式初始化。"""
    if _adapter is None:
        raise RuntimeError("runtime_dependencies:retrieval_unbound")
    return _adapter

def api_retriever(documents, *, embedding_model=None):
    """通过装配的端口实现调用；为接口相关资料选择检索器，避免无关文档扩展上下文。"""
    return _require().api_retriever(documents, embedding_model=embedding_model)

def design_retriever(documents, *, embedding_model=None):
    """通过装配的端口实现调用；为设计资料选择检索器，保留该资料类别的策略和数量约束。"""
    return _require().design_retriever(documents, embedding_model=embedding_model)

def get_project_retriever(pid, corpus, source_revision, documents, *, embedding_model=None, policy=None):
    """通过装配的端口实现调用；按可信项目、资料类别、revision 和检索策略装配索引检索器。"""
    return _require().get_project_retriever(pid, corpus, source_revision, documents, embedding_model=embedding_model, policy=policy)

def knowledge_retriever(documents, *, embedding_model=None):
    """通过装配的端口实现调用；为知识资料选择检索器，供测试方法和用例构造使用。"""
    return _require().knowledge_retriever(documents, embedding_model=embedding_model)

def nfunctional_retriever(documents, *, embedding_model=None):
    """通过装配的端口实现调用；为非功能测试相关资料选择检索器，保持目标方法的证据边界。"""
    return _require().nfunctional_retriever(documents, embedding_model=embedding_model)

def require_retriever(documents, *, embedding_model=None):
    """通过装配的端口实现调用；为需求资料选择检索器，不混用其他项目或类别的索引。"""
    return _require().require_retriever(documents, embedding_model=embedding_model)
