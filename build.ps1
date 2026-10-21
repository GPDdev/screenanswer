param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
& $Python -m PyInstaller --noconfirm --onefile --windowed --name ScreenAnswer --exclude-module numpy --add-data 'screenanswer/ocr.ps1;screenanswer' main.py
if ($LASTEXITCODE -ne 0) { throw 'Build failed.' }
Write-Output 'Created dist/ScreenAnswer.exe'
