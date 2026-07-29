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
PyMuPDF를 AGPL로 링크·배포하는 경우, 배포물 전체에 AGPL 의무가 적용될 수 있습니다. 상용 배포나 라이선스 충돌이 우려되면 대체 PDF 엔진 이슈를 참고하세요.
