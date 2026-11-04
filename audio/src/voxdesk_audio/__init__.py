"""VoxDesk 端侧音频前端（M1 音频 + M2 的 ASR 单点）。

M1 的出口：**知道一句话什么时候开始、什么时候结束**
    sounddevice 采集 → 帧 → [降噪] → Silero VAD 概率 → 端点状态机 → Segment

M2/S4 的出口：**把一段音频变成文本**
    Segment 音频 → StreamingASR（sherpa-onnx zipformer）→ text

不做唤醒（M2/S6 的 openWakeWord），不做串联（M2/S7 的 pipeline）。
"""

from .asr import ASRResult, StreamingASR
from .capture import MicStream, read_wav
from .console import enable_utf8
from .denoise import DenoiseStage, SpectralGate
from .ptt import PushToTalk
from .segmenter import Segment, Segmenter
from .vad import VAD_MODEL_NAME, SileroVAD

__all__ = [
    "ASRResult",
    "DenoiseStage",
    "MicStream",
    "PushToTalk",
    "Segment",
    "Segmenter",
    "SileroVAD",
    "SpectralGate",
    "StreamingASR",
    "VAD_MODEL_NAME",
    "enable_utf8",
    "read_wav",
]
__version__ = "0.3.0"
