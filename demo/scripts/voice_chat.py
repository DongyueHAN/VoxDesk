"""命令行薄壳：实际逻辑在 voxdesk_demo.cli（打包的 exe 也走同一份）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from voxdesk_demo.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
