# 把知识检索上下文接入生成链，不让页面或接口直接构造 Provider SDK。
from __future__ import annotations

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda

from ezllmtest.platform.ai.gateway import get_chat_model
from ezllmtest.modules.knowledge.public import knowledge_retriever


LEGACY_RAG_MINIMUM_TIMEOUT_SECONDS = 300.0


def knowledge_retrieval_chain(documents, *, llm=None, retriever=None):
    """装配检索结果与知识提示词的同步链，资料仍由调用方绑定的检索器提供。"""
    scoped_retriever = retriever or knowledge_retriever(documents)
    selected_llm = llm or get_chat_model(
        minimum_timeout_seconds=LEGACY_RAG_MINIMUM_TIMEOUT_SECONDS
    )
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "请仅根据以下检索到的上下文回答问题。若上下文不足，请明确说明。\n\n{context}",
            ),
            ("human", "{input}"),
        ]
    )
    answer_chain = prompt | selected_llm | StrOutputParser()

    def invoke(payload: dict):
        """先取得相关文档，再生成有依据的知识结果；这是显式模型调用路径。"""
        question = payload["input"]
        context_documents = scoped_retriever.invoke(question)
        context = "\n\n".join(doc.page_content for doc in context_documents)
        answer = answer_chain.invoke({"input": question, "context": context})
        return {"input": question, "context": context_documents, "answer": answer}

    return RunnableLambda(invoke)
