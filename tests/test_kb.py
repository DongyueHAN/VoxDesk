"""kb.py 的单元测试（stdlib unittest，无新增依赖）。

跑法（仓库根）：
    & 'D:\\VoxDesk\\demo\\.venv\\Scripts\\python.exe' -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for candidate in (str(ROOT), str(ROOT / "audio" / "src"), str(ROOT / "tts" / "src")):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

import kb  # noqa: E402


class CorpusCase(unittest.TestCase):
    """给每个用例一个临时语料目录 + 索引文件。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.root = base / "corpus"
        self.root.mkdir()
        self.index_file = base / "index.json"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def write(self, rel: str, text: str) -> Path:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def build(self, **kw) -> dict:
        return kb.build_index(self.root, self.index_file, **kw)


class ChunkTextTests(unittest.TestCase):
    def test_records_line_ranges(self) -> None:
        text = "第一段\n第二行\n\n第三段\n"
        chunks = kb.chunk_text(text)
        self.assertEqual(len(chunks), 1)
        start, end, body = chunks[0]
        self.assertEqual((start, end), (1, 4))
        self.assertIn("第三段", body)

    def test_splits_when_over_budget(self) -> None:
        text = ("甲" * 300) + "\n\n" + ("乙" * 300) + "\n"
        chunks = kb.chunk_text(text, max_chars=480)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0][:2], (1, 1))
        self.assertEqual(chunks[1][:2], (3, 3))

    def test_blank_lines_only_is_empty(self) -> None:
        self.assertEqual(kb.chunk_text("\n\n\n"), [])


class TokenizeTests(unittest.TestCase):
    def test_cjk_bigrams(self) -> None:
        self.assertEqual(kb.tokenize("检索增强"), ["检索", "索增", "增强"])

    def test_single_cjk_char_kept(self) -> None:
        self.assertEqual(kb.tokenize("我"), ["我"])

    def test_latin_words_and_mixed(self) -> None:
        toks = kb.tokenize("RAG 与 BM25")
        self.assertIn("rag", toks)
        self.assertIn("bm25", toks)
        self.assertIn("与", toks)

    def test_punctuation_only(self) -> None:
        self.assertEqual(kb.tokenize("，。！"), [])


class BuildIndexTests(CorpusCase):
    def test_counts_documents_and_chunks(self) -> None:
        self.write("a.md", "甲" * 300 + "\n\n" + "乙" * 300)
        self.write("b.txt", "一段英文 retrieval augmented generation")
        result = self.build()
        self.assertTrue(result["ok"])
        self.assertEqual(result["documents"], 2)
        self.assertEqual(result["added"], 2)
        self.assertEqual(result["chunks"], 3)
        self.assertTrue(self.index_file.exists())

    def test_excludes_hidden_dirs_and_non_text(self) -> None:
        self.write("keep.md", "保留")
        self.write(".obsidian/secret.md", "不该进索引")
        self.write("notes/.trash/old.md", "也不该进")
        self.write("image.png", "not markdown")
        result = self.build()
        self.assertEqual(result["documents"], 1)
        index = json.loads(self.index_file.read_text(encoding="utf-8"))
        self.assertEqual([d["path"] for d in index["docs"]], ["keep.md"])

    def test_missing_corpus_raises(self) -> None:
        with self.assertRaises(kb.CorpusMissing):
            kb.build_index(self.root / "nope", self.index_file)

    def test_index_is_atomic_and_versioned(self) -> None:
        self.write("a.md", "内容")
        self.build()
        index = json.loads(self.index_file.read_text(encoding="utf-8"))
        self.assertEqual(index["version"], kb.INDEX_VERSION)
        self.assertEqual(index["root"], str(self.root.resolve()))
        self.assertEqual(list(self.index_file.parent.glob("*.tmp")), [])


