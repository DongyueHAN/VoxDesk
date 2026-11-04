"""TTSService 的行为测试：用假引擎 + 假播放器，不碰声卡。

真引擎留给 `scripts/accept_s1.py`；这里只验"队列、缓存、换代"三件事。
`max_len=8` 是为了让每句都超过上限、从而切成多段（真实场景是 50）。
"""

from __future__ import annotations

import sys
import time
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from voxdesk_tts.service import TTSService  # noqa: E402


class FakeEngine:
    signature = "fake|default|0"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def voices(self) -> list[str]:
        return []

    def synth(self, text: str, out_path: Path) -> None:
        self.calls.append(text)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(out_path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(22050)
            w.writeframes(b"\x00\x00" * 441)  # 0.02s 静音


class FakePlayer:
    def __init__(self) -> None:
        self.played: list[Path] = []
        self.stopped = False

    def play(self, wav_path: Path, should_stop: object = None) -> bool:
        self.played.append(Path(wav_path))
        return True

    def stop(self) -> None:
        self.stopped = True


class SlowPlayer(FakePlayer):
    def __init__(self, duration: float = 0.2) -> None:
        super().__init__()
        self.duration = duration
        self.started: list[Path] = []

    def play(self, wav_path: Path, should_stop: object = None) -> bool:
        self.started.append(Path(wav_path))
        deadline = time.perf_counter() + self.duration
        while time.perf_counter() < deadline:
            if callable(should_stop) and should_stop():
                return False
            time.sleep(0.005)
        self.played.append(Path(wav_path))
        return True


def build(
    tmp_path: Path,
    player: FakePlayer | None = None,
    max_len: int = 8,
) -> tuple[TTSService, FakeEngine]:
    engine = FakeEngine()
    service = TTSService(
        engine, cache_dir=tmp_path / "cache", player=player or FakePlayer(), max_len=max_len
    )
    return service, engine


def test_speaks_every_segment_in_order(tmp_path: Path) -> None:
    service, engine = build(tmp_path)
    try:
        assert service.speak("第一句话。第二句话。第三句话。") == 3
        assert service.wait(5)
        assert engine.calls == ["第一句话。", "第二句话。", "第三句话。"]
        assert service.stats["played"] == 3
        assert service.stats["synthesized"] == 3
    finally:
        service.close()


def test_second_play_hits_cache(tmp_path: Path) -> None:
    service, engine = build(tmp_path)
    try:
        service.speak("同一句话。再来一句。")
        assert service.wait(5)
        assert len(engine.calls) == 2

        service.speak("同一句话。再来一句。")
        assert service.wait(5)
        assert len(engine.calls) == 2, "第二次不应再合成"
        assert service.stats["cache_hits"] == 2
        assert service.stats["synthesized"] == 0
    finally:
        service.close()


def test_stop_discards_pending_segments(tmp_path: Path) -> None:
    player = SlowPlayer(duration=0.2)
    service, _ = build(tmp_path, player)
    try:
        assert service.speak("第一句话。第二句话。第三句话。第四句话。第五句话。") == 5
        time.sleep(0.1)
        service.stop()
        assert player.stopped
        time.sleep(0.5)
        assert len(player.started) < 5, "stop() 之后不应继续往下播"
        assert service.stats["stop_ms"] is not None
    finally:
        service.close()


def test_stats_reset_per_utterance(tmp_path: Path) -> None:
    service, _ = build(tmp_path)
    try:
        service.speak("一句话。")
        assert service.wait(5)
        assert service.stats["segments"] == 1

        service.speak("第二句话。第三句话。")
        assert service.wait(5)
        assert service.stats["segments"] == 2
        assert service.stats["played"] == 2
    finally:
        service.close()
