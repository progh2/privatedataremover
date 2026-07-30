"""Settings dialog: LLM providers, local-only mode, OCR path."""

from __future__ import annotations

from PySide6.QtCore import Qt
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

from privatedataremover.core.llm import list_ollama_models, probe_connection
from privatedataremover.core.pii.ocr import (
    check_tesseract,
    common_tesseract_candidates,
    install_guide_text,
)
from privatedataremover.core.settings import AppSettings, LlmProvider, coerce_provider


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("설정")
        self.resize(560, 460)
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
        self.ollama_model = QComboBox()
        self.ollama_model.setEditable(True)
        self.ollama_model.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.ollama_model.setMinimumWidth(220)
        self.btn_refresh_ollama = QPushButton("모델 목록 불러오기")
        self.btn_refresh_ollama.clicked.connect(self._refresh_ollama_models)

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
        self.tesseract_cmd.setPlaceholderText("비우면 PATH / 자동 검색 경로 사용")
        self.ocr_languages = QLineEdit()
        self.ocr_languages.setPlaceholderText("예: kor+eng")
        self.ocr_status_label = QLabel("")
        self.ocr_status_label.setWordWrap(True)

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
        model_row = QHBoxLayout()
        model_row.addWidget(self.ollama_model, stretch=1)
        model_row.addWidget(self.btn_refresh_ollama)
        ollama_form.addRow("모델", model_row)
        ollama_form.addRow(
            QLabel("「모델 목록 불러오기」로 로컬 Ollama에 설치된 모델을 선택하세요.")
        )
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
        ocr_layout = QVBoxLayout(ocr_tab)
        ocr_form = QFormLayout()

        tess_row = QHBoxLayout()
        tess_row.addWidget(self.tesseract_cmd, stretch=1)
        browse = QPushButton("찾아보기…")
        browse.clicked.connect(self._browse_tesseract)
        auto_btn = QPushButton("자동 검색")
        auto_btn.setToolTip("PATH 및 일반적인 설치 경로에서 Tesseract를 찾습니다.")
        auto_btn.clicked.connect(self._auto_detect_tesseract)
        tess_row.addWidget(browse)
        tess_row.addWidget(auto_btn)
        ocr_form.addRow("Tesseract 경로", tess_row)
        ocr_form.addRow("OCR 언어", self.ocr_languages)
        lang_hint = QLabel(
            "여러 언어는 <code>kor+eng</code>처럼 <code>+</code>로 연결합니다. "
            "한국어 문서는 <code>kor</code> 언어 팩이 필요합니다."
        )
        lang_hint.setWordWrap(True)
        lang_hint.setOpenExternalLinks(True)
        ocr_form.addRow(lang_hint)
        ocr_layout.addLayout(ocr_form)

        check_row = QHBoxLayout()
        check_btn = QPushButton("Tesseract 확인")
        check_btn.setToolTip("설치 여부와 버전·언어 팩을 검사합니다.")
        check_btn.clicked.connect(self._on_check_tesseract)
        check_row.addWidget(check_btn)
        check_row.addStretch()
        ocr_layout.addLayout(check_row)
        ocr_layout.addWidget(self.ocr_status_label)

        guide = QLabel(install_guide_text())
        guide.setWordWrap(True)
        guide.setOpenExternalLinks(True)
        guide.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        guide_box = QGroupBox("설치 안내")
        guide_layout = QVBoxLayout(guide_box)
        guide_layout.addWidget(guide)
        ocr_layout.addWidget(guide_box)
        ocr_layout.addStretch()
        tabs.addTab(ocr_tab, "OCR")

        tabs.currentChanged.connect(self._on_tab_changed)
        self._tabs = tabs

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

    def _set_ollama_model_text(self, model: str) -> None:
        model = (model or "").strip()
        if not model:
            return
        idx = self.ollama_model.findText(model)
        if idx < 0:
            self.ollama_model.addItem(model)
            idx = self.ollama_model.findText(model)
        self.ollama_model.setCurrentIndex(max(0, idx))
        self.ollama_model.setEditText(model)

    def _load_into_form(self) -> None:
        s = self._settings
        idx = self.provider_combo.findData(s.provider)
        self.provider_combo.setCurrentIndex(max(0, idx))
        self.local_only.setChecked(s.local_only)
        self.ollama_url.setText(s.ollama_base_url)
        self._set_ollama_model_text(s.ollama_model or "llama3.2")
        self.openai_url.setText(s.openai_base_url)
        self.openai_key.setText(s.openai_api_key)
        self.openai_model.setText(s.openai_model)
        self.anthropic_key.setText(s.anthropic_api_key)
        self.anthropic_model.setText(s.anthropic_model)
        self.tesseract_cmd.setText(s.tesseract_cmd)
        self.ocr_languages.setText(s.ocr_languages)

    def _refresh_ollama_models(self) -> None:
        base = self.ollama_url.text().strip() or "http://localhost:11434"
        current = self.ollama_model.currentText().strip()
        self.status_label.setText("Ollama 모델 목록 조회 중…")
        self.status_label.repaint()
        try:
            models = list_ollama_models(base)
        except Exception as exc:  # noqa: BLE001
            self.status_label.setText(
                f'<span style="color:#b00020">모델 목록 실패: {exc}</span>'
            )
            QMessageBox.warning(
                self,
                "Ollama 모델",
                f"모델 목록을 가져오지 못했습니다.\nOllama가 실행 중인지 확인하세요.\n\n{exc}",
            )
            return

        self.ollama_model.blockSignals(True)
        self.ollama_model.clear()
        if models:
            self.ollama_model.addItems(models)
            self.status_label.setText(
                f'<span style="color:#0a7a2f">모델 {len(models)}개 불러옴</span>'
            )
        else:
            self.status_label.setText(
                '<span style="color:#b00020">설치된 모델이 없습니다. '
                "`ollama pull …` 후 다시 시도하세요.</span>"
            )
        self.ollama_model.blockSignals(False)

        if current:
            self._set_ollama_model_text(current)
        elif models:
            self.ollama_model.setCurrentIndex(0)

    def _on_local_only_toggled(self, checked: bool) -> None:
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

    def _on_tab_changed(self, index: int) -> None:
        if self._tabs.tabText(index) == "OCR" and not self.ocr_status_label.text():
            self._on_check_tesseract()

    def _browse_tesseract(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Tesseract 실행 파일 선택",
            "",
            "Executable (*.exe);;All Files (*)",
        )
        if path:
            self.tesseract_cmd.setText(path)
            self._on_check_tesseract()

    def _auto_detect_tesseract(self) -> None:
        candidates = common_tesseract_candidates()
        if not candidates:
            self.ocr_status_label.setText(
                '<span style="color:#b00020">자동 검색으로 Tesseract를 찾지 못했습니다. '
                "아래 설치 안내를 참고하세요.</span>"
            )
            QMessageBox.information(
                self,
                "자동 검색",
                "일반적인 설치 경로에서 Tesseract를 찾지 못했습니다.\n"
                "설치 후 「찾아보기」로 실행 파일을 지정하세요.",
            )
            return
        self.tesseract_cmd.setText(candidates[0])
        if len(candidates) > 1:
            self.ocr_status_label.setText(
                f"자동 검색: {len(candidates)}개 후보 중 첫 경로를 사용합니다."
            )
        self._on_check_tesseract()

    def _on_check_tesseract(self) -> None:
        cmd = self.tesseract_cmd.text().strip()
        langs = self.ocr_languages.text().strip() or "kor+eng"
        self.ocr_status_label.setText("Tesseract 확인 중…")
        self.ocr_status_label.repaint()
        result = check_tesseract(cmd)
        color = "#0a7a2f" if result.available else "#b00020"
        # Highlight missing language packs for the configured OCR languages
        extra = ""
        if result.available and result.languages:
            wanted = [p for p in langs.replace(",", "+").split("+") if p.strip()]
            missing = [w for w in wanted if w not in result.languages]
            if missing:
                color = "#b36b00"
                extra = (
                    f"<br>설정된 언어 중 없음: <b>{', '.join(missing)}</b> "
                    "— 언어 팩을 설치하거나 OCR 언어를 바꾸세요."
                )
        if result.available and result.resolved_cmd and not cmd:
            # Show discovered path so the user can optionally pin it
            extra += f"<br>사용 경로: <code>{result.resolved_cmd}</code>"
        self.ocr_status_label.setText(
            f'<span style="color:{color}">{result.message}</span>{extra}'
        )
        if not result.available:
            QMessageBox.warning(self, "Tesseract 확인", result.message)

    def _collect(self) -> AppSettings:
        return AppSettings(
            llm_provider=coerce_provider(self.provider_combo.currentData()),
            local_only=self.local_only.isChecked(),
            ollama_base_url=self.ollama_url.text().strip() or "http://localhost:11434",
            ollama_model=self.ollama_model.currentText().strip() or "llama3.2",
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
        if result.ok and draft.provider == LlmProvider.OLLAMA:
            # Keep selection; refresh list quietly
            try:
                self._refresh_ollama_models()
            except Exception:  # noqa: BLE001
                pass
        if not result.ok:
            QMessageBox.warning(self, "연결 테스트", result.message)

    def _on_accept(self) -> None:
        draft = self._collect()
        if draft.local_only and draft.provider != LlmProvider.OLLAMA:
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
