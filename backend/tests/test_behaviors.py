"""使用内存替身验证流恢复、取消、审批、隔离与观测边界。"""
import asyncio
import json
import time
from types import SimpleNamespace
from unittest.mock import Mock
import httpx
import pytest

# 在同步测试中执行人工异步场景；外部依赖由测试的替身和隔离守卫阻断。
def run(awaitable):
    return asyncio.run(awaitable)

# 用内存上下文验证工具 scope、人工审批和 MCP 政策，禁止通过真实业务副作用证明安全。
def test_tool_scope_approval_and_mcp_policy():
    from ezllmtest.modules.agent.runtime.execution.executor import AgentToolExecutor, ToolServiceBindings, ToolInvocationContext
    from ezllmtest.modules.agent.domain.contracts import TrustedProjectScope
    from ezllmtest.modules.agent.api.mcp_adapter import _approval_policy_resource, _catalog_resource
    from ezllmtest.modules.agent.runtime.tools.registry import DEFAULT_TOOL_REGISTRY
    read=Mock(return_value={"ready":True})
    stream=Mock(side_effect=AssertionError("unapproved_execution"))
    executor=AgentToolExecutor(bindings=ToolServiceBindings(read,read,read,stream,stream))
    context=ToolInvocationContext(TrustedProjectScope(project_id="EzSynthetic",actor_id="offline",scope_version="v1"))
    result=run(executor.execute("project_setup_status",{},context))
    assert result.status.value=="success"
    read.assert_called_once_with("EzSynthetic")
    forged=run(executor.execute("project_setup_status",{"project_id":"EzOther"},context))
    assert forged.error.code=="invalid_arguments"
    unknown=run(executor.execute("absent",{},context))
    assert unknown.error.code=="unknown_tool"
    definition=next(d for d in DEFAULT_TOOL_REGISTRY.definitions() if d.operation=="project_analysis")
    approval=run(executor.execute(definition.name,{"model_label":"synthetic"},context))
    assert approval.error.code=="approval_required"
    stream.assert_not_called()
    policy=json.loads(_approval_policy_resource())
    assert policy["workflow_requires_approval"] and not policy["model_may_supply_scope"]
    assert len(json.loads(_catalog_resource(DEFAULT_TOOL_REGISTRY))["tools"])==22

# 构造成功、失败及取消流，确认旧有效结果不会被未完成的新草稿覆盖。
@pytest.mark.parametrize("mode",["cache","failure","empty","cancel"])
def test_stream_preserves_effective_result(mode,monkeypatch):
    from ezllmtest.modules.generation.application import stream
    from ezllmtest.modules.generation.schemas.errors import WorkflowStreamError
    from ezllmtest.modules.generation.domain.catalog import list_workflow_definitions
    definition=next(d for d in list_workflow_definitions() if d.phase=="analysis" and d.persistence=="artifact")
    key=SimpleNamespace(source_revision="r"*64,prompt_version=definition.prompt_version,model_label="synthetic")
    artifact=SimpleNamespace(key=key,result={"text_info":"saved"}) if mode=="cache" else None
    lookup=SimpleNamespace(key=key,artifact=artifact,stale=False,has_history=False)
    monkeypatch.setattr(stream,"get_stream_model_metadata",lambda _: {"label":"synthetic","provider":"offline","model":"offline"})
    monkeypatch.setattr(stream.testProjectDao,"find_project",lambda _:True)
    monkeypatch.setattr(stream.workflowArtifactService,"lookup_workflow_artifact",lambda *a:lookup)
    monkeypatch.setattr(stream.workflowArtifactService,"validate_workflow_prerequisites",lambda *a:None)
    save=Mock(side_effect=AssertionError("invalid_result_must_not_overwrite"))
    monkeypatch.setattr(stream.workflowArtifactService,"save_workflow_artifact",save)
    # 用失败、取消和不完整输出三种人工流验证旧有效产物不会被中途结果覆盖。
    async def generated(context):
        if mode=="failure": raise WorkflowStreamError("synthetic_failure","failed",status=502,retryable=True)
        if mode=="cancel": raise asyncio.CancelledError()
        yield {"event":"answer_delta","data":{"text":"partial"}}
    monkeypatch.setattr(stream,"stream_analysis_operation",generated)
    # 耗尽人工工作流事件流，使生成终止及保存边界在测试中实际执行。
    async def collect():
        return [event async for event in stream.stream_llm_workflow(definition.operation,"EzSynthetic","synthetic",{})]
    if mode=="cache":
        events=run(collect())
        assert events[-1]["event"]=="completed" and events[-1]["data"]["from_cache"]
        assert next(x for x in events if x["event"]=="result")["data"]["result"]=={"text_info":"saved"}
    elif mode=="cancel":
        with pytest.raises(asyncio.CancelledError): run(collect())
    else:
        with pytest.raises(WorkflowStreamError): run(collect())
    save.assert_not_called()

