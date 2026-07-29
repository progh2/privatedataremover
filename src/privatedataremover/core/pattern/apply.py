"""Apply seed masks to similar pages."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from privatedataremover.core.adapters.base import BBox, DocumentUnit, MaskSource, PiiType
from privatedataremover.core.pii import DetectionItem, DetectionStatus, new_id


class CoordMode(str, Enum):
    ABSOLUTE = "absolute"
    RELATIVE = "relative"


@dataclass(frozen=True)
class SeedMask:
    bbox: BBox
    pii_type: PiiType
    text: str
    mode: str  # MaskMode value


@dataclass
class PatternProposal:
    pattern_id: str
    seed_index: int
    target_indices: list[int]
    seeds: list[SeedMask]
    coord_mode: CoordMode
    scores: dict[int, float]


def map_bbox(
    bbox: BBox,
    *,
    seed_unit: DocumentUnit,
    target_unit: DocumentUnit,
    mode: CoordMode,
) -> BBox:
    if mode == CoordMode.ABSOLUTE:
        return bbox
    sw = seed_unit.width or 1.0
    sh = seed_unit.height or 1.0
    tw = target_unit.width or sw
    th = target_unit.height or sh
    sx, sy = tw / sw, th / sh
    return BBox(bbox.x0 * sx, bbox.y0 * sy, bbox.x1 * sx, bbox.y1 * sy)


def build_pattern_items(
    proposal: PatternProposal,
    *,
    units: dict[int, DocumentUnit],
    exclude_pages: set[int] | None = None,
) -> list[DetectionItem]:
    """Materialize confirmed pattern masks for target pages."""
    exclude = exclude_pages or set()
    seed_unit = units[proposal.seed_index]
    created: list[DetectionItem] = []
    for target in proposal.target_indices:
        if target in exclude or target == proposal.seed_index:
            continue
        target_unit = units[target]
        for seed in proposal.seeds:
            bbox = map_bbox(
                seed.bbox,
                seed_unit=seed_unit,
                target_unit=target_unit,
                mode=proposal.coord_mode,
            )
            from privatedataremover.core.adapters.base import MaskMode

            try:
                mode = MaskMode(seed.mode)
            except ValueError:
                mode = MaskMode.DELETE_AND_BOX
            created.append(
                DetectionItem(
                    id=new_id(),
                    unit_index=target,
                    bbox=bbox,
                    text=seed.text or "(패턴 마스킹)",
                    pii_type=seed.pii_type,
                    source=MaskSource.PATTERN,
                    status=DetectionStatus.CONFIRMED,
                    confidence=proposal.scores.get(target, 0.8),
                    mode=mode,
                    pattern_id=proposal.pattern_id,
                )
            )
    return created
