# Build Private Data Remover with PyInstaller (Windows)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

python -m pip install -e ".[packaging]" -q
python -m PyInstaller packaging/privatedataremover.spec --noconfirm
Write-Host "Output: dist/PrivateDataRemover/PrivateDataRemover.exe"
