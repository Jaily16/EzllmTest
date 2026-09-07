from __future__ import annotations

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda

from llm.provider import get_chat_model
from vectorstore.retrievers import knowledge_retriever


LEGACY_RAG_MINIMUM_TIMEOUT_SECONDS = 300.0


def knowledge_retrieval_chain(documents, *, llm=None, retriever=None):
    """处理知识库检索chain并返回现有契约规定的结果。

    参数:
        `documents`：调用方传入的现有参数。
        `llm`：调用方传入的现有参数。
        `retriever`：调用方传入的现有参数。

    副作用:
        可能按现有预算与模型选择发起 provider 或 embedding 调用。

    不变量:
        模型选择、Token 上限、取消与失败不覆盖有效结果的语义必须保持不变。"""
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
        """调用当前适配器封装的下游能力，并返回既有契约规定的结果。

        参数:
            `payload`：符合现有契约的载荷。

        副作用:
            可能按现有预算与模型选择发起 provider 或 embedding 调用。

        不变量:
            模型选择、Token 上限、取消与失败不覆盖有效结果的语义必须保持不变。"""
        question = payload["input"]
        context_documents = scoped_retriever.invoke(question)
        context = "\n\n".join(doc.page_content for doc in context_documents)
        answer = answer_chain.invoke({"input": question, "context": context})
        return {"input": question, "context": context_documents, "answer": answer}

    return RunnableLambda(invoke)
