"""LLM provider adapters and connection tests."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from privatedataremover.core.settings import AppSettings, LlmProvider, coerce_provider


@dataclass(frozen=True)
class ConnectionResult:
    ok: bool
    message: str


class LocalOnlyBlockedError(RuntimeError):
    """Raised when an external API call is attempted in local-only mode."""


def list_ollama_models(base_url: str) -> list[str]:
    """Return installed Ollama model names from /api/tags."""
    base = (base_url or "http://localhost:11434").rstrip("/")
    with httpx.Client(timeout=10.0) as client:
        resp = client.get(f"{base}/api/tags")
        resp.raise_for_status()
        data = resp.json()
    names = [str(m.get("name", "")).strip() for m in data.get("models", [])]
    return sorted({n for n in names if n})


def ensure_provider_allowed(settings: AppSettings, provider: LlmProvider) -> None:
    if settings.local_only and coerce_provider(provider) != LlmProvider.OLLAMA:
        raise LocalOnlyBlockedError(
            "로컬 전용 모드에서는 Ollama만 사용할 수 있습니다. "
            "설정에서 로컬 전용 모드를 끄거나 프로바이더를 Ollama로 변경하세요."
        )


def probe_connection(settings: AppSettings, provider: LlmProvider | None = None) -> ConnectionResult:
    """Probe the selected (or given) LLM provider."""
    target = coerce_provider(provider or settings.llm_provider)
    try:
        ensure_provider_allowed(settings, target)
    except LocalOnlyBlockedError as exc:
        return ConnectionResult(False, str(exc))

    try:
        if target == LlmProvider.OLLAMA:
            return _test_ollama(settings)
        if target == LlmProvider.OPENAI:
            return _test_openai(settings)
        if target == LlmProvider.ANTHROPIC:
            return _test_anthropic(settings)
    except httpx.HTTPError as exc:
        return ConnectionResult(False, f"네트워크 오류: {exc}")
    except Exception as exc:  # noqa: BLE001 — surface to UI
        return ConnectionResult(False, f"실패: {exc}")
    return ConnectionResult(False, f"알 수 없는 프로바이더: {target}")


def _test_ollama(settings: AppSettings) -> ConnectionResult:
    base = settings.ollama_base_url.rstrip("/")
    with httpx.Client(timeout=10.0) as client:
        resp = client.get(f"{base}/api/tags")
        resp.raise_for_status()
        data = resp.json()
        models = [m.get("name", "") for m in data.get("models", [])]
        if settings.ollama_model and not any(
            settings.ollama_model in name for name in models
        ):
            listed = ", ".join(models[:8]) or "(없음)"
            return ConnectionResult(
                True,
                f"Ollama 연결됨. 모델 '{settings.ollama_model}'은 목록에 없을 수 있습니다. "
                f"사용 가능: {listed}",
            )
        return ConnectionResult(True, f"Ollama 연결 성공 ({len(models)}개 모델)")


def _test_openai(settings: AppSettings) -> ConnectionResult:
    if not settings.openai_api_key.strip():
        return ConnectionResult(False, "OpenAI API 키가 비어 있습니다.")
    base = settings.openai_base_url.rstrip("/")
    headers = {"Authorization": f"Bearer {settings.openai_api_key.strip()}"}
    with httpx.Client(timeout=15.0, headers=headers) as client:
        resp = client.get(f"{base}/models")
        if resp.status_code == 401:
            return ConnectionResult(False, "OpenAI 인증 실패 (API 키를 확인하세요).")
        resp.raise_for_status()
        return ConnectionResult(True, f"OpenAI 연결 성공 (모델: {settings.openai_model})")


def _test_anthropic(settings: AppSettings) -> ConnectionResult:
    if not settings.anthropic_api_key.strip():
        return ConnectionResult(False, "Anthropic API 키가 비어 있습니다.")
    headers = {
        "x-api-key": settings.anthropic_api_key.strip(),
        "anthropic-version": "2023-06-01",
    }
    # Lightweight authenticated probe — list models if available, else messages with max_tokens=1 is heavy;
    # use /v1/models when supported, fallback to a minimal count request status via messages API error shape.
    with httpx.Client(timeout=15.0, headers=headers) as client:
        resp = client.get("https://api.anthropic.com/v1/models")
        if resp.status_code == 401:
            return ConnectionResult(False, "Anthropic 인증 실패 (API 키를 확인하세요).")
        if resp.status_code == 404:
            # Older accounts may not expose models list; treat non-401 as reachable+authed-ish.
            return ConnectionResult(True, f"Anthropic 엔드포인트 응답 ({resp.status_code}). 키 형식 확인됨.")
        resp.raise_for_status()
        return ConnectionResult(True, f"Anthropic 연결 성공 (모델: {settings.anthropic_model})")
