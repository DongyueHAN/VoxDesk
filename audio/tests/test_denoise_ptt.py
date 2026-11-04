"""降噪与 PTT 的单元测试：都不需要麦克风与真人按键。"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from voxdesk_audio.denoise import DenoiseStage, SpectralGate  # noqa: E402
from voxdesk_audio.ptt import PushToTalk  # noqa: E402

FRAME = 512


def rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(x**2)) + 1e-12)


def noise_frames(n: int = 80, seed: int = 0) -> list[np.ndarray]:
    rng = np.random.default_rng(seed)
    return [rng.normal(0, 0.05, FRAME).astype(np.float32) for _ in range(n)]


class FakeKeyboard:
    """只记录回调，不装全局钩子。"""

    def __init__(self) -> None:
        self.callbacks: dict[str, list] = {"press": [], "release": []}
        self.unhooked: list = []

    def on_press_key(self, key, callback, suppress=False):  # noqa: ANN001
        self.callbacks["press"].append(callback)
        return ("press", callback)

    def on_release_key(self, key, callback, suppress=False):  # noqa: ANN001
        self.callbacks["release"].append(callback)
        return ("release", callback)

    def unhook(self, hook):  # noqa: ANN001
        self.unhooked.append(hook)

    def press(self) -> None:
        for cb in self.callbacks["press"]:
            cb(None)

    def release(self) -> None:
        for cb in self.callbacks["release"]:
            cb(None)


# ---------------- 降噪 ----------------


def test_bypass_returns_input_unchanged():
    stage = DenoiseStage(enabled=False)
    frame = np.random.default_rng(1).normal(0, 0.1, FRAME).astype(np.float32)
    out = stage.process(frame)
    assert np.array_equal(out, frame)
    assert stage.bypass is True


def test_bypass_can_be_toggled():
    stage = DenoiseStage(enabled=False)
    stage.set_bypass(False)
    assert stage.enabled and not stage.bypass


def test_denoise_preserves_length():
    stage = DenoiseStage(enabled=True)
    for frame in noise_frames(10):
        assert stage.process(frame).shape == (FRAME,)


def test_denoise_reduces_stationary_noise():
    stage = DenoiseStage(enabled=True)
    frames = noise_frames(120)
    tail = [rms(stage.process(f)) for f in frames[-40:]]
    quiet = float(np.mean(tail))
    raw = float(np.mean([rms(f) for f in frames[-40:]]))
    assert quiet < raw * 0.7, f"降噪后 {quiet:.4f} 应明显小于原始 {raw:.4f}"


def test_reset_clears_noise_estimate():
    gate = SpectralGate()
    for frame in noise_frames(5):
        gate.process(frame)
    assert gate._noise is not None
    gate.reset()
    assert gate._noise is None


# ---------------- PTT ----------------


def test_ptt_tracks_press_and_release():
    kb = FakeKeyboard()
    ptt = PushToTalk("f2", backend=kb)
    with ptt:
        assert not ptt.pressed
        kb.press()
        assert ptt.pressed
        kb.release()
        assert not ptt.pressed


def test_ptt_counts_presses():
    kb = FakeKeyboard()
    ptt = PushToTalk("f2", backend=kb)
    with ptt:
        for _ in range(3):
            kb.press()
            kb.release()
    assert ptt.press_count == 3


def test_ptt_unhooks_on_exit():
    kb = FakeKeyboard()
    with PushToTalk("f2", backend=kb):
        pass
    assert len(kb.unhooked) == 2
