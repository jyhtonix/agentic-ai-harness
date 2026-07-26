"""Tests for configuration loading."""

from config.settings import settings


class TestSettings:
    def test_defaults(self):
        assert hasattr(settings, "openai_model")
        assert hasattr(settings, "log_level")

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
        # Re-import to trigger reload with monkeypatched env
        from config.settings import Settings
        s = Settings()
        assert s.openai_model == "gpt-4o-mini"
