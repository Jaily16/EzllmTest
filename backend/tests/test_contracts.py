"""核对旧实现实际注册清单，63 条 REST、19 workflows、22 tools 与 MCP 契约。"""
import json, pathlib, dataclasses
from unittest.mock import MagicMock

# 用人工装配对比固定路由、workflows、tools 和 MCP fixture，不进入应用 lifespan。
def test_iteration6_registered_contracts(tmp_path):
    import sqlalchemy

    from ezllmtest.platform import configuration
    configuration.install({"DATABASE_URL":"sqlite:///:memory:","AGENT_TELEMETRY_ENABLED":"false"},tmp_path)
    from ezllmtest.bootstrap.dependencies import bind_persistence
    bind_persistence()
    from ezllmtest.bootstrap.product_app import create_product_app
    product=create_product_app()
    from ezllmtest.modules.agent.api.http import create_agent_api_app
    from ezllmtest.modules.observability.api.http import create_observability_app
    from ezllmtest.modules.observability.infrastructure.storage import ObservabilityStore
    from ezllmtest.modules.generation.domain.catalog import list_workflow_definitions
    from ezllmtest.modules.agent.runtime.tools.registry import DEFAULT_TOOL_REGISTRY
    from ezllmtest.modules.agent.api import mcp_adapter
    agent=create_agent_api_app(service=MagicMock(),project_exists=lambda p:True,allow_test_host=True)
    obs=create_observability_app(store=ObservabilityStore(tmp_path/"synthetic.sqlite3",retention_days=7,max_rows=100000),ingest_token="synthetic-only",allowed_origins=("http://localhost:8180",),health_probe=lambda:{})
    from fastapi.routing import APIRoute
    # 展开 FastAPI 延迟包含的 router，使契约比较覆盖最终注册的业务路由。
    def flatten(routes):
     for route in routes:
      if hasattr(route,"original_router"): yield from flatten(route.original_router.routes)
      else: yield route
    # 提取注册路由的方法、路径和请求 schema，与冻结的历史契约逐项比较。
    def contracts(app):
     rows=[]
     for r in flatten(app.routes):
      if isinstance(r,APIRoute):
       rows.append({"path":r.path,"methods":sorted(r.methods),"name":r.name,"status_code":r.status_code,"response_model":str(r.response_model),"body":r.body_field._type_adapter.json_schema() if r.body_field else None})
     return rows
    result={"routes":{name:contracts(app) for name,app in [("product",product),("agent",agent),("observability",obs)]},"workflows":[dataclasses.asdict(x) for x in list_workflow_definitions()],"tools":[{"name":t.name,"input":t.input_schema(),"output":t.output_schema(),"metadata":t.public_metadata()} for t in DEFAULT_TOOL_REGISTRY.definitions()],"mcp":{"catalog_uri":mcp_adapter.TOOL_CATALOG_URI,"policy_uri":mcp_adapter.APPROVAL_POLICY_URI,"name":mcp_adapter.MCP_SERVER_NAME,"version":mcp_adapter.MCP_SERVER_VERSION}}

    expected=json.loads((pathlib.Path(__file__).parent/"fixtures/iteration6-contracts.json").read_text(encoding="utf-8"))
    assert json.loads(json.dumps(result,default=str)) == expected
