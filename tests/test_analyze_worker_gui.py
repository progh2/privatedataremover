"""GUI-level regression test: threaded analysis must not crash the app.

Reproduces the crash where dropping the last Python reference to a running
QThread destroyed its C++ object mid-flight and killed the process.
"""

from __future__ import annotations

import gc
from pathlib import Path

import fitz
import pytest
from PySide6.QtWidgets import QMessageBox

from privatedataremover.ui.main_window import MainWindow


def _make_pdf(path: Path, pages: int = 3) -> None:
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page()
        page.insert_text((72, 72), f"이름: 홍길동 연락처 010-1234-567{i}")
    doc.save(path)
    doc.close()


@pytest.fixture
def window(qtbot, monkeypatch):
    # Modal dialogs would block the test; silence them.
    monkeypatch.setattr(
        QMessageBox, "information", staticmethod(lambda *a, **k: None)
    )
    monkeypatch.setattr(
        QMessageBox, "critical", staticmethod(lambda *a, **k: None)
    )
    win = MainWindow()
    qtbot.addWidget(win)
    return win


def test_threaded_analysis_survives_gc(qtbot, window, tmp_path) -> None:
    pdf = tmp_path / "sample.pdf"
    _make_pdf(pdf)

    window.chk_use_ocr.setChecked(False)
    window.chk_use_llm.setChecked(False)
    window.open_document_path(pdf)
    assert window.adapter is not None

    window.run_analysis()
    assert window._is_busy() or window.session.items

    qtbot.waitUntil(lambda: not window._is_busy(), timeout=30000)
    # Force garbage collection while the thread winds down — this is what
    # crashed the process before the thread got a parent + late ref release.
    gc.collect()
    qtbot.wait(300)
    gc.collect()

    assert len(window.session.items) > 0
    # Default PDF base font cannot embed Hangul, so assert on the phone number.
    assert any("010-1234-567" in i.text for i in window.session.items)
    # Job refs are released once the thread fully stops.
    qtbot.waitUntil(lambda: window._job_thread is None, timeout=5000)
    assert window._job_worker is None


def test_cancel_mask_then_overlay_click_no_recursion(qtbot, window, tmp_path) -> None:
    """Selecting, cancelling a mask, then clicking the preview must not
    recurse populate() -> setCurrentRow -> selection_changed -> refresh."""
    pdf = tmp_path / "cancel_click.pdf"
    _make_pdf(pdf)

    window.chk_use_ocr.setChecked(False)
    window.chk_use_llm.setChecked(False)
    window.open_document_path(pdf)
    window.run_analysis()
    qtbot.waitUntil(lambda: not window._is_busy(), timeout=30000)
    qtbot.wait(200)
    assert len(window.session.items) >= 2

    # User selects the first row in the detection list (signals unblocked).
    window.detection_panel.list.setCurrentRow(0)
    qtbot.wait(50)
    assert window._selected_id is not None

    # User presses "마스킹 취소".
    window.detection_panel.btn_cancel.click()
    qtbot.wait(50)

    # User clicks another detection box in the preview.
    other = next(
        i for i in window.session.items if i.id != window._selected_id
    )
    window._on_overlay_clicked(other.id)
    qtbot.wait(50)

    # Then selects a row again via the list (second recursion path).
    window.detection_panel.list.setCurrentRow(0)
    qtbot.wait(50)

    assert window._selected_id is not None
    assert window.act_analyze.isEnabled()


