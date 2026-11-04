"""把一段 WAV 喂给 VAD，打印它切出来的段落。

用途：没有麦克风也能验证端点，且结果可复现。

    uv run python scripts/vad_file.py out/test.wav
    uv run python scripts/vad_file.py out/test.wav --min-silence 400 --bar
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from voxdesk_audio import Segmenter, SileroVAD, enable_utf8, read_wav
from voxdesk_audio.capture import iter_frames


def main() -> int:
    enable_utf8()

    ap = argparse.ArgumentParser(description="WAV 端点检测")
    ap.add_argument("wav")
    ap.add_argument("--min-silence", type=int, default=600, help="静音尾判定（ms）")
    ap.add_argument("--min-speech", type=int, default=250, help="最短语音（ms）")
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--model", default=None)
    ap.add_argument("--bar", action="store_true", help="打印每帧概率条")
    args = ap.parse_args()

    audio = read_wav(args.wav)
    vad = SileroVAD(args.model) if args.model else SileroVAD()
    seg = Segmenter(
        threshold=args.threshold,
        min_speech_ms=args.min_speech,
        min_silence_ms=args.min_silence,
    )

    segments = []
    for i, frame in enumerate(iter_frames(audio)):
        prob = vad.prob(frame)
        if args.bar:
            bar = "█" * int(prob * 30)
            print(f"{i * 32 / 1000:>6.2f}s {prob:>5.2f} {bar}", flush=True)
        segments.extend(seg.push(prob))

    tail = seg.flush()
    if tail:
        segments.append(tail)

    total_ms = len(audio) / 16000 * 1000
    print(f"\n{Path(args.wav).name}: {total_ms:.0f}ms 音频 → {len(segments)} 段")
    for s in segments:
        print(f"  {s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