# 使用人工 HTTP 传输和临时 SQLite，验证 ingestion 鉴权、字段脱敏及保留策略。
def test_observation_auth_redaction_and_retention(tmp_path):
    from ezllmtest.modules.observability.infrastructure.storage import ObservabilityStore
    from ezllmtest.modules.observability.api.http import create_observability_app
    from ezllmtest.platform.telemetry.contracts import SpanRecord
    store=ObservabilityStore(tmp_path/"synthetic.sqlite3",retention_days=7,max_rows=100000)
    store.open()
    try:
        now=int(time.time()*1000)
        record=dict(trace_id="1"*32,span_id="2"*16,service="offline",name="agent.run",started_at_ms=now,ended_at_ms=now,duration_ms=0.0)
        from pydantic import ValidationError
        with pytest.raises(ValidationError): SpanRecord(**record,attributes={"prompt":"synthetic-private"})
        store.insert_spans([SpanRecord(**record)])
        assert store.counts()["spans"]==1
        app=create_observability_app(store=store,ingest_token="synthetic-memory-only",allowed_origins=("http://localhost:8180",),health_probe=lambda:{})
        # 通过内存 ASGI transport 验证缺失或错误 token 被拒绝、人工事件可投递且敏感字段不回显。
        async def exercise():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://127.0.0.1:8140") as client:
                for headers in ({},{"X-EzllmTest-Ingest-Token":"wrong"}):
                    response=await client.post("/internal/v1/telemetry/spans",json={"records":[record]},headers=headers)
                    assert response.status_code==403
                response=await client.post("/internal/v1/telemetry/spans",json={"records":[record]},headers={"X-EzllmTest-Ingest-Token":"synthetic-memory-only"})
                assert response.status_code==202
                response=await client.post("/internal/v1/telemetry/spans",json={"records":[{**record,"attributes":{"prompt":"synthetic-private"}}]},headers={"X-EzllmTest-Ingest-Token":"synthetic-memory-only"})
                assert response.status_code==422
                assert "synthetic-private" not in response.text
        run(exercise())
        store.cleanup(now_ms=now+8*86400000)
        assert store.counts()["spans"]==0
        assert store.max_rows==100000 and store.retention_days==7
    finally:
        store.close()

# 模拟遥测鉴权失败，确认凭据缓存失效且异常不传播为产品失败。
def test_telemetry_auth_failure_invalidates_without_business_error(monkeypatch):
    from ezllmtest.platform.telemetry import local_export
    import urllib.error
    credentials=Mock();credentials.get.return_value="synthetic-memory-only"
    monkeypatch.setattr(local_export,"token_provider",lambda:credentials)
    transport=local_export.LocalTelemetryTransport("http://127.0.0.1:49990","",timeout_ms=20)
    transport.opener=Mock()
    transport.opener.open.side_effect=urllib.error.HTTPError("http://127.0.0.1",403,"forbidden",{},None)
    assert transport.post("spans",[{}]) is False
    credentials.invalidate.assert_called_once()
