from langchain_core.vectorstores import InMemoryVectorStore

# 将文档转换成向量进行保存(工具函数)[没有必要，直接调用的时候再构建向量库不就好]
def load_and_save_doc(doc, splitter, embeddings, path):
    pages = splitter.split_documents(doc)
    db = InMemoryVectorStore(embedding=embeddings)
    db.add_documents(documents=pages)
    return db
