# Private Data Remover launcher (PowerShell)
# UTF-8 BOM — Windows PowerShell 5.1 (시스템 기본 CP949)에서도 한글 정상
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$activate = @(
    (Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1"),
    (Join-Path $PSScriptRoot "venv\Scripts\Activate.ps1")
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if ($activate) {
    . $activate
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "[오류] python 을 찾을 수 없습니다. Python 3.11+ 를 설치하세요." -ForegroundColor Red
    exit 1
}

python -c "import privatedataremover" 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "패키지가 없습니다. 편집 모드로 설치합니다..."
    python -m pip install -e ".[dev]"
}

Write-Host "Private Data Remover 실행 중..."
python -m privatedataremover @args
exit $LASTEXITCODE
