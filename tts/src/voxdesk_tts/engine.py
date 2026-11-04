"""TTS 引擎接口与两个实现：SAPI（起步）与 Piper（上线）。

`TTSEngine` 是 S2 换引擎的**唯一开关**：`service.py` 只认这个协议，
不认具体引擎。S2 的验收正是这一点——加 `PiperEngine` 时 `service.py` 一行未改。
"""

from __future__ import annotations

import threading
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .sapi import Voice, list_voices, synth_to_wav

DEFAULT_PIPER_MODEL = Path("models") / "zh_CN-huayan-medium.onnx"


@dataclass(frozen=True)
class EngineVoice:
    """非 SAPI 引擎的音色描述（Piper 一个模型就是一个音色）。"""

    name: str
    lang: str
    detail: str = ""

    def __str__(self) -> str:
        return f"{self.name}  [{self.lang}{' · ' + self.detail if self.detail else ''}]"


class TTSEngine(Protocol):
    """引擎要满足的两件事：报音色、把文本写成 WAV。"""

    signature: str
    """缓存键的一部分。换引擎 / 换音色 / 改语速必须变，否则会读到旧音频。"""

    def voices(self) -> list[Any]: ...

    def synth(self, text: str, out_path: Path) -> None:
        """把 text 合成为 WAV；阻塞直到写完。"""


class SapiEngine:
    """Windows 自带 SAPI 5（零模型、零下载，音质是下限）。"""

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


class PiperEngine:
    """本地 ONNX 引擎（`piper1-gpl`，GPL-3.0）。

    - 模型：`zh_CN-huayan-medium.onnx`（60MB，22.05kHz）
    - 依赖：`piper-tts` + `onnxruntime`，**不需要 torch**
    - 首音：第一次 `synth` 会加载模型（约 0.3–1s），之后常驻内存
    """

    name = "piper"

    def __init__(
        self,
        model_path: str | Path = DEFAULT_PIPER_MODEL,
        rate: int = 0,
        use_cuda: bool = False,
        warmup: bool = False,
    ) -> None:
        self.model_path = Path(model_path)
        self.use_cuda = use_cuda
        self.rate = rate
        self.load_seconds: float | None = None
        self._voice: Any | None = None
        self._lock = threading.Lock()
        if warmup:
            self._load()

    # ---- 协议 ----

    @property
    def signature(self) -> str:
        return f"piper|{self.model_path.stem}|cuda={int(self.use_cuda)}|rate={self.rate}"

    def voices(self) -> list[EngineVoice]:
        return [
            EngineVoice(
                name=self.model_path.stem,
                lang="zh-CN",
                detail=f"ONNX · {'-' if not self.use_cuda else 'cuda'}",
            )
        ]

    def synth(self, text: str, out_path: Path) -> None:
        voice = self._load()
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(out_path), "wb") as wav_file:
            voice.synthesize_wav(text, wav_file, self._syn_config())

    # ---- 内部 ----

    def _load(self) -> Any:
        with self._lock:
            if self._voice is not None:
                return self._voice
            if not self.model_path.exists():
                raise FileNotFoundError(
                    f"找不到 Piper 模型：{self.model_path}\n"
                    "下载：https://huggingface.co/rhasspy/piper-voices/resolve/main/"
                    "zh/zh_CN/huayan/medium/zh_CN-huayan-medium.onnx（+ .onnx.json）"
                )
            from piper import PiperVoice  # 延迟导入：只用 SAPI 时不必装 piper

            start = time.perf_counter()
            self._voice = PiperVoice.load(self.model_path, use_cuda=self.use_cuda)
            self.load_seconds = time.perf_counter() - start
            return self._voice

    def warmup(self) -> None:
        """只加载模型（2s 左右），不合成。服务启动时调一次，避免第一句话慢。"""
        self._load()

    def _syn_config(self) -> Any:
        from piper.config import SynthesisConfig

        # rate ∈ [-10, 10] → length_scale ∈ [2.0, 0.5]（>1 更慢）
        return SynthesisConfig(length_scale=2.0 ** (-self.rate / 10.0))

    def __repr__(self) -> str:
        return f"PiperEngine(model={self.model_path.stem!r}, rate={self.rate})"
