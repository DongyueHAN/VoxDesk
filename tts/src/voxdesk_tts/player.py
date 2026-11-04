"""WAV 播放器：异步播放 + 可打断。

**为什么不用「同步播放 + 另线程 SND_PURGE」**（文档 `09` §7 的骨架写法）：
`winsound` 的 `SND_PURGE` 只停掉**调用线程自己**的发声；同步 `PlaySound` 会把
线程阻塞在播放里，别的线程调 `stop()` 停不掉它——实测会继续念完当前段。

所以这里改成：**异步播放 + 10ms 轮询取消标志**，在**同一个线程**里 purge。
代价是多一个循环，收益是打断延迟可控（实测见 `scripts/accept_s1.py`）。
"""

from __future__ import annotations

import time
import wave
from pathlib import Path
from typing import Callable

import winsound


def wav_seconds(wav_path: str | Path) -> float:
    """读 WAV 头算时长（不用解码，毫秒级）。"""
    with wave.open(str(wav_path), "rb") as w:
        rate = w.getframerate()
        return w.getnframes() / rate if rate else 0.0


class WavPlayer:
    """基于 `winsound` 的单轨播放器。所有 PlaySound 调用都在播放线程里发生。"""

    def __init__(self, poll_interval: float = 0.01) -> None:
        self.poll_interval = poll_interval
        self._stop_at: float | None = None
        self.last_stop_latency_ms: float | None = None

    def play(self, wav_path: str | Path, should_stop: Callable[[], bool] | None = None) -> bool:
        """播完返回 True；被打断返回 False。"""
        seconds = wav_seconds(wav_path)
        self._stop_at = None
        self.last_stop_latency_ms = None

        winsound.PlaySound(str(wav_path), winsound.SND_FILENAME | winsound.SND_ASYNC)

        deadline = time.perf_counter() + seconds
        while time.perf_counter() < deadline:
            if self._stop_at is not None or (should_stop is not None and should_stop()):
                winsound.PlaySound(None, winsound.SND_PURGE)
                if self._stop_at is not None:
                    self.last_stop_latency_ms = (time.perf_counter() - self._stop_at) * 1000
                self._stop_at = None
                return False
            time.sleep(self.poll_interval)
        return True

    def stop(self) -> None:
        """请求停止。真正静音发生在播放线程的下一次轮询（≤10ms）。"""
        self._stop_at = time.perf_counter()
        # 兜底：若当前线程正好持有播放，直接 purge
        winsound.PlaySound(None, winsound.SND_PURGE)
