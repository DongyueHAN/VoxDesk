"""控制台编码。

Windows 下 Python 默认按 cp936 输出，中文在 PowerShell 里会变乱码。
脚本入口调用一次 `enable_utf8()` 即可。
"""

from __future__ import annotations

import sys


def enable_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
