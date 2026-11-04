"""一句话演示：模拟输入文本 → DeepSeek → 播报。

不需要麦克风、不需要录音——把一句话当作用户说的，走完"理解 → 回答 → 念出来"。

    # 默认演示句（接下半句）
    python scripts/demo_one.py

    # 自定义
    python scripts/demo_one.py --text "今天天气怎么样？"
    python scripts/demo_one.py --mock            # 不调 API
    python scripts/demo_one.py --no-tts          # 只出文字，不出声

输出是给录屏用的：每一步一行，带耗时。
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from voxdesk_demo.app import VoiceChat  # noqa: E402
from voxdesk_demo.llm import DeepSeekChat, DeepSeekError  # noqa: E402
from voxdesk_audio import enable_utf8  # noqa: E402

DEFAULT_TEXT = "我说上句，你只接下句：左手看自家下路被双杀激动到大喊nice！"

# 演示"接下半句"时用这个 system prompt，避免模型解释/总结
CONTINUE_SYSTEM = (
    "用户说上半句，你只接下半句。直接给出接的那半句，不要解释、不要引号、"
    "不要重复用户说过的话，不超过 40 个字。"
)


def main() -> int:
    enable_utf8()
    ap = argparse.ArgumentParser(description="一句话演示：文本 → DeepSeek → TTS")
    ap.add_argument("--text", default=DEFAULT_TEXT)
    ap.add_argument("--system", default=CONTINUE_SYSTEM)
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--no-tts", action="store_true", help="只打印回复，不合成不播放")
    args = ap.parse_args()

    llm = None
    if not args.mock:
        try:
            llm = DeepSeekChat()
        except DeepSeekError as exc:
            print(f"✗ {exc}", file=sys.stderr)
            return 2

    chat = VoiceChat(llm=llm, mock=args.mock, system_prompt=args.system)
    try:
        print("─" * 60)
        print(f"[输入] {args.text}")
        print("─" * 60)

        t0 = time.perf_counter()
        turn = chat.handle_text(args.text, speak=not args.no_tts)
        total = (time.perf_counter() - t0) * 1000

        print(f"[回答] {turn.reply_text}")
        print("─" * 60)
        if turn.first_token_ms is not None:
            print(f"首 token   {turn.first_token_ms:>6.0f} ms")
        if turn.llm_ms is not None:
            print(f"LLM 总计   {turn.llm_ms:>6.0f} ms")
        if turn.tts_ms is not None:
            print(f"播报时长   {turn.tts_ms:>6.0f} ms（含播放）")
        print(f"端到端     {total:>6.0f} ms")
        print("─" * 60)
    finally:
        chat.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
