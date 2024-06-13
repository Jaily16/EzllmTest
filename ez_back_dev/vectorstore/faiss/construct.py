import os
from langchain_community.vectorstores import FAISS


# os.environ["LANGCHAIN_API_KEY"] = "ls__8f1d0a23c4cb4c9d8b58076ba3de84c7"
# os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
# os.environ["LANGCHAIN_TRACING_V2"] = "true"
# os.environ["LANGCHAIN_PROJECT"] = "faiss_vector_construct"

# 将文档转换成向量进行保存(工具函数)[没有必要，直接调用的时候再构建向量库不就好]
def load_and_save_doc(doc, splitter, embeddings, path):
    pages = splitter.split_documents(doc)
    db = FAISS.from_documents(pages, embeddings)
    db.save_local(path)
