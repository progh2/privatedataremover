"""Open the appropriate DocumentAdapter for a file path."""

from __future__ import annotations

from pathlib import Path

from privatedataremover.core.adapters.base import DocumentAdapter
from privatedataremover.core.adapters.hwpx import HwpxAdapter
from privatedataremover.core.adapters.pdf import PdfAdapter
from privatedataremover.core.adapters.xlsx import XlsxAdapter


_OPENERS: dict[str, type[DocumentAdapter]] = {
    ".pdf": PdfAdapter,
    ".xlsx": XlsxAdapter,
    ".xlsm": XlsxAdapter,
    ".hwpx": HwpxAdapter,
}


def adapter_for_path(path: Path) -> DocumentAdapter:
    ext = path.suffix.lower()
    cls = _OPENERS.get(ext)
    if cls is None:
        supported = ", ".join(sorted(_OPENERS))
        raise ValueError(f"지원하지 않는 형식입니다: {ext or '(없음)'}\n지원: {supported}")
    return cls()


def open_document(path: Path) -> DocumentAdapter:
    """Create adapter, open path, return ready instance."""
    adapter = adapter_for_path(path)
    adapter.open(Path(path))
    return adapter


def supported_extensions() -> tuple[str, ...]:
    return tuple(sorted(_OPENERS))
