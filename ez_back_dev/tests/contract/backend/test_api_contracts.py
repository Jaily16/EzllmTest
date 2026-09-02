from types import SimpleNamespace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.routers as routers
from app.main import app
from llm.provider import (
    LLMConfigurationError,
    LLMEmptyResponseError,
    LLMOutputParsingError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)


client = TestClient(app)
from repo_paths import REPO_ROOT as PROJECT_ROOT, canonical_document_path


def test_required_testing_workflow_routes_are_preserved():
    paths = app.openapi()["paths"]
    expected = {
        ("POST", "/project/add/{name}"),
        ("GET", "/project/login/{pid}"),
        ("POST", "/uploadFile/{pid}/{doctype}"),
        ("POST", "/project/info/add"),
        ("POST", "/project/info/update"),
        ("GET", "/project/info/{pid}/{info_type}"),
        ("GET", "/project/type/{pid}"),
        ("GET", "/project/type/analyze/{pid}"),
        ("GET", "/project/setup/status/{pid}"),
        ("POST", "/project/setup/finalize/{pid}"),
        ("GET", "/project/workflow/status/{pid}"),
        ("GET", "/project/llm/menu/analyze/{pid}"),
        ("GET", "/project/llm/menu/analyze/update/{pid}/{llm_name}"),
        ("POST", "/project/llm/menu/acquire"),
        ("GET", "/project/llm/plan/{pid}/{llm_name}"),
        ("PUT", "/project/llm/plan/update/{pid}/{llm_name}"),
        ("POST", "/project/llm/plan/stream"),
        ("POST", "/project/llm/workflow/stream"),
        ("GET", "/project/analysis/status/{pid}"),
        ("GET", "/project/llm/unit/menu/{pid}/{llm_name}"),
        ("GET", "/project/llm/unit/menu/update/{pid}/{llm_name}"),
        ("GET", "/project/llm/unit/info/{pid}/{name}/{llm_name}"),
        ("GET", "/project/llm/unit/knowledge/{pid}/{method_type}"),
        ("POST", "/project/llm/unit/case"),
        ("POST", "/project/llm/integration/menu"),
        ("GET", "/project/llm/integration/info/{pid}/{integration_type}/{name}"),
        ("GET", "/project/llm/integration/knowledge/{pid}/{strategy_type}"),
        ("POST", "/project/llm/integration/case"),
        ("GET", "/project/llm/api/info/{pid}"),
        ("POST", "/project/llm/api/case"),
        ("GET", "/project/llm/ui/info/{pid}"),
        ("POST", "/project/llm/ui/case"),
        ("GET", "/project/llm/db/info/{pid}"),
        ("POST", "/project/llm/db/case"),
        ("GET", "/project/llm/functional/info/{pid}"),
        ("POST", "/project/llm/functional/case"),
        ("GET", "/project/llm/nfunctional/info/{pid}"),
        ("POST", "/project/llm/nfunctional/case"),
        ("GET", "/project/llm/acceptance/info/{pid}"),
        ("POST", "/project/llm/acceptance/case"),
    }
    missing = {
        (method, path)
        for method, path in expected
        if path not in paths or method.lower() not in paths[path]
    }
    assert missing == set()


def _setup_status(stage="documents_ready"):
    data = {
        "pid": "Ez1",
        "project_exists": True,
        "stage": stage,
        "document_counts": {"knowledge": 1, "requirements": 1, "design": 1},
        "document_files": {
            "knowledge": ["knowledge.txt"],
            "requirements": ["requirements.txt"],
            "design": ["design.txt"],
        },
        "allowed_actions": ["continue_to_plan"] if stage == "setup_complete" else ["finalize"],
        "source_revision": "rev-1",
        "message": "项目资料已确认" if stage == "setup_complete" else "项目资料已齐全，可以确认创建",
    }
    return SimpleNamespace(model_dump=lambda mode="python": data)


def test_project_setup_routes_keep_legacy_envelopes(monkeypatch):
    monkeypatch.setattr(
        routers.projectSetupService, "get_status", lambda _pid: _setup_status()
    )
    monkeypatch.setattr(
        routers.projectSetupService,
        "finalize",
        lambda _pid: _setup_status("setup_complete"),
    )

    status_response = client.get("/project/setup/status/Ez1")
    finalize_response = client.post("/project/setup/finalize/Ez1")

    assert status_response.status_code == 200
    assert status_response.json()["status"] == 2001
    assert status_response.json()["data"]["stage"] == "documents_ready"
    assert finalize_response.status_code == 200
    assert finalize_response.json()["status"] == 2001
    assert finalize_response.json()["data"]["stage"] == "setup_complete"


