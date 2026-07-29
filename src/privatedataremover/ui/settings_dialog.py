"""Settings dialog: LLM providers, local-only mode, OCR path."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from privatedataremover.core.llm import probe_connection
from privatedataremover.core.settings import AppSettings, LlmProvider


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("설정")
        self.resize(560, 420)
        self._settings = settings

        self.provider_combo = QComboBox()
        self.provider_combo.addItem("Ollama (로컬)", LlmProvider.OLLAMA)
        self.provider_combo.addItem("OpenAI", LlmProvider.OPENAI)
        self.provider_combo.addItem("Anthropic (Claude)", LlmProvider.ANTHROPIC)

        self.local_only = QCheckBox("로컬 전용 모드 (외부 API 호출 차단)")
        self.local_only.setToolTip(
            "켜면 Ollama만 사용할 수 있습니다. OpenAI/Claude 연결 테스트·호출이 차단됩니다."
        )

        # Ollama
        self.ollama_url = QLineEdit()
        self.ollama_model = QLineEdit()

        # OpenAI
        self.openai_url = QLineEdit()
        self.openai_key = QLineEdit()
        self.openai_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_model = QLineEdit()

        # Anthropic
        self.anthropic_key = QLineEdit()
        self.anthropic_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.anthropic_model = QLineEdit()

        self.tesseract_cmd = QLineEdit()
        self.ocr_languages = QLineEdit()

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)

        self._load_into_form()
        self._build_ui()
        self.local_only.toggled.connect(self._on_local_only_toggled)
        self._on_local_only_toggled(self.local_only.isChecked())

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        tabs = QTabWidget()

        llm_tab = QWidget()
        llm_form = QFormLayout(llm_tab)
        llm_form.addRow("기본 프로바이더", self.provider_combo)
        llm_form.addRow(self.local_only)

        ollama_box = QGroupBox("Ollama")
        ollama_form = QFormLayout(ollama_box)
        ollama_form.addRow("Base URL", self.ollama_url)
        ollama_form.addRow("모델", self.ollama_model)
        llm_form.addRow(ollama_box)

        openai_box = QGroupBox("OpenAI")
        openai_form = QFormLayout(openai_box)
        openai_form.addRow("Base URL", self.openai_url)
        openai_form.addRow("API 키", self._key_row(self.openai_key))
        openai_form.addRow("모델", self.openai_model)
        llm_form.addRow(openai_box)

        anthropic_box = QGroupBox("Anthropic (Claude)")
        anthropic_form = QFormLayout(anthropic_box)
        anthropic_form.addRow("API 키", self._key_row(self.anthropic_key))
        anthropic_form.addRow("모델", self.anthropic_model)
        llm_form.addRow(anthropic_box)

        test_row = QHBoxLayout()
        test_btn = QPushButton("연결 테스트")
        test_btn.clicked.connect(self._on_test_connection)
        test_row.addWidget(test_btn)
        test_row.addStretch()
        llm_form.addRow(test_row)
        llm_form.addRow(self.status_label)

        tabs.addTab(llm_tab, "LLM")

        ocr_tab = QWidget()
        ocr_form = QFormLayout(ocr_tab)
        tess_row = QHBoxLayout()
        tess_row.addWidget(self.tesseract_cmd)
        browse = QPushButton("찾아보기…")
        browse.clicked.connect(self._browse_tesseract)
        tess_row.addWidget(browse)
        ocr_form.addRow("Tesseract 경로", tess_row)
        ocr_form.addRow("OCR 언어", self.ocr_languages)
        hint = QLabel("예: kor+eng. 비어 있으면 시스템 PATH의 tesseract를 사용합니다.")
        hint.setWordWrap(True)
        ocr_form.addRow(hint)
        tabs.addTab(ocr_tab, "OCR")

        layout.addWidget(tabs)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _key_row(self, edit: QLineEdit) -> QWidget:
        wrap = QWidget()
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(edit)
        toggle = QPushButton("표시")
        toggle.setCheckable(True)

        def on_toggled(checked: bool) -> None:
            edit.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
            toggle.setText("숨김" if checked else "표시")

        toggle.toggled.connect(on_toggled)
        row.addWidget(toggle)
        return wrap

    def _load_into_form(self) -> None:
        s = self._settings
        idx = self.provider_combo.findData(s.llm_provider)
        self.provider_combo.setCurrentIndex(max(0, idx))
        self.local_only.setChecked(s.local_only)
        self.ollama_url.setText(s.ollama_base_url)
        self.ollama_model.setText(s.ollama_model)
        self.openai_url.setText(s.openai_base_url)
        self.openai_key.setText(s.openai_api_key)
        self.openai_model.setText(s.openai_model)
        self.anthropic_key.setText(s.anthropic_api_key)
        self.anthropic_model.setText(s.anthropic_model)
        self.tesseract_cmd.setText(s.tesseract_cmd)
        self.ocr_languages.setText(s.ocr_languages)

    def _on_local_only_toggled(self, checked: bool) -> None:
        # Soft-disable cloud fields visually
        for w in (
            self.openai_url,
            self.openai_key,
            self.openai_model,
            self.anthropic_key,
            self.anthropic_model,
        ):
            w.setEnabled(not checked)
        if checked and self.provider_combo.currentData() != LlmProvider.OLLAMA:
            self.provider_combo.setCurrentIndex(
                self.provider_combo.findData(LlmProvider.OLLAMA)
            )

    def _browse_tesseract(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Tesseract 실행 파일 선택",
            "",
            "Executable (*.exe);;All Files (*)",
        )
        if path:
            self.tesseract_cmd.setText(path)

    def _collect(self) -> AppSettings:
        return AppSettings(
            llm_provider=self.provider_combo.currentData(),
            local_only=self.local_only.isChecked(),
            ollama_base_url=self.ollama_url.text().strip() or "http://localhost:11434",
            ollama_model=self.ollama_model.text().strip() or "llama3.2",
            openai_base_url=self.openai_url.text().strip() or "https://api.openai.com/v1",
            openai_api_key=self.openai_key.text().strip(),
            openai_model=self.openai_model.text().strip() or "gpt-4o-mini",
            anthropic_api_key=self.anthropic_key.text().strip(),
            anthropic_model=self.anthropic_model.text().strip()
            or "claude-sonnet-4-20250514",
            tesseract_cmd=self.tesseract_cmd.text().strip(),
            ocr_languages=self.ocr_languages.text().strip() or "kor+eng",
        )

    def _on_test_connection(self) -> None:
        draft = self._collect()
        self.status_label.setText("연결 테스트 중…")
        self.status_label.repaint()
        result = probe_connection(draft)
        color = "#0a7a2f" if result.ok else "#b00020"
        self.status_label.setText(
            f'<span style="color:{color}">{result.message}</span>'
        )
        if not result.ok:
            QMessageBox.warning(self, "연결 테스트", result.message)

    def _on_accept(self) -> None:
        draft = self._collect()
        if draft.local_only and draft.llm_provider != LlmProvider.OLLAMA:
            QMessageBox.warning(
                self,
                "로컬 전용 모드",
                "로컬 전용 모드에서는 프로바이더를 Ollama로 설정해야 합니다.",
            )
            return
        self._settings = draft
        self.accept()

    def result_settings(self) -> AppSettings:
        return self._settings
