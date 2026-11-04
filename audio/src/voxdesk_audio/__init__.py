"""VoxDesk 端侧音频前端（S3）。

S3 的出口不是"听懂"，是**知道一句话什么时候开始、什么时候结束**：
    sounddevice 采集 → 帧 → Silero VAD 概率 → 端点状态机 → Segment(start_ms, end_ms)

不做 ASR（M2 的 sherpa-onnx），不做唤醒（M2 的 openWakeWord）。
"""

from .capture import MicStream, read_wav
from .console import enable_utf8
from .segmenter import Segment, Segmenter
from .vad import VAD_MODEL_NAME, SileroVAD

__all__ = [
    "MicStream",
    "Segment",
    "Segmenter",
    "SileroVAD",
    "VAD_MODEL_NAME",
    "enable_utf8",
    "read_wav",
]
__version__ = "0.1.0"
