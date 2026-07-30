@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if exist ".venv\Scripts\activate.bat" (
  call ".venv\Scripts\activate.bat"
) else if exist "venv\Scripts\activate.bat" (
  call "venv\Scripts\activate.bat"
)

where python >nul 2>&1
if errorlevel 1 (
  echo [오류] python 을 찾을 수 없습니다. Python 3.11+ 설치 후 PATH에 추가하세요.
  echo   https://www.python.org/downloads/
  pause
  exit /b 1
)

python -c "import privatedataremover" 1>nul 2>&1
if errorlevel 1 (
  echo 패키지가 없습니다. 편집 모드로 설치합니다...
  python -m pip install -e ".[dev]"
  if errorlevel 1 (
    echo [오류] pip install 실패
    pause
    exit /b 1
  )
)

echo Private Data Remover 실행 중...
python -m privatedataremover %*
set EXITCODE=%ERRORLEVEL%
if not "%EXITCODE%"=="0" pause
exit /b %EXITCODE%
