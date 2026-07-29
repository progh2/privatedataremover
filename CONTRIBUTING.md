# Contributing to Private Data Remover

감사합니다. 기여 전에 [PRD](docs/PRD.md)와 [README](README.md)를 읽어 주세요.

## 원칙

1. **문서 동기화** — 기능·설치·사용법·로드맵이 바뀌면 같은 PR에서 `README.md`와 `docs/PRD.md`를 함께 갱신합니다.
2. **이슈 먼저** — 가능하면 GitHub Issue를 만들고 브랜치/PR에 번호를 링크합니다.
3. **Adapter 경계** — 새 파일 포맷은 `DocumentAdapter` 구현으로 추가합니다. GUI·PII 엔진에 포맷 분기 if문을 흩뿌리지 마세요.
4. **원본 보존** — export는 항상 사본만 만듭니다.

## 개발 환경

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
pytest
python scripts/make_sample_pdf.py   # optional sample PDFs
```

Tesseract·Ollama는 README 설치 절을 참고하세요.  
사용 흐름: [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) · 빌드: [`docs/BUILD.md`](docs/BUILD.md)

## 브랜치·PR

- 브랜치: `feature/<issue-number>-short-name` 또는 `fix/...`
- PR 본문에 `Closes #N` 또는 `Refs #N`
- 체크리스트:
  - [ ] 테스트 추가/갱신 (해당 시)
  - [ ] README / PRD 동기화 (해당 시)
  - [ ] 새 의존성 라이선스를 `THIRD_PARTY_NOTICES.md`에 반영

## 코드 스타일

- Python 3.11+, 타입 힌트 권장
- GUI(`privatedataremover.ui`)와 core(`privatedataremover.core`) 의존 방향: UI → core only
- 시크릿·API 키를 커밋하지 마세요

## 이슈 라벨

`pdf`, `ocr`, `pii`, `ui`, `export`, `llm`, `docs`, `ext-xlsx`, `ext-hwpx`, `good first issue`
