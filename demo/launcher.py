"""打包入口：PyInstaller 从这里进来，等价于 `scripts/voice_chat.py`。

单独放一个文件是因为 PyInstaller 需要一个**脚本**作为入口，
而 `scripts/voice_chat.py` 依赖相对路径，不适合直接当 entry。
"""

from __future__ import annotations

import sys
from pathlib import Path

# 源码运行时把 src 加进 path；打包后 PyInstaller 已收进去，不需要
_SRC = Path(__file__).resolve().parent / "src"
if _SRC.exists() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from voxdesk_demo.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
