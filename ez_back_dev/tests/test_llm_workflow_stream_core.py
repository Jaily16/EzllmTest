import asyncio
import json

from model.ChainJsonModel import ApiList
from llm.streaming import ModelStreamEvent, TokenUsage
from service import llmWorkflowStreamCore as core


def test_stream_model_call_forwards_reasoning_content_and_usage(monkeypatch):
    async def fake_stream(*_args, **_kwargs):
        yield ModelStreamEvent("reasoning", text="thinking")
        yield ModelStreamEvent("content", text="answer")
        yield ModelStreamEvent("usage", usage=TokenUsage(2, 1, 3, 6))

    monkeypatch.setattr(core, "stream_chat_completion", fake_stream)
    context = core.WorkflowContext("p", "DeepSeek", "api_info", {})

    async def collect():
        return [
            item
            async for item in core.stream_model_call(
                context,
                "prompt",
                stage="generate",
                label="生成",
                output_event="answer_delta",
            )
        ]

    events = asyncio.run(collect())

    assert [item["event"] for item in events] == [
        "reasoning_delta",
        "answer_delta",
        "_model_completed",
    ]
    assert events[-1]["data"]["content"] == "answer"
    assert core.aggregate_usage(context) == TokenUsage(2, 1, 3, 6).as_dict()


def test_parse_structured_result_accepts_fenced_json():
    content = f"```json\n{json.dumps({'api_list': ['/v1']})}\n```"

    result = core.parse_structured_result(content, ApiList)

    assert result.api_list == ["/v1"]


def test_require_helpers_reject_missing_payload_values():
    try:
        core.require_string({}, "name")
    except core.WorkflowStreamError as error:
        assert error.code == "invalid_payload"
        assert error.status == 422
    else:
        raise AssertionError("missing string must fail")
