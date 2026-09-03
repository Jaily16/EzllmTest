from __future__ import annotations

import asyncio
import threading

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from vectorstore import indexRegistry as registry


class CountingEmbeddings(Embeddings):
    def __init__(self, model_name: str = "mock-embedding") -> None:
        self.model_name = model_name
        self.document_call_count = 0
        self._lock = threading.Lock()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        with self._lock:
            self.document_call_count += 1
        return [[1.0, float(index + 1)] for index, _text in enumerate(texts)]

    def embed_query(self, _text: str) -> list[float]:
        return [1.0, 1.0]


def _documents(label: str = "alpha") -> list[Document]:
    return [
        Document(
            page_content=f"{label} project content",
            metadata={"source": f"{label}.md", "page": 3},
        )
    ]


def setup_function() -> None:
    registry._reset_index_registry_for_tests()


def teardown_function() -> None:
    registry._reset_index_registry_for_tests()


def test_concurrent_identical_requests_build_one_index():
    embeddings = CountingEmbeddings()

    async def execute():
        return await asyncio.gather(
            *(
                registry.get_project_index(
                    "Ez1", "design", "rev-1", _documents(), embeddings
                )
                for _index in range(5)
            )
        )

    indexes = asyncio.run(execute())

    assert embeddings.document_call_count == 1
    assert all(index is indexes[0] for index in indexes)
    assert registry.index_registry_size() == 1


def test_registry_isolates_projects_revisions_corpora_and_embedding_models():
    first_model = CountingEmbeddings("embedding-a")
    second_model = CountingEmbeddings("embedding-b")

    async def execute():
        first = await registry.get_project_index(
            "Ez1", "design", "rev-1", _documents("first"), first_model
        )
        different_project = await registry.get_project_index(
            "Ez2", "design", "rev-1", _documents("project"), first_model
        )
        different_revision = await registry.get_project_index(
            "Ez1", "design", "rev-2", _documents("revision"), first_model
        )
        different_corpus = await registry.get_project_index(
            "Ez1", "requirements", "rev-1", _documents("corpus"), first_model
        )
        different_model = await registry.get_project_index(
            "Ez1", "design", "rev-1", _documents("model"), second_model
        )
        return {
            id(first),
            id(different_project),
            id(different_revision),
            id(different_corpus),
            id(different_model),
        }

    identities = asyncio.run(execute())

    assert len(identities) == 5
    assert first_model.document_call_count == 4
    assert second_model.document_call_count == 1
    assert registry.index_registry_size() == 5


def test_project_invalidation_forces_one_rebuild_without_touching_other_projects():
    embeddings = CountingEmbeddings()

    async def build(pid: str):
        return await registry.get_project_index(
            pid, "knowledge", "rev-1", _documents(pid), embeddings
        )

    first = asyncio.run(build("Ez1"))
    other = asyncio.run(build("Ez2"))

    assert registry.invalidate_project_indexes("Ez1") == 1
    rebuilt = asyncio.run(build("Ez1"))
    other_again = asyncio.run(build("Ez2"))

    assert rebuilt is not first
    assert other_again is other
    assert embeddings.document_call_count == 3


def test_registry_enforces_lru_capacity():
    embeddings = CountingEmbeddings()

    async def execute():
        first = None
        for index in range(registry.INDEX_CAPACITY + 1):
            value = await registry.get_project_index(
                f"Ez{index}",
                "design",
                "rev-1",
                _documents(str(index)),
                embeddings,
            )
            if index == 0:
                first = value
        rebuilt = await registry.get_project_index(
            "Ez0", "design", "rev-1", _documents("0"), embeddings
        )
        return first, rebuilt

    first, rebuilt = asyncio.run(execute())

    assert registry.index_registry_size() == registry.INDEX_CAPACITY
    assert rebuilt is not first
    assert embeddings.document_call_count == registry.INDEX_CAPACITY + 2


def test_idle_ttl_expires_an_index(monkeypatch):
    embeddings = CountingEmbeddings()
    now = {"value": 100.0}
    monkeypatch.setattr(registry, "_clock", lambda: now["value"])

    async def build():
        return await registry.get_project_index(
            "Ez1", "requirements", "rev-1", _documents(), embeddings
        )

    first = asyncio.run(build())
    now["value"] += registry.INDEX_IDLE_TTL_SECONDS + 1
    rebuilt = asyncio.run(build())

    assert rebuilt is not first
    assert embeddings.document_call_count == 2


def test_empty_documents_do_not_call_embeddings():
    embeddings = CountingEmbeddings()

    index = asyncio.run(
        registry.get_project_index(
            "Ez1", "knowledge", "rev-1", [], embeddings
        )
    )

    assert index.document_count == 0
    assert embeddings.document_call_count == 0
