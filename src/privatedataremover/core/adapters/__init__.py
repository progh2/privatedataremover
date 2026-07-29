"""Adapter package."""

from privatedataremover.core.adapters.base import DocumentAdapter
from privatedataremover.core.adapters.pdf import PdfAdapter

__all__ = ["DocumentAdapter", "PdfAdapter"]
