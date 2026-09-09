# 适配普通项目文档加载，把文件格式差异隐藏在知识端口之后。
from __future__ import annotations

from pathlib import Path
from ezllmtest.platform.files import document_path

import docx2txt
from langchain_core.documents import Document
from pypdf import PdfReader


def _text_document(path: Path) -> list[Document]:
    """读取受数据根约束的文本资料并保留来源元数据，编码处理由统一加载路径负责。"""
    return [
        Document(
            page_content=path.read_text(encoding="utf-8-sig"),
            metadata={"source": str(path)},
        )
    ]


def _pdf_documents(path: Path) -> list[Document]:
    """使用 PDF 加载器读取明确资料并保留页级来源，不递归搜索用户目录。"""
    reader = PdfReader(str(path))
    return [
        Document(
            page_content=page.extract_text() or "",
            metadata={"source": str(path), "page": page_number},
        )
        for page_number, page in enumerate(reader.pages)
    ]


def _word_document(path: Path) -> list[Document]:
    """读取明确 Word 资料并转换为检索文档，仍保留受控来源路径。"""
    return [
        Document(
            page_content=docx2txt.process(str(path)) or "",
            metadata={"source": str(path)},
        )
    ]


def load_document(filepath):
    """将显式文件路径锚定到数据边界后按扩展名选择加载器，不支持的格式返回 False。"""
    path = document_path(filepath)
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return _text_document(path)
    if suffix == ".pdf":
        return _pdf_documents(path)
    if suffix in {".doc", ".docx"}:
        return _word_document(path)
    return False
