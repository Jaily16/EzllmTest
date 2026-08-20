from __future__ import annotations

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda

from llm.provider import get_lazy_chat_model
from vectorstore.retrievers import knowledge_retriever


def knowledge_retrieval_chain(documents, *, llm=None, retriever=None):
    """Build a request-scoped RAG runnable while preserving the legacy result keys."""
    scoped_retriever = retriever or knowledge_retriever(documents)
    selected_llm = llm or get_lazy_chat_model()
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
        question = payload["input"]
        context_documents = scoped_retriever.invoke(question)
        context = "\n\n".join(doc.page_content for doc in context_documents)
        answer = answer_chain.invoke({"input": question, "context": context})
        return {"input": question, "context": context_documents, "answer": answer}

    return RunnableLambda(invoke)
