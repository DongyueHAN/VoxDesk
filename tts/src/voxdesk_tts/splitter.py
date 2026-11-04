"""切句：把一段文字切成适合逐段合成 / 播放的小块。

为什么必须切：整段合成要等整段写完才出声（S0 实测 5.8s 文本合成 0.05s，
但一次塞 500 字，首音就得等全部合成完）。切成 50 字以内，第一段几十毫秒就能开播。

三步：
1. **先按句末标点切成"句"**（。！？；…），收尾引号跟着上一句；
2. **再合并**：相邻的短句只要总长不超过 `max_len` 就并成一段——
   避免"好。""嗯。"这种一句一段的碎碎念；
3. **超长句硬切**：单句超过 `max_len` 时，退到最近的逗号/空格处切；
   实在没有断点才按字数切。
"""

from __future__ import annotations

import re

_SENT_END = "。！？!?；;…\n"
_CLOSERS = "”’」』）)】》>"
_SOFT_BREAK = "，,、：: "
_WS = re.compile(r"[ \t\u3000]+")
_HARD_BREAK_MIN = 8


def normalize(text: str) -> str:
    """压掉多余空白与 Markdown 强调符号。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _WS.sub(" ", text)
    text = text.replace("**", "").replace("__", "")
    return text.strip()


def _sentences(text: str) -> list[str]:
    """按句末标点切，收尾符号并进上一句。"""
    units: list[str] = []
    buf = ""
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        buf += ch
        i += 1
        if ch in _SENT_END:
            while i < n and text[i] in _CLOSERS:
                buf += text[i]
                i += 1
            piece = buf.strip()
            if piece:
                units.append(piece)
            buf = ""
    piece = buf.strip()
    if piece:
        units.append(piece)
    return units


def _hard_cut(unit: str, max_len: int) -> list[str]:
    """把超长句切成不超过 max_len 的块，尽量在逗号/空格处断。"""
    pieces: list[str] = []
    rest = unit
    while len(rest) > max_len:
        window = rest[:max_len]
        cut = max(window.rfind(c) for c in _SOFT_BREAK)
        if cut < max_len // 2:
            cut = max_len - 1
        piece = rest[: cut + 1].strip()
        if piece:
            pieces.append(piece)
        rest = rest[cut + 1 :]
    rest = rest.strip()
    if rest:
        pieces.append(rest)
    return pieces


def split(text: str, max_len: int = 50) -> list[str]:
    """切句并合并短句，保证每段长度 ≤ `max_len`。"""
    if max_len < _HARD_BREAK_MIN:
        raise ValueError(f"max_len 至少 {_HARD_BREAK_MIN}")

    text = normalize(text)
    if not text:
        return []

    out: list[str] = []
    buf = ""
    for unit in _sentences(text):
        if len(unit) > max_len:
            if buf:
                out.append(buf)
                buf = ""
            out.extend(_hard_cut(unit, max_len))
            continue

        if len(buf) + len(unit) <= max_len:
            buf += unit
        else:
            if buf:
                out.append(buf)
            buf = unit

    if buf:
        out.append(buf)
    return out
