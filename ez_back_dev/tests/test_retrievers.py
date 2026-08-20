from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from vectorstore.retrievers import design_retriever


class KeywordEmbeddings(Embeddings):
    def _vector(self, text: str) -> list[float]:
        lowered = text.lower()
        return [
            float("alpha" in lowered),
            float("beta" in lowered),
            float("shared" in lowered),
        ]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


def test_design_retrievers_are_project_scoped():
    project_a = design_retriever(
        [Document(page_content="alpha shared project A")],
        embedding_model=KeywordEmbeddings(),
    )
    project_b = design_retriever(
        [Document(page_content="beta shared project B")],
        embedding_model=KeywordEmbeddings(),
    )

    a_contents = [doc.page_content for doc in project_a.invoke("alpha")]
    b_contents = [doc.page_content for doc in project_b.invoke("beta")]

    assert a_contents == ["alpha shared project A"]
    assert b_contents == ["beta shared project B"]
    assert all("project B" not in content for content in a_contents)
    assert all("project A" not in content for content in b_contents)


def test_empty_project_does_not_require_embeddings():
    retriever = design_retriever([])

    assert retriever.invoke("anything") == []
