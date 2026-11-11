"""IF-10 · 形象驱动（`CMP-14`，工作包 WP5）。

契约见 `docs/system/docs/03-architecture.md` §3.2 `IF-10`：
`DriveAvatar(frame) -> void`，**异步投递**——形象掉帧不许回头影响播报（`FLOW-08`）。

渲染器路线**暂定**（`DEC-003`：Live2D / VRM / 贴图），所以这里只定 `frame` 的形状，
不管怎么画。当前只有 `NullAvatar`（什么也不做），接上真渲染器时替换 `get_sink()` 即可，
调用方（`voice_app.chat`）一行都不用改。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

EMOTIONS: tuple[str, ...] = ("neutral", "happy", "confused", "angry", "surprised")
"""与 `REQ-F-102` 的 5 种表情一致。"""


@dataclass(frozen=True)
class AvatarFrame:
    """一帧驱动指令。

    - `text`：这一轮要说的内容（形象可据此做口型或字幕）
    - `emotion`：情绪，取值见 `EMOTIONS`
    - `motion`：待机/动作名，`None` 表示不动
    - `viseme`：由 TTS 音频块算出的口型；`None` 表示这一帧不带口型（`FLOW-08`）
    """

    text: str
    emotion: str = "neutral"
    motion: str | None = None
    viseme: str | None = None


class AvatarSink(Protocol):
    def drive(self, frame: AvatarFrame) -> None: ...


class NullAvatar:
    """默认实现：不渲染。留着它是为了让整条链路先跑通，而不是等渲染器。"""

    def drive(self, frame: AvatarFrame) -> None:  # noqa: ARG002 - 故意不做事
        return None


_sink: AvatarSink = NullAvatar()


def get_sink() -> AvatarSink:
    return _sink


def set_sink(sink: AvatarSink) -> None:
    """接真渲染器时调用；测试里可注入假 sink。"""
    global _sink
    _sink = sink


def emit(text: str, emotion: str = "neutral", motion: str | None = None) -> None:
    """主链路唯一入口：任何异常都不许冒泡到播报。"""
    if emotion not in EMOTIONS:
        emotion = "neutral"
    try:
        _sink.drive(AvatarFrame(text=text, emotion=emotion, motion=motion))
    except Exception:  # noqa: BLE001 - 形象是旁路，坏了不能影响回答
        if os.environ.get("VOXDESK_AVATAR_DEBUG"):
            raise


def contract() -> dict:
    return {
        "interface": "IF-10",
        "component": "CMP-14",
        "work_package": "WP5",
        "renderer": "undecided (DEC-003)",
        "sink": type(get_sink()).__name__,
        "emotions": list(EMOTIONS),
    }
