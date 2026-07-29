"""Tests for pattern similarity, apply, and undo history."""

from __future__ import annotations

from privatedataremover.core.adapters.base import BBox, DocumentUnit, ExtractedSpan, MaskSource, PiiType
from privatedataremover.core.history import HistoryStack, restore_session, snapshot_from_session
from privatedataremover.core.pattern import find_similar_pages, page_fingerprint, similarity
from privatedataremover.core.pattern.apply import (
    CoordMode,
    PatternProposal,
    SeedMask,
    build_pattern_items,
    map_bbox,
)
from privatedataremover.core.pii import DetectionStatus
from privatedataremover.core.pii.session import DetectionSession


def test_similarity_and_fingerprint() -> None:
    a = page_fingerprint([ExtractedSpan(0, "성명 #### 전화 ###-####-####")])
    b = page_fingerprint([ExtractedSpan(1, "성명 #### 전화 ###-####-####")])
    c = page_fingerprint([ExtractedSpan(2, "완전히 다른 문서 내용입니다")])
    assert similarity(a, b) > 0.9
    assert similarity(a, c) < 0.5


def test_find_similar_pages() -> None:
    fps = {
        0: "form header name phone address",
        1: "form header name phone address",
        2: "invoice total amount due",
    }
    sims = find_similar_pages(fps, 0, threshold=0.5)
    assert any(s.unit_index == 1 for s in sims)
    assert all(s.unit_index != 2 for s in sims) or sims[0].unit_index == 1


def test_map_bbox_relative() -> None:
    seed = DocumentUnit(0, "p1", 100, 200)
    target = DocumentUnit(1, "p2", 200, 400)
    mapped = map_bbox(BBox(10, 20, 30, 40), seed_unit=seed, target_unit=target, mode=CoordMode.RELATIVE)
    assert mapped == BBox(20, 40, 60, 80)


def test_build_and_rollback_pattern() -> None:
    units = {
        0: DocumentUnit(0, "p1", 100, 100),
        1: DocumentUnit(1, "p2", 100, 100),
    }
    proposal = PatternProposal(
        pattern_id="pat1",
        seed_index=0,
        target_indices=[1],
        seeds=[SeedMask(BBox(5, 5, 25, 15), PiiType.PHONE, "010", "delete_and_box")],
        coord_mode=CoordMode.ABSOLUTE,
        scores={1: 0.9},
    )
    items = build_pattern_items(proposal, units=units)
    assert len(items) == 1
    assert items[0].source == MaskSource.PATTERN
    assert items[0].pattern_id == "pat1"

    session = DetectionSession()
    session.apply_pattern_items(items)
    assert len(session.masks()) == 1
    n = session.rollback_pattern("pat1")
    assert n == 1
    assert len(session.masks()) == 0


def test_undo_redo_history() -> None:
    session = DetectionSession()
    history = HistoryStack()
    history.push(snapshot_from_session(session, label="empty"))
    session.add_manual(0, BBox(0, 0, 10, 10))
    assert len(session.masks()) == 1
    current = snapshot_from_session(session)
    prev = history.undo(current)
    assert prev is not None
    restore_session(session, prev)
    assert len(session.masks()) == 0
    restored = history.redo(snapshot_from_session(session))
    assert restored is not None
    restore_session(session, restored)
    assert len(session.masks()) == 1


def test_ignore_region_skips_detection() -> None:
    session = DetectionSession()
    session.add_ignore_region(0, BBox(0, 0, 100, 100))
    from privatedataremover.core.pii import DetectionItem

    item = DetectionItem(
        id="x",
        unit_index=0,
        bbox=BBox(10, 10, 20, 20),
        text="010-1111-2222",
        pii_type=PiiType.PHONE,
        source=MaskSource.RULE,
        status=DetectionStatus.PENDING,
    )
    assert session.add_items([item]) == 0