def test_project_workflow_status_route_keeps_legacy_envelope(monkeypatch):
    data = {
        "pid": "Ez1",
        "stage": "analysis_ready",
        "allowed_routes": ["/plan", "/menu", "/ui"],
        "completed_operations": ["project_analysis"],
        "stale_operations": [],
        "menu": {"ui_test": True},
        "source_revision": "rev-1",
        "message": "项目分析已就绪，可以开始测试",
    }
    service = SimpleNamespace(
        get_project_workflow_status=lambda _pid: SimpleNamespace(
            model_dump=lambda mode="python": data
        )
    )
    monkeypatch.setattr(
        routers, "projectWorkflowStatusService", service, raising=False
    )

    response = client.get("/project/workflow/status/Ez1")

    assert response.status_code == 200
    assert response.json() == {
        "status": 2001,
        "reason": "项目工作流状态获取成功",
        "data": data,
    }


def test_project_setup_finalize_maps_missing_documents_to_422(monkeypatch):
    from service.projectSetupService import (
        ProjectSetupStatus,
        ProjectSetupValidationError,
    )

    status = ProjectSetupStatus(
        pid="Ez1",
        project_exists=True,
        stage="requirements_uploaded",
        document_counts={"knowledge": 1, "requirements": 1, "design": 0},
        document_files={"knowledge": [], "requirements": [], "design": []},
        allowed_actions=["upload_design"],
        source_revision=None,
        message="请补充开发设计文档",
    )

    def fail(_pid):
        raise ProjectSetupValidationError("请补充开发设计文档", status)

    monkeypatch.setattr(routers.projectSetupService, "finalize", fail)

    response = client.post("/project/setup/finalize/Ez1")

    assert response.status_code == 422
    assert response.json()["status"] == 5001
    assert response.json()["reason"] == "请补充开发设计文档"
    assert response.json()["data"]["document_counts"]["knowledge"] == 1


@pytest.mark.parametrize(
    "path", ["/project/type/Ez1", "/project/type/analyze/Ez1"]
)
def test_project_type_legacy_path_and_planned_alias_match(monkeypatch, path):
    monkeypatch.setattr(
        routers.projectSetupService, "analyze_project_type", lambda _pid: 0
    )

    response = client.get(path)

    assert response.status_code == 200
    assert response.json() == {
        "status": 2001,
        "reason": "成功分析并建立项目",
        "data": -1,
    }


@pytest.mark.parametrize(
    ("function_name", "method", "path", "json_body"),
    [
        ("get_test_menu", "post", "/project/llm/menu/acquire", {"summary": "s"}),
        ("generate_test_plan", "get", "/project/llm/plan/p/GLM-4.7", None),
        ("summarize_unit_info", "get", "/project/llm/unit/menu/p/GLM-4.7", None),
        (
            "get_integration_test_info",
            "post",
            "/project/llm/integration/menu",
            {"summary": "s"},
        ),
        ("find_out_apis_info", "get", "/project/llm/api/info/p", None),
        ("find_out_ui_info", "get", "/project/llm/ui/info/p", None),
        ("find_out_database_info", "get", "/project/llm/db/info/p", None),
        ("find_out_use_cases_info", "get", "/project/llm/functional/info/p", None),
        (
            "find_out_nonfunctional_info",
            "get",
            "/project/llm/nfunctional/info/p",
            None,
        ),
        ("find_out_requirement_info", "get", "/project/llm/acceptance/info/p", None),
    ],
)
def test_each_testing_workflow_keeps_success_envelope(
    monkeypatch, function_name, method, path, json_body
):
    monkeypatch.setattr(routers, function_name, lambda *args, **kwargs: {"ok": True})

    response = client.request(method, path, json=json_body)

    assert response.status_code == 200
    assert response.json()["status"] == 2001
    assert response.json()["data"] == {"ok": True}


