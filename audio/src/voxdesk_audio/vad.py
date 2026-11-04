"""Silero VAD v5 的 ONNX 封装。

模型只有 ~2MB，用 onnxruntime 直接跑，**不需要 torch**（`silero-vad` 的 PyPI 包会拖
2.5GB 的 torch，为了一个 2MB 的模型不值）。

**最大的坑（踩过一次）**：这个 ONNX 模型不是"喂 512 点就完事"。它内部维护一个
**64 点的上下文**（16k 下），调用时要先把上一帧的尾巴拼上去：

    input = concat(context[-64:], frame[512])   →  形状 (1, 576)
    context = input[-64:]

只喂 512 点也能跑通、不报错，但概率会全部塌到 0.00x（看起来像"永远没人说话"）。
对照实现见 `silero-vad/utils_vad.py` 的 `context_size = 64 if sr == 16000`。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import onnxruntime as ort

VAD_MODEL_NAME = "silero_vad.onnx"
DEFAULT_MODEL_PATH = Path("models") / VAD_MODEL_NAME

FRAME_SAMPLES = 512  # 16kHz 下 32ms
FRAME_MS = 32
CONTEXT_SAMPLES = 64  # 16k 下 4ms；8k 模型是 32
STATE_SHAPE = (2, 1, 128)


class SileroVAD:
    """逐帧输出"这 32ms 里有人在说话"的概率。有状态：换一句话前要 `reset()`。"""

    def __init__(
        self,
        model_path: str | Path = DEFAULT_MODEL_PATH,
        sample_rate: int = 16000,
        providers: list[str] | None = None,
    ) -> None:
        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(
                f"找不到 VAD 模型：{path}\n"
                "下载（~2.3MB）：https://cdn.jsdelivr.net/gh/snakers4/silero-vad@master/"
                f"src/silero_vad/data/{VAD_MODEL_NAME}"
            )
        self.model_path = path
        self.sample_rate = sample_rate
        self.session = ort.InferenceSession(
            str(path), providers=providers or ["CPUExecutionProvider"]
        )
        self._names = {i.name for i in self.session.get_inputs()}
        self._state = np.zeros(STATE_SHAPE, dtype=np.float32)
        self._context = np.zeros(CONTEXT_SAMPLES, dtype=np.float32)

    def reset(self) -> None:
        """清空帧间状态（RNN state + 上下文）。"""
        self._state = np.zeros(STATE_SHAPE, dtype=np.float32)
        self._context = np.zeros(CONTEXT_SAMPLES, dtype=np.float32)

    def prob(self, frame: np.ndarray) -> float:
        """输入 512 点 float32 帧（-1..1），返回语音概率。"""
        x = np.asarray(frame, dtype=np.float32).reshape(-1)
        if x.shape[0] != FRAME_SAMPLES:
            raise ValueError(f"帧长必须是 {FRAME_SAMPLES} 点，收到 {x.shape[0]}")

        # 关键：拼接 64 点上下文，得到 576 点输入
        inp = np.concatenate([self._context, x]).reshape(1, -1)

        feed: dict[str, np.ndarray] = {"input": inp, "state": self._state}
        if "sr" in self._names:
            feed["sr"] = np.array(self.sample_rate, dtype=np.int64)

        out, state = self.session.run(None, feed)
        self._state = state
        self._context = inp[0, -CONTEXT_SAMPLES:]
        return float(np.asarray(out).reshape(-1)[0])

    def __enter__(self) -> "SileroVAD":
        return self

    def __exit__(self, *exc: object) -> None:
        self.reset()
