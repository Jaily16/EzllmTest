import asyncio

from service.agentContracts import TrustedProjectScope
from service.agentInternalToolAdapter import InternalAgentToolAdapter
from service.agentToolExecutor import AgentToolExecutor, ToolInvocationContext
from service.agentToolSchemas import ToolExecutionResult, ToolExecutionStatus


class _FakeExecutor(AgentToolExecutor):
    def __init__(self):
        self.calls = []

    async def execute(self, tool_name, arguments, context):
        self.calls.append((tool_name, arguments, context.project_scope.project_id))
        return ToolExecutionResult(
            tool_name=tool_name,
            status=ToolExecutionStatus.SUCCESS,
            data={"ok": True},
        )


def test_internal_adapter_shares_registry_and_delegates_without_http():
    executor = _FakeExecutor()
    adapter = InternalAgentToolAdapter(executor=executor)
    context = ToolInvocationContext(
        project_scope=TrustedProjectScope(
            project_id="project-a",
            actor_id="trusted-user",
            scope_version="v1",
        )
    )
    result = asyncio.run(
        adapter.invoke("project_setup_status", {}, context)
    )

    assert len(adapter.definitions()) == 22
    assert result.data == {"ok": True}
    assert executor.calls == [("project_setup_status", {}, "project-a")]
