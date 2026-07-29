"""HWPX DocumentAdapter — ZIP/XML text extract and string-redact export."""

from __future__ import annotations

import io
import re
import shutil
import zipfile
from pathlib import Path
from typing import Iterator, Sequence
from xml.etree import ElementTree as ET

from privatedataremover.core.adapters.base import (
    BBox,
    DocumentAdapter,
    DocumentUnit,
    ExtractedSpan,
    MaskRegion,
)
from privatedataremover.core.export_utils import file_sha256


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _iter_text_nodes(root: ET.Element) -> list[ET.Element]:
    """Collect elements that look like text runs (t, t span, etc.)."""
    nodes: list[ET.Element] = []
    for el in root.iter():
        name = _local(el.tag).lower()
        if name in {"t", "text", "char"} or (el.text and el.text.strip() and name.endswith("t")):
            if el.text and el.text.strip():
                nodes.append(el)
    return nodes


class HwpxAdapter(DocumentAdapter):
    """Minimal HWPX support via zip+xml (see docs/HWPX_SPIKE.md)."""

    format_id = "hwpx"

    def __init__(self) -> None:
        self._path: Path | None = None
        self._sections: list[tuple[str, bytes]] = []  # (arcname, xml bytes)
        self._original_sha256: str | None = None

    @property
    def unit_count(self) -> int:
        return len(self._sections)

    def open(self, path: Path) -> None:
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(path)
        self.close()
        if not zipfile.is_zipfile(path):
            raise ValueError("유효한 HWPX(ZIP) 파일이 아닙니다.")
        sections: list[tuple[str, bytes]] = []
        with zipfile.ZipFile(path, "r") as zf:
            names = [
                n
                for n in zf.namelist()
                if re.search(r"Contents/section\d+\.xml$", n.replace("\\", "/"))
                or n.replace("\\", "/").endswith("header.xml")
            ]
            # Prefer section*.xml ordered; include header
            sections_only = sorted(
                n for n in names if "section" in n.replace("\\", "/").lower()
            )
            headers = [n for n in names if n.replace("\\", "/").endswith("header.xml")]
            ordered = headers + sections_only
            if not ordered:
                # Fallback: any Contents/*.xml
                ordered = sorted(
                    n
                    for n in zf.namelist()
                    if n.replace("\\", "/").startswith("Contents/") and n.endswith(".xml")
                )
            for name in ordered:
                sections.append((name, zf.read(name)))
        if not sections:
            raise ValueError("HWPX에서 본문 XML 섹션을 찾지 못했습니다.")
        self._path = path
        self._sections = sections
        self._original_sha256 = file_sha256(path)

    def close(self) -> None:
        self._path = None
        self._sections = []
        self._original_sha256 = None

    def assert_original_untouched(self) -> None:
        if self._path and self._original_sha256:
            if file_sha256(self._path) != self._original_sha256:
                raise RuntimeError(f"원본 HWPX가 변경되었습니다: {self._path}")

    def iter_units(self) -> Iterator[DocumentUnit]:
        for i, (name, data) in enumerate(self._sections):
            # Rough size from text length
            text_len = len(self._plain_text(data))
            yield DocumentUnit(
                index=i,
                label=Path(name).name,
                width=400.0,
                height=float(max(200, text_len // 2)),
                meta={"section": name},
            )

    def extract_spans(self, unit_index: int) -> Sequence[ExtractedSpan]:
        self._require()
        name, data = self._sections[unit_index]
        root = ET.fromstring(data)
        spans: list[ExtractedSpan] = []
        for i, node in enumerate(_iter_text_nodes(root)):
            text = (node.text or "").strip()
            if not text:
                continue
            spans.append(
                ExtractedSpan(
                    unit_index=unit_index,
                    text=text,
                    bbox=BBox(0, float(i), 400, float(i + 1)),
                    from_ocr=False,
                )
            )
        return spans

    def render_unit_preview(self, unit_index: int, scale: float = 1.0) -> bytes:
        from PIL import Image, ImageDraw, ImageFont

        self._require()
        name, data = self._sections[unit_index]
        plain = self._plain_text(data)
        lines = plain.splitlines() or ["(빈 섹션)"]
        lines = lines[:80]
        w = int(520 * scale)
        line_h = int(16 * scale)
        h = int(40 * scale) + line_h * len(lines) + 20
        img = Image.new("RGB", (w, h), (252, 252, 250))
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default()
        draw.text((10, 8), f"HWPX · {Path(name).name}", fill=(30, 30, 30), font=font)
        y = int(32 * scale)
        for line in lines:
            draw.text((10, y), line[:90], fill=(0, 0, 0), font=font)
            y += line_h
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def export_safe(
        self,
        dest: Path,
        masks: Sequence[MaskRegion],
        *,
        text_remove: bool = True,
        draw_black_boxes: bool = True,
        replacement: str = "***",
    ) -> None:
        """Copy HWPX zip and replace masked label/snippet strings in XML."""
        self._require()
        dest = Path(dest)
        if self._path and dest.resolve() == self._path.resolve():
            raise ValueError("원본 파일과 같은 경로로는 저장할 수 없습니다.")

        needles: list[str] = []
        for m in masks:
            if m.label and m.label not in ("(수동 마스킹)", "(패턴 마스킹)"):
                needles.append(m.label.strip())
        needles = [n for n in needles if n]
        # Also collect from bbox-index spans if labels empty — use extract
        if not needles:
            for m in masks:
                spans = self.extract_spans(m.unit_index)
                idx = int(m.bbox.y0)
                if 0 <= idx < len(spans):
                    needles.append(spans[idx].text)

        shutil.copy2(self._path, dest)  # type: ignore[arg-type]
        if not needles or not text_remove:
            self.assert_original_untouched()
            return

        # Rewrite XML entries inside the zip
        tmp = dest.with_suffix(dest.suffix + ".tmp")
        with zipfile.ZipFile(dest, "r") as zin, zipfile.ZipFile(
            tmp, "w", compression=zipfile.ZIP_DEFLATED
        ) as zout:
            for info in zin.infolist():
                data = zin.read(info.filename)
                name = info.filename.replace("\\", "/")
                if name.endswith(".xml") and name.startswith("Contents/"):
                    try:
                        text = data.decode("utf-8")
                    except UnicodeDecodeError:
                        text = data.decode("utf-8", errors="ignore")
                    for needle in needles:
                        if needle in text:
                            text = text.replace(needle, replacement)
                    data = text.encode("utf-8")
                zout.writestr(info, data)
        tmp.replace(dest)
        self.assert_original_untouched()
        _ = draw_black_boxes  # visual boxes not applicable to XML run MVP

    def export_rasterized(
        self,
        dest: Path,
        masks: Sequence[MaskRegion],
        *,
        dpi: int = 200,
    ) -> None:
        import fitz

        self._require()
        # Build masked copy in memory path then rasterize previews
        import tempfile

        with tempfile.TemporaryDirectory(prefix="pdr_hwpx_") as td:
            tmp = Path(td) / "masked.hwpx"
            self.export_safe(tmp, masks)
            other = HwpxAdapter()
            other.open(tmp)
            try:
                out = fitz.open()
                scale = max(0.8, dpi / 150.0)
                for i, _ in enumerate(other.iter_units()):
                    png = other.render_unit_preview(i, scale=scale)
                    pix = fitz.Pixmap(png)
                    page = out.new_page(width=pix.width, height=pix.height)
                    page.insert_image(page.rect, pixmap=pix)
                out.save(dest)
                out.close()
            finally:
                other.close()
        self.assert_original_untouched()

    def _plain_text(self, data: bytes) -> str:
        root = ET.fromstring(data)
        parts = [(n.text or "").strip() for n in _iter_text_nodes(root)]
        return "\n".join(p for p in parts if p)

    def _require(self) -> None:
        if not self._sections or self._path is None:
            raise RuntimeError("HWPX 파일이 열려 있지 않습니다.")
