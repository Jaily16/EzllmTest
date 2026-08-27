from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _read(name: str) -> str:
    return (PROJECT_ROOT / "docs" / name).read_text(encoding="utf-8")


def test_agent_adr_locks_the_approved_runtime_and_boundaries():
    adr = _read("iteration-4-agent-architecture-adr.md")

    for required in (
        "Accepted for Aspect 1 contracts; runtime adoption deferred",
        "Python 3.11",
        "FastAPI",
        "LangGraph",
        "single Agent",
        "workflow catalog",
        "application service layer",
        "must not call itself through HTTP or MCP",
        "MySQL",
        "Redis",
        "Agent thread/checkpoint",
        "loopback MCP",
        "127.0.0.1",
        "chain-of-thought",
        "JSON",
        "no arbitrary file, Shell, network, SQL, or dynamic Python tool",
        "trusted runtime",
        "zero approval bypass",
        "zero duplicate side effects",
        "zero cross-project leakage",
    ):
        assert required in adr


def test_measurement_protocol_defines_dataset_metrics_and_relative_gates():
    protocol = _read("iteration-4-measurement-protocol.md")

    for required in (
        "iteration4_agent_eval_v1.json",
        "deterministic_fake",
        "seed 20260827",
        "5 warm-ups",
        "30 measured samples",
        "nearest-rank",
        "p50",
        "p95",
        "TTFE",
        "throughput",
        "estimated_cost_units",
        "1.15",
        "5%",
        "runtime_not_installed",
        "no claimed improvement",
    ):
        assert required in protocol


def test_compatibility_matrix_is_explicit_about_static_only_validation():
    matrix = _read("iteration-4-compatibility-matrix.md")

    for required in (
        "LangGraph 1.2.11",
        "langgraph-checkpoint-redis 0.5.2",
        "MCP Python SDK 2.1.1",
        "RedisJSON",
        "RediSearch",
        "Streamable HTTP",
        "protocol-only, install deferred",
        "No dependency was installed",
        "No integration test was run",
    ):
        assert required in matrix


def test_baseline_document_records_user_assets_and_manifests():
    baseline = _read("iteration-4-aspect-1-baseline.md")

    for required in (
        "3c49e864a523a4af4c0f3efd4f845e8ce7b1caed",
        "README.md",
        "iteration-4-overview.md",
        "iteration-4-prompts.md",
        "19 workflows",
        "180 passed in 5.13s",
        "131F71733433D2806083756DFB2B5E315B66A678E304EBA6EB3E82FF0F4C7FEF",
        "769EC529E786375A8DCDB5FCE27C1A4A44D5DDEDC3B9946E2850DEA8477BD5C3",
        "C93CDE311DB8675A62A781E20F613DD291D049743CF30A684EE3B94EA074DEAA",
    ):
        assert required in baseline
