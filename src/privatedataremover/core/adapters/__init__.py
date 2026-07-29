"""Adapter package."""

from privatedataremover.core.adapters.base import DocumentAdapter
from privatedataremover.core.adapters.factory import open_document, supported_extensions
from privatedataremover.core.adapters.pdf import PdfAdapter
from privatedataremover.core.adapters.xlsx import XlsxAdapter
from privatedataremover.core.adapters.hwpx import HwpxAdapter

__all__ = [
    "DocumentAdapter",
    "PdfAdapter",
    "XlsxAdapter",
    "HwpxAdapter",
    "open_document",
    "supported_extensions",
]
