"""音频输入：麦克风流与 WAV 文件，统一成 16k 单声道 float32 帧。

采集只在回调里做一件事：**拷贝入队**。绝不在回调里跑推理——
那是端侧音频最常见的卡顿来源（见 `docs/04-tech-stack.md` §3.1）。
"""

from __future__ import annotations

import queue
import wave
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import sounddevice as sd

from .vad import FRAME_SAMPLES


def _to_float(data: np.ndarray, width: int) -> np.ndarray:
    if width == 2:
        return data.astype(np.float32) / 32768.0
    if width == 4:
        return data.astype(np.float32) / 2147483648.0
    if width == 1:
        return (data.astype(np.float32) - 128.0) / 128.0
    raise ValueError(f"不支持的位深：{width * 8} bit")


def resample(x: np.ndarray, src: int, dst: int) -> np.ndarray:
    """线性插值重采样。对 VAD 足够——它只看能量包络，不听音色。"""
    if src == dst or len(x) == 0:
        return x.astype(np.float32, copy=False)
    n = int(round(len(x) * dst / src))
    idx = np.linspace(0, len(x) - 1, n, dtype=np.float64)
    i0 = np.floor(idx).astype(np.int64)
    i1 = np.minimum(i0 + 1, len(x) - 1)
    frac = (idx - i0).astype(np.float32)
    return (x[i0] * (1 - frac) + x[i1] * frac).astype(np.float32)


def read_wav(path: str | Path, sample_rate: int = 16000) -> np.ndarray:
    """读 WAV → 单声道 float32（-1..1）→ 重采样到 `sample_rate`。"""
    with wave.open(str(path), "rb") as w:
        channels, width, rate, frames = (
            w.getnchannels(),
            w.getsampwidth(),
            w.getframerate(),
            w.getnframes(),
        )
        raw = w.readframes(frames)

    data = np.frombuffer(raw, dtype=np.uint8)
    dtype = {1: np.uint8, 2: np.int16, 4: np.int32}[width]
    samples = data.view(dtype).astype(np.float32) if width == 1 else data.view(dtype)
    audio = _to_float(np.asarray(samples), width)

    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    return resample(audio.astype(np.float32), rate, sample_rate)


def iter_frames(audio: np.ndarray, frame: int = FRAME_SAMPLES) -> Iterator[np.ndarray]:
    """按 512 点切帧；末尾补零，保证不漏掉最后一小段。"""
    for start in range(0, len(audio), frame):
        chunk = audio[start : start + frame]
        if len(chunk) < frame:
            chunk = np.pad(chunk, (0, frame - len(chunk)))
        yield chunk


class MicStream:
    """麦克风 → 帧队列。用作上下文管理器。"""

    def __init__(
        self,
        device: int | str | None = None,
        sample_rate: int = 16000,
        block: int = FRAME_SAMPLES,
    ) -> None:
        self.device = device
        self.sample_rate = sample_rate
        self.block = block
        self._q: queue.Queue[np.ndarray] = queue.Queue()
        self._stream: sd.InputStream | None = None

    def _callback(self, indata, frames, time_info, status) -> None:  # noqa: ANN001
        if status:
            # 溢出/欠载：不致命，记一笔就行
            print(f"[audio] {status}", flush=True)
        self._q.put(indata[:, 0].copy())

    def __enter__(self) -> "MicStream":
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            blocksize=self.block,
            channels=1,
            dtype="float32",
            device=self.device,
            callback=self._callback,
        )
        self._stream.start()
        return self

    def frames(self, limit: int | None = None) -> Iterator[np.ndarray]:
        count = 0
        while limit is None or count < limit:
            yield self._q.get()
            count += 1

    def __exit__(self, *exc: object) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
