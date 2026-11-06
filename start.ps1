# 启动 VoxDesk-Web
# 优先用本仓库 .venv；没有则复用 D:\VoxDesk\demo\.venv（依赖已装好）
# 用法： .\start.ps1           默认 8800 端口
#        .\start.ps1 -Port 9000

param([int]$Port = 8800)

$ErrorActionPreference = "Stop"
$localPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$fallbackPython = "D:\VoxDesk\demo\.venv\Scripts\python.exe"
$python = if (Test-Path $localPython) { $localPython } else { $fallbackPython }
if (-not (Test-Path $python)) {
    throw "找不到 Python 环境。请按 requirements.txt 建 .venv，或保留 $fallbackPython"
}

Set-Location $PSScriptRoot
Write-Host "启动：http://127.0.0.1:$Port" -ForegroundColor Cyan
& $python server.py --port $Port
