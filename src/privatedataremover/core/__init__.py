"""Document format adapters (PDF now; Excel/HWPX later)."""

from privatedataremover.core.adapters.base import (
    BBox,
    DocumentAdapter,
    DocumentUnit,
    ExtractedSpan,
    MaskRegion,
)

__all__ = [
    "BBox",
    "DocumentAdapter",
    "DocumentUnit",
    "ExtractedSpan",
    "MaskRegion",
]
