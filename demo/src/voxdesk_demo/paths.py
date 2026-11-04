"""运行时路径：源码运行与打包后（PyInstaller）都能找到模型和 .env。

两种模式：
- **源码**：模型还在各自切片里（`audio/models/`、`tts/models/`）
- **打包**：`sys.frozen` 为真，程序根目录是 exe 所在目录，模型统一放 `models/`
"""

from __future__ import annotations

import sys
from pathlib import Path

# 三个切片各自的模型（打包时按这个布局拷到 models/ 下）
ASR_DIR_NAME = "sherpa-onnx-streaming-paraformer-bilingual-zh-en"
PIPER_MODEL_NAME = "zh_CN-huayan-medium.onnx"
VAD_MODEL_NAME = "silero_vad.onnx"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_root() -> Path:
    """源码运行时是仓库根；打包后是 exe 所在目录。"""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def models_dir() -> Path:
    """打包后的模型根目录（exe 旁边）。"""
    return app_root() / "models"


def default_asr_dir() -> Path:
    if is_frozen():
        return models_dir() / ASR_DIR_NAME
    return app_root() / "audio" / "models" / ASR_DIR_NAME


def default_piper_model() -> Path:
    if is_frozen():
        return models_dir() / PIPER_MODEL_NAME
    return app_root() / "tts" / "models" / PIPER_MODEL_NAME


def default_vad_model() -> Path:
    if is_frozen():
        return models_dir() / VAD_MODEL_NAME
    return app_root() / "audio" / "models" / VAD_MODEL_NAME


def env_files() -> list[Path]:
    """`.env` 的查找顺序：当前目录 → 程序根目录。"""
    return [Path.cwd() / ".env", app_root() / ".env"]
