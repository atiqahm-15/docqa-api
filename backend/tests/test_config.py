from app.config import Settings, get_settings


def test_settings_reads_google_api_key_from_env(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key-123")
    settings = Settings(_env_file=None)
    assert settings.google_api_key == "test-key-123"


def test_settings_has_default_gemini_models():
    settings = Settings(_env_file=None, google_api_key="x")
    assert settings.gemini_chat_model == "gemini-2.5-flash"
    assert settings.gemini_embedding_model == "gemini-embedding-2-preview"


def test_settings_allows_model_override_from_env(monkeypatch):
    monkeypatch.setenv("GEMINI_CHAT_MODEL", "gemini-2.5-pro")
    settings = Settings(_env_file=None, google_api_key="x")
    assert settings.gemini_chat_model == "gemini-2.5-pro"


def test_settings_default_allowed_origins_include_localhost():
    settings = Settings(_env_file=None, google_api_key="x")
    assert "http://localhost:5173" in settings.allowed_origins


def test_get_settings_returns_cached_instance(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "x")
    get_settings.cache_clear()
    first = get_settings()
    second = get_settings()
    assert first is second
    get_settings.cache_clear()
