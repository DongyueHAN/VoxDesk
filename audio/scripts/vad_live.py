"""实时端点检测：对着麦克风说话，终端打印每一句话的起止。

两种模式：

    # 1) 自动断句（VAD）
    uv run python scripts/vad_live.py
    uv run python scripts/vad_live.py --denoise          # 开谱减降噪
    uv run python scripts/vad_live.py --min-silence 400

    # 2) 按住说话（PTT）
    uv run python scripts/vad_live.py --ptt f2

Ctrl+C 结束。这就是 S3 的"耳朵"——它不识别内容，只判断"一句话什么时候结束"。
"""

from __future__ import annotations

import argparse
import contextlib
import time

from voxdesk_audio import (
    DenoiseStage,
    MicStream,
    PushToTalk,
    Segment,
    Segmenter,
    SileroVAD,
    enable_utf8,
)
from voxdesk_audio.vad import FRAME_MS


def main() -> int:
    enable_utf8()

    ap = argparse.ArgumentParser(description="实时端点检测")
    ap.add_argument("--device", type=int, default=None, help="输入设备编号（见 list_devices）")
    ap.add_argument("--min-silence", type=int, default=600)
    ap.add_argument("--min-speech", type=int, default=250)
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--denoise", action="store_true", help="开降噪（默认 bypass）")
    ap.add_argument("--ptt", default=None, metavar="KEY", help="按住说话，如 f2")
    ap.add_argument("--seconds", type=float, default=None, help="只跑 N 秒（自测用）")
    args = ap.parse_args()

    vad = SileroVAD()
    seg = Segmenter(
        threshold=args.threshold,
        min_speech_ms=args.min_speech,
        min_silence_ms=args.min_silence,
    )
    denoise = DenoiseStage(enabled=args.denoise)

    mode = f"PTT（按住 {args.ptt}）" if args.ptt else f"VAD（静音尾 {args.min_silence}ms）"
    dn = "降噪开" if args.denoise else "降噪 bypass"
    print(f"监听中… {mode} · {dn} · Ctrl+C 退出")

    limit = None if args.seconds is None else int(args.seconds * 1000 / FRAME_MS)
    started = time.perf_counter()
    count = 0
    held_from: int | None = None

    try:
        with MicStream(device=args.device) as mic, contextlib.ExitStack() as stack:
            ptt = stack.enter_context(PushToTalk(args.ptt)) if args.ptt else None

            for frame in mic.frames(limit=limit):
                frame = denoise.process(frame)
                prob = vad.prob(frame)
                now_ms = int((time.perf_counter() - started) * 1000)

                if ptt is not None:
                    # PTT 模式：按下记起点，松开立刻成段（不依赖 VAD 静音尾）
                    if ptt.pressed and held_from is None:
                        held_from = now_ms
                    elif not ptt.pressed and held_from is not None:
                        if now_ms - held_from >= args.min_speech:
                            count += 1
                            print(f"\n  #{count} {Segment(held_from, now_ms)}   （PTT）", flush=True)
                        held_from = None
                else:
                    for s in seg.push(prob):
                        count += 1
                        print(f"\n  #{count} {s}", flush=True)

                active = ptt.pressed if ptt else seg.in_speech
                state = "说话中 ●" if active else "静音  ·"
                bar = "█" * int(prob * 20)
                print(f"\r{state}  {prob:>4.2f} {bar:<20}", end="", flush=True)
    except KeyboardInterrupt:
        print()
    finally:
        tail = seg.flush()
        if tail:
            count += 1
            print(f"\n  #{count} {tail}   （流结束时闭合）")
    print(f"\n共 {count} 段。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
