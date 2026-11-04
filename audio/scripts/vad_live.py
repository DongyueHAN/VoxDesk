"""实时端点检测：对着麦克风说话，终端打印每一句话的起止。

    uv run python scripts/vad_live.py
    uv run python scripts/vad_live.py --device 1 --min-silence 400

Ctrl+C 结束。这就是 S3 的"耳朵"——它不识别内容，只判断"一句话什么时候结束"。
"""

from __future__ import annotations

import argparse
import sys
import time

from voxdesk_audio import MicStream, Segmenter, SileroVAD, enable_utf8
from voxdesk_audio.vad import FRAME_MS


def main() -> int:
    enable_utf8()

    ap = argparse.ArgumentParser(description="实时端点检测")
    ap.add_argument("--device", type=int, default=None, help="输入设备编号（见 list_devices）")
    ap.add_argument("--min-silence", type=int, default=600)
    ap.add_argument("--min-speech", type=int, default=250)
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--seconds", type=float, default=None, help="只跑 N 秒（自测用）")
    args = ap.parse_args()

    vad = SileroVAD()
    seg = Segmenter(
        threshold=args.threshold,
        min_speech_ms=args.min_speech,
        min_silence_ms=args.min_silence,
    )

    print(f"监听中…（静音尾 {args.min_silence}ms，Ctrl+C 退出）")
    started = time.perf_counter()
    count = 0
    try:
        with MicStream(device=args.device) as mic:
            limit = None if args.seconds is None else int(args.seconds * 1000 / FRAME_MS)
            for frame in mic.frames(limit=limit):
                prob = vad.prob(frame)
                for s in seg.push(prob):
                    count += 1
                    since = time.perf_counter() - started
                    print(f"  #{count} {s}   （发生在 {since:.1f}s 处）", flush=True)
                # 单行状态：说话中显示实心，静音显示概率
                bar = "█" * int(prob * 20)
                state = "说话中 ●" if seg.in_speech else "静音  ·"
                print(f"\r{state}  {prob:>4.2f} {bar:<20}", end="", flush=True)
    except KeyboardInterrupt:
        print()
    finally:
        tail = seg.flush()
        if tail:
            count += 1
            print(f"  #{count} {tail}   （流结束时闭合）")
    print(f"\n共 {count} 段。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
