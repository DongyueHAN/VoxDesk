"""VoxDesk TTS 切片。

S0：SAPI 出声 + 合成落盘。
S1：分句 + 缓存 + 队列 + 打断（`TTSService`）。
S2：加入 `PiperEngine`，验证"换引擎不改调用方"。
"""

from .console import enable_utf8
from .engine import DEFAULT_PIPER_MODEL, EngineVoice, PiperEngine, SapiEngine, TTSEngine
from .player import WavPlayer, wav_seconds
from .sapi import Voice, list_voices, speak, synth_to_wav
from .service import TTSService
from .splitter import split

__all__ = [
    "DEFAULT_PIPER_MODEL",
    "EngineVoice",
    "PiperEngine",
    "SapiEngine",
    "TTSEngine",
    "TTSService",
    "Voice",
    "WavPlayer",
    "enable_utf8",
    "list_voices",
    "make_engine",
    "speak",
    "split",
    "synth_to_wav",
    "wav_seconds",
]
__version__ = "0.3.0"


def make_engine(
    name: str = "sapi",
    *,
    voice: str | None = None,
    rate: int = 0,
    model: str | None = None,
    use_cuda: bool = False,
    warmup: bool = True,
) -> TTSEngine:
    """按名字造引擎。脚本层只认这个函数，不直接 import 具体类。

    `warmup=True`（默认）会在构造时加载 Piper 模型（约 2s），
    避免第一句话把加载时间算进首音——真实服务本来就在启动时加载。
    """
    if name == "piper":
        return PiperEngine(model or DEFAULT_PIPER_MODEL, rate=rate, use_cuda=use_cuda, warmup=warmup)
    if name == "sapi":
        return SapiEngine(voice=voice, rate=rate)
    raise ValueError(f"未知引擎 {name!r}，可选：sapi / piper")
