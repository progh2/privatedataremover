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