def test_case_request_models_keep_existing_fields():
    from model.HttpModel import (
        AcceptanceTestInvokeModel,
        ApiTestInvokeModel,
        DBTestInvokeModel,
        FunctionalTestInvokeModel,
        IntegrationTestInvokeModel,
        NFunctionalTestInvokeModel,
        UITestInvokeModel,
        UnitTestInvokeModel,
    )

    expected_fields = {
        UnitTestInvokeModel: {
            "unit_test_knowledge",
            "static_method",
            "unit_test_method_knowledge",
            "unit",
            "unit_info",
            "output_type",
            "llm_name",
        },
        IntegrationTestInvokeModel: {
            "integration_test_knowledge",
            "strategy",
            "strategy_knowledge",
            "blackbox_method_knowledge",
            "integration_object",
            "integration_object_info",
            "output_type",
        },
        ApiTestInvokeModel: {"pid", "info", "test_type", "output_type", "api_name"},
        UITestInvokeModel: {"pid", "info"},
        DBTestInvokeModel: {"pid", "info"},
        FunctionalTestInvokeModel: {
            "pid",
            "info",
            "test_type",
            "output_type",
            "use_case_name",
        },
        NFunctionalTestInvokeModel: {"pid", "info", "method_name"},
        AcceptanceTestInvokeModel: {"pid", "info"},
    }

    for model, fields in expected_fields.items():
        assert set(model.model_fields) == fields


@pytest.mark.parametrize(
    ("function_name", "path", "body"),
    [
        (
            "generate_test_cases",
            "/project/llm/unit/case",
            {
                "unit_test_knowledge": "k",
                "static_method": "m",
                "unit_test_method_knowledge": "mk",
                "unit": "u",
                "unit_info": "i",
                "output_type": 0,
                "llm_name": "GLM-4.7",
            },
        ),
        (
            "generate_integration_test_cases",
            "/project/llm/integration/case",
            {
                "integration_test_knowledge": "k",
                "strategy": "s",
                "strategy_knowledge": "sk",
                "blackbox_method_knowledge": "bk",
                "integration_object": "o",
                "integration_object_info": "i",
                "output_type": 0,
            },
        ),
        (
            "generate_api_test_cases",
            "/project/llm/api/case",
            {"pid": "p", "info": "i", "test_type": 0, "output_type": 0, "api_name": ""},
        ),
        ("generate_ui_test_cases", "/project/llm/ui/case", {"pid": "p", "info": "i"}),
        ("generate_db_test_cases", "/project/llm/db/case", {"pid": "p", "info": "i"}),
        (
            "generate_functional_test_cases",
            "/project/llm/functional/case",
            {
                "pid": "p",
                "info": "i",
                "test_type": 0,
                "output_type": 0,
                "use_case_name": "",
            },
        ),
        (
            "generate_nonfunctional_test_cases",
            "/project/llm/nfunctional/case",
            {"pid": "p", "info": "i", "method_name": "m"},
        ),
        (
            "generate_acceptance_test_cases",
            "/project/llm/acceptance/case",
            {"pid": "p", "info": "i"},
        ),
    ],
)
def test_each_case_route_accepts_legacy_body_and_keeps_envelope(
    monkeypatch, function_name, path, body
):
    monkeypatch.setattr(routers, function_name, lambda *args, **kwargs: "generated")

    response = client.post(path, json=body)

    assert response.status_code == 200
    assert response.json()["status"] == 2001
    assert response.json()["data"] == "generated"


def test_success_envelope_remains_compatible(monkeypatch):
    monkeypatch.setattr(
        routers,
        "summarize_unit_info",
        lambda pid, llm_name: {"text_info": "ok", "list_info": {}},
    )

    response = client.get("/project/llm/unit/menu/project/GLM-4.7")

    assert response.status_code == 200
    assert response.json() == {
        "status": 2001,
        "reason": "单元测试类型分析完成",
        "data": {"text_info": "ok", "list_info": {}},
    }


