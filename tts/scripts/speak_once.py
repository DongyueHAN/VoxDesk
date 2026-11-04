"""S0 的正戏：让机器念出一句话。

用法：
    uv run python scripts/speak_once.py
    uv run python scripts/speak_once.py --text "第一句。第二句。" --voice "Microsoft Huihui"
    uv run python scripts/speak_once.py --list          # 顺带列出音色

退出码 0 = 已播完；非 0 = 失败（错误信息在 stderr）。
"""

from __future__ import annotations

import argparse
import sys

from voxdesk_tts import enable_utf8, list_voices, speak


def main() -> int:
    enable_utf8()

    ap = argparse.ArgumentParser(description="用 SAPI 念一句话")
    ap.add_argument("--text", default="你好，我是 VoxDesk。现在开始 S0 测试。")
    ap.add_argument("--voice", default=None, help="音色名，支持模糊匹配；默认系统默认音色")
    ap.add_argument("--rate", type=int, default=0, help="语速 -10..10，默认 0")
    ap.add_argument("--list", action="store_true", help="先列出音色再朗读")
    args = ap.parse_args()

    if args.list:
        for v in list_voices():
            print(f"  - {v}")

    print(f"→ 朗读：{args.text}（音色 {args.voice or '默认'}）")
    try:
        elapsed = speak(args.text, voice=args.voice, rate=args.rate)
    except Exception as exc:  # noqa: BLE001 - CLI 边界，打印即可
        print(f"✗ 失败：{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(f"✓ 播完，用时 {elapsed:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
