"""S4 单点验证：把一个 wav 转成文本，并报告首字与总耗时。

    uv run python scripts/asr_file.py out/corpus/01.wav
    uv run python scripts/asr_file.py out/corpus/01.wav --chunk-ms 32
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from voxdesk_audio import StreamingASR, enable_utf8, read_wav


def main() -> int:
    enable_utf8()

    ap = argparse.ArgumentParser(description="单文件 ASR")
    ap.add_argument("wav")
    ap.add_argument("--chunk-ms", type=int, default=100, help="喂块大小（模拟流式）")
    ap.add_argument("--model", default=None)
    ap.add_argument("--fp32", action="store_true", help="用 fp32 模型（默认 int8）")
    args = ap.parse_args()

    audio = read_wav(args.wav, 16000)
    asr = StreamingASR(args.model) if args.model else StreamingASR(use_int8=not args.fp32)
    result = asr.transcribe(audio, chunk_ms=args.chunk_ms)

    print(f"文件   {Path(args.wav).name}")
    print(f"音频   {result.audio_s:.2f}s（{result.chunks} 块 × {args.chunk_ms}ms）")
    print(f"文本   {result.text}")
    print(f"首字   {result.first_char_ms:.0f}ms" if result.first_char_ms else "首字   （无输出）")
    print(f"总耗时 {result.total_ms:.0f}ms   实时因子 {result.rtf:.3f}")
    return 0 if result.text else 1


if __name__ == "__main__":
    raise SystemExit(main())
