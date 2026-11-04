"""列出本机可用的 SAPI 音色。

用法：
    uv run python scripts/probe_voices.py          # 全部
    uv run python scripts/probe_voices.py --zh     # 只看中文
    uv run python scripts/probe_voices.py --json   # 机器可读
"""

from __future__ import annotations

import argparse
import json
import sys

from voxdesk_tts import enable_utf8, list_voices


def main() -> int:
    enable_utf8()

    ap = argparse.ArgumentParser(description="列出 SAPI 音色")
    ap.add_argument("--zh", action="store_true", help="只看中文音色")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    voices = list_voices(zh_only=args.zh)
    if not voices:
        print("✗ 没找到任何音色。检查：设置 → 时间和语言 → 语音 → 语音包", file=sys.stderr)
        return 1

    if args.json:
        rows = [{"name": v.name, "lang": v.lang, "gender": v.gender, "age": v.age} for v in voices]
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0

    print(f"共 {len(voices)} 个音色：")
    for i, v in enumerate(voices, 1):
        print(f"  {i}. {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