def test_plan_stream_route_keeps_sse_event_contract(monkeypatch):
    async def fake_stream(*_args, **_kwargs):
        yield {
            "event": "meta",
            "data": {
                "request_id": "request-id",
                "label": "DeepSeek",
                "provider": "deepseek",
                "model": "deepseek-v4-flash",
            },
        }
        yield {"event": "answer_delta", "data": {"text": "测试计划"}}
        yield {
            "event": "completed",
            "data": {"saved": True, "from_cache": False},
        }

    monkeypatch.setattr(routers, "stream_test_plan", fake_stream)

    response = client.post(
        "/project/llm/plan/stream",
        json={"pid": "p", "llm_name": "DeepSeek", "regenerate": True},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: meta\n" in response.text
    assert "event: answer_delta\n" in response.text
    assert "event: completed\n" in response.text
    assert '"text":"测试计划"' in response.text


def test_project_analysis_status_returns_persisted_readiness(monkeypatch):
    monkeypatch.setattr(routers.testProjectDao, "find_project", lambda _pid: object())

    async def fake_status(_pid):
        return {
            "summary_ready": True,
            "plan_ready": True,
            "menu_ready": True,
            "ready": True,
            "menu": {"test_plan": True},
        }

    monkeypatch.setattr(routers, "get_project_analysis_status", fake_status)

    response = client.get("/project/analysis/status/p")

    assert response.status_code == 200
    assert response.json()["status"] == 2001
    assert response.json()["data"]["ready"] is True


def test_generic_workflow_stream_route_keeps_sse_contract(monkeypatch):
    async def fake_stream(*_args, **_kwargs):
        yield {"event": "progress", "data": {"stage": "rag", "percent": 50}}
        yield {"event": "reasoning_delta", "data": {"text": "思考"}}
        yield {"event": "answer_delta", "data": {"text": "测试用例"}}
        yield {"event": "result", "data": {"result": {"test_cases": "测试用例"}}}
        yield {"event": "completed", "data": {"saved": True}}

    monkeypatch.setattr(routers, "stream_llm_workflow", fake_stream)

    response = client.post(
        "/project/llm/workflow/stream",
        json={
            "operation": "ui_case",
            "pid": "p",
            "llm_name": "DeepSeek",
            "payload": {"info": "ui info"},
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: progress\n" in response.text
    assert "event: reasoning_delta\n" in response.text
    assert "event: answer_delta\n" in response.text
    assert "event: result\n" in response.text


def test_generic_workflow_stream_masks_unexpected_exception_details(monkeypatch):
    async def failing_stream(*_args, **_kwargs):
        raise RuntimeError("secret-upstream-body")
        yield

    monkeypatch.setattr(routers, "stream_llm_workflow", failing_stream)

    response = client.post(
        "/project/llm/workflow/stream",
        json={
            "operation": "ui_case",
            "pid": "p",
            "llm_name": "DeepSeek",
            "payload": {"info": "ui info"},
        },
    )

    assert response.status_code == 200
    assert "event: error\n" in response.text
    assert '"code":"internal_error"' in response.text
    assert "大模型任务执行失败，请稍后重试" in response.text
    assert "secret-upstream-body" not in response.text


def test_plan_stream_masks_unexpected_exception_details(monkeypatch):
    async def failing_stream(*_args, **_kwargs):
        raise RuntimeError("secret-upstream-body")
        yield

    monkeypatch.setattr(routers, "stream_test_plan", failing_stream)

    response = client.post(
        "/project/llm/plan/stream",
        json={"pid": "p", "llm_name": "GLM-4.7", "regenerate": True},
    )

    assert response.status_code == 200
    assert "event: error\n" in response.text
    assert '"code":"internal_error"' in response.text
    assert "secret-upstream-body" not in response.text


def test_illegal_model_uses_compatible_error_envelope():
    response = client.get("/project/llm/unit/menu/project/not-supported")

    assert response.status_code == 400
    assert response.json()["status"] == 5401
    assert response.json()["data"] is False
    assert "Supported models" in response.json()["reason"]


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (LLMConfigurationError("DASHSCOPE_API_KEY is not configured"), 503),
        (LLMTimeoutError("通义千问 request timed out"), 504),
        (LLMRateLimitError("通义千问 request was rate limited"), 429),
        (LLMOutputParsingError("invalid structured output"), 502),
        (LLMEmptyResponseError("通义千问 returned an empty response"), 502),
        (LLMProviderError("通义千问 provider request failed"), 502),
    ],
)
def test_typed_llm_errors_have_deterministic_http_mapping(
    monkeypatch, error, expected_status
):
    def fail(_pid, _llm_name):
        raise error

    monkeypatch.setattr(routers, "summarize_unit_info", fail)

    response = client.get("/project/llm/unit/menu/project/通义千问")

    assert response.status_code == expected_status
    assert response.json() == {
        "status": 5401,
        "reason": str(error),
        "data": False,
    }


def test_iteration2_release_uses_one_schema_only_sql_file():
    schema = (PROJECT_ROOT / "ezllmtest.sql").read_text(encoding="utf-8")
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    closeout = canonical_document_path("docs/iteration-2-closeout.md").read_text(
        encoding="utf-8"
    )

    assert "CREATE TABLE `tb_project_workflow_artifact`" in schema
    for legacy_table in (
        "tb_test_project",
        "tb_project_knowledge",
        "tb_project_requirement_testdoc",
        "tb_project_design_testdoc",
        "tb_project_type",
        "tb_project_info",
    ):
        assert legacy_table in closeout
    assert "唯一的数据库结构文件" in readme
    assert not (PROJECT_ROOT / "ez_back_dev" / "migrations").exists()
    assert "mysql -u root -p ezllmtest_dev < ezllmtest.sql" in readme
    assert "未执行" in closeout
    assert "仓库中不再保留独立迁移目录" in closeout
