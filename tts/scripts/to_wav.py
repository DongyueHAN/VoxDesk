"""把文本合成成 WAV 并报告音频参数——S0 的"可验证产物"。

这一步是阶段 B 的钥匙（见 `09-tts-module.md` §6.4）：只有能落盘，
才能谈缓存、队列，以及后面换引擎时的 A/B 对比。

用法：
    uv run python scripts/to_wav.py
    uv run python scripts/to_wav.py --text "你好" --voice "Microsoft Huihui" --play
"""

from __future__ import annotations

import argparse
import json
import sys
import winsound
from pathlib import Path

from voxdesk_tts import enable_utf8, synth_to_wav


def main() -> int:
    enable_utf8()

    ap = argparse.ArgumentParser(description="合成到 WAV 并报告参数")
    ap.add_argument("--text", default="你好，我是 VoxDesk。现在开始 S0 测试。")
    ap.add_argument("--out", default=str(Path("out") / "s0_hello.wav"))
    ap.add_argument("--voice", default=None)
    ap.add_argument("--rate", type=int, default=0)
    ap.add_argument("--play", action="store_true", help="合成后用 winsound 播一遍")
    args = ap.parse_args()

    try:
        info = synth_to_wav(args.text, args.out, voice=args.voice, rate=args.rate)
    except Exception as exc:  # noqa: BLE001 - CLI 边界
        print(f"✗ 失败：{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(info, ensure_ascii=False, indent=2))
    if info["seconds"] == 0:
        print("✗ 合成出 0 秒音频，说明文本没被念出来", file=sys.stderr)
        return 1

    if args.play:
        print("→ 播放中…")
        winsound.PlaySound(str(Path(str(info["path"])).resolve()), winsound.SND_FILENAME)
        print("✓ 播放结束")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
