"""VoxDesk TTS 切片。

S0：SAPI 出声 + 合成落盘。
S1：分句 + 缓存 + 队列 + 打断（`TTSService`）。
"""

from .console import enable_utf8
from .engine import SapiEngine, TTSEngine
from .player import WavPlayer, wav_seconds
from .sapi import Voice, list_voices, speak, synth_to_wav
from .service import TTSService
from .splitter import split

__all__ = [
    "SapiEngine",
    "TTSEngine",
    "TTSService",
    "Voice",
    "WavPlayer",
    "enable_utf8",
    "list_voices",
    "speak",
    "split",
    "synth_to_wav",
    "wav_seconds",
]
__version__ = "0.2.0"
