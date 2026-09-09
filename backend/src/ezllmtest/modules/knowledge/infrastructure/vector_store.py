# 封装向量存储构造和检索实现，调用方通过知识端口取得能力。
from langchain_core.vectorstores import InMemoryVectorStore

# 将文档转换成向量进行保存(工具函数)[没有必要，直接调用的时候再构建向量库不就好]
def load_and_save_doc(doc, splitter, embeddings, path):
    """切分并嵌入文档到内存向量库；历史 path 参数不表示向磁盘保存。"""
    pages = splitter.split_documents(doc)
    db = InMemoryVectorStore(embedding=embeddings)
    db.add_documents(documents=pages)
    return db
