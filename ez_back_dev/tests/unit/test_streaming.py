import asyncio
from types import SimpleNamespace

import pytest

from llm import streaming
from llm.provider import provider_options
from service.workflowBudget import profile_for


def stream_settings():
    return SimpleNamespace(
        zhipu_api_key="test-key",
        zhipu_base_url="https://open.bigmodel.cn/api/paas/v4/",
        zhipu_chat_model="glm-4.7",
        zhipu_timeout_seconds=45.0,
        dashscope_api_key="test-key",
        dashscope_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        dashscope_chat_model="qwen3.5-plus",
        dashscope_timeout_seconds=45.0,
        deepseek_api_key="test-key",
        deepseek_base_url="https://api.deepseek.com",
        deepseek_chat_model="deepseek-v4-flash",
        deepseek_timeout_seconds=45.0,
        moonshot_api_key="test-key",
        moonshot_base_url="https://api.moonshot.cn/v1",
        moonshot_chat_model="kimi-k2.5",
        moonshot_timeout_seconds=45.0,
    )


def test_vendor_stream_requests_enable_thinking_with_balanced_budget(monkeypatch):
    monkeypatch.setattr(streaming, "get_settings", stream_settings)

    glm = streaming.build_stream_request("GLM-4.7", "prompt", 32768)
    qwen = streaming.build_stream_request("通义千问", "prompt", 32768)
    deepseek = streaming.build_stream_request("DeepSeek", "prompt", 32768)
    kimi = streaming.build_stream_request("Moonshot Kimi", "prompt", 32768)

    assert glm["extra_body"] == {"thinking": {"type": "enabled"}}
    assert qwen["extra_body"] == {
        "enable_thinking": True,
        "thinking_budget": 8192,
    }
    assert deepseek["extra_body"] == {"thinking": {"type": "enabled"}}
    assert deepseek["reasoning_effort"] == "high"
    assert "temperature" not in deepseek
    assert kimi["extra_body"] == {"thinking": {"type": "enabled"}}
    assert "temperature" not in kimi
    assert all(
        request["stream_options"] == {"include_usage": True}
        for request in (glm, qwen, deepseek, kimi)
    )


def test_stream_request_applies_stage_cap_and_disables_qwen_thinking(
    monkeypatch,
):
    monkeypatch.setattr(streaming, "get_settings", stream_settings)
    options = provider_options(
        profile_for("api_info", "structured"),
        "通义千问",
    )

    request = streaming.build_stream_request(
        "通义千问",
        "prompt",
        32_768,
        request_options=options,
    )

    assert request["max_tokens"] <= 2_048
    assert request["extra_body"] == {"enable_thinking": False}
    assert request["messages"] == [{"role": "user", "content": "prompt"}]


def test_stream_request_allows_only_the_frozen_json_response_format(monkeypatch):
    monkeypatch.setattr(streaming, "get_settings", stream_settings)

    request = streaming.build_stream_request(
        "GLM-4.7",
        "return json",
        4_096,
        request_options={
            "max_tokens": 4_096,
            "temperature": 0,
            "extra_body": {"thinking": {"type": "disabled"}},
            "response_format": {"type": "json_object"},
        },
    )

    assert request["response_format"] == {"type": "json_object"}
    with pytest.raises(ValueError, match="unsupported response_format"):
        streaming.build_stream_request(
            "GLM-4.7",
            "return json",
            4_096,
            request_options={"response_format": {"type": "json_schema"}},
        )


def test_token_usage_is_classified_without_guessing():
    usage = streaming.parse_token_usage(
        {
            "prompt_tokens": 100,
            "completion_tokens": 80,
            "completion_tokens_details": {"reasoning_tokens": 30},
            "total_tokens": 180,
        }
    )
    incomplete = streaming.parse_token_usage(
        {"prompt_tokens": 100, "completion_tokens": 80, "total_tokens": 180}
    )

    assert usage == streaming.TokenUsage(100, 30, 50, 180)
    assert incomplete == streaming.TokenUsage(100, None, None, 180)


def test_stream_adapter_preserves_reasoning_content_and_usage(monkeypatch):
    chunks = [
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(
                        content=None,
                        model_extra={"reasoning_content": "先分析"},
                    )
                )
            ],
            usage=None,
        ),
        SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content="最终答案"))],
            usage=None,
        ),
        SimpleNamespace(
            choices=[],
            usage={
                "prompt_tokens": 10,
                "completion_tokens": 8,
                "completion_tokens_details": {"reasoning_tokens": 3},
                "total_tokens": 18,
            },
        ),
    ]

    class FakeStream:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        def __aiter__(self):
            return self

        async def __anext__(self):
            if not chunks:
                raise StopAsyncIteration
            return chunks.pop(0)

    class FakeCompletions:
        async def create(self, **_kwargs):
            return FakeStream()

    class FakeClient:
        chat = SimpleNamespace(completions=FakeCompletions())

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

    monkeypatch.setattr(streaming, "get_settings", stream_settings)
    monkeypatch.setattr(streaming, "_create_stream_client", lambda *_args: FakeClient())

    async def collect():
        return [
            event
            async for event in streaming.stream_chat_completion(
                "DeepSeek", "prompt", 32768
            )
        ]

    events = asyncio.run(collect())

    assert [(event.kind, event.text) for event in events[:2]] == [
        ("reasoning", "先分析"),
        ("content", "最终答案"),
    ]
    assert events[2].usage == streaming.TokenUsage(10, 3, 5, 18)
