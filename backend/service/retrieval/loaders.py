from __future__ import annotations

from pathlib import Path

import docx2txt
from langchain_core.documents import Document
from pypdf import PdfReader


def _text_document(path: Path) -> list[Document]:
    """处理文本文档并返回现有契约规定的结果。"""
    return [
        Document(
            page_content=path.read_text(encoding="utf-8-sig"),
            metadata={"source": str(path)},
        )
    ]


def _pdf_documents(path: Path) -> list[Document]:
    """处理PDF文档并返回现有契约规定的结果。"""
    reader = PdfReader(str(path))
    return [
        Document(
            page_content=page.extract_text() or "",
            metadata={"source": str(path), "page": page_number},
        )
        for page_number, page in enumerate(reader.pages)
    ]


def _word_document(path: Path) -> list[Document]:
    """处理WORD文档并返回现有契约规定的结果。"""
    return [
        Document(
            page_content=docx2txt.process(str(path)) or "",
            metadata={"source": str(path)},
        )
    ]


def load_document(filepath):
    """加载文档，并遵循现有调用契约。"""
    path = Path(filepath)
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return _text_document(path)
    if suffix == ".pdf":
        return _pdf_documents(path)
    if suffix in {".doc", ".docx"}:
        return _word_document(path)
    return False
