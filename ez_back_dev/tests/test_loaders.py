from zipfile import ZIP_DEFLATED, ZipFile

from pypdf import PdfWriter

from vectorstore.loader import load_document


def test_text_and_markdown_loaders_preserve_source_and_unicode(tmp_path):
    text_path = tmp_path / "requirement.txt"
    markdown_path = tmp_path / "knowledge.md"
    text_path.write_text("中文需求", encoding="utf-8-sig")
    markdown_path.write_text("# 测试知识", encoding="utf-8")

    text_doc = load_document(text_path)[0]
    markdown_doc = load_document(markdown_path)[0]

    assert text_doc.page_content == "中文需求"
    assert text_doc.metadata["source"] == str(text_path)
    assert markdown_doc.page_content == "# 测试知识"
    assert markdown_doc.metadata["source"] == str(markdown_path)


def test_pdf_loader_returns_one_document_per_page(tmp_path):
    pdf_path = tmp_path / "empty-pages.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_blank_page(width=72, height=72)
    with pdf_path.open("wb") as stream:
        writer.write(stream)

    documents = load_document(pdf_path)

    assert len(documents) == 2
    assert [doc.metadata["page"] for doc in documents] == [0, 1]
    assert all(doc.metadata["source"] == str(pdf_path) for doc in documents)


def test_docx_loader_uses_local_document_xml(tmp_path):
    docx_path = tmp_path / "design.docx"
    document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body><w:p><w:r><w:t>local design content</w:t></w:r></w:p></w:body>
</w:document>"""
    with ZipFile(docx_path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", document_xml)

    document = load_document(docx_path)[0]

    assert "local design content" in document.page_content
    assert document.metadata["source"] == str(docx_path)


def test_unknown_document_extension_keeps_legacy_false_result(tmp_path):
    unsupported_path = tmp_path / "data.bin"
    unsupported_path.write_bytes(b"data")

    assert load_document(unsupported_path) is False
