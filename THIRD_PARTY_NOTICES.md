# Third-Party Notices

이 프로젝트는 다음 오픈소스 구성 요소를 사용할 수 있습니다.  
배포·수정 시 각 라이선스 의무를 확인하세요.

| 구성 요소 | 용도 | 라이선스 (요약) | 비고 |
|-----------|------|-----------------|------|
| PySide6 | GUI | LGPLv3 / 상용 | Qt for Python |
| PyMuPDF (pymupdf) | PDF | **AGPL-3.0** 또는 상용 | AGPL 의무(소스 제공 등) 준수 또는 상용 라이선스 검토 |
| pytesseract | OCR 래퍼 | Apache-2.0 | Tesseract 엔진은 별도 설치 (Apache-2.0) |
| httpx | HTTP | BSD-3-Clause | LLM API |
| openai (optional) | OpenAI SDK | Apache-2.0 | |
| anthropic (optional) | Claude SDK | MIT | |
| pytest | 테스트 | MIT | dev |

앱 소스 코드는 [Apache License 2.0](LICENSE)입니다.

**배포 정책 (2026-07-29, #4):** 오픈소스 바이너리/소스 배포에서 **PyMuPDF AGPL-3.0을 수용**합니다.  
자세한 내용은 [`docs/LICENSING.md`](docs/LICENSING.md)를 참고하세요.  
상용 폐쇄 배포가 필요하면 Artifex 상용 라이선스 또는 대체 PDF 엔진을 검토하세요.
