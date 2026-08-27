import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "ez_back_dev/tests/fixtures/iteration4_aspect5_manifest_v1.json"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def test_aspect5_manifest_keeps_packages_and_protected_sources_frozen():
    manifest = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert manifest["package_manifests"] == {
        "ez_back_dev/requirements.txt": "54EB1002BA00AEE7F11546990EEF78EFB0A4AC52ED5F850AC1A119203E8969AD",
        "ez_front_dev/package.json": "769EC529E786375A8DCDB5FCE27C1A4A44D5DDEDC3B9946E2850DEA8477BD5C3",
        "ez_front_dev/package-lock.json": "C93CDE311DB8675A62A781E20F613DD291D049743CF30A684EE3B94EA074DEAA",
    }
    for relative, expected in manifest["protected_sources"].items():
        if relative not in {
            "README.md",
            "docs/iteration-4-overview.md",
            "docs/iteration-4-prompts.md",
        }:
            assert _sha(ROOT / relative) == expected
    parent = ROOT / "ez_back_dev/tests/fixtures" / manifest["parent"]["fixture"]
    assert _sha(parent) == manifest["parent"]["fixture_sha256"]
    assert manifest["approved_dependency_changes"] == []


def test_context_rag_document_freezes_memory_citations_and_dense_fallback():
    text = (
        ROOT / "docs/iteration-4-aspect-5-context-rag-contract.md"
    ).read_text(encoding="utf-8")
    for required in (
        "ContextBinding",
        "MySQL",
        "Redis thread evidence",
        "dense_v1",
        "hybrid_rrf_v1",
        "hybrid_rerank_v1",
        "metadata-only",
        "6,000",
        "N/A",
        "zero invalid citations/leaks",
    ):
        assert required in text
    lowered = text.lower()
    assert "chain-of-thought" not in lowered
    assert "v-html" in text
