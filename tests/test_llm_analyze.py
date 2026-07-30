"""Tests for LLM PII JSON parsing helpers."""

from __future__ import annotations

from privatedataremover.core.adapters.base import BBox, ExtractedSpan
from privatedataremover.core.llm.analyze import _parse_items
from privatedataremover.core.pii.rules import bbox_for_snippet


def test_parse_items_object_wrapper() -> None:
    raw = '{"items":[{"type":"name","text":"홍길동","confidence":0.9}]}'
    items = _parse_items(raw)
    assert len(items) == 1
    assert items[0]["text"] == "홍길동"


def test_parse_items_bare_array() -> None:
    raw = '[{"type":"address","text":"서울시 강남구","confidence":0.8}]'
    items = _parse_items(raw)
    assert items[0]["type"] == "address"


def test_parse_items_results_key_and_fence() -> None:
    raw = '```json\n{"results":[{"type":"phone","text":"010-1111-2222","confidence":1}]}\n```'
    items = _parse_items(raw)
    assert items[0]["type"] == "phone"


def test_bbox_for_snippet_unions_parts() -> None:
    spans = [
        ExtractedSpan(0, "서울시", BBox(0, 0, 50, 10)),
        ExtractedSpan(0, "강남구", BBox(50, 0, 100, 10)),
        ExtractedSpan(0, "역삼동", BBox(100, 0, 150, 10)),
    ]
    box = bbox_for_snippet("서울시 강남구 역삼동", spans)
    assert box is not None
    assert box.x0 == 0
    assert box.x1 == 150
