"""临时 demo 入口：语音 → ASR → DeepSeek → TTS。

三种输入方式（按方便程度）：

    # 1) 拿现成 wav 跑通链路（不需要麦克风、不需要 key——加 --mock）
    uv run python scripts/voice_chat.py --file ..\\audio\\out\\corpus\\01.wav --mock

    # 2) 固定录 N 秒（不需要键盘）
    uv run python scripts/voice_chat.py --seconds 4

    # 3) 按住说话（默认 f2）
    uv run python scripts/voice_chat.py

真调 API 前先设 key：`$env:DEEPSEEK_API_KEY = "sk-..."`。
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

from voxdesk_audio import MicStream, PushToTalk, enable_utf8, read_wav
from voxdesk_demo.app import VoiceChat
from voxdesk_demo.llm import KEY_ENV, DeepSeekChat, DeepSeekError

SR = 16000


def record_seconds(seconds: float, device: int | None) -> np.ndarray:
    frames: list[np.ndarray] = []
    with MicStream(device=device) as mic:
        frames.extend(mic.frames(limit=int(seconds * 1000 / 32)))
    return np.concatenate(frames) if frames else np.zeros(0, np.float32)


def record_while_pressed(ptt: PushToTalk, device: int | None) -> np.ndarray:
    """按下后开麦、松开停。开麦有 ~50ms 开销，所以第一个字可能被削——demo 够用。"""
    frames: list[np.ndarray] = []
    with MicStream(device=device) as mic:
        while ptt.pressed:
            frames.extend(mic.frames(limit=1))
    return np.concatenate(frames) if frames else np.zeros(0, np.float32)


def report(turn) -> None:
    if not turn.user_text:
        print("（没有听到内容，跳过）")
        return
    print(f"\n你说：{turn.user_text}")
    print(f"它说：{turn.reply_text}")
    print(f"耗时：{turn}  |  合计 {turn.total_ms:.0f}ms")


def main() -> int:
    enable_utf8()

    ap = argparse.ArgumentParser(description="语音 → ASR → DeepSeek → TTS（临时 demo）")
    ap.add_argument("--file", default=None, help="用现成 wav，不录音")
    ap.add_argument("--seconds", type=float, default=None, help="录 N 秒")
    ap.add_argument("--ptt", default="f2", help="按住说话的键（默认 f2）")
    ap.add_argument("--device", type=int, default=None, help="输入设备编号")
    ap.add_argument("--mock", action="store_true", help="不调 API，用固定回复")
    ap.add_argument("--key", default=None, help=f"API key（默认读环境变量 {KEY_ENV}）")
    ap.add_argument("--model", default="deepseek-chat")
    ap.add_argument("--system", default=None, help="覆盖 system prompt")
    args = ap.parse_args()

    llm = None
    if not args.mock:
        try:
            llm = DeepSeekChat(api_key=args.key, model=args.model)
        except DeepSeekError as exc:
            print(f"✗ {exc}", file=sys.stderr)
            print("  想先看链路，可以加 --mock", file=sys.stderr)
            return 2

    chat = VoiceChat(llm=llm, mock=args.mock, **({"system_prompt": args.system} if args.system else {}))
    try:
        if args.file:
            audio = read_wav(args.file, SR)
            print(f"读入 {Path(args.file).name}：{len(audio) / SR:.2f}s")
            report(chat.handle_audio(audio))
            return 0

        if args.seconds:
            print(f"录音 {args.seconds}s…（现在开始说）")
            report(chat.handle_audio(record_seconds(args.seconds, args.device)))
            return 0

        print(f"按住 {args.ptt} 说话，松开即回答。Ctrl+C 退出。")
        with PushToTalk(args.ptt) as ptt:
            while True:
                while not ptt.pressed:
                    time.sleep(0.02)
                audio = record_while_pressed(ptt, args.device)
                if len(audio) < 0.3 * SR:
                    print("（太短，忽略）")
                    continue
                report(chat.handle_audio(audio))
    except KeyboardInterrupt:
        print("\n退出。")
    except DeepSeekError as exc:
        print(f"✗ API 出错：{exc}", file=sys.stderr)
        return 3
    finally:
        chat.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
