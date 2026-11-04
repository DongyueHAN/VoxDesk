# 构建可分发的 Windows 目录：D:\VoxDesk\VoxDeskVoice\（exe + 依赖 + 模型）
#
# 用法：在 PowerShell 里
#     cd D:\VoxDesk\demo
#     .\build.ps1
#
# 产物：**仓库根下的 VoxDeskVoice\**（与 demo\ 同级），整个文件夹压缩后即可拷到别的机器（约 460MB）
# 注意：模型不进 git（根 .gitignore 已忽略 models/），构建时从各切片拷过来；
#       产物目录也在 .gitignore 里（/VoxDeskVoice/），不会被误提交

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "[1/3] 同步依赖…"
uv sync

Write-Host "[2/3] PyInstaller 打包（输出到 ..\VoxDeskVoice）…"
uv run pyinstaller --noconfirm --clean --onedir --name VoxDeskVoice `
    --distpath ".." `
    --workpath "build" `
    --collect-all sherpa_onnx `
    --collect-all onnxruntime `
    --collect-all piper `
    --collect-all sounddevice `
    --collect-all soundcard `
    --collect-submodules win32com `
    --hidden-import pythoncom `
    --hidden-import pywintypes `
    --add-data ".env.example;." `
    launcher.py

Write-Host "[3/3] 拷模型…"
$dist = Join-Path ".." "VoxDeskVoice"
$models = Join-Path $dist "models"
New-Item -ItemType Directory -Force -Path $models | Out-Null
Copy-Item -Recurse -Force (Join-Path "..\audio\models" "sherpa-onnx-streaming-paraformer-bilingual-zh-en") $models
Copy-Item -Force (Join-Path "..\tts\models" "zh_CN-huayan-medium.onnx"), (Join-Path "..\tts\models" "zh_CN-huayan-medium.onnx.json") $models
Copy-Item -Force (Join-Path "..\audio\models" "silero_vad.onnx") $models
Copy-Item -Force ".env.example" (Join-Path $dist ".env.example")

# 如果 demo\.env 存在，顺手复制一份过去（省得手动拷；注意这份含真 key，分发前删掉）
if (Test-Path ".env") {
    Copy-Item -Force ".env" (Join-Path $dist ".env")
    Write-Host "  已把 demo\.env 复制到产物目录（分发前记得删除）"
}

$size = [math]::Round((Get-ChildItem $dist -Recurse -File | Measure-Object Length -Sum).Sum / 1MB)
Write-Host ""
Write-Host "完成：$((Resolve-Path $dist).Path)（$size MB）"
Write-Host "分发：压缩整个 VoxDeskVoice 文件夹（不含 .env）；接收方解压后双击 VoxDeskVoice.exe"
Write-Host ""
Write-Host "首次运行前：把 .env.example 复制成 .env（**与 exe 同目录**，即 VoxDeskVoice\.env）并填入 DEEPSEEK_API_KEY。"
Write-Host "直接双击没有 .env 时，窗口会停在'按回车关闭'并提示缺 key，不会再一闪而过。"
