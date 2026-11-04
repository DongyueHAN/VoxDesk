"""合成语料工具：把「一句一个 wav」拼成一条已知起止的长流。

验收和 A/B 都要它——**期望值必须算得出来**，否则"切错几条"只能靠感觉。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .capture import read_wav

SR = 16000


def build_composite(
    corpus_dir: str | Path,
    gap_ms: int = 700,
    lead_ms: int = 1000,
    tail_ms: int = 500,
) -> tuple[np.ndarray, list[tuple[int, int]]]:
    """返回 (音频, 每句真实起止 ms)。句与句之间插入 `gap_ms` 静音。"""
    files = sorted(Path(corpus_dir).glob("*.wav"))
    if not files:
        raise SystemExit(f"{corpus_dir} 里没有 wav，先生成语料")

    lead = np.zeros(int(SR * lead_ms / 1000), dtype=np.float32)
    gap = np.zeros(int(SR * gap_ms / 1000), dtype=np.float32)
    tail = np.zeros(int(SR * tail_ms / 1000), dtype=np.float32)

    chunks: list[np.ndarray] = [lead]
    cursor = len(lead)
    spans: list[tuple[int, int]] = []
    for path in files:
        audio = read_wav(path, SR)
        spans.append((int(cursor * 1000 / SR), int((cursor + len(audio)) * 1000 / SR)))
        chunks.extend([audio, gap])
        cursor += len(audio) + len(gap)
    chunks.append(tail)
    return np.concatenate(chunks), spans


def add_noise(audio: np.ndarray, snr_db: float, seed: int = 0) -> np.ndarray:
    """按目标 SNR 叠高斯白噪声（稳态噪声的粗模型）。"""
    signal_power = float(np.mean(audio**2)) + 1e-12
    noise_power = signal_power / (10 ** (snr_db / 10))
    rng = np.random.default_rng(seed)
    noise = rng.normal(0, np.sqrt(noise_power), len(audio)).astype(np.float32)
    mixed = audio + noise
    peak = float(np.max(np.abs(mixed)))
    return (mixed / peak * 0.9).astype(np.float32) if peak > 0.99 else mixed
