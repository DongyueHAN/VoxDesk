"""TTS 引擎接口与 SAPI 实现。

`TTSEngine` 是 S2 换引擎的**唯一开关**：`service.py` 只认这个协议，
不认 SAPI。换 Piper 时新增一个 `PiperEngine`，`service.py` 一行不改。
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .sapi import Voice, list_voices, synth_to_wav


class TTSEngine(Protocol):
    """引擎要满足的两件事：报音色、把文本写成 WAV。"""

    signature: str
    """缓存键的一部分。换引擎 / 换音色 / 改语速必须变，否则会读到旧音频。"""

    def voices(self) -> list[Voice]: ...

    def synth(self, text: str, out_path: Path) -> None:
        """把 text 合成为 WAV；阻塞直到写完。"""


class SapiEngine:
    """Windows 自带 SAPI 5（零模型、零下载）。"""

    name = "sapi"

    def __init__(self, voice: str | None = None, rate: int = 0) -> None:
        self.voice = voice
        self.rate = rate

    @property
    def signature(self) -> str:
        return f"sapi|{self.voice or 'default'}|{self.rate}"

    def voices(self) -> list[Voice]:
        return list_voices()

    def synth(self, text: str, out_path: Path) -> None:
        synth_to_wav(text, out_path, voice=self.voice, rate=self.rate)

    def __repr__(self) -> str:
        return f"SapiEngine(voice={self.voice!r}, rate={self.rate})"
