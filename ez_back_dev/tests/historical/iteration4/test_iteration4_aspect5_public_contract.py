from pathlib import Path

from service.agentWorkbenchContracts import public_capabilities
from service.agentToolSchemas import ToolExecutionResult


from repo_paths import canonical_frontend_path
from repo_paths import REPO_ROOT as ROOT


def test_capabilities_publish_agent_only_metadata_citation_policy():
    retrieval = public_capabilities()["retrieval"]
    assert retrieval == {
        "strategy": "dense_v1",
        "policy_version": "iteration4-aspect5-v1",
        "citation_mode": "metadata_only",
        "rerank_enabled": False,
        "agent_only": True,
    }


def test_mcp_shared_output_schema_adds_optional_retrieval_evidence():
    schema = ToolExecutionResult.model_json_schema(mode="serialization")
    assert "retrieval_evidence" in schema["properties"]
    assert "retrieval_evidence" not in schema.get("required", [])


def test_workbench_uses_typed_plain_text_metadata_citations_only():
    state = canonical_frontend_path("ez_front_dev/src/state/agentWorkbench.ts").read_text(
        encoding="utf-8"
    )
    view = canonical_frontend_path("ez_front_dev/src/components/AgentWorkbench.vue").read_text(
        encoding="utf-8"
    )
    assert "interface AgentRetrievalCitation" in state
    assert "retrieval_evidence" in state
    assert "citation.source_label" in view
    assert "citation.page" in view
    assert "citation.rank" in view
    assert "citation.chunk_hash" in view
    assert "v-html" not in view
    assert "citation.page_content" not in view
