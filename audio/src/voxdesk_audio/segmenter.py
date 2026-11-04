"""端点状态机：把逐帧概率变成 `Segment(start_ms, end_ms)`。

三个参数决定手感（与 `docs/04-tech-stack.md` §3.2 的 yaml 一致）：

| 参数 | 默认 | 作用 |
| --- | --- | --- |
| `threshold` | 0.5 | 语音概率阈值 |
| `min_speech_ms` | 250 | 短于此不算一句话（咳嗽、敲键盘） |
| `min_silence_ms` | 600 | 静音尾判定——**半双工下最主要的延迟来源** |
| `speech_pad_ms` | 100 | 前后各补一点，防止切掉字头字尾 |

这是**纯逻辑**：不碰音频、不碰模型，所以能用合成序列测死（`tests/test_segmenter.py`）。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Segment:
    """一段语音的起止（毫秒，相对流开始）。"""

    start_ms: int
    end_ms: int

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms

    def __str__(self) -> str:
        return f"[{self.start_ms:>6} → {self.end_ms:>6}] {self.duration_ms:>5}ms"


class Segmenter:
    def __init__(
        self,
        threshold: float = 0.5,
        min_speech_ms: int = 250,
        min_silence_ms: int = 600,
        speech_pad_ms: int = 100,
        frame_ms: int = 32,
    ) -> None:
        self.threshold = threshold
        self.min_speech_ms = min_speech_ms
        self.min_silence_ms = min_silence_ms
        self.speech_pad_ms = speech_pad_ms
        self.frame_ms = frame_ms

        self._now = 0
        self._in_speech = False
        self._start = 0
        self._last_voice = 0
        self._silence_since: int | None = None

    # ---- 只读状态 ----

    @property
    def in_speech(self) -> bool:
        return self._in_speech

    @property
    def now_ms(self) -> int:
        return self._now

    # ---- 主逻辑 ----

    def push(self, prob: float, now_ms: int | None = None) -> list[Segment]:
        """喂一帧概率；返回这一帧**闭合**的段落（可能 0 个或 1 个）。"""
        self._now = now_ms if now_ms is not None else self._now + self.frame_ms
        voice = prob >= self.threshold

        if not self._in_speech:
            if voice:
                self._in_speech = True
                self._start = max(0, self._now - self.frame_ms - self.speech_pad_ms)
                self._last_voice = self._now
                self._silence_since = None
            return []

        if voice:
            self._last_voice = self._now
            self._silence_since = None
            return []

        if self._silence_since is None:
            self._silence_since = self._now

        if self._now - self._silence_since < self.min_silence_ms:
            return []

        return self._close(self._silence_since + self.speech_pad_ms)

    def flush(self) -> Segment | None:
        """流结束时把未闭合的段落吐出来。"""
        if not self._in_speech:
            return None
        segment = self._close(self._last_voice + self.speech_pad_ms)
        return segment[0] if segment else None

    # ---- 内部 ----

    def _close(self, end_ms: int) -> list[Segment]:
        start, in_speech = self._start, self._in_speech
        self._in_speech = False
        self._silence_since = None
        if end_ms - start < self.min_speech_ms:
            return []
        del in_speech
        return [Segment(start_ms=start, end_ms=end_ms)]
