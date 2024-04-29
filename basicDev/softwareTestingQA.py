import os

from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains.history_aware_retriever import create_history_aware_retriever
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

os.environ["OPENAI_API_KEY"] = "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"
os.environ["TAVILY_API_KEY"] = "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"

loader1 = PyPDFLoader("refer.pdf")
loder2 = PyPDFLoader("BusinessTest1.pdf")
pages = loader1.load()
doc = loder2.load()
embeddings = OpenAIEmbeddings()

text_splitter = RecursiveCharacterTextSplitter()
reference = text_splitter.split_documents(pages)
vector = FAISS.from_documents(reference, embeddings)

retriever = vector.as_retriever()

prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一名软件测试专家。这是你需要进行测试分析的业务文档:\n\n{context}"),
    ("user", "{input}")
])

llm = ChatOpenAI()

# chain = create_stuff_documents_chain(llm, prompt)
#
# res = chain.invoke({"context": pages, "input": "请问黑盒测试是什么"})
# print(res)


retriever_chain = create_history_aware_retriever(llm, retriever, prompt)

res = retriever_chain.invoke({"context": pages, "input": "请对机票订购系统做出完整的测试计划"})
print(res)


