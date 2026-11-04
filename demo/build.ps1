# 构建可分发的 Windows 目录：dist\VoxDeskVoice\（exe + 依赖 + 模型）
#
# 用法：在 PowerShell 里
#     cd D:\VoxDesk\demo
#     .\build.ps1
#
# 产物：dist\VoxDeskVoice\，整个文件夹压缩后即可拷到别的机器（约 460MB）
# 注意：模型不进 git（根 .gitignore 已忽略 models/），构建时从各切片拷过来

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "[1/3] 同步依赖…"
uv sync

Write-Host "[2/3] PyInstaller 打包…"
uv run pyinstaller --noconfirm --clean --onedir --name VoxDeskVoice `
    --collect-all sherpa_onnx `
    --collect-all onnxruntime `
    --collect-all piper `
    --collect-all sounddevice `
    --collect-submodules win32com `
    --hidden-import pythoncom `
    --hidden-import pywintypes `
    --add-data ".env.example;." `
    launcher.py

Write-Host "[3/3] 拷模型…"
$dist = Join-Path "dist" "VoxDeskVoice"
$models = Join-Path $dist "models"
New-Item -ItemType Directory -Force -Path $models | Out-Null
Copy-Item -Recurse -Force (Join-Path "..\audio\models" "sherpa-onnx-streaming-paraformer-bilingual-zh-en") $models
Copy-Item -Force (Join-Path "..\tts\models" "zh_CN-huayan-medium.onnx"), (Join-Path "..\tts\models" "zh_CN-huayan-medium.onnx.json") $models
Copy-Item -Force (Join-Path "..\audio\models" "silero_vad.onnx") $models
Copy-Item -Force ".env.example" (Join-Path $dist ".env.example")

$size = [math]::Round((Get-ChildItem $dist -Recurse -File | Measure-Object Length -Sum).Sum / 1MB)
Write-Host ""
Write-Host "完成：$dist（$size MB）"
Write-Host "分发：压缩整个 VoxDeskVoice 文件夹；接收方解压后双击 VoxDeskVoice.exe"
