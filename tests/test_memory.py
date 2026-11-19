"""memory.py 的单元测试（stdlib unittest，无新增依赖）。

这些用例**不接 LLM**：记忆用固定数据写入，只证明"存得对、找得回、忘得掉"。

跑法（仓库根）：
    & 'D:\\VoxDesk\\demo\\.venv\\Scripts\\python.exe' -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for candidate in (str(ROOT), str(ROOT / "audio" / "src"), str(ROOT / "tts" / "src")):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

import memory  # noqa: E402

NOW = datetime(2026, 11, 19, 12, 0, tzinfo=memory.TZ)
"""固定"现在"：2026-11-19（周四）。所有用例都用它，避免测试随真实时间漂移。"""


class StoreCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.store = memory.MemoryStore(base / "records.jsonl", base / "audit.jsonl")
        self.base = base

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def add(self, text: str, **kw):
        kw.setdefault("now", NOW)
        return self.store.add(text, **kw)


class TimeHintTests(unittest.TestCase):
    def test_relative_days(self) -> None:
        self.assertEqual(memory.parse_time_hint("昨天早饭", NOW)[:2], (date(2026, 11, 18),) * 2)
        self.assertEqual(memory.parse_time_hint("今天早饭", NOW)[:2], (date(2026, 11, 19),) * 2)
        self.assertEqual(memory.parse_time_hint("前天", NOW)[:2], (date(2026, 11, 17),) * 2)

    def test_last_week_is_a_span(self) -> None:
        start, end, _ = memory.parse_time_hint("上周做了什么", NOW)
        self.assertEqual(start.weekday(), 0)  # 周一
        self.assertEqual((end - start).days, 6)
        self.assertLess(end, date(2026, 11, 17))

    def test_explicit_date_is_stripped(self) -> None:
        start, end, cleaned = memory.parse_time_hint("2026-11-18 早饭", NOW)
        self.assertEqual(start, date(2026, 11, 18))
        self.assertEqual(start, end)
        self.assertNotIn("2026", cleaned)

    def test_no_hint(self) -> None:
        start, end, cleaned = memory.parse_time_hint("早饭吃了什么", NOW)
        self.assertIsNone(start)
        self.assertIsNone(end)
        self.assertEqual(cleaned, "早饭吃了什么")


class WriteTests(StoreCase):
    def test_add_and_persist(self) -> None:
        mem = self.add("早饭吃了包子和豆浆", kind="event", date_str="2026-11-18")
        self.assertEqual(mem.kind, "event")
        self.assertEqual(mem.date, "2026-11-18")
        self.assertEqual(mem.status, "active")

        reloaded = memory.MemoryStore(self.store.records_path, self.store.audit_path)
        again = reloaded.get(mem.id)
        self.assertIsNotNone(again)
        self.assertEqual(again.text, "早饭吃了包子和豆浆")

    def test_date_defaults_to_today_but_is_not_created_at(self) -> None:
        mem = self.add("晚饭吃了面条")
        self.assertEqual(mem.date, "2026-11-19")
        self.assertTrue(mem.created_at.startswith("2026-11-19"))

    def test_tech_text_is_rejected_by_domain_gate(self) -> None:
        with self.assertRaises(memory.MemoryStoreError):
            self.add("修复 Python 脚本报错和数据库连接")
        self.assertEqual(self.store.all(), [])

    def test_force_bypasses_domain_gate(self) -> None:
        mem = self.add("修复 Python 脚本报错", force=True)
        self.assertEqual(mem.domain, "tech")

    def test_empty_text_raises(self) -> None:
        with self.assertRaises(memory.MemoryQueryEmpty):
            self.add("   ")

    def test_similar_same_day_merges_instead_of_duplicating(self) -> None:
        first = self.add("早饭吃了包子和豆浆", date_str="2026-11-18")
        second = self.add("早饭吃了包子和豆浆", date_str="2026-11-18")
        self.assertEqual(first.id, second.id)
        self.assertEqual(len(self.store.all()), 1)
        self.assertEqual(second.hits, 1)

    def test_different_day_does_not_merge(self) -> None:
        self.add("早饭吃了包子", date_str="2026-11-18")
        self.add("早饭吃了包子", date_str="2026-11-17")
        self.assertEqual(len(self.store.all()), 2)

    def test_schedule_gets_default_expiry_next_day(self) -> None:
        mem = self.add("十点开会", kind="schedule", date_str="2026-11-20")
        self.assertEqual(mem.expires_at, "2026-11-21")

    def test_atomic_write_leaves_no_temp_file(self) -> None:
        self.add("早饭吃了包子")
        leftovers = [p for p in self.base.iterdir() if p.name.endswith(".tmp")]
        self.assertEqual(leftovers, [])

    def test_audit_log_is_appended(self) -> None:
        self.add("早饭吃了包子")
        lines = self.store.audit_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(json.loads(lines[0])["action"], "add")


class SearchTests(StoreCase):
    def test_finds_by_content(self) -> None:
        self.add("早饭吃了包子和豆浆", date_str="2026-11-18")
        hits = self.store.search("包子", now=NOW)
        self.assertTrue(hits)
        self.assertEqual(hits[0][0].text, "早饭吃了包子和豆浆")
        self.assertGreater(hits[0][1], 0)

    def test_yesterday_query_hits_yesterdays_record_only(self) -> None:
        self.add("早饭吃了包子和豆浆", date_str="2026-11-18")
        self.add("早饭吃了油条", date_str="2026-11-19")

        hits = self.store.search("昨天早饭吃了什么", now=NOW)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0][0].date, "2026-11-18")

        hits = self.store.search("今天早饭吃了什么", now=NOW)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0][0].date, "2026-11-19")

    def test_no_match_returns_empty(self) -> None:
        self.add("早饭吃了包子", date_str="2026-11-18")
        self.assertEqual(self.store.search("量子纠缠退相干", now=NOW), [])

    def test_time_window_falls_back_when_words_do_not_overlap(self) -> None:
        """记录说"会议"、查询说"安排"，没有共同词；靠时间窗兜底才对。"""
        self.add("上午十点和小王确认产品会议", kind="schedule", date_str="2026-11-20")
        hits = self.store.search("明天有什么安排", now=NOW)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0][0].date, "2026-11-20")

    def test_no_window_and_no_overlap_still_returns_empty(self) -> None:
        self.add("上午十点开会", kind="schedule", date_str="2026-11-20")
        self.assertEqual(self.store.search("有什么安排", now=NOW), [])

    def test_touch_reinforces_hit(self) -> None:
        mem = self.add("早饭吃了包子", date_str="2026-11-18")
        self.store.search("包子", now=NOW)
        self.assertEqual(self.store.get(mem.id).hits, 1)

    def test_touch_false_does_not_write(self) -> None:
        mem = self.add("早饭吃了包子", date_str="2026-11-18")
        self.store.search("包子", now=NOW, touch=False)
        self.assertEqual(self.store.get(mem.id).hits, 0)

    def test_importance_breaks_ties(self) -> None:
        self.add("午饭吃了面条", importance=5, date_str="2026-11-19")
        self.add("午饭吃了米饭", importance=1, date_str="2026-11-19")
        hits = self.store.search("午饭", now=NOW)
        self.assertEqual(hits[0][0].importance, 5)

    def test_empty_query_raises(self) -> None:
        with self.assertRaises(memory.MemoryQueryEmpty):
            self.store.search("  ", now=NOW)

    def test_k_is_clamped(self) -> None:
        for i in range(8):
            self.add(f"早饭吃了第{i}种东西", date_str="2026-11-18")
        self.assertLessEqual(len(self.store.search("早饭", 3, now=NOW)), 3)


class ForgettingTests(StoreCase):
    def test_expired_schedule_is_not_searchable(self) -> None:
        self.add("十点开会", kind="schedule", date_str="2026-11-19")
        later = NOW + timedelta(days=2)
        self.assertEqual(self.store.search("开会", now=later), [])

    def test_decay_marks_schedule_expired(self) -> None:
        mem = self.add("十点开会", kind="schedule", date_str="2026-11-19")
        counts = self.store.decay(now=NOW + timedelta(days=2))
        self.assertEqual(counts["expired"], 1)
        self.assertEqual(self.store.get(mem.id).status, "expired")

    def test_decay_archives_old_event(self) -> None:
        old = (NOW - timedelta(days=100)).date().isoformat()
        mem = self.add("吃了顿火锅", kind="event", date_str=old)
        counts = self.store.decay(now=NOW)
        self.assertEqual(counts["archived"], 1)
        self.assertEqual(self.store.get(mem.id).status, "archived")
        self.assertEqual(self.store.search("火锅", now=NOW), [])

    def test_archived_record_is_purged_after_grace(self) -> None:
        old = (NOW - timedelta(days=200)).date().isoformat()
        self.add("吃了顿火锅", kind="event", date_str=old)
        self.store.decay(now=NOW)  # 归档
        counts = self.store.decay(now=NOW + timedelta(days=memory.PURGE_AFTER_DAYS + 1))
        self.assertEqual(counts["purged"], 1)
        self.assertEqual(self.store.all(), [])

    def test_fresh_record_survives_decay(self) -> None:
        mem = self.add("早饭吃了包子", date_str="2026-11-19")
        counts = self.store.decay(now=NOW)
        self.assertEqual(counts["kept"], 1)
        self.assertEqual(self.store.get(mem.id).status, "active")

    def test_decay_score_halves_over_one_half_life(self) -> None:
        mem = self.add("吃了顿火锅", kind="event", date_str="2026-11-01")
        half = memory.HALF_LIFE_DAYS["event"]
        score_now = memory.decay_score(mem, NOW)
        score_later = memory.decay_score(mem, NOW + timedelta(days=half))
        self.assertAlmostEqual(score_now / 2, score_later, places=2)

    def test_preference_lasts_longer_than_schedule(self) -> None:
        later = NOW + timedelta(days=30)
        preference = memory.Memory(
            id="p", kind="preference", text="不吃香菜", date="2026-11-01", importance=3
        )
        schedule = memory.Memory(
            id="s", kind="schedule", text="开会", date="2026-11-01", importance=3
        )
        self.assertGreater(
            memory.decay_score(preference, later), memory.decay_score(schedule, later)
        )

    def test_forget_removes_record(self) -> None:
        mem = self.add("早饭吃了包子")
        self.assertTrue(self.store.forget(mem.id))
        self.assertIsNone(self.store.get(mem.id))
        self.assertFalse(self.store.forget(mem.id))


class ProfileTests(StoreCase):
    def test_profile_holds_preferences_and_facts_only(self) -> None:
        self.add("不吃香菜", kind="preference", date_str="2026-11-10")
        self.add("住在杭州", kind="fact", date_str="2026-11-01")
        self.add("早饭吃了包子", kind="event", date_str="2026-11-18")
        texts = [m.text for m in self.store.profile(now=NOW)]
        self.assertIn("不吃香菜", texts)
        self.assertIn("住在杭州", texts)
        self.assertNotIn("早饭吃了包子", texts)

    def test_profile_drops_archived_records(self) -> None:
        old = (NOW - timedelta(days=400)).date().isoformat()
        mem = self.add("不吃香菜", kind="preference", date_str=old)
        self.store.decay(now=NOW)
        self.assertEqual(self.store.get(mem.id).status, "archived")
        self.assertEqual(self.store.profile(now=NOW), [])

    def test_format_includes_profile_block(self) -> None:
        self.add("不吃香菜", kind="preference", date_str="2026-11-10")
        block = memory.format_for_prompt([], profile=self.store.profile(now=NOW))
        self.assertIn("稳定偏好", block)
        self.assertIn("不吃香菜", block)

    def test_format_combines_profile_and_memories(self) -> None:
        self.add("不吃香菜", kind="preference", date_str="2026-11-10")
        self.add("早饭吃了包子", date_str="2026-11-18")
        hits = self.store.search("包子", now=NOW)
        block = memory.format_for_prompt(hits, profile=self.store.profile(now=NOW))
        self.assertIn("不吃香菜", block)
        self.assertIn("早饭吃了包子", block)
        self.assertIn("2026-11-18", block)


class PromptAndStatsTests(StoreCase):
    def test_format_for_prompt_carries_dates(self) -> None:
        self.add("早饭吃了包子和豆浆", date_str="2026-11-18")
        hits = self.store.search("包子", now=NOW)
        block = memory.format_for_prompt(hits)
        self.assertIn("2026-11-18", block)
        self.assertIn("早饭吃了包子和豆浆", block)
        self.assertIn("没记过", block)

    def test_format_for_prompt_empty(self) -> None:
        self.assertEqual(memory.format_for_prompt([]), "")

    def test_stats_shape(self) -> None:
        self.add("早饭吃了包子", date_str="2026-11-18")
        info = self.store.stats(now=NOW)
        self.assertEqual(info["records"], 1)
        self.assertEqual(info["by_kind"]["event"], 1)
        self.assertEqual(info["by_status"]["active"], 1)
        self.assertGreater(info["avg_score"], 0)

    def test_corrupt_line_is_skipped(self) -> None:
        self.add("早饭吃了包子", date_str="2026-11-18")
        with self.store.records_path.open("a", encoding="utf-8") as fh:
            fh.write("{ 这不是 JSON\n")
        self.assertEqual(len(self.store.all()), 1)


if __name__ == "__main__":
    unittest.main()
