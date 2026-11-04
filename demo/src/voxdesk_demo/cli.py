"""命令行入口（源码运行与打包后的 exe 共用）。

    VoxDeskVoice.exe                 按住 F2 说话（双击默认走这里）
    VoxDeskVoice.exe --seconds 4     录 4 秒
    VoxDeskVoice.exe --file x.wav    用现成 wav
    VoxDeskVoice.exe --mock          不调 API

**双击 exe 时**（无参数）出错或正常结束都会停在"按回车关闭"，避免窗口一闪而过。
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import numpy as np

from voxdesk_audio import MicStream, PushToTalk, enable_utf8, read_wav
from voxdesk_demo import __version__, paths
from voxdesk_demo.app import VoiceChat
from voxdesk_demo.llm import KEY_ENV, DeepSeekChat, DeepSeekError, load_env_file

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


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="语音 → ASR → DeepSeek → TTS（临时 demo）")
    ap.add_argument("--file", default=None, help="用现成 wav，不录音")
    ap.add_argument("--seconds", type=float, default=None, help="录 N 秒")
    ap.add_argument("--ptt", default="f2", help="按住说话的键（默认 f2）")
    ap.add_argument("--device", type=int, default=None, help="输入设备编号")
    ap.add_argument("--mock", action="store_true", help="不调 API，用固定回复")
    ap.add_argument("--key", default=None, help=f"API key（默认读环境变量 {KEY_ENV} 或 .env）")
    ap.add_argument("--model", default=None, help="模型名（默认读 DEEPSEEK_MODEL 或 deepseek-chat）")
    ap.add_argument("--system", default=None, help="覆盖 system prompt")
    ap.add_argument("--models", default=None, help="模型根目录（默认 exe 旁边的 models/）")
    return ap


def banner(args: argparse.Namespace, root: Path) -> None:
    kind = "打包版" if paths.is_frozen() else "源码版"
    has_key = bool(args.key or os.environ.get(KEY_ENV))
    mode = "mock（不调 API）" if args.mock else ("DeepSeek API" if has_key else "DeepSeek API · **未配置 key**")
    print("=" * 62)
    print(f"VoxDesk Voice {__version__} · {kind}")
    print(f"模型目录：{root}")
    print(f"模式：{mode}")
    print("=" * 62)


def run(args: argparse.Namespace) -> int:
    load_env_file()  # 让 banner 的 key 状态反映 .env
    if args.models:
        root = Path(args.models)
        asr_dir, piper_model = root / paths.ASR_DIR_NAME, root / paths.PIPER_MODEL_NAME
    else:
        root = paths.models_dir() if paths.is_frozen() else paths.app_root()
        asr_dir, piper_model = paths.default_asr_dir(), paths.default_piper_model()

    banner(args, root)

    llm = None
    if not args.mock:
        try:
            llm = DeepSeekChat(api_key=args.key, model=args.model)
        except DeepSeekError as exc:
            print(f"\n✗ {exc}", file=sys.stderr)
            print(f"  预期位置：{paths.env_files()[0]}（与 exe 同目录）", file=sys.stderr)
            print("  临时办法：在同目录新建 .env，写一行 DEEPSEEK_API_KEY=sk-...", file=sys.stderr)
            print("  不花钱验链路：加 --mock", file=sys.stderr)
            return 2

    kwargs = {"system_prompt": args.system} if args.system else {}
    print("正在加载模型（首次约 3 秒）…", flush=True)
    try:
        chat = VoiceChat(
            llm=llm,
            mock=args.mock,
            asr_model_dir=asr_dir,
            model_dir=piper_model,
            **kwargs,
        )
    except FileNotFoundError as exc:
        print(f"\n✗ {exc}", file=sys.stderr)
        print(f"  模型应放在：{root}", file=sys.stderr)
        return 4

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

        print(f"就绪。按住 {args.ptt} 说话，松开即回答；Ctrl+C 退出。\n")
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
        print(f"\n✗ API 出错：{exc}", file=sys.stderr)
        return 3
    finally:
        chat.close()
    return 0


def _pause_on_exit() -> None:
    """双击 exe（无参数）时停一下，否则窗口一闪而过，什么都看不见。"""
    try:
        sys.stdout.flush()
        input("\n按回车关闭窗口…")
    except (EOFError, KeyboardInterrupt):
        pass


def main(argv: list[str] | None = None) -> int:
    enable_utf8()
    args = build_parser().parse_args(argv)
    interactive = paths.is_frozen() and not (argv if argv is not None else sys.argv[1:])

    code = 1
    try:
        code = run(args)
    except KeyboardInterrupt:
        print("\n已中断。")
        code = 0
    except Exception as exc:  # noqa: BLE001 - 双击场景下必须让用户看到错误
        print(f"\n✗ 未预期的错误：{type(exc).__name__}: {exc}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        code = 9
    finally:
        if interactive:
            _pause_on_exit()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
