from types import SimpleNamespace

import pytest

from llm import provider


def test_only_glm_47_is_supported():
    provider.ensure_supported_model("GLM-4.7")
    provider.ensure_supported_model("通义千问")
    provider.ensure_supported_model("DeepSeek")
    provider.ensure_supported_model("Moonshot Kimi")
    with pytest.raises(provider.UnsupportedModelError, match="Supported models"):
        provider.ensure_supported_model("GPT-3.5")


def test_provider_builds_zhipu_clients_without_network(monkeypatch):
    settings = SimpleNamespace(
        llm_configured=True,
        zhipu_api_key="test-key",
        zhipu_base_url="https://open.bigmodel.cn/api/paas/v4/",
        zhipu_chat_model="glm-4.7",
        zhipu_embedding_model="embedding-3",
        zhipu_timeout_seconds=30.0,
    )
    monkeypatch.setattr(provider, "get_settings", lambda: settings)
    provider.clear_provider_caches()

    chat = provider.get_chat_client("GLM-4.7")
    embeddings = provider.get_embeddings()

    assert chat.model_name == "glm-4.7"
    assert str(chat.openai_api_base).rstrip("/") == settings.zhipu_base_url.rstrip("/")
    assert embeddings.model == "embedding-3"
    assert embeddings.chunk_size == 64
    provider.clear_provider_caches()


def test_lazy_embeddings_expose_configured_model_without_creating_client(
    monkeypatch,
):
    settings = SimpleNamespace(zhipu_embedding_model="embedding-custom")
    monkeypatch.setattr(provider, "get_settings", lambda: settings)
    monkeypatch.setattr(
        provider,
        "get_embeddings",
        lambda: pytest.fail("embedding client was created"),
    )

    embeddings = provider.LazyZhipuEmbeddings()

    assert embeddings.model_name == "embedding-custom"


def test_supported_model_context_capabilities_cover_application_baseline():
    specs = {spec.label: spec for spec in provider.list_model_specs()}

    assert specs["GLM-4.7"].context_window_tokens == 200_000
    assert specs["通义千问"].context_window_tokens == 1_000_000
    assert specs["DeepSeek"].context_window_tokens == 1_000_000
    assert specs["Moonshot Kimi"].context_window_tokens == 256_000
    assert all(spec.max_output_tokens >= 32_768 for spec in specs.values())
