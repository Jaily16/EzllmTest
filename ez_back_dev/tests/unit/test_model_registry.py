import pytest
import httpx2

from llm import provider


def test_registry_exposes_stable_public_labels_and_official_defaults():
    specs = provider.list_model_specs()

    assert [spec.label for spec in specs] == [
        "GLM-4.7",
        "通义千问",
        "DeepSeek",
        "Moonshot Kimi",
    ]
    assert {spec.label: spec.default_model for spec in specs} == {
        "GLM-4.7": "glm-4.7",
        "通义千问": "qwen3.5-plus",
        "DeepSeek": "deepseek-v4-flash",
        "Moonshot Kimi": "kimi-k2.5",
    }
    assert {spec.label: spec.provider for spec in specs} == {
        "GLM-4.7": "zhipu",
        "通义千问": "alibaba",
        "DeepSeek": "deepseek",
        "Moonshot Kimi": "moonshot",
    }


def test_registry_rejects_unknown_public_label():
    with pytest.raises(provider.UnsupportedModelError, match="Unsupported model"):
        provider.get_model_spec("unknown-model")


def test_missing_selected_provider_key_has_clear_error(monkeypatch):
    monkeypatch.setattr(
        provider,
        "get_settings",
        lambda: provider_test_settings(dashscope_api_key=""),
    )
    provider.clear_provider_caches()

    with pytest.raises(provider.LLMConfigurationError, match="DASHSCOPE_API_KEY"):
        provider.get_chat_client("通义千问")

    provider.clear_provider_caches()


def test_factory_passes_provider_parameters_without_network(monkeypatch):
    created = []

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            created.append(kwargs)

    monkeypatch.setattr(provider, "ChatOpenAI", FakeChatOpenAI)
    monkeypatch.setattr(provider, "get_settings", provider_test_settings)
    provider.clear_provider_caches()

    provider.get_chat_client("GLM-4.7")
    provider.get_chat_client("通义千问")
    provider.get_chat_client("DeepSeek")
    provider.get_chat_client("Moonshot Kimi")

    assert [item["model"] for item in created] == [
        "glm-4.7",
        "qwen3.5-plus",
        "deepseek-v4-flash",
        "kimi-k2.5",
    ]
    assert [item["base_url"] for item in created] == [
        "https://open.bigmodel.cn/api/paas/v4/",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "https://api.deepseek.com",
        "https://api.moonshot.ai/v1",
    ]
    assert [item["timeout"] for item in created] == [45.0, 46.0, 47.0, 48.0]
    assert created[0]["temperature"] == 0.5
    assert created[1]["temperature"] == 0.5
    assert created[2]["temperature"] == 0.5
    assert "temperature" not in created[3]
    assert all(item["max_retries"] == 0 for item in created)
    provider.clear_provider_caches()


def test_factory_honors_long_task_minimum_timeout(monkeypatch):
    created = []

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            created.append(kwargs)

    monkeypatch.setattr(provider, "ChatOpenAI", FakeChatOpenAI)
    monkeypatch.setattr(provider, "get_settings", provider_test_settings)
    provider.clear_provider_caches()

    provider.get_chat_client("DeepSeek", minimum_timeout_seconds=300.0)

    assert created[0]["timeout"] == 300.0
    provider.clear_provider_caches()


def test_invocation_translates_timeout_rate_limit_and_empty_output(monkeypatch):
    class FakeClient:
        def __init__(self, result=None, error=None):
            self.result = result
            self.error = error

        def invoke(self, value):
            if self.error:
                raise self.error
            return self.result

    class FakeRateLimitError(RuntimeError):
        status_code = 429

    monkeypatch.setattr(
        provider, "get_chat_client", lambda label: FakeClient(error=TimeoutError())
    )
    with pytest.raises(provider.LLMTimeoutError, match="DeepSeek"):
        provider.invoke_chat_model("DeepSeek", "hello")

    monkeypatch.setattr(
        provider,
        "get_chat_client",
        lambda label: FakeClient(
            error=provider.APITimeoutError(
                request=httpx2.Request("POST", "https://example.test")
            )
        ),
    )
    with pytest.raises(provider.LLMTimeoutError, match="DeepSeek"):
        provider.invoke_chat_model("DeepSeek", "hello")

    monkeypatch.setattr(
        provider,
        "get_chat_client",
        lambda label: FakeClient(error=FakeRateLimitError()),
    )
    with pytest.raises(provider.LLMRateLimitError, match="DeepSeek"):
        provider.invoke_chat_model("DeepSeek", "hello")

    monkeypatch.setattr(
        provider,
        "get_chat_client",
        lambda label: FakeClient(result=type("Message", (), {"content": "  "})()),
    )
    with pytest.raises(provider.LLMEmptyResponseError, match="DeepSeek"):
        provider.invoke_chat_model("DeepSeek", "hello")


def provider_test_settings(**overrides):
    values = {
        "zhipu_api_key": "unit-test-placeholder",
        "zhipu_base_url": "https://open.bigmodel.cn/api/paas/v4/",
        "zhipu_chat_model": "glm-4.7",
        "zhipu_embedding_model": "embedding-3",
        "zhipu_timeout_seconds": 45.0,
        "dashscope_api_key": "unit-test-placeholder",
        "dashscope_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "dashscope_chat_model": "qwen3.5-plus",
        "dashscope_timeout_seconds": 46.0,
        "deepseek_api_key": "unit-test-placeholder",
        "deepseek_base_url": "https://api.deepseek.com",
        "deepseek_chat_model": "deepseek-v4-flash",
        "deepseek_timeout_seconds": 47.0,
        "moonshot_api_key": "unit-test-placeholder",
        "moonshot_base_url": "https://api.moonshot.ai/v1",
        "moonshot_chat_model": "kimi-k2.5",
        "moonshot_timeout_seconds": 48.0,
    }
    values.update(overrides)
    return type("Settings", (), values)()
