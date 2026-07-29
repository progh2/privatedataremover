"""Tests for settings and LLM local-only gate."""

from __future__ import annotations

from privatedataremover.core.llm import LocalOnlyBlockedError, ensure_provider_allowed, probe_connection
from privatedataremover.core.settings import AppSettings, LlmProvider


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
