import asyncio
import json
from types import SimpleNamespace

from model.ChainJsonModel import ApiList
from llm.streaming import ModelStreamEvent, TokenUsage
from service import llmWorkflowStreamCore as core
from tools.documentTools import num_tokens_from_string


def test_stream_model_call_forwards_reasoning_content_and_usage(monkeypatch):
    requests = []

    async def fake_stream(name, prompt, max_tokens, **kwargs):
        requests.append((name, prompt, max_tokens, kwargs))
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
    assert requests[0][2] == 8_192
    assert requests[0][3]["request_options"]["reasoning_effort"] == "high"


def test_structured_call_bounds_context_and_emits_sanitized_progress(
    monkeypatch,
):
    requests = []

    async def fake_stream(_name, prompt, max_tokens, **kwargs):
        requests.append((prompt, max_tokens, kwargs))
        yield ModelStreamEvent("content", text="answer")

    monkeypatch.setattr(core, "stream_chat_completion", fake_stream)
    context = core.WorkflowContext("p", "通义千问", "api_info", {})
    oversized = "context-token " * 20_000

    async def collect():
        return [
            item
            async for item in core.stream_model_call(
                context,
                oversized,
                stage="api_info_structured",
                label="提取接口",
            )
        ]

    events = asyncio.run(collect())
    prompt_text, max_tokens, kwargs = requests[0]
    reduction = next(
        item for item in events if item["event"] == "progress"
    )

    assert num_tokens_from_string(prompt_text) <= 32_000
    assert max_tokens <= 2_048
    assert kwargs["request_options"]["extra_body"] == {
        "enable_thinking": False
    }
    assert "context-token" not in str(reduction["data"])
    assert reduction["data"]["current"] <= reduction["data"]["total"]


def test_stream_model_call_preserves_instruction_when_context_is_reduced(
    monkeypatch,
):
    requests = []

    async def fake_stream(_name, prompt, _max_tokens, **_kwargs):
        requests.append(prompt)
        yield ModelStreamEvent("content", text="answer")

    monkeypatch.setattr(core, "stream_chat_completion", fake_stream)
    monkeypatch.setattr(
        core,
        "effective_context_budget",
        lambda *_args: 20,
        raising=False,
    )
    context = core.WorkflowContext("p", "GLM-4.7", "api_info", {})

    async def collect():
        return [
            item
            async for item in core.stream_model_call(
                context,
                "",
                instruction_text="REQUIRED_SCHEMA",
                context_text="evidence " * 200,
                stage="api_info_structured",
                label="提取接口",
            )
        ]

    asyncio.run(collect())

    assert requests[0].startswith("REQUIRED_SCHEMA\n\n")
    assert requests[0].count("REQUIRED_SCHEMA") == 1


def test_partition_texts_within_budget_preserves_every_input_marker():
    values = [f"marker-{index} value" for index in range(20)]

    batches = core.partition_texts_within_budget(
        values,
        6,
        token_counter=lambda value: len(value.split()),
    )

    flattened = "\n\n".join(part for batch in batches for part in batch)
    assert len(batches) > 1
    assert all(f"marker-{index}" in flattened for index in range(20))


def test_split_documents_within_budget_preserves_middle_evidence():
    document = SimpleNamespace(
        page_content="HEAD " + "middle " * 100 + "TAIL",
        metadata={"source": "fixture"},
    )

    chunks = core.split_documents_within_budget(
        [document],
        20,
        token_counter=lambda value: len(value.split()),
    )

    combined = " ".join(item.page_content for item in chunks)
    assert len(chunks) > 1
    assert "HEAD" in combined
    assert "middle" in combined
    assert "TAIL" in combined
    assert all(item.metadata["source"] == "fixture" for item in chunks)


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
