from app.config import get_settings


def test_settings_read_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "mysql+pymysql://user:pass@localhost/test")
    monkeypatch.setenv("ZHIPU_API_KEY", "test-key")
    monkeypatch.setenv("ZHIPU_CHAT_MODEL", "glm-4.7")
    monkeypatch.setenv("ZHIPU_EMBEDDING_MODEL", "embedding-3")
    monkeypatch.setenv("ZHIPU_TIMEOUT_SECONDS", "31")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "unit-test-placeholder")
    monkeypatch.setenv("DASHSCOPE_CHAT_MODEL", "qwen3.7-plus")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "unit-test-placeholder")
    monkeypatch.setenv("DEEPSEEK_CHAT_MODEL", "deepseek-v4-flash")
    monkeypatch.setenv("MOONSHOT_API_KEY", "unit-test-placeholder")
    monkeypatch.setenv("MOONSHOT_CHAT_MODEL", "kimi-k3")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:8080,http://127.0.0.1:8080")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.database_url.endswith("/test")
    assert settings.llm_configured is True
    assert settings.zhipu_chat_model == "glm-4.7"
    assert settings.zhipu_embedding_model == "embedding-3"
    assert settings.zhipu_timeout_seconds == 31.0
    assert settings.dashscope_chat_model == "qwen3.7-plus"
    assert settings.deepseek_chat_model == "deepseek-v4-flash"
    assert settings.moonshot_chat_model == "kimi-k3"
    assert len(settings.cors_origins) == 2
    get_settings.cache_clear()


def test_placeholder_key_is_not_configured(monkeypatch):
    monkeypatch.setenv("ZHIPU_API_KEY", "replace_with_your_zhipu_api_key")
    get_settings.cache_clear()

    assert get_settings().llm_configured is False
    get_settings.cache_clear()
