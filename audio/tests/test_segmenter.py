"""端点状态机是纯逻辑，用合成概率序列测死它——不需要麦克风。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from voxdesk_audio.segmenter import Segmenter  # noqa: E402

FRAME = 32


def feed(seg: Segmenter, probs: list[float]) -> list:
    out = []
    for p in probs:
        out.extend(seg.push(p))
    return out


def test_silence_only_emits_nothing():
    seg = Segmenter()
    assert feed(seg, [0.0] * 100) == []
    assert seg.flush() is None


def test_short_voice_is_rejected_by_min_speech():
    seg = Segmenter(min_speech_ms=250)
    # 3 帧语音 = 96ms，然后静音
    probs = [0.9] * 3 + [0.0] * 40
    assert feed(seg, probs) == []


def test_voice_then_long_silence_emits_one_segment():
    seg = Segmenter(min_speech_ms=250, min_silence_ms=600, speech_pad_ms=100)
    probs = [0.0] * 5 + [0.9] * 20 + [0.0] * 40
    segs = feed(seg, probs)
    assert len(segs) == 1
    assert segs[0].duration_ms >= 20 * FRAME


def test_short_pause_does_not_split():
    """静音 300ms < min_silence 600ms：不该断开。"""
    seg = Segmenter(min_silence_ms=600)
    probs = [0.0] * 3 + [0.9] * 10 + [0.0] * 9 + [0.9] * 10 + [0.0] * 40
    assert len(feed(seg, probs)) == 1


def test_long_pause_splits():
    """静音 800ms > min_silence 600ms：必须断成两段。"""
    seg = Segmenter(min_silence_ms=600)
    probs = [0.9] * 10 + [0.0] * 25 + [0.9] * 10 + [0.0] * 40
    assert len(feed(seg, probs)) == 2


def test_flush_closes_open_segment():
    seg = Segmenter(min_speech_ms=250)
    feed(seg, [0.9] * 20)
    assert seg.in_speech
    seg_end = seg.flush()
    assert seg_end is not None
    assert seg_end.duration_ms >= 250
    assert not seg.in_speech


def test_padding_does_not_go_negative():
    seg = Segmenter(speech_pad_ms=100)
    segs = feed(seg, [0.9] * 20 + [0.0] * 40)
    assert segs and segs[0].start_ms == 0
