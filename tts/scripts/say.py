"""S1 的日常用法：把一段文字念出来，可中途打断。

    uv run python scripts/say.py --text "第一句。第二句。第三句。"
    uv run python scripts/say.py --file note.txt --voice Huihui
    uv run python scripts/say.py --text "很长的一段话……" --stop-after 1.5   # 演示打断

退出码 0 = 正常播完或被正常打断；非 0 = 失败。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from voxdesk_tts import TTSService, enable_utf8, make_engine


def main() -> int:
    enable_utf8()

    ap = argparse.ArgumentParser(description="用 TTSService 念一段文字")
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--text", help="要念的文字")
    src.add_argument("--file", help="从文件读（UTF-8）")
    ap.add_argument("--engine", default="sapi", choices=["sapi", "piper"], help="引擎")
    ap.add_argument("--model", default=None, help="Piper 模型路径（默认 models/zh_CN-huayan-medium.onnx）")
    ap.add_argument("--voice", default=None, help="音色名，支持模糊匹配（仅 sapi）")
    ap.add_argument("--rate", type=int, default=0, help="语速 -10..10")
    ap.add_argument("--max-len", type=int, default=50, help="每段最大字数")
    ap.add_argument("--stop-after", type=float, default=None, help="播 N 秒后调用 stop()")
    ap.add_argument("--stats", action="store_true", help="打印统计")
    args = ap.parse_args()

    if args.file:
        text = Path(args.file).read_text(encoding="utf-8")
    elif args.text:
        text = args.text
    else:
        text = "第一句。第二句。第三句。这是 S1 的默认测试文本。"

    engine = make_engine(args.engine, voice=args.voice, rate=args.rate, model=args.model)
    with TTSService(engine, cache_dir="cache", max_len=args.max_len) as service:
        segments = service.speak(text)
        print(f"→ {len(text)} 字，切成 {segments} 段")

        if args.stop_after is not None:
            import time

            time.sleep(args.stop_after)
            service.stop()
            print(f"■ 已在第 {args.stop_after}s 打断，静音耗时 {service.stats['stop_ms']}ms")
        else:
            if not service.wait(timeout=120):
                print("✗ 超时未播完", file=sys.stderr)
                return 1
            print(f"✓ 播完，总耗时 {service.stats['total_ms']}ms")

        if args.stats:
            print(json.dumps(service.stats, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
