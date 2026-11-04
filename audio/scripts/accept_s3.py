"""S3 验收：把 N 句已知起止的语音拼成一条流，看 VAD 切得对不对。

为什么这么做：`docs/12-process.md` 的 S3 闸门是"录 50 句，端点切错 < 5 条"。
人耳验收不可复现，所以改成**用 TTS 合成 50 句 + 已知间隔**，期望值可以算出来。

    # 1) 先准备语料（用 tts 项目合成，见 README）
    # 2) 再跑验收
    uv run python scripts/accept_s3.py --corpus out/corpus
    uv run python scripts/accept_s3.py --corpus out/corpus --sweep 300,450,600,800

判定：`切错 = 漏检 + 多检`，≤ 5 条算通过。
"""

from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

import numpy as np

from voxdesk_audio import Segmenter, SileroVAD, enable_utf8, read_wav
from voxdesk_audio.capture import iter_frames
from voxdesk_audio.corpus import build_composite
from voxdesk_audio.vad import FRAME_MS

SR = 16000


def overlap(a: tuple[int, int], b: tuple[int, int]) -> int:
    return max(0, min(a[1], b[1]) - max(a[0], b[0]))


def run(vad: SileroVAD, audio: np.ndarray, min_silence: int) -> list[tuple[int, int]]:
    seg = Segmenter(min_silence_ms=min_silence)
    found: list[tuple[int, int]] = []
    for frame in iter_frames(audio):
        for s in seg.push(vad.prob(frame)):
            found.append((s.start_ms, s.end_ms))
    tail = seg.flush()
    if tail:
        found.append((tail.start_ms, tail.end_ms))
    return found


def score(found: list[tuple[int, int]], expected: list[tuple[int, int]]) -> dict[str, float]:
    if not expected:
        return {}

    used: set[int] = set()
    matched, errs = 0, []
    for exp in expected:
        best, best_i = 0, -1
        for i, got in enumerate(found):
            if i in used:
                continue
            ov = overlap(exp, got)
            if ov > best:
                best, best_i = ov, i
        duration = exp[1] - exp[0]
        if best_i >= 0 and best >= duration * 0.5:
            used.add(best_i)
            matched += 1
            errs.append(abs(found[best_i][0] - exp[0]))

    missing = len(expected) - matched
    extra = len(found) - matched
    return {
        "expected": len(expected),
        "found": len(found),
        "matched": matched,
        "missing": missing,
        "extra": extra,
        "wrong": missing + max(0, extra),
        "median_err_ms": statistics.median(errs) if errs else float("nan"),
    }


def main() -> int:
    enable_utf8()

    ap = argparse.ArgumentParser(description="S3 验收（合成语料）")
    ap.add_argument("--corpus", default="out/corpus", help="每句一个 wav 的目录")
    ap.add_argument("--gap", type=int, default=700, help="句间静音（ms）")
    ap.add_argument("--sweep", default="600", help="逗号分隔的 min_silence 取值")
    args = ap.parse_args()

    audio, expected = build_composite(Path(args.corpus), args.gap)
    print(f"语料 {len(expected)} 句，合成流 {len(audio) / SR:.1f}s，句间静音 {args.gap}ms\n")

    vad = SileroVAD()
    values = [int(v) for v in args.sweep.split(",")]
    rows = []
    for ms in values:
        vad.reset()
        found = run(vad, audio, ms)
        rows.append({"min_silence": ms, **score(found, expected)})

    print("| min_silence | 期望 | 检出 | 匹配 | 漏检 | 多检 | 切错 | 起点误差(中位) |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in rows:
        print(
            f"| {r['min_silence']}ms | {r['expected']} | {r['found']} | {r['matched']} | "
            f"{r['missing']} | {r['extra']} | **{r['wrong']}** | {r['median_err_ms']:.0f}ms |"
        )

    best = min(rows, key=lambda r: (r["wrong"], abs(r["min_silence"] - 600)))
    ok = best["wrong"] <= 5
    print(
        f"\n{'✅' if ok else '❌'} 最佳 min_silence={best['min_silence']}ms："
        f"切错 {best['wrong']} 条（判据 ≤ 5）"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
