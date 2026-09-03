from pathlib import Path


from repo_paths import BACKEND_ROOT

SERVICE_ROOT = BACKEND_ROOT / "service"


def test_legacy_llm_services_do_not_route_by_project_overflow_or_14500():
    failures = []
    for path in sorted(SERVICE_ROOT.glob("llm*Service.py")):
        if path.name.endswith("StreamService.py"):
            continue
        source = path.read_text(encoding="utf-8")
        if ".overflow" in source or "get_project_type" in source or "14500" in source:
            failures.append(path.name)
    assert failures == []


def test_legacy_whole_corpus_services_share_the_policy_adapter():
    canonical_by_compatibility_name = {
        "llmAcceptanceTestService.py": SERVICE_ROOT / "legacy" / "acceptance.py",
        "llmApiTestService.py": SERVICE_ROOT / "legacy" / "api.py",
        "llmDatabaseTestService.py": SERVICE_ROOT / "legacy" / "database.py",
        "llmFunctionalTestService.py": SERVICE_ROOT / "legacy" / "functional.py",
        "llmIntegrationTestService.py": SERVICE_ROOT / "legacy" / "integration.py",
        "llmSummarizeService.py": SERVICE_ROOT / "legacy" / "summarize.py",
        "llmTestPlanService.py": SERVICE_ROOT / "workflow" / "test_plan.py",
        "llmUITestService.py": SERVICE_ROOT / "legacy" / "ui.py",
        "llmUnitTestService.py": SERVICE_ROOT / "legacy" / "unit.py",
    }
    missing_policy_adapter = [
        compatibility_name
        for compatibility_name, canonical_path in canonical_by_compatibility_name.items()
        if not canonical_path.is_file()
        or "invoke_exhaustive_document_analysis"
        not in canonical_path.read_text(encoding="utf-8")
    ]
    assert missing_policy_adapter == []
