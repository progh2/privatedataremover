"""Application settings persisted via QSettings."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from enum import Enum
from typing import Any


class LlmProvider(str, Enum):
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


def coerce_provider(value: Any) -> LlmProvider:
    """Normalize QSettings/UI values to LlmProvider (plain str has no .value)."""
    if isinstance(value, LlmProvider):
        return value
    if isinstance(value, str):
        try:
            return LlmProvider(value)
        except ValueError:
            return LlmProvider.OLLAMA
    return LlmProvider.OLLAMA


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if value is None:
        return default
    return bool(value)


@dataclass
class AppSettings:
    """User-configurable settings for LLM, OCR, and privacy mode."""

    llm_provider: LlmProvider = LlmProvider.OLLAMA
    local_only: bool = False

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    tesseract_cmd: str = ""
    ocr_languages: str = "kor+eng"

    def __post_init__(self) -> None:
        self.llm_provider = coerce_provider(self.llm_provider)
        self.local_only = _coerce_bool(self.local_only, False)

    @property
    def provider(self) -> LlmProvider:
        return coerce_provider(self.llm_provider)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        # asdict may already stringify str-Enums; always store a plain string.
        data["llm_provider"] = self.provider.value
        data["local_only"] = bool(self.local_only)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppSettings:
        raw = {str(k): v for k, v in dict(data).items()}
        known = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in raw.items() if k in known}
        if "llm_provider" in filtered:
            filtered["llm_provider"] = coerce_provider(filtered["llm_provider"])
        if "local_only" in filtered:
            filtered["local_only"] = _coerce_bool(filtered["local_only"])
        return cls(**filtered)

    def allows_external_api(self) -> bool:
        return not self.local_only


ORG_NAME = "privatedataremover"
APP_NAME = "Private Data Remover"
SETTINGS_KEY = "app_settings"


def load_settings() -> AppSettings:
    from PySide6.QtCore import QSettings

    store = QSettings(ORG_NAME, APP_NAME)
    raw = store.value(SETTINGS_KEY)
    if isinstance(raw, dict):
        return AppSettings.from_dict(raw)
    return AppSettings()


def save_settings(settings: AppSettings) -> None:
    from PySide6.QtCore import QSettings

    # Ensure enum is normalized before persistence (guards against str contamination).
    settings.llm_provider = coerce_provider(settings.llm_provider)
    store = QSettings(ORG_NAME, APP_NAME)
    store.setValue(SETTINGS_KEY, settings.to_dict())
    store.sync()
