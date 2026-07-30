"""Undo/redo snapshots for DetectionSession."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from privatedataremover.core.adapters.base import BBox, PiiType
from privatedataremover.core.pii import DetectionItem, SessionIgnoreRules


@dataclass
class SessionSnapshot:
    items: list[DetectionItem]
    ignored_types: set[PiiType]
    ignored_texts: set[str]
    cancelled_ids: set[str]
    ignored_regions: list[tuple[int | None, BBox]]
    label: str = ""


class HistoryStack:
    """Linear undo/redo of session snapshots."""

    def __init__(self, *, limit: int = 50) -> None:
        self._undo: list[SessionSnapshot] = []
        self._redo: list[SessionSnapshot] = []
        self._limit = limit

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def push(self, snapshot: SessionSnapshot) -> None:
        self._undo.append(snapshot)
        if len(self._undo) > self._limit:
            self._undo.pop(0)
        self._redo.clear()

    def undo(self, current: SessionSnapshot) -> SessionSnapshot | None:
        if not self._undo:
            return None
        prev = self._undo.pop()
        self._redo.append(current)
        return prev

    def redo(self, current: SessionSnapshot) -> SessionSnapshot | None:
        if not self._redo:
            return None
        nxt = self._redo.pop()
        self._undo.append(current)
        return nxt


def clone_item(item: DetectionItem) -> DetectionItem:
    return DetectionItem(
        id=item.id,
        unit_index=item.unit_index,
        bbox=BBox(item.bbox.x0, item.bbox.y0, item.bbox.x1, item.bbox.y1),
        text=item.text,
        pii_type=item.pii_type,
        source=item.source,
        status=item.status,
        confidence=item.confidence,
        mode=item.mode,
        pattern_id=item.pattern_id,
        ignored_reason=item.ignored_reason,
    )


def snapshot_from_session(session: Any, *, label: str = "") -> SessionSnapshot:
    regions: list[tuple[int | None, BBox]] = []
    for page, box in getattr(session.rules, "ignored_regions", []):
        regions.append(
            (
                page,
                BBox(box.x0, box.y0, box.x1, box.y1),
            )
        )
    return SessionSnapshot(
        items=[clone_item(i) for i in session.items],
        ignored_types=set(session.rules.ignored_types),
        ignored_texts=set(session.rules.ignored_texts),
        cancelled_ids=set(session.rules.cancelled_ids),
        ignored_regions=regions,
        label=label,
    )


def restore_session(session: Any, snap: SessionSnapshot) -> None:
    regions: list[tuple[int | None, BBox]] = []
    for page, box in snap.ignored_regions:
        regions.append((page, BBox(box.x0, box.y0, box.x1, box.y1)))
    session.items = [clone_item(i) for i in snap.items]
    session.rules = SessionIgnoreRules(
        ignored_types=set(snap.ignored_types),
        ignored_texts=set(snap.ignored_texts),
        cancelled_ids=set(snap.cancelled_ids),
        ignored_regions=regions,
    )
