"""降噪 A/B：同一段带噪语音，开/关降噪各跑一遍 VAD，比三个指标。

**为什么不能只看"切错条数"**：VAD 对稳态噪声很皮实，5 dB 白噪下照样 0 切错——
这个指标**没有分辨力**，看不出降噪好坏。所以补两个更敏感的：

| 指标 | 含义 | 好的方向 |
| --- | --- | --- |
| `切错` | 漏检 + 多检 | 越小越好 |
| `分离度` | 语音帧平均概率 − 静音帧平均概率 | 越大越好 |
| `Brier` | 概率与真值的均方误差 | 越小越好 |

    uv run python scripts/denoise_ab.py --corpus out/corpus
    uv run python scripts/denoise_ab.py --corpus out/corpus --snr inf,10,5,0
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from voxdesk_audio import DenoiseStage, Segmenter, SileroVAD, enable_utf8
from voxdesk_audio.capture import iter_frames
from voxdesk_audio.corpus import add_noise, build_composite

FRAME_MS = 32


def overlap(a: tuple[int, int], b: tuple[int, int]) -> int:
    return max(0, min(a[1], b[1]) - max(a[0], b[0]))


def wrong_count(found: list[tuple[int, int]], expected: list[tuple[int, int]]) -> int:
    used: set[int] = set()
    matched = 0
    for exp in expected:
        best, best_i = 0, -1
        for i, got in enumerate(found):
            if i in used:
                continue
            ov = overlap(exp, got)
            if ov > best:
                best, best_i = ov, i
        if best_i >= 0 and best >= (exp[1] - exp[0]) * 0.5:
            used.add(best_i)
            matched += 1
    return len(expected) - matched + max(0, len(found) - matched)


def frame_truth(expected: list[tuple[int, int]], n_frames: int) -> np.ndarray:
    centers = np.arange(n_frames) * FRAME_MS + FRAME_MS / 2
    mask = np.zeros(n_frames, dtype=bool)
    for start, end in expected:
        mask |= (centers >= start) & (centers < end)
    return mask


def run(vad: SileroVAD, audio, min_silence: int, denoise: DenoiseStage) -> tuple[list, list[float]]:
    vad.reset()
    denoise.reset()
    seg = Segmenter(min_silence_ms=min_silence)
    found: list[tuple[int, int]] = []
    probs: list[float] = []
    for frame in iter_frames(audio):
        p = vad.prob(denoise.process(frame))
        probs.append(p)
        for s in seg.push(p):
            found.append((s.start_ms, s.end_ms))
    tail = seg.flush()
    if tail:
        found.append((tail.start_ms, tail.end_ms))
    return found, probs


def main() -> int:
    enable_utf8()

    ap = argparse.ArgumentParser(description="降噪 A/B（端点 + 概率质量）")
    ap.add_argument("--corpus", default="out/corpus")
    ap.add_argument("--gap", type=int, default=700)
    ap.add_argument("--min-silence", type=int, default=600)
    ap.add_argument("--snr", default="inf,10,5,0")
    args = ap.parse_args()

    clean, expected = build_composite(Path(args.corpus), args.gap)
    vad = SileroVAD()
    truth = frame_truth(expected, len(clean) // 512 + 1)

    print(f"语料 {len(expected)} 句 · 干净流 {len(clean) / 16000:.1f}s · min_silence={args.min_silence}ms\n")
    print("| SNR | 降噪 | 切错 | 分离度 | Brier |")
    print("| --- | --- | --- | --- | --- |")

    rows = []
    for snr_text in args.snr.split(","):
        key = snr_text.strip().lower()
        snr = None if key in {"inf", "none", "clean"} else float(key)
        audio = clean if snr is None else add_noise(clean, snr, seed=42)
        for enabled in (False, True):
            found, probs = run(vad, audio, args.min_silence, DenoiseStage(enabled=enabled))
            p = np.array(probs[: len(truth)], dtype=float)
            t = truth[: len(p)]
            sep = float(p[t].mean() - p[~t].mean()) if t.any() and (~t).any() else float("nan")
            brier = float(np.mean((p - t.astype(float)) ** 2))
            wrong = wrong_count(found, expected)
            rows.append((snr, enabled, wrong, sep, brier))
            label = "干净" if snr is None else f"{snr:g} dB"
            print(f"| {label} | {'开' if enabled else 'off'} | {wrong} | {sep:+.3f} | {brier:.4f} |")

    print("\n结论（关 vs 开）：")
    for snr in sorted({r[0] for r in rows}, key=lambda v: 999 if v is None else v):
        off = next(r for r in rows if r[0] == snr and not r[1])
        on = next(r for r in rows if r[0] == snr and r[1])
        label = "干净" if snr is None else f"{snr:g} dB"
        verdict = []
        verdict.append("分离度↑" if on[3] > off[3] else "分离度↓")
        verdict.append("Brier↓" if on[4] < off[4] else "Brier↑")
        print(f"{label:<6} {verdict[0]} {verdict[1]}（{off[3]:+.3f}→{on[3]:+.3f}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
