from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1] / "service"


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
    expected = {
        "llmAcceptanceTestService.py",
        "llmApiTestService.py",
        "llmDatabaseTestService.py",
        "llmFunctionalTestService.py",
        "llmIntegrationTestService.py",
        "llmSummarizeService.py",
        "llmTestPlanService.py",
        "llmUITestService.py",
        "llmUnitTestService.py",
    }
    routed = {
        path.name
        for path in SERVICE_ROOT.glob("llm*Service.py")
        if "invoke_exhaustive_document_analysis" in path.read_text(encoding="utf-8")
    }
    assert expected <= routed
