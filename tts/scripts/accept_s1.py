"""S1 验收：跑完四项可测项，打一张表。

对应 `docs/09-tts-module.md` §8 的 B-1..B-4：

    B-1 分句   500 字文本每段 ≤ 50 字，且不切断完整句子
    B-2 首音   点击到第一声 ≤ 1.5s
    B-3 打断   播报中 stop()，300ms 内静音
    B-4 缓存   同一句第二次播放不再触发合成

用法：
    uv run python scripts/accept_s1.py
    uv run python scripts/accept_s1.py --no-audio    # 只测分句，不出声

退出码 0 = 全过。
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

from voxdesk_tts import SapiEngine, TTSService, enable_utf8, split
from voxdesk_tts.splitter import normalize

PARA = (
    "语音助手的第一段话要短，因为用户等的是回应，不是文章。"
    "切句的目的不是排版，是让声音尽早出来。"
    "一段话如果超过五十个字，就应该在标点处断开，"
    "让播放器先播前半句，合成器同时准备后半句。"
)
LONG_TEXT = "".join(PARA for _ in range(5))  # ≈ 450–500 字
SHORT_TEXT = "你好，这是首音测试。"


def check_split() -> tuple[bool, str]:
    segments = split(LONG_TEXT, 50)
    longest = max(len(s) for s in segments)
    broken = [s for s in segments[:-1] if s[-1] not in "。！？!?…"]
    lossless = "".join(segments).replace(" ", "") == normalize(LONG_TEXT).replace(" ", "")
    ok = longest <= 50 and not broken and lossless
    detail = f"{len(LONG_TEXT)} 字 → {len(segments)} 段，最长 {longest} 字"
    if broken:
        detail += f"，{len(broken)} 段未在句末断开"
    if not lossless:
        detail += "，有内容丢失"
    return ok, detail


def check_first_audio(service: TTSService, cache_dir: Path, runs: int = 3) -> tuple[bool, str]:
    """冷启动才算数：每轮先清空缓存，否则测的是"读 WAV"不是"合成"。"""
    samples: list[float] = []
    for _ in range(runs):
        shutil.rmtree(cache_dir, ignore_errors=True)
        cache_dir.mkdir(parents=True, exist_ok=True)
        service.speak(SHORT_TEXT)
        service.wait(timeout=20)
        value = service.stats["first_audio_ms"]
        if value is not None:
            samples.append(float(value))
    if not samples:
        return False, "没测到首音（没有音频输出？）"

    samples.sort()
    median = samples[len(samples) // 2]

    service.speak(SHORT_TEXT)  # 缓存已热，再测一次
    service.wait(timeout=20)
    warm = service.stats["first_audio_ms"]

    detail = (
        f"冷启动中位数 {median:.0f}ms（{runs} 次：{samples[0]:.0f}–{samples[-1]:.0f}ms）"
        f"，缓存命中 {warm:.0f}ms"
    )
    return median <= 1500, detail


def check_stop(service: TTSService) -> tuple[bool, str]:
    service.speak(LONG_TEXT * 2)  # 足够长，保证 stop 时还在播
    time.sleep(1.0)
    if not service.stats.get("played") and service.stats.get("first_audio_ms") is None:
        return False, "打断测试前没有开始播放"
    service.stop()
    value = service.stats["stop_ms"]
    return (value is not None and value <= 300), f"静音耗时 {value}ms"


def check_cache(service: TTSService, cache_dir: Path) -> tuple[bool, str]:
    shutil.rmtree(cache_dir, ignore_errors=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    service.speak(SHORT_TEXT)
    service.wait(timeout=20)
    first_synth = service.stats["synthesized"]

    service.speak(SHORT_TEXT)
    service.wait(timeout=20)
    second_synth = service.stats["synthesized"]
    hits = service.stats["cache_hits"]

    ok = first_synth > 0 and second_synth == 0 and hits > 0
    return ok, f"首轮合成 {first_synth} 段，次轮合成 {second_synth} 段、命中 {hits} 段"


def main() -> int:
    enable_utf8()

    ap = argparse.ArgumentParser(description="S1 验收")
    ap.add_argument("--no-audio", action="store_true", help="只测分句，不出声")
    args = ap.parse_args()

    rows: list[tuple[str, bool, str]] = []

    ok, detail = check_split()
    rows.append(("B-1 分句", ok, detail))

    if not args.no_audio:
        engine = SapiEngine()
        cache_dir = Path("cache") / "accept"
        with TTSService(engine, cache_dir=cache_dir) as service:
            rows.append(("B-2 首音", *check_first_audio(service, cache_dir)))
            rows.append(("B-3 打断", *check_stop(service)))
            rows.append(("B-4 缓存", *check_cache(service, cache_dir)))

    print("\nS1 验收结果")
    print("-" * 72)
    for name, ok, detail in rows:
        print(f"{'✅' if ok else '❌'} {name:<8} {detail}")
    print("-" * 72)

    failed = [name for name, ok, _ in rows if not ok]
    if failed:
        print(f"未通过：{'、'.join(failed)}")
        return 1
    print("全部通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
