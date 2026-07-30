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

# Common Hancom HWPML local-names that hold visible text.
_TEXT_LOCAL_NAMES = frozenset(
    {
        "t",
        "text",
        "char",
        "hl",  # highlight run sometimes wraps text
    }
)

_CONTENTS_XML = re.compile(r"^Contents/.+\.xml$", re.IGNORECASE)
_SECTION_XML = re.compile(r"Contents/section\d+\.xml$", re.IGNORECASE)
_HEADER_FOOTER = re.compile(
    r"Contents/(header|footer)\d*\.xml$", re.IGNORECASE
)


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _iter_text_nodes(root: ET.Element) -> list[tuple[str, ET.Element]]:
    """Return (text, element) for text-bearing HWPML nodes.

    Prefers dedicated text run tags (e.g. hp:t). Falls back to any element
    whose direct text is non-empty to tolerate schema drift.
    """
    preferred: list[tuple[str, ET.Element]] = []
    fallback: list[tuple[str, ET.Element]] = []
    for el in root.iter():
        raw = el.text
        if not raw:
            continue
        text = raw.strip()
        if not text:
            continue
        name = _local(el.tag).lower()
        if name in _TEXT_LOCAL_NAMES or name.endswith(":t") or name == "t":
            preferred.append((text, el))
        else:
            # Skip giant container blobs when preferred runs exist later
            if len(text) <= 500:
                fallback.append((text, el))
    return preferred if preferred else fallback


def _collect_xml_names(zf: zipfile.ZipFile) -> list[str]:
    names = [n.replace("\\", "/") for n in zf.namelist()]
    headers = sorted(n for n in names if _HEADER_FOOTER.search(n))
    sections = sorted(n for n in names if _SECTION_XML.search(n))
    if sections or headers:
        return headers + sections
    return sorted(n for n in names if _CONTENTS_XML.match(n))


class HwpxAdapter(DocumentAdapter):
    """Minimal HWPX support via zip+xml (see docs/HWPX_SPIKE.md)."""

    format_id = "hwpx"

    def __init__(self) -> None:
        self._path: Path | None = None
        self._sections: list[tuple[str, bytes]] = []
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
            ordered = _collect_xml_names(zf)
            if not ordered:
                raise ValueError("HWPX에서 본문 XML 섹션을 찾지 못했습니다.")
            for name in ordered:
                sections.append((name, zf.read(name)))
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
            text_len = len(self._plain_text(data))
            kind = "header/footer" if _HEADER_FOOTER.search(name) else "section"
            yield DocumentUnit(
                index=i,
                label=f"{Path(name).name} [{kind}]",
                width=400.0,
                height=float(max(200, text_len // 2)),
                meta={"section": name, "kind": kind},
            )

    def extract_spans(self, unit_index: int) -> Sequence[ExtractedSpan]:
        self._require()
        _name, data = self._sections[unit_index]
        root = ET.fromstring(data)
        spans: list[ExtractedSpan] = []
        for i, (text, _node) in enumerate(_iter_text_nodes(root)):
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
        if not needles:
            for m in masks:
                spans = self.extract_spans(m.unit_index)
                idx = int(m.bbox.y0)
                if 0 <= idx < len(spans):
                    needles.append(spans[idx].text)
        # Longer needles first to avoid partial clobbering
        needles = sorted({n for n in needles if n}, key=len, reverse=True)

        shutil.copy2(self._path, dest)  # type: ignore[arg-type]
        if not needles or not text_remove:
            self.assert_original_untouched()
            return

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
        _ = draw_black_boxes

    def export_rasterized(
        self,
        dest: Path,
        masks: Sequence[MaskRegion],
        *,
        dpi: int = 200,
    ) -> None:
        import fitz
        import tempfile

        self._require()
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
        parts = [text for text, _ in _iter_text_nodes(root)]
        return "\n".join(parts)

    def _require(self) -> None:
        if not self._sections or self._path is None:
            raise RuntimeError("HWPX 파일이 열려 있지 않습니다.")
