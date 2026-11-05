"""下载 VoxDesk 需要的三个模型（不随仓库分发）。

    # 全部（约 290MB）
    python scripts/fetch_models.py

    # 只下某一个
    python scripts/fetch_models.py --what vad
    python scripts/fetch_models.py --what tts
    python scripts/fetch_models.py --what asr

    # 已经存在就跳过；要重下加 --force
    python scripts/fetch_models.py --force

为什么不用 git 传：ASR 的 encoder.int8.onnx 有 157.8MB，超过 GitHub 单文件 100MB 硬限制，
而且这些模型本来就是公开可下载的。所以仓库只放这个脚本。

只用标准库（urllib），不需要额外依赖；先写 .part 再改名，中断不会留下半个文件。
国内网络建议保留默认镜像顺序（hf-mirror 优先，huggingface.co 兜底）。
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# 国内镜像优先；官方站兜底
MIRRORS = ("https://hf-mirror.com", "https://huggingface.co")
ASR_REPO = "csukuangfj/sherpa-onnx-streaming-paraformer-bilingual-zh-en"
TTS_PATH = "rhasspy/piper-voices/resolve/main/zh/zh_CN/huayan/medium"


@dataclass(frozen=True)
class Target:
    what: str
    dest: Path
    urls: tuple[str, ...]
    note: str = ""


def targets(root: Path) -> list[Target]:
    asr_dir = root / "audio" / "models" / "sherpa-onnx-streaming-paraformer-bilingual-zh-en"
    tts_dir = root / "tts" / "models"
    vad_dir = root / "audio" / "models"

    def hf(repo_and_file: str) -> tuple[str, ...]:
        return tuple(f"{m}/{repo_and_file}/resolve/main" if False else f"{m}/{repo_and_file}"
                     for m in MIRRORS)

    return [
        Target(
            "vad",
            vad_dir / "silero_vad.onnx",
            (
                "https://cdn.jsdelivr.net/gh/snakers4/silero-vad@master/src/silero_vad/data/silero_vad.onnx",
                "https://raw.githubusercontent.com/snakers4/silero-vad/master/src/silero_vad/data/silero_vad.onnx",
            ),
            "Silero VAD v5（2.3MB）",
        ),
        Target("asr", asr_dir / "encoder.int8.onnx", hf(f"{ASR_REPO}/resolve/main/encoder.int8.onnx"), "Paraformer 编码器（157.8MB）"),
        Target("asr", asr_dir / "decoder.int8.onnx", hf(f"{ASR_REPO}/resolve/main/decoder.int8.onnx"), "Paraformer 解码器（68.3MB）"),
        Target("asr", asr_dir / "tokens.txt", hf(f"{ASR_REPO}/resolve/main/tokens.txt"), "词表（0.1MB）"),
        Target("tts", tts_dir / "zh_CN-huayan-medium.onnx", hf(f"{TTS_PATH}/zh_CN-huayan-medium.onnx"), "Piper 音色（60MB）"),
        Target("tts", tts_dir / "zh_CN-huayan-medium.onnx.json", hf(f"{TTS_PATH}/zh_CN-huayan-medium.onnx.json"), "音色配置"),
    ]


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}GB"


def _fetch_one(url: str, dest: Path, timeout: int = 60) -> bool:
    part = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "voxdesk-fetch/1.0"})
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - 固定 https
            total = int(resp.headers.get("Content-Length") or 0)
            done = 0
            with part.open("wb") as fh:
                while True:
                    chunk = resp.read(1024 * 256)
                    if not chunk:
                        break
                    fh.write(chunk)
                    done += len(chunk)
                    if total:
                        pct = done * 100 / total
                        speed = done / max(time.perf_counter() - start, 0.001)
                        print(f"\r  {pct:5.1f}%  {human(done)}/{human(total)}  {human(speed)}/s", end="")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
        part.unlink(missing_ok=True)
        print(f"\r  该源失败：{type(exc).__name__}: {str(exc)[:70]}")
        return False

    if total and part.stat().st_size != total:
        part.unlink(missing_ok=True)
        print(f"\r  大小不符（期望 {total}，实际 {part.stat().st_size}）")
        return False

    os.replace(part, dest)
    print(f"\r  完成 {human(dest.stat().st_size)}，用时 {time.perf_counter() - start:.1f}s            ")
    return True


def download(t: Target, force: bool = False) -> bool:
    if t.dest.exists() and not force:
        print(f"  跳过（已存在 {human(t.dest.stat().st_size)}）")
        return False

    t.dest.parent.mkdir(parents=True, exist_ok=True)
    for i, url in enumerate(t.urls, 1):
        host = url.split("/")[2]
        print(f"  源 {i}/{len(t.urls)}：{host}")
        if _fetch_one(url, t.dest):
            return True
    raise SystemExit(f"✗ 所有源都失败：{t.dest.name}")


def main() -> int:
    ap = argparse.ArgumentParser(description="下载 VoxDesk 的模型（VAD / ASR / TTS）")
    ap.add_argument("--what", choices=["all", "vad", "asr", "tts"], default="all")
    ap.add_argument("--force", action="store_true", help="已存在也重新下载")
    ap.add_argument("--out", default=None, help="仓库根目录（默认自动推断，测试用）")
    args = ap.parse_args()

    root = Path(args.out).resolve() if args.out else REPO_ROOT
    todo = targets(root)
    if args.what != "all":
        todo = [t for t in todo if t.what == args.what]

    print(f"目标目录：{root}\n")
    new = 0
    for t in todo:
        print(f"[{t.what}] {t.note or t.dest.name} → {t.dest.relative_to(root)}")
        if download(t, args.force):
            new += 1

    print()
    print(f"完成：新下载 {new} 个文件。" if new else "完成：模型都已存在，没有下载。")
    print("自检：python scripts/voice_chat.py --mock 或 python ..\\audio\\scripts\\vad_live.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
