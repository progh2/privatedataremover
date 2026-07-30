"""LLM-based PII extraction (structured JSON)."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from privatedataremover.core.adapters.base import BBox, ExtractedSpan, MaskSource, PiiType
from privatedataremover.core.llm import ensure_provider_allowed
from privatedataremover.core.pii import DetectionItem, DetectionStatus, new_id
from privatedataremover.core.pii.rules import bbox_for_snippet
from privatedataremover.core.settings import AppSettings, LlmProvider, coerce_provider

# Prefer object wrapper: Ollama format=json often fails on bare arrays.
_SYSTEM = """당신은 한국어 문서 개인정보(PII) 탐지 전문가입니다.
문서 텍스트에서 개인정보를 모두 찾아 아래 JSON만 출력하세요.

출력 스키마(반드시 이 객체 형식):
{"items":[{"type":"<유형>","text":"<문서에 나온 값만>","confidence":0.0-1.0}]}
개인정보가 없으면 {"items":[]}

type 허용값:
phone|email|rrn|name|address|account|card|birthdate|passport|driver_license|employee_or_student_id|other

반드시 찾을 것(빠뜨리지 말 것):
1) name — 사람 이름(한글·영문). 「성명/이름/신청인/수신인/고객명」 등 라벨 옆 값,
   「홍길동님」「김철수 씨」 형태, 서명·담당자·예금주 칸의 이름.
2) address — 도로명·지번 주소 전체. 「주소/거주지/배송지/소재지」 옆 값,
   시·군·구·동·로·길·번지·호·아파트명이 이어진 한 줄을 하나의 address로.
3) phone, email, rrn(주민등록번호), account, card, birthdate,
   passport, driver_license, employee_or_student_id
4) other — 위 유형이 애매하지만 개인정보로 보이는 값

규칙:
- text에는 문서에 실제 등장한 문자열만. 추측·생성·번역 금지.
- 라벨(예: "이름:")은 text에 넣지 말고 값만 넣으세요.
- 주소는 시·구·동을 쪼개지 말고 가능한 한 긴 한 덩어리로.
- 이름은 가능한 한 성+이름 전체를 하나의 name으로.
- 확신이 낮아도 후보면 포함하고 confidence만 낮추세요.
- JSON 외 설명·마크다운·코드펜스 금지.
"""

_USER_TEMPLATE = """다음 문서에서 개인정보(특히 이름·주소)를 빠짐없이 찾아 JSON으로만 답하세요.

문서:
---
{text}
---
"""

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
    # Common aliases models invent
    "성명": PiiType.NAME,
    "이름": PiiType.NAME,
    "주소": PiiType.ADDRESS,
    "전화번호": PiiType.PHONE,
    "연락처": PiiType.PHONE,
    "주민등록번호": PiiType.RRN,
    "주민번호": PiiType.RRN,
    "이메일": PiiType.EMAIL,
    "생년월일": PiiType.BIRTHDATE,
    "계좌": PiiType.ACCOUNT,
    "계좌번호": PiiType.ACCOUNT,
    "카드": PiiType.CARD,
    "카드번호": PiiType.CARD,
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
    if len(text) > 12000:
        text = text[:12000]

    ensure_provider_allowed(settings, settings.provider)
    raw = _call_llm(settings, text)
    parsed = _parse_items(raw)
    items: list[DetectionItem] = []
    for row in parsed:
        if not isinstance(row, dict):
            continue
        type_key = str(row.get("type", "other")).lower().strip()
        pii_type = _TYPE_MAP.get(type_key, PiiType.OTHER)
        snippet = str(row.get("text", "")).strip()
        if not snippet:
            continue
        # Strip accidental label prefixes models sometimes include
        snippet = re.sub(
            r"^(?:성\s*명|이\s*름|이름|주소|거주지|배송지|Name|Address)\s*[:：=\-]\s*",
            "",
            snippet,
        ).strip()
        if not snippet:
            continue
        try:
            conf = float(row.get("confidence", 0.7))
        except (TypeError, ValueError):
            conf = 0.7
        bbox = bbox_for_snippet(snippet, spans) or BBox(0, 0, 0, 0)
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
    user = _USER_TEMPLATE.format(text=text)
    provider = coerce_provider(settings.llm_provider)
    if provider == LlmProvider.OLLAMA:
        return _ollama_chat(settings, user)
    if provider == LlmProvider.OPENAI:
        return _openai_chat(settings, user)
    if provider == LlmProvider.ANTHROPIC:
        return _anthropic_chat(settings, user)
    raise ValueError(f"Unsupported provider: {provider}")


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
        "options": {"temperature": 0},
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
        "response_format": {"type": "json_object"},
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
        "max_tokens": 4096,
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


def _parse_items(raw: str) -> list[Any]:
    """Parse LLM JSON into a list of item dicts."""
    raw = raw.strip()
    if not raw:
        return []
    # Strip markdown fences if present
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if fence:
        raw = fence.group(1).strip()

    try:
        data = json.loads(raw)
        return _coerce_items_list(data)
    except json.JSONDecodeError:
        pass

    match_obj = re.search(r"\{[\s\S]*\}", raw)
    if match_obj:
        try:
            data = json.loads(match_obj.group(0))
            items = _coerce_items_list(data)
            if items:
                return items
        except json.JSONDecodeError:
            pass

    match_arr = re.search(r"\[[\s\S]*\]", raw)
    if match_arr:
        try:
            data = json.loads(match_arr.group(0))
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            return []
    return []


def _coerce_items_list(data: Any) -> list[Any]:
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    for key in ("items", "results", "data", "pii", "entities", "findings"):
        val = data.get(key)
        if isinstance(val, list):
            return val
    # Single object shaped like an item
    if "text" in data and "type" in data:
        return [data]
    return []
