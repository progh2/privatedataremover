# 빌드 · 패키징

## 개발 실행

```bash
pip install -e ".[dev]"
python -m privatedataremover
```

## PyInstaller (데스크탑 실행 파일)

```bash
pip install -e ".[dev,packaging]"
pyinstaller packaging/privatedataremover.spec
```

결과물:

- Windows: `dist/PrivateDataRemover/PrivateDataRemover.exe`
- macOS / Linux: `dist/PrivateDataRemover/PrivateDataRemover`

> Qt / PyMuPDF 플러그인 때문에 onedir 구성을 기본으로 합니다.  
> 바이러스 백신에 오탐될 수 있으니 서명·배포 채널을 확인하세요.

### Windows 빠른 스크립트

```powershell
pwsh scripts/build_windows.ps1
```

## 샘플 PDF

```bash
python scripts/make_sample_pdf.py
```

`tests/fixtures/` 아래에 수동 테스트용 PDF가 생성됩니다.

## CI

GitHub Actions `.github/workflows/ci.yml`에서 `pytest`를 실행합니다.
