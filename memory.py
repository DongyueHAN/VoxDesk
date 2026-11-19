"""长期记忆（记忆层内核）：日常生活域的持久记忆 + 时间衰减遗忘。

与 `CMP-12` 知识库（`kb.py`）的区别：知识库索引**静态文档**，这里存的是
**应用自己在对话中长出来的事实**。分离设计的原因见 `docs/impl/DECISIONS.md` ADR-0010。

三条硬规则：

1. **`date` 是事件发生日，不是写入时间**。回答"昨天早饭吃了什么"必须有这个字段，
   否则检索一定把旧事当成今天。
2. **只收日常生活域**。日程、饮食、健康、家务、家庭、社交、偏好；技术问题进不来
   （`classify_domain`）。P3 接 LLM 抽取后，这条规则降级为兜底。
3. **会忘**。`decay_score = 重要度 × 0.5^(龄期/半衰期) × (1 + 0.2·ln(1+命中))`；
   日程 7 天、事件 30 天、事实 90 天、偏好 180 天、摘要 45 天。
   低于 `ARCHIVE_BELOW` 转归档，归档 90 天未被用到才真删；日程另有 `expires_at` 硬过期。

存储：`data/memory/records.jsonl`（一行一条，整体原子改写）+ `audit.jsonl`（只追加）。
两个文件都在 `data/` 下，已被 gitignore。
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import uuid
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import kb
import paths

TZ = timezone(timedelta(hours=8))

KINDS = ("event", "schedule", "preference", "fact", "summary")
STATUSES = ("active", "archived", "expired")

HALF_LIFE_DAYS = {
    "schedule": 7,
    "event": 30,
    "fact": 90,
    "preference": 180,
    "summary": 45,
}
"""半衰期：过这么久，这条记忆的分数减半。日程最短，偏好最长。"""

ARCHIVE_BELOW = 0.15
"""低于此分数转归档（不再注入 prompt，但可恢复）。"""

PURGE_AFTER_DAYS = 90
"""归档/过期后这么久没被用到，才真正删除。"""

ALWAYS_ON_KINDS = ("preference", "fact")
"""语义记忆（稳定偏好与事实）不走检索，**常驻注入** prompt。

