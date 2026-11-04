"""降噪 Stage：谱减（spectral gate）+ bypass 开关。

**为什么不是 RNNoise**：PyPI 上没有可用的 RNNoise 轮子（`rnnoise` / `pyrnnoise` 都不存在），
Windows 上要自己编 C 库。所以这里先上**自研谱减**——纯 numpy、实时、无编译依赖，
目标正是"风扇/空调"这类稳态噪声（`docs/04-tech-stack.md` §3.3 里 RNNoise 的定位）。

接口留成了 `DenoiseStage` + `backend`，将来拿到 RNNoise / DeepFilterNet 的库，
换一个 backend 即可，`vad` 与 `capture` 一行不动。

**bypass 是硬要求**（`04` §3.3）：降噪对近场麦克风收益有限，过度处理会伤辅音。
所以默认 `enabled=False`，由调用方显式开启，且随时可 `set_bypass(True)`。
"""

from __future__ import annotations

import numpy as np


class SpectralGate:
    """50% 重叠的 STFT 谱减。输入 512 点，输出 512 点（内部有 1 帧延迟）。"""

    def __init__(
        self,
        frame: int = 512,
        hop: int = 256,
        over_subtraction: float = 2.0,
        floor_gain: float = 0.08,
        noise_alpha: float = 0.02,
    ) -> None:
        self.frame = frame
        self.hop = hop
        self.over_subtraction = over_subtraction
        self.floor_gain = floor_gain
        self.noise_alpha = noise_alpha

        self.window = np.hanning(frame).astype(np.float32)
        # 分析与合成都用 hann，重叠 50%：sum(w^2)/hop 是重建增益
        self._gain_norm = float(np.sum(self.window**2) / hop)

        self._in = np.zeros(0, np.float32)
        self._out = np.zeros(frame, np.float32)
        self._produced = np.zeros(0, np.float32)
        self._noise: np.ndarray | None = None

    def reset(self) -> None:
        self._in = np.zeros(0, np.float32)
        self._out = np.zeros(self.frame, np.float32)
        self._produced = np.zeros(0, np.float32)
        self._noise = None

    def process(self, block: np.ndarray) -> np.ndarray:
        x = np.asarray(block, dtype=np.float32).reshape(-1)
        self._in = np.concatenate([self._in, x])

        while len(self._in) >= self.frame:
            window = self._in[: self.frame]
            self._in = self._in[self.hop :]
            self._out += self._step(window)
            self._produced = np.concatenate([self._produced, self._out[: self.hop]])
            self._out = np.concatenate([self._out[self.hop :], np.zeros(self.hop, np.float32)])

        if len(self._produced) < len(x):
            # 起步阶段产出不足：用已有样本 + 零补齐，保证长度一致
            pad = np.zeros(len(x) - len(self._produced), np.float32)
            out = np.concatenate([self._produced, pad])[: len(x)]
            self._produced = np.zeros(0, np.float32)
            return out.astype(np.float32)

        out = self._produced[: len(x)]
        self._produced = self._produced[len(x) :]
        return out.astype(np.float32)

    def _step(self, window: np.ndarray) -> np.ndarray:
        spec = np.fft.rfft(window * self.window)
        mag = np.abs(spec)

        if self._noise is None:
            self._noise = mag.copy()
        else:
            # 慢跟踪噪声底：语音起时不要立刻把语音当噪声
            self._noise = (1 - self.noise_alpha) * self._noise + self.noise_alpha * mag

        gain = 1.0 - self.over_subtraction * self._noise / (mag + 1e-9)
        np.clip(gain, self.floor_gain, 1.0, out=gain)

        y = np.fft.irfft(spec * gain, n=self.frame) * self.window
        return (y / self._gain_norm).astype(np.float32)


class DenoiseStage:
    """降噪的对外接口：`process(frame) -> frame`，带 bypass。"""

    def __init__(self, enabled: bool = False, backend: SpectralGate | None = None) -> None:
        self.enabled = enabled
        self.backend = backend or SpectralGate()

    @property
    def bypass(self) -> bool:
        return not self.enabled

    def set_bypass(self, on: bool) -> None:
        self.enabled = not on

    def reset(self) -> None:
        self.backend.reset()

    def process(self, frame: np.ndarray) -> np.ndarray:
        x = np.asarray(frame, dtype=np.float32)
        if not self.enabled:
            return x.copy()
        return self.backend.process(x)
