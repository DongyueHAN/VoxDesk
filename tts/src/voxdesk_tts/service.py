"""TTSService：分句 → 合成（带缓存）→ 播放，可随时打断。

线程模型（对应文档 `09` §3 的图）：

    调用方 ──speak()──▶ 合成队列 ▶ 合成线程 ──▶ 播放队列 ▶ 播放线程 ▶ 声卡
                         ▲                                    │
                     stop() 换代 + 清空 ◀────────────────────┘

两个关键设计：

1. **换代（generation）**：每次 `speak()` 把 `_gen` 加一，队列里的任务带着旧代号。
   播放线程看到代号不匹配就丢弃——这样 `stop()` 不必真去"取消"已经在合成的任务，
   结果自然作废。比给 SAPI 装取消钩子简单得多。
2. **合成与播放分离**：第一段在播时，第二段已经在合成，句与句之间不留空档。
"""

from __future__ import annotations

import hashlib
import queue
import sys
import threading
import time
from pathlib import Path
from typing import Any

from .engine import TTSEngine
from .player import WavPlayer
from .splitter import split

SynthItem = tuple[int, str, Path]


class TTSService:
    """对外只有四个方法：`speak()` / `stop()` / `wait()` / `voices()`。"""

    def __init__(
        self,
        engine: TTSEngine,
        cache_dir: str | Path = "cache",
        player: Any | None = None,
        max_len: int = 50,
    ) -> None:
        self.engine = engine
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.player = player if player is not None else WavPlayer()
        self.max_len = max_len

        self._synth_q: queue.Queue[SynthItem | None] = queue.Queue()
        self._play_q: queue.Queue[tuple[int, Path] | None] = queue.Queue()
        self._lock = threading.Lock()
        self._gen = 0
        self._t0 = 0.0
        self._closed = False
        self._synth_busy = threading.Event()
        self._playing = threading.Event()
        self.stats: dict[str, Any] = {}
        self._reset_stats()

        self._synth_thread = threading.Thread(
            target=self._synth_loop, name="tts-synth", daemon=True
        )
        self._play_thread = threading.Thread(target=self._play_loop, name="tts-play", daemon=True)
        self._synth_thread.start()
        self._play_thread.start()

    # ------------------------------------------------------------------ 公开 API

    def speak(self, text: str) -> int:
        """把 text 切句后排队，**立刻返回**；返回段数。"""
        segments = split(text, self.max_len)
        with self._lock:
            if self._closed:
                raise RuntimeError("service 已关闭")
            self._gen += 1
            gen = self._gen
            self._reset_stats()
            self.stats["segments"] = len(segments)
            self._t0 = time.perf_counter()
            _drain(self._synth_q)
            _drain(self._play_q)
            for segment in segments:
                self._synth_q.put((gen, segment, self._cache_path(segment)))
        return len(segments)

    def stop(self) -> None:
        """停止播报并丢弃未播内容；返回时已静音（实测见 `scripts/accept_s1.py`）。"""
        start = time.perf_counter()
        with self._lock:
            self._gen += 1
            _drain(self._synth_q)
            _drain(self._play_q)
        self.player.stop()

        # 等播放线程确认（轮询间隔 10ms，给 0.5s 余量）
        while time.perf_counter() - start < 0.5:
            if not self._playing.is_set():
                break
            time.sleep(0.005)
        self.stats["stop_ms"] = round((time.perf_counter() - start) * 1000, 1)

    def wait(self, timeout: float = 30.0) -> bool:
        """等本轮到播完。超时返回 False。"""
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            if not self._playing.is_set() and not self._synth_busy.is_set():
                if self._synth_q.empty() and self._play_q.empty():
                    return True
            time.sleep(0.01)
        return False

    def voices(self) -> list[Any]:
        return self.engine.voices()

    def close(self) -> None:
        with self._lock:
            self._closed = True
        self.player.stop()
        self._synth_q.put(None)
        self._play_q.put(None)
        for thread in (self._synth_thread, self._play_thread):
            thread.join(timeout=2.0)

    # ------------------------------------------------------------------ 内部

    def _reset_stats(self) -> None:
        self.stats = {
            "segments": 0,
            "synthesized": 0,
            "cache_hits": 0,
            "played": 0,
            "first_audio_ms": None,
            "total_ms": None,
            "stop_ms": None,
        }

    def _cache_path(self, segment: str) -> Path:
        raw = f"{self.engine.signature}|{segment}".encode("utf-8")
        return self.cache_dir / f"{hashlib.sha1(raw).hexdigest()[:16]}.wav"

    def _synth_loop(self) -> None:
        while True:
            item = self._synth_q.get()
            if item is None:
                return
            gen, segment, wav = item
            if gen != self._gen:
                continue

            self._synth_busy.set()
            try:
                if wav.exists():
                    self.stats["cache_hits"] += 1
                else:
                    try:
                        self.engine.synth(segment, wav)
                    except Exception as exc:  # noqa: BLE001 - 单段失败不该拖垮整轮
                        print(f"[tts] 合成失败：{segment!r} -> {exc}", file=sys.stderr)
                        continue
                    self.stats["synthesized"] += 1
            finally:
                self._synth_busy.clear()

            if gen != self._gen or self._closed:
                continue
            self._play_q.put((gen, wav))

    def _play_loop(self) -> None:
        while True:
            item = self._play_q.get()
            if item is None:
                return
            gen, wav = item
            if gen != self._gen or self._closed:
                continue

            if self.stats["first_audio_ms"] is None:
                self.stats["first_audio_ms"] = round((time.perf_counter() - self._t0) * 1000, 1)

            self._playing.set()
            try:
                finished = bool(self.player.play(wav, should_stop=lambda: gen != self._gen))
            finally:
                self._playing.clear()

            if gen != self._gen:
                continue
            if finished:
                self.stats["played"] += 1
                if self.stats["played"] == self.stats["segments"]:
                    self.stats["total_ms"] = round((time.perf_counter() - self._t0) * 1000, 1)

    def __enter__(self) -> TTSService:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def _drain(q: queue.Queue[Any]) -> None:
    while True:
        try:
            q.get_nowait()
        except queue.Empty:
            return
