"""运行时路径：所有资源都在本仓库内；外部只作为密钥的兜底读取。

模型已按计划复制到：
    audio/models/sherpa-onnx-streaming-paraformer-bilingual-zh-en
    audio/models/silero_vad.onnx
    tts/models/zh_CN-huayan-medium.onnx

不再通过 D:\\VoxDesk 的源码运行；D:\\VoxDesk\\demo\\.env 只作为 key 的兜底来源。
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
AUDIO_SRC = ROOT / "audio" / "src"
TTS_SRC = ROOT / "tts" / "src"

ASR_MODEL_DIR = ROOT / "audio" / "models" / "sherpa-onnx-streaming-paraformer-bilingual-zh-en"
VAD_MODEL = ROOT / "audio" / "models" / "silero_vad.onnx"
PIPER_MODEL = ROOT / "tts" / "models" / "zh_CN-huayan-medium.onnx"

DATA_DIR = ROOT / "data"
CHATS_DIR = DATA_DIR / "chats"
ARCHIVE_DIR = DATA_DIR / "archive"
OUT_DIR = ROOT / "out"

ENV_FILES = [ROOT / ".env", Path(r"D:\VoxDesk\demo\.env")]


def ensure_dirs() -> None:
    for path in (DATA_DIR, CHATS_DIR, ARCHIVE_DIR, OUT_DIR):
        path.mkdir(parents=True, exist_ok=True)


def install_sys_path() -> None:
    """让 server 可以直接 import 本仓库内的 audio / tts 源码。"""
    import sys

    for path in (str(TTS_SRC), str(AUDIO_SRC), str(ROOT)):
        if path not in sys.path:
            sys.path.insert(0, path)
