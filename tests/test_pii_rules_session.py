"""Tests for rule detection and session confirm/cancel."""

from __future__ import annotations

from privatedataremover.core.adapters.base import BBox, ExtractedSpan, PiiType
from privatedataremover.core.pii import DetectionStatus
from privatedataremover.core.pii.rules import detect_in_spans, detect_in_text
from privatedataremover.core.pii.session import DetectionSession


def test_detect_phone_and_email() -> None:
    spans = [
        ExtractedSpan(0, "연락처 010-1234-5678", BBox(10, 10, 200, 30)),
        ExtractedSpan(0, "메일 test@example.com", BBox(10, 40, 200, 60)),
    ]
    items = detect_in_spans(spans)
    types = {i.pii_type for i in items}
    assert PiiType.PHONE in types
    assert PiiType.EMAIL in types


def test_detect_rrn() -> None:
    items = detect_in_text(
        "주민 900101-1234567",
        unit_index=0,
        bbox=BBox(0, 0, 100, 20),
    )
    assert any(i.pii_type == PiiType.RRN for i in items)


def test_detect_labeled_name_and_address() -> None:
    text = "성명: 홍길동  주소: 서울특별시 강남구 테헤란로 123"
    items = detect_in_text(text, unit_index=0, bbox=BBox(0, 0, 200, 20))
    names = [i for i in items if i.pii_type == PiiType.NAME]
    addrs = [i for i in items if i.pii_type == PiiType.ADDRESS]
    assert any("홍길동" in i.text for i in names)
    assert any("강남구" in i.text or "테헤란로" in i.text for i in addrs)


def test_detect_name_nim_suffix() -> None:
    items = detect_in_text(
        "김철수님께서 방문하셨습니다.",
        unit_index=0,
        bbox=BBox(0, 0, 100, 20),
    )
    assert any(i.pii_type == PiiType.NAME and "김철수" in i.text for i in items)


def test_detect_sido_address() -> None:
    items = detect_in_text(
        "배송은 부산광역시 해운대구 우동 1234번지입니다.",
        unit_index=0,
        bbox=BBox(0, 0, 100, 20),
    )
    assert any(i.pii_type == PiiType.ADDRESS for i in items)


def test_detect_name_rejects_common_words() -> None:
    items = detect_in_text(
        "이상의 내용은 정보 보호를 위한 안내입니다.",
        unit_index=0,
        bbox=BBox(0, 0, 100, 20),
    )
    names = [i.text for i in items if i.pii_type == PiiType.NAME]
    assert "이상" not in names
    assert "정보" not in names


def test_joined_spans_detect_split_fields() -> None:
    spans = [
        ExtractedSpan(0, "이름:", BBox(0, 0, 40, 20)),
        ExtractedSpan(0, "박영희", BBox(40, 0, 100, 20)),
        ExtractedSpan(0, "주소:", BBox(0, 30, 40, 50)),
        ExtractedSpan(0, "경기도 성남시 분당구 판교로 10", BBox(40, 30, 300, 50)),
    ]
    items = detect_in_spans(spans)
    assert any(i.pii_type == PiiType.NAME and "박영희" in i.text for i in items)
    assert any(i.pii_type == PiiType.ADDRESS and "분당구" in i.text for i in items)


def test_session_confirm_cancel_ignore_type() -> None:
    session = DetectionSession()
    items = detect_in_text(
        "010-9999-8888 and a@b.co",
        unit_index=0,
        bbox=BBox(0, 0, 50, 10),
    )
    session.add_items(items)
    assert len(session.items) >= 1

    first = session.items[0]
    session.confirm(first.id)
    assert first.status == DetectionStatus.CONFIRMED
    assert len(session.masks()) == 1

    session.cancel_mask(first.id)
    assert first.status == DetectionStatus.CANCELLED
    assert len(session.masks()) == 0

    # Re-adding same text should be suppressed via ignored_texts
    again = detect_in_text(first.text, unit_index=0, bbox=BBox(0, 0, 50, 10))
    added = session.add_items(again)
    assert added == 0


def test_manual_mask() -> None:
    session = DetectionSession()
    item = session.add_manual(1, BBox(5, 5, 40, 20), pii_type=PiiType.CUSTOM)
    assert item.status == DetectionStatus.CONFIRMED
    assert len(session.masks()) == 1


def test_cancel_by_type() -> None:
    session = DetectionSession()
    items = detect_in_text("010-1111-2222", unit_index=0, bbox=BBox(0, 0, 10, 10))
    session.add_items(items)
    for i in session.items:
        session.confirm(i.id)
    n = session.cancel_by_type(PiiType.PHONE)
    assert n >= 1
    assert all(
        i.status != DetectionStatus.CONFIRMED
        for i in session.items
        if i.pii_type == PiiType.PHONE
    )
