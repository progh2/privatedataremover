"""LLM-based PII extraction (structured JSON)."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from privatedataremover.core.adapters.base import BBox, ExtractedSpan, MaskSource, PiiType
from privatedataremover.core.llm import ensure_provider_allowed
from privatedataremover.core.pii import DetectionItem, DetectionStatus, new_id
from privatedataremover.core.settings import AppSettings, LlmProvider

_SYSTEM = (
    "You are a Korean document privacy assistant. "
    "Find personal information in the given text. "
    "Reply with ONLY a JSON array of objects: "
    '[{"type":"phone|email|rrn|name|address|account|card|birthdate|passport|'
    'driver_license|employee_or_student_id|other","text":"...","confidence":0.0-1.0}]. '
    "If none, reply []. Do not invent text that is not present."
)

_TYPE_MAP = {
    "phone": PiiType.PHONE,
    "email": PiiType.EMAIL,
    "rrn": PiiType.RRN,
    "name": PiiType.NAME,
    "address": PiiType.ADDRESS,
    "account": PiiType.ACCOUNT,
    "card": PiiType.CARD,
    "birthdate": PiiType.BIRTHDATE,
    "passport": PiiType.PASSPORT,
    "driver_license": PiiType.DRIVER_LICENSE,
    "employee_or_student_id": PiiType.EMPLOYEE_OR_STUDENT_ID,
    "other": PiiType.OTHER,
}


def analyze_page_with_llm(
    settings: AppSettings,
    *,
    unit_index: int,
    page_text: str,
    spans: list[ExtractedSpan],
) -> list[DetectionItem]:
    """Call configured LLM and map results onto span bboxes when possible."""
    text = page_text.strip()
    if not text:
        return []
    # Cap payload size
    if len(text) > 12000:
        text = text[:12000]

    ensure_provider_allowed(settings, settings.llm_provider)
    raw = _call_llm(settings, text)
    parsed = _parse_json_array(raw)
    items: list[DetectionItem] = []
    for row in parsed:
        if not isinstance(row, dict):
            continue
        type_key = str(row.get("type", "other")).lower().strip()
        pii_type = _TYPE_MAP.get(type_key, PiiType.OTHER)
        snippet = str(row.get("text", "")).strip()
        if not snippet:
            continue
        try:
            conf = float(row.get("confidence", 0.7))
        except (TypeError, ValueError):
            conf = 0.7
        bbox = _match_bbox(snippet, spans) or BBox(0, 0, 0, 0)
        items.append(
            DetectionItem(
                id=new_id(),
                unit_index=unit_index,
                bbox=bbox,
                text=snippet,
                pii_type=pii_type,
                source=MaskSource.AI,
                status=DetectionStatus.PENDING,
                confidence=max(0.0, min(conf, 1.0)),
            )
        )
    return items


def _call_llm(settings: AppSettings, text: str) -> str:
    user = f"Document text:\n{text}"
    if settings.llm_provider == LlmProvider.OLLAMA:
        return _ollama_chat(settings, user)
    if settings.llm_provider == LlmProvider.OPENAI:
        return _openai_chat(settings, user)
    if settings.llm_provider == LlmProvider.ANTHROPIC:
        return _anthropic_chat(settings, user)
    raise ValueError(f"Unsupported provider: {settings.llm_provider}")


def _ollama_chat(settings: AppSettings, user: str) -> str:
    base = settings.ollama_base_url.rstrip("/")
    payload = {
        "model": settings.ollama_model,
        "stream": False,
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user},
        ],
        "format": "json",
    }
    with httpx.Client(timeout=120.0) as client:
        resp = client.post(f"{base}/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return str(data.get("message", {}).get("content", ""))


def _openai_chat(settings: AppSettings, user: str) -> str:
    if not settings.openai_api_key.strip():
        raise ValueError("OpenAI API 키가 없습니다.")
    base = settings.openai_base_url.rstrip("/")
    headers = {"Authorization": f"Bearer {settings.openai_api_key.strip()}"}
    payload = {
        "model": settings.openai_model,
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user},
        ],
        "temperature": 0,
    }
    with httpx.Client(timeout=120.0, headers=headers) as client:
        resp = client.post(f"{base}/chat/completions", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return str(data["choices"][0]["message"]["content"])


def _anthropic_chat(settings: AppSettings, user: str) -> str:
    if not settings.anthropic_api_key.strip():
        raise ValueError("Anthropic API 키가 없습니다.")
    headers = {
        "x-api-key": settings.anthropic_api_key.strip(),
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": settings.anthropic_model,
        "max_tokens": 2048,
        "system": _SYSTEM,
        "messages": [{"role": "user", "content": user}],
    }
    with httpx.Client(timeout=120.0, headers=headers) as client:
        resp = client.post("https://api.anthropic.com/v1/messages", json=payload)
        resp.raise_for_status()
        data = resp.json()
        parts = data.get("content", [])
        texts = [p.get("text", "") for p in parts if p.get("type") == "text"]
        return "\n".join(texts)


def _parse_json_array(raw: str) -> list[Any]:
    raw = raw.strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "items" in data:
            items = data["items"]
            return items if isinstance(items, list) else []
    except json.JSONDecodeError:
        pass
    match = re.search(r"\[[\s\S]*\]", raw)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            return []
    return []


def _match_bbox(snippet: str, spans: list[ExtractedSpan]) -> BBox | None:
    needle = snippet.strip()
    if not needle:
        return None
    for span in spans:
        if needle in span.text and span.bbox is not None:
            return span.bbox
    # Try loose containment of span in snippet
    for span in spans:
        if span.text.strip() and span.text.strip() in needle and span.bbox is not None:
            return span.bbox
    return None
