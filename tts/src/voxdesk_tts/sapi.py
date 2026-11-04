"""SAPI 最小封装：枚举音色 / 朗读 / 合成到 WAV。

S0 只需要这三件事，所以刻意不做接口抽象——抽象留给 S2（换引擎时再抽 `TTSEngine`，
见文档 `09-tts-module.md` §4）。现在多写一层，等于在还没有第二个引擎时就猜接口。

**一个踩过的坑**：SAPI 是 COM 组件，`SpVoice` 等对象必须在 `CoUninitialize()` 之前释放。
如果让它们活到进程退出，解释器会打印 `Win32 exception occurred releasing IUnknown`。
所以下面所有 COM 引用都关在 `_collect` / `_speak` / `_synth` 的栈帧里——函数返回时
引用随帧销毁，此时 COM 还开着。
"""

from __future__ import annotations

import time
import wave
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import pythoncom
import win32com.client

# SAPI 常量（MSDN: SpeechStreamFileMode / SpeechVoiceSpeakFlags）
SSFM_CREATE_FOR_WRITE = 3  # 覆盖写入
SVSF_DEFAULT = 0  # 同步朗读：Speak() 返回时已播完
SVSF_ASYNC = 1  # 异步朗读

# SAPI 用十六进制 LCID 表示语言
_LCID = {
    "804": "zh-CN",
    "404": "zh-TW",
    "C04": "zh-HK",
    "409": "en-US",
    "809": "en-GB",
    "411": "ja-JP",
    "412": "ko-KR",
}


@dataclass(frozen=True)
class Voice:
    """一个已安装的 SAPI 音色。"""

    name: str
    lcid: str
    gender: str
    age: str

    @property
    def lang(self) -> str:
        return _LCID.get(self.lcid.upper(), f"LCID-{self.lcid}")

    def __str__(self) -> str:
        return f"{self.name}  [{self.lang} · {self.gender} · {self.age}]"


@contextmanager
def _com() -> Iterator[None]:
    """成对初始化 / 释放 COM。"""
    pythoncom.CoInitialize()
    try:
        yield
    finally:
        pythoncom.CoUninitialize()


# --------------------------------------------------------------------------
# 内部实现：所有 COM 引用都活在这些函数的栈帧里（见模块开头的坑）
# --------------------------------------------------------------------------


def _attr(token: Any, name: str) -> str:
    try:
        return str(token.GetAttribute(name)).strip()
    except Exception:  # 某些音色没有该属性
        return "?"


def _collect(zh_only: bool) -> list[Voice]:
    sapi = win32com.client.Dispatch("SAPI.SpVoice")
    tokens = sapi.GetVoices()

    voices: list[Voice] = []
    for i in range(tokens.Count):
        token = tokens.Item(i)
        v = Voice(
            name=str(token.GetDescription()).strip(),
            lcid=_attr(token, "Language").upper(),
            gender=_attr(token, "Gender"),
            age=_attr(token, "Age"),
        )
        if not zh_only or v.lang.startswith("zh"):
            voices.append(v)
    return voices


def _build(voice: str | None) -> Any:
    """新建 SpVoice，并按名字选中音色（先精确、后模糊）。"""
    sapi = win32com.client.Dispatch("SAPI.SpVoice")
    if not voice:
        return sapi

    tokens = sapi.GetVoices()
    names = [str(tokens.Item(i).GetDescription()).strip() for i in range(tokens.Count)]
    exact = [i for i, n in enumerate(names) if n == voice]
    fuzzy = [i for i, n in enumerate(names) if voice.lower() in n.lower()]
    hit = exact or fuzzy
    if not hit:
        raise ValueError(f"找不到音色 {voice!r}，可用：{names}")
    sapi.Voice = tokens.Item(hit[0])
    return sapi


def _clamp(rate: int) -> int:
    return max(-10, min(10, rate))


def _speak(text: str, voice: str | None, rate: int) -> float:
    sapi = _build(voice)
    sapi.Rate = _clamp(rate)
    start = time.perf_counter()
    sapi.Speak(text, SVSF_DEFAULT)
    return time.perf_counter() - start


def _synth(text: str, out: Path, voice: str | None, rate: int) -> dict[str, object]:
    out.parent.mkdir(parents=True, exist_ok=True)

    sapi = _build(voice)
    sapi.Rate = _clamp(rate)

    stream = win32com.client.Dispatch("SAPI.SpFileStream")
    stream.Open(str(out.resolve()), SSFM_CREATE_FOR_WRITE, True)
    default_out = sapi.AudioOutputStream
    sapi.AudioOutputStream = stream
    try:
        start = time.perf_counter()
        sapi.Speak(text, SVSF_DEFAULT)
        elapsed = time.perf_counter() - start
    finally:
        sapi.AudioOutputStream = default_out
        stream.Close()

    with wave.open(str(out), "rb") as w:
        frames = w.getnframes()
        rate_hz = w.getframerate()
        channels = w.getnchannels()
        width = w.getsampwidth()

    seconds = frames / rate_hz if rate_hz else 0.0
    return {
        "path": str(out),
        "seconds": round(seconds, 3),
        "sample_rate": rate_hz,
        "channels": channels,
        "bits": width * 8,
        "bytes": out.stat().st_size,
        "synth_seconds": round(elapsed, 3),
        "realtime_factor": round(elapsed / seconds, 3) if seconds else None,
    }


# --------------------------------------------------------------------------
# 公开 API
# --------------------------------------------------------------------------


def list_voices(zh_only: bool = False) -> list[Voice]:
    """列出本机 SAPI 5 已安装的音色。"""
    with _com():
        return _collect(zh_only)


def speak(text: str, voice: str | None = None, rate: int = 0) -> float:
    """同步朗读，返回实际耗时（秒）。`rate` ∈ [-10, 10]，0 为正常语速。"""
    with _com():
        return _speak(text, voice, rate)


def synth_to_wav(
    text: str,
    out_path: str | Path,
    voice: str | None = None,
    rate: int = 0,
) -> dict[str, object]:
    """把文本合成成 WAV 文件（不出声），返回时长 / 采样率 / 体积 / 实时因子。"""
    with _com():
        return _synth(text, Path(out_path), voice, rate)
