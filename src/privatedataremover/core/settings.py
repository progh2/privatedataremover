"""Application settings persisted via QSettings."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class LlmProvider(str, Enum):
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


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

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["llm_provider"] = self.llm_provider.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppSettings:
        raw = dict(data)
        provider = raw.pop("llm_provider", LlmProvider.OLLAMA.value)
        known = set(cls.__dataclass_fields__)
        filtered = {k: v for k, v in raw.items() if k in known}
        settings = cls(**filtered)
        try:
            settings.llm_provider = LlmProvider(provider)
        except ValueError:
            settings.llm_provider = LlmProvider.OLLAMA
        return settings

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

    store = QSettings(ORG_NAME, APP_NAME)
    store.setValue(SETTINGS_KEY, settings.to_dict())
    store.sync()
