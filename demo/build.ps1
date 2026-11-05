# 构建可分发的 Windows 目录：<仓库根>\VoxDeskVoice\（exe + 依赖 + 模型）
#
# 用法（Windows PowerShell 5.1 或 PowerShell 7 都行）：
#     cd <仓库>\demo
#     .\build.ps1
#
# 产物：与 demo\ 同级的 VoxDeskVoice\（约 464MB），压缩后可拷到别的机器
# 说明：模型不进 git；缺模型时本脚本会自动调用 scripts\fetch_models.py 下载
#       产物目录已在 .gitignore 里（/VoxDeskVoice/），不会被误提交

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# 全部用绝对路径，避免依赖当前目录（老版本用 ".." 相对路径，是报错来源之一）
$root = Split-Path -Parent $PSScriptRoot
$dist = Join-Path $root "VoxDeskVoice"
$models = Join-Path $dist "models"

# [0/4] 模型预检
Write-Host "[0/4] 检查模型..."
$needed = @(
    (Join-Path $root "audio\models\silero_vad.onnx"),
    (Join-Path $root "audio\models\sherpa-onnx-streaming-paraformer-bilingual-zh-en\encoder.int8.onnx"),
    (Join-Path $root "audio\models\sherpa-onnx-streaming-paraformer-bilingual-zh-en\decoder.int8.onnx"),
    (Join-Path $root "audio\models\sherpa-onnx-streaming-paraformer-bilingual-zh-en\tokens.txt"),
    (Join-Path $root "tts\models\zh_CN-huayan-medium.onnx"),
    (Join-Path $root "tts\models\zh_CN-huayan-medium.onnx.json")
)
$missing = @($needed | Where-Object { -not (Test-Path $_) })
if ($missing.Count -gt 0) {
    Write-Host "  缺少 $($missing.Count) 个模型文件，开始下载（约 290MB）..."
    uv run python scripts\fetch_models.py
    if ($LASTEXITCODE -ne 0) { throw "模型下载失败，构建中止" }
} else {
    Write-Host "  模型齐全，跳过下载"
}

# [1/4] 依赖
Write-Host "[1/4] 同步依赖..."
uv sync
if ($LASTEXITCODE -ne 0) { throw "uv sync 失败，构建中止" }

# [2/4] PyInstaller
Write-Host "[2/4] PyInstaller 打包（输出到 $dist）..."
uv run pyinstaller --noconfirm --clean --onedir --name VoxDeskVoice `
    --distpath $root `
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
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 失败，构建中止" }
if (-not (Test-Path (Join-Path $dist "VoxDeskVoice.exe"))) {
    throw "没有生成 VoxDeskVoice.exe，构建中止"
}

# [3/4] 拷模型
Write-Host "[3/4] 拷模型..."
New-Item -ItemType Directory -Force -Path $models | Out-Null
Copy-Item -Recurse -Force (Join-Path $root "audio\models\sherpa-onnx-streaming-paraformer-bilingual-zh-en") $models
Copy-Item -Force (Join-Path $root "tts\models\zh_CN-huayan-medium.onnx"), (Join-Path $root "tts\models\zh_CN-huayan-medium.onnx.json") $models
Copy-Item -Force (Join-Path $root "audio\models\silero_vad.onnx") $models
Copy-Item -Force ".env.example" (Join-Path $dist ".env.example")

# [4/4] 可选：带上本地 .env（含真 key，分发前删掉）
if (Test-Path ".env") {
    Copy-Item -Force ".env" (Join-Path $dist ".env")
    Write-Host "  已把 demo\.env 复制到产物目录（分发前记得删除）"
}

$bytes = (Get-ChildItem $dist -Recurse -File | Measure-Object Length -Sum).Sum
$size = [math]::Round($bytes / 1MB)
Write-Host ""
Write-Host "完成：$dist（$size MB）"
Write-Host "分发：压缩整个 VoxDeskVoice 文件夹（不含 .env）；接收方解压后双击 VoxDeskVoice.exe"
Write-Host ""
Write-Host "首次运行前：把 .env.example 复制成 .env（与 exe 同目录），填入 DEEPSEEK_API_KEY"
Write-Host "直接双击没有 .env 时，窗口会停在'按回车关闭'并提示缺 key，不会一闪而过"