class IncrementalTests(CorpusCase):
    def test_second_build_reuses_everything(self) -> None:
        self.write("a.md", "内容甲")
        self.write("b.md", "内容乙")
        self.build()
        again = self.build()
        self.assertEqual(again["added"], 0)
        self.assertEqual(again["updated"], 0)
        self.assertEqual(again["reused"], 2)

    def test_single_file_change_updates_only_that_file(self) -> None:
        self.write("a.md", "内容甲")
        self.write("b.md", "内容乙")
        self.build()
        import os
        import time

        path = self.root / "a.md"
        path.write_text("内容甲改了", encoding="utf-8")
        os.utime(path, (time.time() + 5, time.time() + 5))
        again = self.build()
        self.assertEqual(again["updated"], 1)
        self.assertEqual(again["reused"], 1)
        self.assertEqual(again["added"], 0)

    def test_same_content_touch_is_reused_not_rebuilt(self) -> None:
        import os
        import time

        path = self.write("a.md", "内容甲")
        self.build()
        os.utime(path, (time.time() + 5, time.time() + 5))
        again = self.build()
        self.assertEqual(again["updated"], 0)
        self.assertEqual(again["reused"], 1)

    def test_removed_file_counted_and_dropped(self) -> None:
        self.write("a.md", "内容甲")
        gone = self.write("b.md", "内容乙")
        self.build()
        gone.unlink()
        again = self.build()
        self.assertEqual(again["removed"], 1)
        self.assertEqual(again["documents"], 1)

    def test_force_rebuilds_all(self) -> None:
        self.write("a.md", "内容甲")
        self.build()
        again = self.build(force=True)
        self.assertEqual(again["reused"], 0)
        self.assertEqual(again["added"], 1)


class SearchTests(CorpusCase):
    def test_finds_chinese_and_reports_lines(self) -> None:
        self.write("kb.md", ("甲" * 300) + "\n\n" + ("检索增强" * 75) + "\n")
        self.write("other.md", "无关内容")
        self.build()
        hits = kb.search("检索增强", 5, self.index_file)
        self.assertTrue(hits)
        self.assertEqual(hits[0].path, "kb.md")
        self.assertEqual((hits[0].start_line, hits[0].end_line), (3, 3))
        self.assertEqual(hits[0].ref(), "kb.md:3-3")
        self.assertIn("检索", hits[0].snippet)

    def test_finds_latin(self) -> None:
        self.write("en.md", "Retrieval augmented generation improves recall")
        self.build()
        hits = kb.search("augmented", 5, self.index_file)
        self.assertEqual(hits[0].path, "en.md")

    def test_no_match_returns_empty_not_error(self) -> None:
        self.write("a.md", "内容甲")
        self.build()
        self.assertEqual(kb.search("量子纠缠退相干", 5, self.index_file), [])

    def test_incidental_common_token_is_not_a_hit(self) -> None:
        """只共享一个常见词（采样）不算命中，否则会违反 REQ-F-089 的拒答要求。"""
        self.write("audio.md", "音频需要 16k 采样率，否则进入 ASR 前要重采样。")
        self.build()
        self.assertEqual(kb.search("量子纠缠玻色采样", 5, self.index_file), [])

    def test_partial_match_hits_when_coverage_enough(self) -> None:
        self.write("a.md", "接口契约以代码为准，改字段要同步前端。")
        self.build()
        hits = kb.search("接口契约", 5, self.index_file)
        self.assertTrue(hits)
        self.assertEqual(hits[0].path, "a.md")

    def test_empty_query_raises(self) -> None:
        with self.assertRaises(kb.QueryInvalid):
            kb.search("   ", 5, self.index_file)

    def test_missing_index_raises(self) -> None:
        with self.assertRaises(kb.IndexMissing):
            kb.search("任意", 5, self.index_file)

    def test_k_is_clamped_and_ordered(self) -> None:
        for i in range(5):
            self.write(f"d{i}.md", "检索" * 50 + f"编号{i}")
        self.build()
        hits = kb.search("检索", 3, self.index_file)
        self.assertLessEqual(len(hits), 3)
        scores = [h.score for h in hits]
        self.assertEqual(scores, sorted(scores, reverse=True))


class StatsAndSafetyTests(CorpusCase):
    def test_stats_reports_counts(self) -> None:
        self.write("a.md", "内容甲")
        self.build()
        info = kb.stats(self.index_file)
        self.assertEqual(info["documents"], 1)
        self.assertGreater(info["index_bytes"], 0)

    def test_inside_rejects_parent_escape(self) -> None:
        outside = self.root.parent / "outside.md"
        self.assertFalse(kb._inside(self.root, outside))
        self.assertTrue(kb._inside(self.root, self.root / "a.md"))

    def test_iter_skips_files_over_size_cap(self) -> None:
        big = self.root / "big.md"
        big.write_bytes(b"x" * (kb.MAX_FILE_BYTES + 1))
        self.write("small.md", "小")
        names = [p.name for p in kb.iter_documents(self.root)]
        self.assertEqual(names, ["small.md"])


if __name__ == "__main__":
    unittest.main()
