"""Detection session: items, confirm/ignore/cancel, mask derivation."""

from __future__ import annotations

from privatedataremover.core.adapters.base import BBox, MaskMode, MaskRegion, MaskSource, PiiType
from privatedataremover.core.pii import (
    DetectionItem,
    DetectionStatus,
    SessionIgnoreRules,
    new_id,
)


class DetectionSession:
    """In-memory workspace for one open document."""

    def __init__(self) -> None:
        self.items: list[DetectionItem] = []
        self.rules = SessionIgnoreRules()

    def clear(self) -> None:
        self.items.clear()
        self.rules = SessionIgnoreRules()

    def add_items(self, items: list[DetectionItem], *, merge: bool = True) -> int:
        """Add detections, skipping ignored types/texts and duplicates."""
        added = 0
        for item in items:
            if item.pii_type in self.rules.ignored_types:
                continue
            norm = item.text.strip().lower()
            if norm and norm in self.rules.ignored_texts:
                continue
            if merge and self._find_similar(item):
                continue
            self.items.append(item)
            added += 1
        return added

    def _find_similar(self, item: DetectionItem) -> DetectionItem | None:
        for existing in self.items:
            if existing.status in (DetectionStatus.IGNORED, DetectionStatus.CANCELLED):
                continue
            if (
                existing.unit_index == item.unit_index
                and existing.pii_type == item.pii_type
                and existing.text.strip() == item.text.strip()
            ):
                return existing
            if (
                existing.unit_index == item.unit_index
                and _bbox_iou(existing.bbox, item.bbox) > 0.6
            ):
                return existing
        return None

    def get(self, item_id: str) -> DetectionItem | None:
        for item in self.items:
            if item.id == item_id:
                return item
        return None

    def confirm(self, item_id: str) -> None:
        item = self.get(item_id)
        if item:
            item.status = DetectionStatus.CONFIRMED

    def ignore(self, item_id: str, *, remember_text: bool = True) -> None:
        item = self.get(item_id)
        if not item:
            return
        item.status = DetectionStatus.IGNORED
        if remember_text and item.text.strip():
            self.rules.ignored_texts.add(item.text.strip().lower())

    def cancel_mask(self, item_id: str) -> None:
        item = self.get(item_id)
        if not item:
            return
        item.status = DetectionStatus.CANCELLED
        self.rules.cancelled_ids.add(item.id)
        if item.text.strip():
            self.rules.ignored_texts.add(item.text.strip().lower())

    def confirm_all_pending(self, *, unit_index: int | None = None) -> int:
        n = 0
        for item in self.items:
            if item.status != DetectionStatus.PENDING:
                continue
            if unit_index is not None and item.unit_index != unit_index:
                continue
            item.status = DetectionStatus.CONFIRMED
            n += 1
        return n

    def cancel_by_type(
        self, pii_type: PiiType, *, unit_index: int | None = None
    ) -> int:
        n = 0
        for item in self.items:
            if item.pii_type != pii_type:
                continue
            if item.status != DetectionStatus.CONFIRMED:
                continue
            if unit_index is not None and item.unit_index != unit_index:
                continue
            self.cancel_mask(item.id)
            n += 1
        return n

    def ignore_type(self, pii_type: PiiType) -> None:
        self.rules.ignored_types.add(pii_type)
        for item in self.items:
            if item.pii_type == pii_type and item.status == DetectionStatus.PENDING:
                item.status = DetectionStatus.IGNORED

    def add_manual(
        self,
        unit_index: int,
        bbox: BBox,
        *,
        pii_type: PiiType = PiiType.CUSTOM,
        text: str = "",
        mode: MaskMode = MaskMode.DELETE_AND_BOX,
    ) -> DetectionItem:
        item = DetectionItem(
            id=new_id(),
            unit_index=unit_index,
            bbox=bbox,
            text=text or "(수동 마스킹)",
            pii_type=pii_type,
            source=MaskSource.MANUAL,
            status=DetectionStatus.CONFIRMED,
            confidence=1.0,
            mode=mode,
        )
        self.items.append(item)
        return item

    def remove_item(self, item_id: str) -> None:
        self.items = [i for i in self.items if i.id != item_id]

    def masks(self) -> list[MaskRegion]:
        out: list[MaskRegion] = []
        for item in self.items:
            if item.status != DetectionStatus.CONFIRMED:
                continue
            out.append(
                MaskRegion(
                    id=item.id,
                    unit_index=item.unit_index,
                    bbox=item.bbox,
                    mode=item.mode,
                    pii_type=item.pii_type,
                    source=item.source,
                    pattern_id=item.pattern_id,
                    label=item.text,
                )
            )
        return out

    def filtered(
        self,
        *,
        unit_index: int | None = None,
        pii_type: PiiType | None = None,
        status: DetectionStatus | None = None,
        hide_terminal: bool = False,
    ) -> list[DetectionItem]:
        result: list[DetectionItem] = []
        for item in self.items:
            if unit_index is not None and item.unit_index != unit_index:
                continue
            if pii_type is not None and item.pii_type != pii_type:
                continue
            if status is not None and item.status != status:
                continue
            if hide_terminal and item.status in (
                DetectionStatus.IGNORED,
                DetectionStatus.CANCELLED,
            ):
                continue
            result.append(item)
        return result


def _bbox_iou(a: BBox, b: BBox) -> float:
    ix0, iy0 = max(a.x0, b.x0), max(a.y0, b.y0)
    ix1, iy1 = min(a.x1, b.x1), min(a.y1, b.y1)
    iw, ih = max(0.0, ix1 - ix0), max(0.0, iy1 - iy0)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, a.x1 - a.x0) * max(0.0, a.y1 - a.y0)
    area_b = max(0.0, b.x1 - b.x0) * max(0.0, b.y1 - b.y0)
    union = area_a + area_b - inter
    return inter / union if union else 0.0
