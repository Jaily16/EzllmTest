import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "ez_back_dev/tests/fixtures/iteration4_aspect5_manifest_v1.json"


def _sha(path: Path) -> str:
    payload = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(payload).hexdigest().upper()


def test_aspect5_manifest_keeps_packages_and_protected_sources_frozen():
    manifest = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert manifest["package_manifests"] == {
        "ez_back_dev/requirements.txt": "54EB1002BA00AEE7F11546990EEF78EFB0A4AC52ED5F850AC1A119203E8969AD",
        "ez_front_dev/package.json": "769EC529E786375A8DCDB5FCE27C1A4A44D5DDEDC3B9946E2850DEA8477BD5C3",
        "ez_front_dev/package-lock.json": "C93CDE311DB8675A62A781E20F613DD291D049743CF30A684EE3B94EA074DEAA",
    }
    assert manifest["protected_sources"] == {
        "ez_back_dev/app/main.py": "DBEC0E6438CC0F96669B67F78B6B04CF96365BD2271C4A2485FF8E97BB3162E6",
        "ez_back_dev/app/routers.py": "A3DDD017C3D50B30ED6FD65A5138F7D8A8F70BA8245C788A1210155AD3FD30A1",
        "ez_back_dev/service/workflowCatalog.py": "E9265C343F3768CF7F924ACE0056E47D5471A5976826E55CAF230F81A9CAAC6A",
        "README.md": "71ADFD7358A4DFAF5F254CD5584BDB606C7CD4FFC0B045DB96F4391BAB7D8AFE",
        "docs/iteration-4-overview.md": "8E4FC33E3139E313BAA39E832D9D8CE765918383301E3135CFEB377BAB0DC786",
        "docs/iteration-4-prompts.md": "34653AEFBECB2B4ACAE22311930929E21AA0F4C25881E40404629B5AA3247C0D",
    }
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
