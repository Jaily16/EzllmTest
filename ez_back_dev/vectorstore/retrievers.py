from langchain.storage import InMemoryStore
from llm.llm_chatGPT import ChatGPTModel
from langchain_community.vectorstores import Chroma, FAISS
from langchain.retrievers import ParentDocumentRetriever, ContextualCompressionRetriever
from vectorstore.splitter import design_parent_text_splitter, design_child_text_splitter, knowledge_text_splitter, \
    require_child_text_splitter, require_parent_text_splitter, testdoc_text_splitter_for_api, \
    testdoc_text_splitter_for_nfunctional
from langchain_openai import OpenAIEmbeddings, OpenAI
from langchain.retrievers.document_compressors import LLMChainExtractor

embeddings = ChatGPTModel().get_embeddings()

# 用于开发设计文档的retrievers
design_vectorstore = Chroma(
    collection_name="design_split_parent",
    embedding_function=OpenAIEmbeddings()
)
design_store = InMemoryStore()
design_retriever = ParentDocumentRetriever(
    vectorstore=design_vectorstore,
    docstore=design_store,
    child_splitter=design_child_text_splitter,
    parent_splitter=design_parent_text_splitter
)

# 用于需求文档的retrievers
require_vectorstore = Chroma(
    collection_name="require_split_parent",
    embedding_function=OpenAIEmbeddings()
)
require_store = InMemoryStore()
require_retriever = ParentDocumentRetriever(
    vectorstore=require_vectorstore,
    docstore=require_store,
    child_splitter=require_child_text_splitter,
    parent_splitter=require_parent_text_splitter
)


# 用于构造知识库搜索的密集和稀疏检索器融合retriever
def knowledge_retriever(documents):
    texts = knowledge_text_splitter.split_documents(documents)
    retriever = FAISS.from_documents(texts, OpenAIEmbeddings()).as_retriever()
    llm = OpenAI(temperature=0)
    compressor = LLMChainExtractor.from_llm(llm)
    compression_retriever = ContextualCompressionRetriever(
        base_compressor=compressor,
        base_retriever=retriever
    )
    return compression_retriever


def api_retriever(documents):
    texts = testdoc_text_splitter_for_api.split_documents(documents)
    retriever = FAISS.from_documents(texts, OpenAIEmbeddings()).as_retriever()
    return retriever


def nfunctional_retriever(documents):
    texts = testdoc_text_splitter_for_nfunctional.split_documents(documents)
    retriever = FAISS.from_documents(texts, OpenAIEmbeddings()).as_retriever()
    return retriever
