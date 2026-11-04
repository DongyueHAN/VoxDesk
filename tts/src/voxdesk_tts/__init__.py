"""VoxDesk TTS 切片。

S0 只暴露 SAPI 的三件事：枚举音色、朗读、合成到 WAV。
"""

from .console import enable_utf8
from .sapi import Voice, list_voices, speak, synth_to_wav

__all__ = ["Voice", "enable_utf8", "list_voices", "speak", "synth_to_wav"]
__version__ = "0.1.0"
