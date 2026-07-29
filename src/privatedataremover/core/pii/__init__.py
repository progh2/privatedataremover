"""PII detection domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4

from privatedataremover.core.adapters.base import BBox, MaskMode, MaskSource, PiiType


class DetectionStatus(str, Enum):
    PENDING = "pending"  # suggested, not yet masked
    CONFIRMED = "confirmed"  # user confirmed → masked
    IGNORED = "ignored"  # do not propose again this session
    CANCELLED = "cancelled"  # was masked, user cancelled


PII_TYPE_LABELS: dict[PiiType, str] = {
    PiiType.NAME: "이름",
    PiiType.RRN: "주민등록번호",
    PiiType.PASSPORT: "여권",
    PiiType.DRIVER_LICENSE: "운전면허",
    PiiType.PHONE: "전화번호",
    PiiType.EMAIL: "이메일",
    PiiType.ADDRESS: "주소",
    PiiType.ACCOUNT: "계좌",
    PiiType.CARD: "카드번호",
    PiiType.BIRTHDATE: "생년월일",
    PiiType.EMPLOYEE_OR_STUDENT_ID: "사번/학번",
    PiiType.CUSTOM: "사용자 지정",
    PiiType.OTHER: "기타",
}

SOURCE_LABELS: dict[MaskSource, str] = {
    MaskSource.AI: "AI",
    MaskSource.RULE: "규칙",
    MaskSource.MANUAL: "수동",
    MaskSource.PATTERN: "패턴",
}

STATUS_LABELS: dict[DetectionStatus, str] = {
    DetectionStatus.PENDING: "대기",
    DetectionStatus.CONFIRMED: "마스킹됨",
    DetectionStatus.IGNORED: "무시",
    DetectionStatus.CANCELLED: "취소됨",
}


def new_id() -> str:
    return uuid4().hex[:12]


@dataclass
class DetectionItem:
    """One PII candidate or manual mask entry."""

    id: str
    unit_index: int
    bbox: BBox
    text: str
    pii_type: PiiType
    source: MaskSource
    status: DetectionStatus = DetectionStatus.PENDING
    confidence: float = 1.0
    mode: MaskMode = MaskMode.DELETE_AND_BOX
    pattern_id: str | None = None
    ignored_reason: str = ""

    @property
    def type_label(self) -> str:
        return PII_TYPE_LABELS.get(self.pii_type, self.pii_type.value)

    @property
    def source_label(self) -> str:
        return SOURCE_LABELS.get(self.source, self.source.value)

    @property
    def status_label(self) -> str:
        return STATUS_LABELS.get(self.status, self.status.value)

    @property
    def snippet(self) -> str:
        t = self.text.replace("\n", " ").strip()
        return t if len(t) <= 40 else t[:37] + "…"


@dataclass
class SessionIgnoreRules:
    """Session-scoped suppressions so rescans do not re-propose."""

    ignored_types: set[PiiType] = field(default_factory=set)
    ignored_texts: set[str] = field(default_factory=set)  # normalized lowercase
    cancelled_ids: set[str] = field(default_factory=set)
    # (page index or None=all pages, bbox in page coords)
    ignored_regions: list[tuple[int | None, BBox]] = field(default_factory=list)

