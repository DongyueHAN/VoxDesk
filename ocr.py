"""IF-09 · OCR 引擎（`CMP-13`，工作包 WP2）。

契约见 `docs/system/docs/03-architecture.md` §3.2 `IF-09`：
`Recognize(image, source) -> TextBlock[]`，三来源归一（屏幕框选 / 摄像头 / 图片文件），
返回**带置信度与版面坐标**的文本块；低置信度块必须能被上层标记（`REQ-F-096`）。

当前状态：**只有契约，没有引擎**。引擎选型属 `docs/system/docs/06-tech-stack.md` 的待评估项，
排期卡在 `DEC-007`（三来源优先级）。调用 `recognize()` 会抛 `OcrUnavailable`，
路由 `/api/ocr` 据此返回 501，而不是假装成功。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Source = Literal["screen", "camera", "file"]

SOURCES: tuple[Source, ...] = ("screen", "camera", "file")

CONFIDENCE_WARN = 0.60
"""低于此值的块应由界面标黄并允许用户改完再提交（`REQ-F-096`）。"""


class OcrUnavailable(RuntimeError):
    """OCR 引擎尚未接入。"""


@dataclass(frozen=True)
class TextBlock:
    """一个识别出的文本块。

    `bbox` 为 `(x1, y1, x2, y2)`，单位是**原图像素**；版面与表格保序靠它还原（`REQ-F-093`）。
    """

    text: str
    confidence: float
    bbox: tuple[int, int, int, int]

    @property
    def low_confidence(self) -> bool:
        return self.confidence < CONFIDENCE_WARN


def recognize(image: bytes, source: Source = "file") -> list[TextBlock]:
    """把一张图识别成文本块。**当前未实现。**"""
    if source not in SOURCES:
        raise ValueError(f"unknown OCR source: {source!r}; expected one of {SOURCES}")
    raise OcrUnavailable(
        "OCR 引擎未接入：先定 DEC-007（三来源优先级）与 06 技术栈的 OCR 选型，"
        "再实现本函数；契约见 docs/system/docs/03-architecture.md §3.2 IF-09。"
    )


def contract() -> dict:
    """给 `/api/ocr` 的健康探测用：说明这条接口的现状。"""
    return {
        "interface": "IF-09",
        "component": "CMP-13",
        "work_package": "WP2",
        "available": False,
        "sources": list(SOURCES),
        "confidence_warn": CONFIDENCE_WARN,
        "blocked_by": "DEC-007",
    }
