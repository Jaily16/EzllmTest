from service import llmTestPlanService as service


def test_regenerated_plan_uses_long_task_timeout_without_network(monkeypatch):
    selected_models = []
    updated_rows = []
    fake_llm = object()

    monkeypatch.setattr(
        service.testProjectDao,
        "get_project_type",
        lambda _pid: type("ProjectType", (), {"overflow": 0})(),
    )
    monkeypatch.setattr(
        service,
        "choose_llm_by_name",
        lambda name, minimum_timeout_seconds: (
            selected_models.append((name, minimum_timeout_seconds)) or fake_llm
        ),
    )
    monkeypatch.setattr(
        service.documentTools,
        "generate_require_testdocs_str",
        lambda _pid: "project requirements",
    )
    monkeypatch.setattr(
        service.BasicChain,
        "invoke_stuff_chain_get_str_with_str",
        lambda _prompt, _content, llm: "generated plan" if llm is fake_llm else "",
    )
    monkeypatch.setattr(
        service.testProjectDao,
        "update_project_info",
        lambda *args: updated_rows.append(args),
    )

    result = service.generate_test_plan_again("project-id", "DeepSeek")

    assert result == "generated plan"
    assert selected_models == [
        ("DeepSeek", service.TEST_PLAN_MINIMUM_TIMEOUT_SECONDS)
    ]
    assert updated_rows == [
        ("project-id", service.InfoType.PROJECT_TEST_PLAN.value, "generated plan")
    ]
