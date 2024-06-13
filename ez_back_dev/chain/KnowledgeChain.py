# 利用langchain自带的retrieval_chain来进行基于测试知识库的搜索跟问答，实现RAG方式
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_retrieval_chain
from langchain import hub
from llm.llm_chatGPT import ChatGPTModel
from vectorstore.retrievers import knowledge_retriever


def knowledge_retrieval_chain(documents):
    retrieval_qa_chat_prompt = hub.pull("langchain-ai/retrieval-qa-chat")
    llm = ChatGPTModel().get_model()
    combine_docs_chain = create_stuff_documents_chain(
        llm, retrieval_qa_chat_prompt
    )
    retriever = knowledge_retriever(documents)
    retrieval_chain = create_retrieval_chain(retriever, combine_docs_chain)
    return retrieval_chain
