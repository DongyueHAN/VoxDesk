"""S4 的离线评测：50 句合成语料上有标准答案，可以直接算 CER。

语料是用 TTS 合成出来的（所以文本已知），这让"ASR 准不准"变成一个可复现的数字，
而不是"听起来差不多"。

    uv run python scripts/asr_cer.py --corpus out/corpus
    uv run python scripts/asr_cer.py --corpus out/corpus --limit 10 --model models/xxx
"""

from __future__ import annotations

import argparse
from pathlib import Path

from voxdesk_audio import StreamingASR, enable_utf8, read_wav

# 与生成语料时的 10 句池一致（scripts/asr_cer.py 与 README 的生成命令必须同步）
POOL = [
    "第一句测试。语音端点检测要判断一句话什么时候开始。",
    "第二句稍长一点，用来观察中段停顿会不会被误切。",
    "第三句很短。",
    "第四句带问号，这样可以吗？",
    "第五句带感叹号！",
    "第六句分成两半，中间有一个逗号停顿，但不应该断开。",
    "第七句里有很多字，因为要验证长句不会被中间的换气声切断，所以写得长一些再长一些。",
    "第八句。",
    "第九句包含数字二零二六和英文单词 VoxDesk。",
    "第十句收尾，看看最后一段能不能被 flush 吐出来。",
]

PUNCT = set("，。！？、；：“”‘’（）《》【】…—·, .!?;:\"'()<>[]{}~`-")


def normalize(text: str) -> str:
    return "".join(ch.lower() for ch in text if ch not in PUNCT and not ch.isspace())


def levenshtein(a: str, b: str) -> int:
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def main() -> int:
    enable_utf8()

    ap = argparse.ArgumentParser(description="语料 CER 评测")
    ap.add_argument("--corpus", default="out/corpus")
    ap.add_argument("--model", default=None)
    ap.add_argument("--limit", type=int, default=0, help="只测前 N 句（0=全部）")
    ap.add_argument("--chunk-ms", type=int, default=100)
    args = ap.parse_args()

    files = sorted(Path(args.corpus).glob("*.wav"))
    if not files:
        raise SystemExit(f"{args.corpus} 里没有 wav")
    if args.limit:
        files = files[: args.limit]

    asr = StreamingASR(args.model) if args.model else StreamingASR()

    total_err = total_len = 0
    firsts: list[float] = []
    rtf: list[float] = []
    print(f"{'文件':<10}{'CER':>7}  {'首字ms':>7}  {'RTF':>6}  参考 / 识别")
    print("-" * 100)
    for i, path in enumerate(files, 1):
        ref = normalize(POOL[(i - 1) % len(POOL)])
        result = asr.transcribe(read_wav(path, 16000), chunk_ms=args.chunk_ms)
        hyp = normalize(result.text)
        err = levenshtein(ref, hyp)
        cer = err / max(1, len(ref))
        total_err += err
        total_len += len(ref)
        if result.first_char_ms:
            firsts.append(result.first_char_ms)
        rtf.append(result.rtf)
        print(f"{path.name:<10}{cer:>6.1%}  {result.first_char_ms or 0:>7.0f}  {result.rtf:>6.3f}  {result.text}")

    print("-" * 100)
    print(f"整体 CER：{total_err / total_len:.1%}（{total_err}/{total_len} 字）")
    if firsts:
        print(f"首字：中位 {sorted(firsts)[len(firsts) // 2]:.0f}ms  最大 {max(firsts):.0f}ms")
    print(f"实时因子：中位 {sorted(rtf)[len(rtf) // 2]:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