def test_ignore_advances_selection_and_undo_restores(qtbot, window, tmp_path) -> None:
    """Fast review: 무시 moves selection to the next row; Ctrl+Z restores."""
    from privatedataremover.core.pii import DetectionStatus

    pdf = tmp_path / "review.pdf"
    _make_pdf(pdf, pages=3)

    window.chk_use_ocr.setChecked(False)
    window.chk_use_llm.setChecked(False)
    window.open_document_path(pdf)
    window.run_analysis()
    qtbot.waitUntil(lambda: not window._is_busy(), timeout=30000)
    qtbot.wait(200)

    ids = window.detection_panel.ordered_ids()
    assert len(ids) >= 2

    window.detection_panel.list.setCurrentRow(0)
    qtbot.wait(50)
    first_id, second_id = ids[0], ids[1]
    assert window._selected_id == first_id

    window.detection_panel.btn_ignore.click()
    qtbot.wait(50)
    assert window.session.get(first_id).status == DetectionStatus.IGNORED
    # Selection advanced to the next item for fast review.
    assert window._selected_id == second_id
    assert window.detection_panel.current_id() == second_id
    assert window.act_undo.isEnabled()

    window.undo()
    qtbot.wait(50)
    assert window.session.get(first_id).status == DetectionStatus.PENDING
    assert window.act_redo.isEnabled()

    window.redo()
    qtbot.wait(50)
    assert window.session.get(first_id).status == DetectionStatus.IGNORED


def test_overlay_click_resets_filter_and_selects(qtbot, window, tmp_path) -> None:
    """Clicking a mask in the preview shows that item in the list, switching
    the type filter to 모든 유형 if it would hide the item."""
    from privatedataremover.core.adapters.base import PiiType

    pdf = tmp_path / "overlay_filter.pdf"
    _make_pdf(pdf)

    window.chk_use_ocr.setChecked(False)
    window.chk_use_llm.setChecked(False)
    window.open_document_path(pdf)
    window.run_analysis()
    qtbot.waitUntil(lambda: not window._is_busy(), timeout=30000)
    qtbot.wait(200)

    phone = next(
        i for i in window.session.items if i.pii_type == PiiType.PHONE
    )
    panel = window.detection_panel

    # Filter to a type that hides the phone item.
    email_idx = panel.filter_type.findData(PiiType.EMAIL)
    panel.filter_type.setCurrentIndex(email_idx)
    qtbot.wait(50)
    assert phone.id not in panel.ordered_ids()

    # Clicking the phone overlay must reset the filter and select the item.
    window._on_overlay_clicked(phone.id)
    qtbot.wait(50)
    assert panel.filter_pii_type() is None
    assert panel.current_id() == phone.id


def test_cancel_type_via_signal_does_not_crash(qtbot, window, tmp_path) -> None:
    """PiiType is a str Enum; Signal(object) delivers it as plain str.
    The button path through the panel signal must still work."""
    from privatedataremover.core.adapters.base import PiiType
    from privatedataremover.core.pii import DetectionStatus

    pdf = tmp_path / "cancel_type.pdf"
    _make_pdf(pdf)

    window.chk_use_ocr.setChecked(False)
    window.chk_use_llm.setChecked(False)
    window.open_document_path(pdf)
    window.run_analysis()
    qtbot.waitUntil(lambda: not window._is_busy(), timeout=30000)
    qtbot.wait(200)

    panel = window.detection_panel
    # cancel_by_type only affects confirmed masks, so confirm first.
    panel.btn_confirm_all.click()
    qtbot.wait(50)
    phone_idx = panel.filter_type.findData(PiiType.PHONE)
    panel.filter_type.setCurrentIndex(phone_idx)
    qtbot.wait(50)

    # Real user path: button click → Signal(object) → main window handler.
    panel.btn_cancel_type.click()
    qtbot.wait(50)

    phones = [i for i in window.session.items if i.pii_type == PiiType.PHONE]
    assert phones
    assert all(i.status == DetectionStatus.CANCELLED for i in phones)


def test_second_analysis_after_first(qtbot, window, tmp_path) -> None:
    pdf = tmp_path / "sample2.pdf"
    _make_pdf(pdf, pages=2)

    window.chk_use_ocr.setChecked(False)
    window.chk_use_llm.setChecked(False)
    window.open_document_path(pdf)

    for _ in range(2):
        window.run_analysis()
        qtbot.waitUntil(lambda: not window._is_busy(), timeout=30000)
        qtbot.wait(200)

    assert window.act_analyze.isEnabled()
