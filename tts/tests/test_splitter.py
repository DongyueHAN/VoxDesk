"""切句是纯函数，先把它测死——不需要麦克风也不需要扬声器。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from voxdesk_tts.splitter import normalize, split  # noqa: E402


def test_merges_short_sentences_up_to_limit():
    assert split("一。二。三。") == ["一。二。三。"]


def test_splits_when_merging_would_exceed_limit():
    # 每句 5 字，两句话 10 字 > 8，必须分开
    assert split("第一句话。第二句话！", max_len=8) == ["第一句话。", "第二句话！"]


def test_keeps_closing_quote_with_sentence():
    assert split("他说“好。”然后走了。", max_len=8) == ["他说“好。”", "然后走了。"]


def test_respects_max_len_on_monster_sentence():
    text = "啊" * 200
    segments = split(text, max_len=50)
    assert all(len(s) <= 50 for s in segments)
    assert "".join(segments) == text


def test_breaks_at_comma_when_over_limit():
    text = "前半句很长很长很长很长很长很长很长，后半句也不短，还有别的"
    segments = split(text, max_len=20)
    assert all(len(s) <= 20 for s in segments)
    assert segments[0].endswith("，")


def test_does_not_break_english_words():
    text = "This is a fairly long English sentence that wraps at spaces rather than midword."
    segments = split(text, max_len=30)
    assert all(len(s) <= 30 for s in segments)
    assert all(s.endswith(" ") is False for s in segments)
    joined = "".join(segments).replace(" ", "")
    assert joined == text.replace(" ", "")


def test_empty_and_whitespace():
    assert split("") == []
    assert split("   \n\t  ") == []


def test_normalize_strips_markdown_and_collapses_spaces():
    assert normalize("  **加粗**   文字  ") == "加粗 文字"


def test_rejects_tiny_max_len():
    try:
        split("测试", max_len=3)
    except ValueError:
        return
    raise AssertionError("max_len 太小时应当抛 ValueError")
