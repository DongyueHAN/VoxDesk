"""两个引擎的 A/B 基准：合成速度、首音、打断、缓存、体积。

同一段文本、同一套 `TTSService`，只换引擎——这是 S2 要证明的东西。

    uv run python scripts/bench_engines.py                 # sapi + piper
    uv run python scripts/bench_engines.py --engines piper
    uv run python scripts/bench_engines.py --repeat 3      # 每项重复取中位数

输出一张 markdown 表，可直接粘进文档。
"""

from __future__ import annotations

import argparse
import json
import shutil
import statistics
import time
import wave
from pathlib import Path

from voxdesk_tts import TTSService, enable_utf8, make_engine, wav_seconds

TEXT = "第一句测试。第二句稍长一点的句子，用来观察切句效果。第三句收尾。"
LONG = "这是一段用来测试打断的长文本。" * 8


def synth_only(engine: object, out: Path, repeat: int) -> dict[str, float]:
    """直接调引擎，不经过队列：测纯合成速度。"""
    times, seconds = [], []
    for _ in range(repeat):
        if out.exists():
            out.unlink()
        start = time.perf_counter()
        engine.synth(TEXT, out)  # type: ignore[attr-defined]
        times.append(time.perf_counter() - start)
        seconds.append(wav_seconds(out))
    synth = statistics.median(times)
    audio = statistics.median(seconds)
    return {
        "synth_s": synth,
        "audio_s": audio,
        "rtf": synth / audio if audio else float("nan"),
    }


def via_service(name: str, model: str | None, cache_dir: Path, repeat: int) -> dict[str, float | str]:
    """走完整链路：清缓存 → 说 → 量首音；再测打断。"""
    engine = make_engine(name, model=model)
    shutil.rmtree(cache_dir, ignore_errors=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    firsts: list[float] = []
    with TTSService(engine, cache_dir=cache_dir) as service:
        for _ in range(repeat):
            shutil.rmtree(cache_dir, ignore_errors=True)
            cache_dir.mkdir(parents=True, exist_ok=True)
            service.speak(TEXT)
            service.wait(timeout=60)
            value = service.stats["first_audio_ms"]
            if value is not None:
                firsts.append(float(value))

        # 缓存命中：同一句第二次
        service.speak(TEXT)
        service.wait(timeout=60)
        warm_synth = service.stats["synthesized"]
        warm_hits = service.stats["cache_hits"]

        # 打断：长文本播 0.8s 后 stop
        service.speak(LONG)
        time.sleep(0.8)
        service.stop()
        stop_ms = service.stats["stop_ms"]

    return {
        "first_ms": statistics.median(firsts) if firsts else float("nan"),
        "warm_synth": warm_synth,
        "warm_hits": warm_hits,
        "stop_ms": stop_ms if stop_ms is not None else float("nan"),
    }


def model_size(name: str, model: str | None) -> str:
    if name != "piper":
        return "0（系统自带）"
    path = Path(model) if model else Path("models") / "zh_CN-huayan-medium.onnx"
    total = path.stat().st_size if path.exists() else 0
    json_path = path.with_suffix(path.suffix + ".json")
    if json_path.exists():
        total += json_path.stat().st_size
    return f"{total / 1024 / 1024:.0f} MB"


def main() -> int:
    enable_utf8()

    ap = argparse.ArgumentParser(description="引擎 A/B 基准")
    ap.add_argument("--engines", nargs="+", default=["sapi", "piper"])
    ap.add_argument("--model", default=None)
    ap.add_argument("--repeat", type=int, default=3)
    args = ap.parse_args()

    rows = []
    for name in args.engines:
        engine = make_engine(name, model=args.model)
        synth = synth_only(engine, Path("out") / f"bench_{name}.wav", args.repeat)
        flow = via_service(name, args.model, Path("cache") / f"bench-{name}", args.repeat)
        rows.append(
            {
                "engine": name,
                "load_s": getattr(engine, "load_seconds", None),
                "synth_s": round(synth["synth_s"], 3),
                "audio_s": round(synth["audio_s"], 2),
                "rtf": round(synth["rtf"], 3),
                "first_ms": round(float(flow["first_ms"]), 0),
                "stop_ms": flow["stop_ms"],
                "cache": f"{flow['warm_hits']} 命中 / {flow['warm_synth']} 合成",
                "size": model_size(name, args.model),
            }
        )

    print("\n| 引擎 | 模型加载 | 合成耗时 | 音频时长 | 实时因子 | 首音(冷) | 打断 | 二次播放 | 体积 |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in rows:
        load = "—" if r["load_s"] is None else f"{r['load_s']:.2f}s"
        print(
            f"| **{r['engine']}** | {load} | {r['synth_s']}s | {r['audio_s']}s | "
            f"{r['rtf']} | {r['first_ms']:.0f}ms | {r['stop_ms']}ms | {r['cache']} | {r['size']} |"
        )

    Path("out").mkdir(exist_ok=True)
    (Path("out") / "bench.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\n明细已写 out/bench.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
