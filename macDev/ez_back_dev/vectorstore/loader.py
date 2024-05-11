import os
from langchain_community.document_loaders import TextLoader, PyPDFLoader
from langchain_community.document_loaders import Docx2txtLoader, UnstructuredMarkdownLoader


def load_document(filepath):
    postfix = os.path.splitext(filepath)[-1]
    if postfix == ".txt":
        loader = TextLoader(filepath)
        return loader.load()
    elif postfix == ".pdf":
        loader = PyPDFLoader(filepath)
        return loader.load()
    elif postfix == ".md":
        loader = UnstructuredMarkdownLoader(filepath)
        return loader.load()
    elif postfix == ".doc" or postfix == ".docx":
        loader = Docx2txtLoader(filepath)
        return loader.load()
    else:
        return False