原因："不吃香菜"永远等不到一个含"香菜"的查询，而它几乎对所有"吃什么"的问题都相关。
这类记忆数量少、句子短，常驻的成本低于漏召回的代价。
"""

DEFAULT_K = 6
MAX_K = 20
MAX_PROFILE = 8
MIN_COVERAGE = 0.4
MAX_TEXT_CHARS = 240
HITS_BOOST = 0.2

LIFE_HINTS = (
    "早", "午", "晚", "饭", "吃", "喝", "睡", "起床", "上班", "下班", "加班",
    "会议", "开会", "约", "见", "生日", "医院", "看病", "药", "复诊", "体检",
    "家", "妈", "爸", "女儿", "儿子", "孩子", "老婆", "老公", "朋友", "同事",
    "喜欢", "讨厌", "不吃", "爱吃", "习惯", "买菜", "超市", "快递", "取件",
    "天气", "下雨", "运动", "跑步", "健身", "电影", "旅行", "机票", "酒店", "票",
)
"""日常生活域的正向信号。"""

TECH_HINTS = (
    "代码", "函数", "报错", "编译", "部署", "接口", "数据库", "服务器", "重构",
    "单测", "测试", "调试", "依赖", "脚本", "仓库", "分支", "提交", "合并",
    "模型", "提示词", "索引", "检索", "算法", "架构", "性能", "内存泄漏",
    "python", "docker", "git", "api", "bug", "sql", "json", "http",
)
"""技术域信号；命中多于生活信号时拒绝入库。"""


class MemoryStoreError(RuntimeError):
    status = 500


class MemoryQueryEmpty(MemoryStoreError):
    """查询或记忆内容为空。"""

    status = 400


# --------------------------------------------------------------------- 时间


def _now(value=None) -> datetime:
    """把 None / datetime / date / 字符串统一成本地时区的 datetime。"""
    if value is None:
        return datetime.now(TZ)
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=TZ)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=TZ)
    if isinstance(value, str):
        parsed = _parse_dt(value)
        if parsed:
            return parsed
    raise TypeError(f"无法解析时间：{value!r}")


def _parse_dt(text) -> datetime | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d",
    ):
        try:
            parsed = datetime.strptime(raw, fmt)
        except ValueError:
            continue
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=TZ)
    return None


def _day(text) -> date | None:
    parsed = _parse_dt(text)
    return parsed.date() if parsed else None


_RELATIVE_DAYS = (
    ("今天", 0),
    ("今日", 0),
    ("昨天", -1),
    ("昨日", -1),
    ("前天", -2),
    ("明天", 1),
    ("后天", 2),
)
_RELATIVE_WEEKS = (("本周", 0), ("这周", 0), ("上周", -1))
_EXPLICIT_DATE = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")
_MONTH_DAY = re.compile(r"(\d{1,2})月(\d{1,2})[日号]?")


def parse_time_hint(query: str, now=None) -> tuple[date | None, date | None, str]:
    """把查询里的时间词变成日期区间，并把时间词从查询里剥掉。

    必须剥掉：否则"昨天"这种词会稀释词覆盖率，让真正的内容词匹配不上。
    返回 `(起始日, 结束日, 去掉时间词后的查询)`；没有时间词时区间为 `None`。
    """
    moment = _now(now)
    text = str(query or "")
    start: date | None = None
    end: date | None = None

    for word, delta in _RELATIVE_DAYS:
        if word in text:
            start = end = moment.date() + timedelta(days=delta)
            text = text.replace(word, " ")
            break

    if start is None:
        for word, delta in _RELATIVE_WEEKS:
            if word in text:
                monday = moment.date() - timedelta(days=moment.weekday())
                start = monday + timedelta(weeks=delta)
                end = start + timedelta(days=6)
                text = text.replace(word, " ")
                break

    if start is None:
        found = _EXPLICIT_DATE.search(text)
        if found:
            try:
                start = end = date(
                    int(found.group(1)), int(found.group(2)), int(found.group(3))
                )
                text = text[: found.start()] + " " + text[found.end() :]
            except ValueError:
                pass

    if start is None:
        found = _MONTH_DAY.search(text)
        if found:
            try:
                start = end = date(moment.year, int(found.group(1)), int(found.group(2)))
                text = text[: found.start()] + " " + text[found.end() :]
            except ValueError:
                pass

    return start, end, " ".join(text.split())


# --------------------------------------------------------------------- 领域


def classify_domain(text: str) -> str:
    """粗判是否属于日常生活域。技术信号多于生活信号就判 `tech`。

    这是**规则兜底**：P3 接 LLM 抽取后由模型打 `domain`，本函数只做交叉校验。
    """
    low = str(text or "").lower()
    life = sum(1 for word in LIFE_HINTS if word in low)
    tech = sum(1 for word in TECH_HINTS if word in low)
    return "tech" if tech > life else "life"


# --------------------------------------------------------------------- 记忆


@dataclass
class Memory:
    """一条记忆。`date` 是**事件发生日**，与 `created_at`（写入时间）不同。"""

    id: str
    kind: str
    text: str
    date: str
    subject: str = ""
    importance: int = 3
    source: dict = field(default_factory=dict)
    created_at: str = ""
    last_used_at: str | None = None
    hits: int = 0
    expires_at: str | None = None
    status: str = "active"
    archived_at: str | None = None
    domain: str = "life"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Memory:
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


def decay_score(mem: Memory, now=None) -> float:
    """重要度 × 时间衰减 × 命中强化。日程/事件/事实/偏好各有半衰期。"""
    moment = _now(now)
    stamps = [d for d in (_day(mem.date), _day(mem.last_used_at)) if d]
    if not stamps:
        return 0.0
    age = max(0, (moment.date() - max(stamps)).days)
    half = HALF_LIFE_DAYS.get(mem.kind, 30)
    importance = max(1, min(5, int(mem.importance or 3))) / 5
    return round(importance * 0.5 ** (age / half) * (1 + HITS_BOOST * math.log1p(mem.hits)), 4)


def is_expired(mem: Memory, now=None) -> bool:
    due = _parse_dt(mem.expires_at)
    return bool(due and due <= _now(now))


def default_expiry(kind: str, day: date) -> str | None:
    """日程默认在事件次日 0 点失效：过期日程绝不能再当有效事实注入。"""
    if kind != "schedule":
        return None
    return (day + timedelta(days=1)).isoformat()


def format_for_prompt(
    hits: list[tuple[Memory, float]],
    *,
    profile: list[Memory] | None = None,
    limit: int = DEFAULT_K,
) -> str:
    """渲染成注入 system prompt 的两块：常驻偏好/事实 + 本轮回溯到的记忆。

    记忆块**每条都带日期**，否则模型会把旧事当成今天。
    """
    blocks: list[str] = []
    if profile:
        lines = ["【关于用户的稳定偏好与事实】与当前问题相关时参考，不必主动复述。"]
        for mem in profile[:MAX_PROFILE]:
            lines.append(f"- {mem.text}")
        blocks.append("\n".join(lines))
    if hits:
        lines = ["【关于用户的记忆】只在和当前问题相关时使用；日期是事件发生日，"]
        lines.append("不要把旧事当成今天的事；记忆里没有的事就说没记过，不要编。")
        for mem, _score in hits[:limit]:
            subject = f"{mem.subject}：" if mem.subject else ""
            lines.append(f"- {mem.date}｜{mem.kind}｜{subject}{mem.text}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


# --------------------------------------------------------------------- 存储


class MemoryStore:
    """JSONL 存储。整体原子改写，规模是几百条量级，不做数据库。"""

    def __init__(self, records_path: Path | str | None = None, audit_path: Path | str | None = None):
        if records_path:
            self.records_path = Path(records_path)
            default_audit = self.records_path.parent / "audit.jsonl"
        else:
            self.records_path = paths.MEMORY_DIR / "records.jsonl"
            default_audit = paths.MEMORY_DIR / "audit.jsonl"
        self.audit_path = Path(audit_path) if audit_path else default_audit
        self.records_path.parent.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------------- 基础

    def _load(self) -> list[Memory]:
        if not self.records_path.exists():
            return []
        out: list[Memory] = []
        try:
            text = self.records_path.read_text(encoding="utf-8")
        except OSError:
            return []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict) and data.get("id"):
                out.append(Memory.from_dict(data))
        return out

    def _save(self, records: list[Memory]) -> None:
        payload = "\n".join(json.dumps(r.to_dict(), ensure_ascii=False) for r in records)
        tmp = self.records_path.with_name(f".{self.records_path.name}.{os.getpid()}.tmp")
        try:
            tmp.write_text(payload + ("\n" if payload else ""), encoding="utf-8")
            os.replace(tmp, self.records_path)
        finally:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass

    def _audit(self, action: str, mem: Memory, reason: str = "", now=None) -> None:
        row = {
            "at": _now(now).isoformat(timespec="seconds"),
            "action": action,
            "id": mem.id,
            "kind": mem.kind,
            "date": mem.date,
            "text": mem.text[:80],
            "reason": reason,
        }
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        with self.audit_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    @staticmethod
    def _jaccard(a: str, b: str) -> float:
        left, right = set(kb.tokenize(a)), set(kb.tokenize(b))
        if not left or not right:
            return 0.0
        return len(left & right) / len(left | right)

    # ---------------------------------------------------------------- 写入

    def add(
        self,
        text: str,
        *,
        kind: str = "event",
        date_str: str | None = None,
        subject: str = "",
        importance: int = 3,
        source: dict | None = None,
        expires_at: str | None = None,
        force: bool = False,
        now=None,
    ) -> Memory:
        """写入一条记忆。同一天、同类、内容高度相似时合并而不是新增。"""
        moment = _now(now)
        body = " ".join(str(text or "").split())
        if not body:
            raise MemoryQueryEmpty("记忆内容为空")
        body = body[:MAX_TEXT_CHARS]
        kind = kind if kind in KINDS else "event"

        domain = classify_domain(body)
        if domain != "life" and not force:
            raise MemoryStoreError(f"不属于日常生活域（判定 {domain}）：{body[:40]}")

        day = _day(date_str) if date_str else moment.date()
        if day is None:
            raise MemoryQueryEmpty(f"date 无法解析：{date_str!r}")

        records = self._load()
        for existing in records:
            if (
                existing.kind == kind
                and existing.date == day.isoformat()
                and existing.status == "active"
                and self._jaccard(existing.text, body) >= 0.6
            ):
                if len(body) >= len(existing.text):
                    existing.text = body
                existing.importance = max(int(existing.importance), int(importance))
                existing.hits += 1
                existing.last_used_at = moment.isoformat(timespec="seconds")
                if source:
                    existing.source = source
                if expires_at:
                    existing.expires_at = expires_at
                self._save(records)
                self._audit("merge", existing, "同一天同类相似内容", moment)
                return existing

        mem = Memory(
            id=uuid.uuid4().hex[:16],
            kind=kind,
            text=body,
            date=day.isoformat(),
            subject=str(subject or "")[:40],
            importance=max(1, min(5, int(importance))),
            source=dict(source or {}),
            created_at=moment.isoformat(timespec="seconds"),
            expires_at=expires_at or default_expiry(kind, day),
            domain=domain,
        )
        records.append(mem)
        self._save(records)
        self._audit("add", mem, "", moment)
        return mem

    def forget(self, mem_id: str, *, now=None) -> bool:
        records = self._load()
        kept = [r for r in records if r.id != mem_id]
        if len(kept) == len(records):
            return False
        dropped = next(r for r in records if r.id == mem_id)
        self._save(kept)
        self._audit("forget", dropped, "手动删除", now)
        return True

    # ---------------------------------------------------------------- 检索

    def search(
        self,
        query: str,
        k: int = DEFAULT_K,
        *,
        now=None,
        touch: bool = True,
    ) -> list[tuple[Memory, float]]:
        """检索记忆：时间过滤优先，再按内容打分并乘上衰减分。

        命中会被"强化"（`hits+1`、刷新 `last_used_at`），这让常用的记忆活得更久。
        查不到返回空列表——上层据此说"没记过"，不要编（`REQ-F-089`）。
        """
        moment = _now(now)
        raw = " ".join(str(query or "").split())
        if not raw:
            raise MemoryQueryEmpty("query 为空")
        start, end, cleaned = parse_time_hint(raw, moment)
        tokens = set(kb.tokenize(cleaned)) if cleaned else set()
        try:
            limit = max(1, min(MAX_K, int(k)))
        except (TypeError, ValueError):
            limit = DEFAULT_K

        records = [r for r in self._load() if r.status == "active" and not is_expired(r, moment)]
        if start and end:
            records = [r for r in records if start <= (_day(r.date) or moment.date()) <= end]

        if tokens:
            needed = max(1, math.ceil(MIN_COVERAGE * len(tokens)))
            df: Counter = Counter()
            candidates: list[tuple[Memory, Counter, int]] = []
            for record in records:
                tf = Counter(kb.tokenize(record.text))
                hit = tokens & tf.keys()
                if hit:
                    df.update(hit)
                if len(hit) >= needed:
                    candidates.append((record, tf, len(hit)))
            if not candidates:
                # 词不重叠但给了时间窗：按时间兜底。
                # "明天有什么安排"与记录"十点开会"没有共同词，靠内容匹配永远打不中，
                # 而"那一天有哪些事"本身就是时间问题。
                if start and end:
                    ranked = [(r, decay_score(r, moment)) for r in records]
                else:
                    return []
            else:
                total = len(records) or 1
                ranked = []
                for record, tf, _ in candidates:
                    base = 0.0
                    for tok in tokens & tf.keys():
                        idf = math.log(1 + (total - df[tok] + 0.5) / (df[tok] + 0.5))
                        base += idf * (tf[tok] * 2.2) / (tf[tok] + 1.2)
                    ranked.append((record, round(base * decay_score(record, moment), 4)))
        else:
            ranked = [(r, decay_score(r, moment)) for r in records]

        ranked.sort(key=lambda pair: (-pair[1], pair[0].date, pair[0].id))
        top = ranked[:limit]

        if touch and top:
            ids = {m.id for m, _ in top}
            stamp = moment.isoformat(timespec="seconds")
            refreshed = self._load()
            for record in refreshed:
                if record.id in ids:
                    record.hits += 1
                    record.last_used_at = stamp
            self._save(refreshed)
        return top

    # ---------------------------------------------------------------- 遗忘

    def decay(self, *, now=None, purge: bool = True) -> dict:
        """执行遗忘：硬过期 → 衰减归档 → 归档满期清除。"""
        moment = _now(now)
        records = self._load()
        counts = {"expired": 0, "archived": 0, "purged": 0, "kept": 0}
        kept: list[Memory] = []

        for record in records:
            if record.status == "active" and is_expired(record, moment):
                record.status = "expired"
                record.archived_at = moment.isoformat(timespec="seconds")
                counts["expired"] += 1
                self._audit("expire", record, "expires_at 到点", moment)
            elif record.status == "active" and decay_score(record, moment) < ARCHIVE_BELOW:
                record.status = "archived"
                record.archived_at = moment.isoformat(timespec="seconds")
                counts["archived"] += 1
                self._audit("archive", record, f"分数低于 {ARCHIVE_BELOW}", moment)

            if purge and record.status in ("archived", "expired"):
                since = _parse_dt(record.archived_at)
                if since and (moment - since).days >= PURGE_AFTER_DAYS:
                    counts["purged"] += 1
                    self._audit("purge", record, f"归档满 {PURGE_AFTER_DAYS} 天", moment)
                    continue

            kept.append(record)
            if record.status == "active":
                counts["kept"] += 1

        self._save(kept)
        return counts

    # ---------------------------------------------------------------- 查询

    def get(self, mem_id: str) -> Memory | None:
        for record in self._load():
            if record.id == mem_id:
                return record
        return None

    def profile(self, limit: int = MAX_PROFILE, *, now=None) -> list[Memory]:
        """常驻注入的语义记忆：稳定偏好与事实，按衰减分排序取前 N 条。"""
        moment = _now(now)
        records = [
            r
            for r in self._load()
            if r.status == "active"
            and not is_expired(r, moment)
            and r.kind in ALWAYS_ON_KINDS
        ]
        records.sort(key=lambda r: (-decay_score(r, moment), r.date, r.id))
        return records[: max(1, min(MAX_PROFILE, int(limit or MAX_PROFILE)))]

    def all(self, status: str | None = None) -> list[Memory]:
        records = self._load()
        return [r for r in records if status is None or r.status == status]

    def stats(self, *, now=None) -> dict:
        moment = _now(now)
        records = self._load()
        active = [r for r in records if r.status == "active"]
        return {
            "ok": True,
            "records": len(records),
            "by_status": dict(Counter(r.status for r in records)),
            "by_kind": dict(Counter(r.kind for r in records)),
            "active": len(active),
            "avg_score": round(sum(decay_score(r, moment) for r in active) / len(active), 3)
            if active
            else 0.0,
            "next_expiry": min((r.expires_at for r in active if r.expires_at), default=None),
            "oldest_date": min((r.date for r in records), default=None),
            "records_path": self.records_path.as_posix(),
        }


# --------------------------------------------------------------------- CLI


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass

    ap = argparse.ArgumentParser(description="长期记忆：写入 / 检索 / 遗忘（日常生活域）")
    ap.add_argument("--records", help="records.jsonl 路径（默认 data/memory/）")
    ap.add_argument("--add", metavar="TEXT", help="写入一条记忆")
    ap.add_argument("--kind", default="event", choices=list(KINDS))
    ap.add_argument("--date", dest="date_str", help="事件发生日 YYYY-MM-DD（默认今天）")
    ap.add_argument("--subject", default="", help="主体，如“用户”或人名")
    ap.add_argument("--importance", type=int, default=3, help="重要度 1-5")
    ap.add_argument("--expires", help="硬过期时间，如 2026-11-20T10:00")
    ap.add_argument("--force", action="store_true", help="跳过日常生活域过滤")
    ap.add_argument("--search", metavar="QUERY", help="检索（支持 昨天/上周/2026-11-18）")
    ap.add_argument("-k", type=int, default=DEFAULT_K)
    ap.add_argument("--profile", action="store_true", help="只看常驻的偏好与事实")
    ap.add_argument("--decay", action="store_true", help="执行遗忘")
    ap.add_argument("--forget", metavar="ID", help="手动删除一条记忆")
    ap.add_argument("--stats", action="store_true")
    args = ap.parse_args(argv)

    store = MemoryStore(args.records)
    try:
        if args.add:
            mem = store.add(
                args.add,
                kind=args.kind,
                date_str=args.date_str,
                subject=args.subject,
                importance=args.importance,
                expires_at=args.expires,
                force=args.force,
            )
            print(json.dumps(mem.to_dict(), ensure_ascii=False, indent=2))
        if args.forget:
            print("已删除" if store.forget(args.forget) else "没有这条记录")
        if args.decay:
            print(json.dumps(store.decay(), ensure_ascii=False))
        if args.search:
            hits = store.search(args.search, args.k)
            block = format_for_prompt(hits, profile=store.profile())
            print(block or "没有记过（不要编造，按 REQ-F-089 明说）")
        if args.profile:
            print(format_for_prompt([], profile=store.profile()) or "（没有常驻偏好/事实）")
        if args.stats or not (
            args.add or args.search or args.decay or args.forget or args.profile
        ):
            print(json.dumps(store.stats(), ensure_ascii=False, indent=2))
    except MemoryStoreError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
