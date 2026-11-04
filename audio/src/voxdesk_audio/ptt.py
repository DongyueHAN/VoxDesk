"""PTT（Push-To-Talk）：按住说话、松开断句。

用 `keyboard` 的全局钩子，不需要窗口焦点——这对语音助手是硬需求：
你在任何程序里按一下就能说话。

`backend` 参数是为了**可测**：单测里注入一个假的键盘模块，直接调它的回调，
不需要真人按键。真机上 backend 就是 `keyboard` 模块本身。

> 失败降级：`keyboard` 在极少数环境（受控桌面、部分远程会话）装不上钩子。
> 那种情况下 `PushToTalk.start()` 会抛异常，调用方退回 VAD 自动断句即可——
> 这正是 `04` §3.1 写的"失败时降级为托盘点击"。
"""

from __future__ import annotations

import threading
from typing import Any

try:  # 允许无键盘环境下 import 本模块（测试用假 backend）
    import keyboard as _keyboard
except Exception:  # pragma: no cover - 只影响默认 backend
    _keyboard = None


class PushToTalk:
    def __init__(self, key: str = "f2", backend: Any | None = None) -> None:
        self.key = key
        self._kb = backend if backend is not None else _keyboard
        if self._kb is None:
            raise RuntimeError("没有 keyboard 模块，PTT 不可用（可退回 VAD 自动断句）")

        self._pressed = threading.Event()
        self._hooks: list[Any] = []
        self.press_count = 0

    # ---- 生命周期 ----

    def start(self) -> None:
        self._hooks.append(self._kb.on_press_key(self.key, self._on_press, suppress=False))
        self._hooks.append(self._kb.on_release_key(self.key, self._on_release, suppress=False))

    def stop(self) -> None:
        for hook in self._hooks:
            try:
                self._kb.unhook(hook)
            except Exception:  # pragma: no cover
                pass
        self._hooks.clear()
        self._pressed.clear()

    def __enter__(self) -> "PushToTalk":
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.stop()

    # ---- 状态 ----

    @property
    def pressed(self) -> bool:
        return self._pressed.is_set()

    def _on_press(self, _event: Any = None) -> None:
        if not self._pressed.is_set():
            self.press_count += 1
        self._pressed.set()

    def _on_release(self, _event: Any = None) -> None:
        self._pressed.clear()
