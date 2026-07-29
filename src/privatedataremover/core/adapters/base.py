"""Abstract document adapter and shared geometry types.

New formats (xlsx, hwpx) implement DocumentAdapter without changing GUI/PII core.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterator, Sequence


class PiiType(str, Enum):
    """Detected or user-assigned personal data category."""

    NAME = "name"
    RRN = "rrn"  # resident registration number
    PASSPORT = "passport"
    DRIVER_LICENSE = "driver_license"
    PHONE = "phone"
    EMAIL = "email"
    ADDRESS = "address"
    ACCOUNT = "account"
    CARD = "card"
    BIRTHDATE = "birthdate"
    EMPLOYEE_OR_STUDENT_ID = "employee_or_student_id"
    CUSTOM = "custom"
    OTHER = "other"


class MaskMode(str, Enum):
    BLACK_BOX = "black_box"
    DELETE_AND_BOX = "delete_and_box"


class MaskSource(str, Enum):
    AI = "ai"
    RULE = "rule"
    MANUAL = "manual"
    PATTERN = "pattern"


@dataclass(frozen=True)
class BBox:
    """Axis-aligned box in page/unit coordinates (origin top-left, y down)."""

    x0: float
    y0: float
    x1: float
    y1: float

    def padded(self, pad: float) -> BBox:
        return BBox(self.x0 - pad, self.y0 - pad, self.x1 + pad, self.y1 + pad)


@dataclass
class DocumentUnit:
    """One navigable unit: PDF page, Excel sheet, or HWPX section."""

    index: int
    label: str
    width: float
    height: float
    meta: dict = field(default_factory=dict)


@dataclass
class ExtractedSpan:
    """Text span with optional geometry for overlay and masking."""

    unit_index: int
    text: str
    bbox: BBox | None = None
    from_ocr: bool = False


@dataclass
class MaskRegion:
    """A region to redact in a document unit."""

    id: str
    unit_index: int
    bbox: BBox
    mode: MaskMode = MaskMode.DELETE_AND_BOX
    pii_type: PiiType = PiiType.CUSTOM
    source: MaskSource = MaskSource.MANUAL
    pattern_id: str | None = None
    label: str = ""


class DocumentAdapter(ABC):
    """Format-specific open / extract / mask / export contract."""

    format_id: str = "unknown"

    @property
    def path(self) -> Path | None:
        return getattr(self, "_path", None)

    @property
    def unit_count(self) -> int:
        return sum(1 for _ in self.iter_units())

    def assert_original_untouched(self) -> None:
        """Optional integrity check; overrides may raise if original changed."""
        return

    @abstractmethod
    def open(self, path: Path) -> None:
        """Load document from path. Must not modify the original file."""

    @abstractmethod
    def close(self) -> None:
        """Release resources."""

    @abstractmethod
    def iter_units(self) -> Iterator[DocumentUnit]:
        """Yield pages, sheets, or sections."""

    @abstractmethod
    def extract_spans(self, unit_index: int) -> Sequence[ExtractedSpan]:
        """Return text spans for PII analysis (native text and/or OCR)."""

    @abstractmethod
    def render_unit_preview(self, unit_index: int, scale: float = 1.0) -> bytes:
        """Return PNG (or similar) bytes for UI preview."""

    @abstractmethod
    def export_safe(
        self,
        dest: Path,
        masks: Sequence[MaskRegion],
        *,
        text_remove: bool = True,
        draw_black_boxes: bool = True,
    ) -> None:
        """Export copy with selective text removal and/or black boxes."""

    @abstractmethod
    def export_rasterized(
        self,
        dest: Path,
        masks: Sequence[MaskRegion],
        *,
        dpi: int = 200,
    ) -> None:
        """Rasterize each unit (with masks baked in) into a new PDF."""
