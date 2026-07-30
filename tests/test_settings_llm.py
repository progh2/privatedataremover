"""Tests for settings and LLM local-only gate."""

from __future__ import annotations

from privatedataremover.core.llm import LocalOnlyBlockedError, ensure_provider_allowed, probe_connection
from privatedataremover.core.settings import AppSettings, LlmProvider, coerce_provider


def test_settings_roundtrip_dict() -> None:
    s = AppSettings(
        llm_provider=LlmProvider.OPENAI,
        local_only=True,
        openai_api_key="sk-test",
    )
    restored = AppSettings.from_dict(s.to_dict())
    assert restored.llm_provider == LlmProvider.OPENAI
    assert restored.local_only is True
    assert restored.openai_api_key == "sk-test"


def test_settings_accepts_plain_string_provider() -> None:
    """QSettings may round-trip enums as plain strings (no .value)."""
    s = AppSettings.from_dict({"llm_provider": "anthropic", "local_only": "true"})
    assert s.llm_provider is LlmProvider.ANTHROPIC
    assert s.local_only is True
    assert s.to_dict()["llm_provider"] == "anthropic"
    assert s.provider.value == "anthropic"


def test_coerce_provider() -> None:
    assert coerce_provider("ollama") is LlmProvider.OLLAMA
    assert coerce_provider(LlmProvider.OPENAI) is LlmProvider.OPENAI
    assert coerce_provider("nope") is LlmProvider.OLLAMA


def test_local_only_blocks_external() -> None:
    s = AppSettings(local_only=True, llm_provider=LlmProvider.OLLAMA)
    ensure_provider_allowed(s, LlmProvider.OLLAMA)
    try:
        ensure_provider_allowed(s, LlmProvider.OPENAI)
        assert False, "expected LocalOnlyBlockedError"
    except LocalOnlyBlockedError:
        pass


def test_probe_connection_local_only_openai() -> None:
    s = AppSettings(local_only=True, llm_provider=LlmProvider.OPENAI)
    result = probe_connection(s, LlmProvider.OPENAI)
    assert result.ok is False
    assert "로컬 전용" in result.message


def test_list_ollama_models_parses(monkeypatch) -> None:
    class FakeResp:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"models": [{"name": "llama3.2:latest"}, {"name": "mistral"}]}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url):
            assert url.endswith("/api/tags")
            return FakeResp()

    import privatedataremover.core.llm as llm_mod

    monkeypatch.setattr(llm_mod.httpx, "Client", FakeClient)
    from privatedataremover.core.llm import list_ollama_models

    assert list_ollama_models("http://localhost:11434") == ["llama3.2:latest", "mistral"]
