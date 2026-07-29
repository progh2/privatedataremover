"""Main application window (skeleton for M1)."""

from __future__ import annotations

import sys


def run_app() -> int:
    """Start the Qt event loop with a minimal shell window."""
    try:
        from PySide6.QtWidgets import QApplication, QLabel, QMainWindow
    except ImportError:
        print(
            "PySide6 is required. Install with: pip install -e .\n"
            "See README.md for full setup.",
            file=sys.stderr,
        )
        return 1

    app = QApplication(sys.argv)
    app.setApplicationName("Private Data Remover")
    app.setOrganizationName("privatedataremover")

    window = QMainWindow()
    window.setWindowTitle("Private Data Remover")
    window.resize(960, 640)
    window.setCentralWidget(
        QLabel(
            "Private Data Remover\n\n"
            "프로젝트 골격입니다. PDF 뷰어·탐지·마스킹은 마일스톤 M1–M4에서 구현됩니다.\n"
            "자세한 내용: README.md / docs/PRD.md"
        )
    )
    window.show()
    return app.exec()
