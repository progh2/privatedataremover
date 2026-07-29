"""Rule-based Korean/common PII detectors."""

from __future__ import annotations

import re
from dataclasses import dataclass

from privatedataremover.core.adapters.base import BBox, ExtractedSpan, MaskSource, PiiType
from privatedataremover.core.pii import DetectionItem, DetectionStatus, new_id


@dataclass(frozen=True)
class RulePattern:
    pii_type: PiiType
    pattern: re.Pattern[str]
    confidence: float = 0.9


# Order matters: more specific first.
_RULES: list[RulePattern] = [
    RulePattern(
        PiiType.RRN,
        re.compile(r"(?<!\d)\d{6}\s*[-–]?\s*[1-4]\d{6}(?!\d)"),
        0.95,
    ),
    RulePattern(
        PiiType.CARD,
        re.compile(r"(?<!\d)(?:\d{4}[-\s]?){3}\d{4}(?!\d)"),
        0.85,
    ),
    RulePattern(
        PiiType.PHONE,
        re.compile(
            r"(?<!\d)(?:0\d{1,2}|01[016789])[-\s]?\d{3,4}[-\s]?\d{4}(?!\d)"
        ),
        0.9,
    ),
    RulePattern(
        PiiType.EMAIL,
        re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
        0.95,
    ),
    RulePattern(
        PiiType.ACCOUNT,
        re.compile(r"(?<!\d)\d{2,6}[-\s]\d{2,6}[-\s]\d{2,8}(?!\d)"),
        0.7,
    ),
    RulePattern(
        PiiType.BIRTHDATE,
        re.compile(
            r"(?<!\d)(?:19|20)\d{2}[.\-/년]\s*\d{1,2}[.\-/월]\s*\d{1,2}일?(?!\d)"
        ),
        0.75,
    ),
]


def detect_in_text(
    text: str,
    *,
    unit_index: int,
    bbox: BBox | None,
    enabled: set[PiiType] | None = None,
) -> list[DetectionItem]:
    """Find rule matches in a single text blob (optionally with one bbox)."""
    found: list[DetectionItem] = []
    for rule in _RULES:
        if enabled is not None and rule.pii_type not in enabled:
            continue
        for match in rule.pattern.finditer(text):
            found.append(
                DetectionItem(
                    id=new_id(),
                    unit_index=unit_index,
                    bbox=bbox or BBox(0, 0, 0, 0),
                    text=match.group(0),
                    pii_type=rule.pii_type,
                    source=MaskSource.RULE,
                    status=DetectionStatus.PENDING,
                    confidence=rule.confidence,
                )
            )
    return found


def detect_in_spans(
    spans: list[ExtractedSpan],
    *,
    enabled: set[PiiType] | None = None,
) -> list[DetectionItem]:
    """Run rules on each span; prefer span bbox for overlay."""
    items: list[DetectionItem] = []
    seen: set[tuple[int, str, str]] = set()
    for span in spans:
        for item in detect_in_text(
            span.text,
            unit_index=span.unit_index,
            bbox=span.bbox,
            enabled=enabled,
        ):
            key = (item.unit_index, item.pii_type.value, item.text)
            if key in seen:
                continue
            seen.add(key)
            items.append(item)
    return items
