"""流式 ASR：sherpa-onnx（zipformer 或 paraformer，自动识别目录里是哪一种）。

S4 只做**单点**：一段 16k 单声道音频 → 文本 + 首字延迟。不接 VAD、不接 LLM（S7 才串联）。

模型选择（`13-M2process.md` §1）：
- 先试 `zipformer-zh-14M`（70MB）：能跑通，但中文 **CER 34.3%**，不可用；
- 换 `streaming-paraformer-bilingual-zh-en`（1GB 包，int8 子集实际 ~230MB）：文档 `04` 选的就是 Paraformer。

两种模型的构造器不同（`from_transducer` 要 joiner，`from_paraformer` 不要），
所以这里按目录内容自动选，调用方只看 `transcribe()`。

**首字**的口径：喂 100ms 一块，第一次 `get_result()` 非空时的墙钟时间。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import sherpa_onnx

DEFAULT_MODEL_DIR = Path("models") / "sherpa-onnx-streaming-paraformer-bilingual-zh-en"
SAMPLE_RATE = 16000
CHUNK_MS = 100


@dataclass(frozen=True)
class ASRResult:
    text: str
    audio_s: float
    first_char_ms: float | None
    total_ms: float
    chunks: int

    @property
    def rtf(self) -> float:
        return self.total_ms / (self.audio_s * 1000) if self.audio_s else float("nan")


def _find(model_dir: Path, prefix: str, use_int8: bool) -> Path:
    patterns = [f"{prefix}*int8*.onnx", f"{prefix}*.onnx"] if use_int8 else [f"{prefix}*.onnx"]
    for pattern in patterns:
        matches = sorted(model_dir.glob(pattern))
        if matches:
            return matches[0]
    raise FileNotFoundError(f"{model_dir} 里找不到 {prefix}*.onnx")


class StreamingASR:
    def __init__(
        self,
        model_dir: str | Path = DEFAULT_MODEL_DIR,
        num_threads: int = 2,
        use_int8: bool = True,
    ) -> None:
        d = Path(model_dir)
        if not d.exists():
            raise FileNotFoundError(
                f"找不到 ASR 模型目录：{d}\n"
                "推荐（中文流式 Paraformer）：https://github.com/k2-fsa/sherpa-onnx/releases/"
                "download/asr-models/sherpa-onnx-streaming-paraformer-bilingual-zh-en.tar.bz2"
            )

        tokens = d / "tokens.txt"
        encoder = _find(d, "encoder", use_int8)
        decoder = _find(d, "decoder", use_int8)
        joiner = next(iter(sorted(d.glob("joiner*int8*.onnx"))), None) or next(
            iter(sorted(d.glob("joiner*.onnx"))), None
        )

        self.model_dir = d
        self.kind = "transducer" if joiner else "paraformer"
        common = dict(
            tokens=str(tokens),
            encoder=str(encoder),
            decoder=str(decoder),
            num_threads=num_threads,
            sample_rate=SAMPLE_RATE,
            feature_dim=80,
            decoding_method="greedy_search",
            enable_endpoint_detection=False,  # 端点交给 audio 的 Segmenter，别两套打架
        )
        if joiner:
            self.recognizer = sherpa_onnx.OnlineRecognizer.from_transducer(joiner=str(joiner), **common)
        else:
            self.recognizer = sherpa_onnx.OnlineRecognizer.from_paraformer(**common)

    def transcribe(self, audio: np.ndarray, chunk_ms: int = CHUNK_MS, tail_pad_ms: int = 500) -> ASRResult:
        """喂完整段音频（float32，16k），返回文本与耗时。"""
        samples = np.asarray(audio, dtype=np.float32).reshape(-1)
        # 流式模型需要一点尾巴静音才会吐出最后几个字（实测：不加会截断）
        if tail_pad_ms > 0:
            samples = np.concatenate([samples, np.zeros(int(SAMPLE_RATE * tail_pad_ms / 1000), np.float32)])
        chunk = max(160, int(SAMPLE_RATE * chunk_ms / 1000))

        stream = self.recognizer.create_stream()
        start = time.perf_counter()
        first_char_ms: float | None = None
        text = ""

        for i in range(0, len(samples), chunk):
            stream.accept_waveform(SAMPLE_RATE, samples[i : i + chunk])
            while self.recognizer.is_ready(stream):
                self.recognizer.decode_stream(stream)

            partial = self.recognizer.get_result(stream).strip()
            if first_char_ms is None and partial:
                first_char_ms = (time.perf_counter() - start) * 1000
            text = partial

        stream.input_finished()
        while self.recognizer.is_ready(stream):
            self.recognizer.decode_stream(stream)
        text = self.recognizer.get_result(stream).strip()

        total_ms = (time.perf_counter() - start) * 1000
        return ASRResult(
            text=text,
            audio_s=len(samples) / SAMPLE_RATE,
            first_char_ms=first_char_ms,
            total_ms=total_ms,
            chunks=(len(samples) + chunk - 1) // chunk,
        )
