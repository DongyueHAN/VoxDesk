"""CMP-12 · 知识接入：本地 Markdown 语料的索引与检索（`IF-07`）。

契约见 `docs/system/docs/03-architecture.md` §3.2 `IF-07`：
`Search(query, k) -> Chunk[]`，返回值**必须带来源路径与行号**，调用方据此引用原文
（`REQ-F-088`）；检索不到就返回空列表，由上层明说"没记过"，不许编造（`REQ-F-089`）。

选型见 `docs/impl/DECISIONS.md` ADR-0009：
纯标准库、JSON 索引、CJK 双字切分；不依赖 `rg` 二进制，也不引入分词模型；
向量检索留到第二版（`ADR-0009` 的"先全文、后混合"）。

语料根目录优先级：`VOXDESK_KB_DIR` 环境变量 > 本仓 `docs/`。
索引落在 `data/kb/index.json`（`data/` 已 gitignore），**语料原文不进仓库**。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import paths

INDEX_VERSION = 1
CHUNK_CHARS = 480
"""一个片段的字符上限：够模型读，又不至于把整篇塞进 prompt。"""

MAX_FILE_BYTES = 2 * 1024 * 1024
DEFAULT_K = 5
MAX_K = 50
SNIPPET_CHARS = 160
MIN_COVERAGE = 0.4
"""命中片段必须覆盖查询词的多少比例。

纯 OR 会让"量子纠缠玻色采样"靠常见词"采样"误命中任何讲采样率的文档，
而 `REQ-F-089` 要求检索不到就明说没记过。用覆盖率门槛把这类偶然命中挡掉。
"""

SUFFIXES = frozenset({".md", ".txt"})
EXCLUDE_DIRS = frozenset({".obsidian", ".trash", ".git", "__pycache__", "node_modules"})

_CJK_RUN = re.compile(r"[\u4e00-\u9fff]+")
_LATIN_WORD = re.compile(r"[a-z0-9_]{2,}")


class KbError(RuntimeError):
    status = 500


class CorpusMissing(KbError):
    """语料目录不存在或不是目录。"""

    status = 409


class IndexMissing(KbError):
    """索引还没建。"""

    status = 409


class QueryInvalid(KbError):
    """查询为空或没有可检索的词。"""

    status = 400


@dataclass(frozen=True)
class Chunk:
    """一个检索命中。`path` 相对语料根，`start_line`/`end_line` 从 1 开始。"""

    path: str
    start_line: int
    end_line: int
    text: str
    score: float = 0.0
    snippet: str = ""

    def ref(self) -> str:
        """`笔记路径:起-止` 的引用形式，回答里直接贴这个。"""
        return f"{self.path}:{self.start_line}-{self.end_line}"


# --------------------------------------------------------------------- 路径


def corpus_dir() -> Path:
    """语料根：环境变量 > 本仓 `docs/`。"""
    raw = os.environ.get("VOXDESK_KB_DIR")
    return (Path(raw).expanduser() if raw else (paths.ROOT / "docs")).resolve()


def index_path() -> Path:
    return paths.KB_INDEX_DIR / "index.json"


def _inside(root: Path, target: Path) -> bool:
    try:
        target.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def iter_documents(root: Path):
    """按白名单遍历语料：只收 `.md`/`.txt`，跳过隐藏目录、附件与大文件。

    用 `os.scandir` 而不是 `Path.resolve()` 逐个校验：10k 篇时后者要额外
    2 万次文件系统调用，是增量重建超预算的主因。目录是走进去的，越界只可能
    来自**符号链接**，所以只对链接做包含性检查。
    """
    root = root.resolve()
    stack = [str(root)]
    while stack:
        current = stack.pop()
        try:
            entries = list(os.scandir(current))
        except OSError:
            continue
        dirs: list[str] = []
        for entry in entries:
            try:
                if entry.is_symlink():
                    if not _inside(root, Path(entry.path)):
                        continue
                    if entry.is_dir():
                        continue
                if entry.is_dir(follow_symlinks=False):
                    name = entry.name
                    if name not in EXCLUDE_DIRS and not name.startswith("."):
                        dirs.append(entry.path)
                    continue
                if not entry.is_file(follow_symlinks=False):
                    continue
                path = Path(entry.path)
                if path.suffix.lower() not in SUFFIXES:
                    continue
                if entry.stat(follow_symlinks=False).st_size > MAX_FILE_BYTES:
                    continue
            except OSError:
                continue
            yield path
        stack.extend(sorted(dirs, reverse=True))


# --------------------------------------------------------------------- 切块


def chunk_text(text: str, max_chars: int = CHUNK_CHARS) -> list[tuple[int, int, str]]:
    """按空行切段、再合并到 `max_chars`，同时记下每块的行号区间。

    返回 `[(start_line, end_line, text)]`，行号 1-based，包含首尾。
    """
    lines = text.splitlines()
    blocks: list[tuple[int, int, str]] = []
    start: int | None = None
    buf: list[str] = []
    for lineno, line in enumerate(lines, 1):
        if line.strip():
            if start is None:
                start = lineno
            buf.append(line)
        elif buf:
            blocks.append((start or lineno, lineno - 1, "\n".join(buf)))
            buf, start = [], None
    if buf:
        blocks.append((start or 1, len(lines), "\n".join(buf)))

    chunks: list[tuple[int, int, str]] = []
    cur: list[tuple[int, int, str]] = []
    cur_len = 0
    for s, e, body in blocks:
        body = body.strip()
        if not body:
            continue
        if cur and cur_len + len(body) + 2 > max_chars:
            chunks.append((cur[0][0], cur[-1][1], "\n\n".join(b[2] for b in cur)))
            cur, cur_len = [], 0
        cur.append((s, e, body))
        cur_len += len(body) + 2
    if cur:
        chunks.append((cur[0][0], cur[-1][1], "\n\n".join(b[2] for b in cur)))
    return chunks


def tokenize(text: str) -> list[str]:
    """无依赖分词：拉丁词 + CJK 双字。

    `unicode61`/空格切分对中文无效（整句变一个 token），双字切分是零依赖下
    召回与精度的折中；单字串保留原字，避免"你"这类查询永远打不中。
    """
    low = text.lower()
    tokens = _LATIN_WORD.findall(low)
    for run in _CJK_RUN.findall(low):
        if len(run) == 1:
            tokens.append(run)
        else:
            tokens.extend(run[i : i + 2] for i in range(len(run) - 1))
    return tokens


# --------------------------------------------------------------------- 索引


def load_index(index_file: Path | None = None, *, missing_ok: bool = False) -> dict:
    path = Path(index_file) if index_file else index_path()
    if not path.exists():
        if missing_ok:
            return {"version": INDEX_VERSION, "root": "", "built_at": "", "docs": []}
        raise IndexMissing(f"索引不存在：{path}；先跑 `python kb.py --build`")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise KbError(f"读取索引失败：{exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("docs"), list):
        raise KbError("索引文件格式异常")
    if data.get("version") != INDEX_VERSION:
        raise KbError(f"索引版本不匹配（{data.get('version')} != {INDEX_VERSION}），请重建")
    return data


def build_index(
    root: Path | None = None,
    index_file: Path | None = None,
    *,
    force: bool = False,
) -> dict:
    """增量建索引：`mtime+size` 未变直接复用，变了再比 `sha1`，真变了才重新切块。"""
    root = (Path(root) if root else corpus_dir()).resolve()
    if not root.is_dir():
        raise CorpusMissing(f"语料目录不存在：{root}（用 VOXDESK_KB_DIR 指定）")
    out = Path(index_file) if index_file else index_path()

    previous = {} if force else {
        d["path"]: d for d in load_index(out, missing_ok=True)["docs"] if isinstance(d, dict)
    }

    t0 = time.perf_counter()
    docs: list[dict] = []
    added = updated = reused = 0
    for path in iter_documents(root):
        rel = path.relative_to(root).as_posix()
        try:
            st = path.stat()
        except OSError:
            continue
        old = previous.get(rel)
        if (
            old
            and old.get("size") == st.st_size
            and int(old.get("mtime") or 0) == int(st.st_mtime)
        ):
            docs.append(old)
            reused += 1
            continue
        try:
            raw = path.read_bytes()
        except OSError:
            continue
        sha1 = hashlib.sha1(raw).hexdigest()
        if old and old.get("sha1") == sha1:
            docs.append({**old, "mtime": st.st_mtime, "size": st.st_size})
            reused += 1
            continue
        chunks = [[s, e, body] for s, e, body in chunk_text(raw.decode("utf-8", "replace"))]
        docs.append(
            {"path": rel, "mtime": st.st_mtime, "size": st.st_size, "sha1": sha1, "chunks": chunks}
        )
        if old:
            updated += 1
        else:
            added += 1

    docs.sort(key=lambda d: d["path"])
    seen = {d["path"] for d in docs}
    removed = len(set(previous) - seen)

    payload = {
        "version": INDEX_VERSION,
        "root": str(root),
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "docs": docs,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(f".{out.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, out)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass

    return {
        "ok": True,
        "root": str(root),
        "index": str(out),
        "documents": len(docs),
        "chunks": sum(len(d["chunks"]) for d in docs),
        "added": added,
        "updated": updated,
        "reused": reused,
        "removed": removed,
        "ms": round((time.perf_counter() - t0) * 1000, 1),
    }


# --------------------------------------------------------------------- 检索


def _snippet(text: str, tokens: set[str], width: int = SNIPPET_CHARS) -> str:
    low = text.lower()
    head = -1
    for tok in tokens:
        pos = low.find(tok)
        if pos != -1 and (head == -1 or pos < head):
            head = pos
    if head == -1:
        return " ".join(text[:width].split())
    start = max(0, head - width // 3)
    return " ".join(text[start : start + width].split())


_ROWS_CACHE: dict[str, tuple[float, list[tuple]]] = {}
"""索引文件路径 → (mtime, 预分词片段)。

每次查询都对全库重新分词，1 万篇要 600ms；缓存后同一份索引的重复查询降到毫秒级，
索引文件被重建导致 mtime 变化时自动失效。
"""


def _rows(index_file: Path | None = None) -> list[tuple[str, int, int, str, Counter, int]]:
    path = Path(index_file) if index_file else index_path()
    if not path.exists():
        raise IndexMissing(f"索引不存在：{path}；先跑 `python kb.py --build`")
    mtime = path.stat().st_mtime
    cached = _ROWS_CACHE.get(str(path))
    if cached and cached[0] == mtime:
        return cached[1]
    index = load_index(path)
    rows: list[tuple[str, int, int, str, Counter, int]] = []
    for doc in index["docs"]:
        for chunk in doc.get("chunks") or []:
            body = str(chunk[2])
            tf = Counter(tokenize(body))
            rows.append(
                (doc["path"], int(chunk[0]), int(chunk[1]), body, tf, sum(tf.values()) or len(body))
            )
    _ROWS_CACHE[str(path)] = (mtime, rows)
    return rows


def search(
    query: str,
    k: int = DEFAULT_K,
    index_file: Path | None = None,
) -> list[Chunk]:
    """BM25（k1=1.2, b=0.75）排序的片段检索；无命中返回空列表，不抛错。"""
    q = " ".join(str(query or "").split())
    if not q:
        raise QueryInvalid("query 为空")
    q_tokens = set(tokenize(q))
    if not q_tokens:
        raise QueryInvalid("query 没有可检索的词")
    try:
        k = max(1, min(MAX_K, int(k)))
    except (TypeError, ValueError):
        k = DEFAULT_K

    rows = _rows(index_file)
    if not rows:
        return []

    needed = max(1, math.ceil(MIN_COVERAGE * len(q_tokens)))
    df: Counter = Counter()
    scored: list[tuple[str, int, int, str, Counter, int]] = []
    total_len = 0
    for row in rows:
        tf = row[4]
        total_len += row[5]
        hit = q_tokens & tf.keys()
        if hit:
            df.update(hit)
        if len(hit) >= needed:
            scored.append(row)
    if not scored:
        return []

    n = len(rows)
    avgdl = (total_len / n) or 1.0
    k1, b = 1.2, 0.75
    results: list[Chunk] = []
    for path, s, e, body, tf, dl in scored:
        score = 0.0
        for tok in q_tokens & tf.keys():
            idf = math.log(1 + (n - df[tok] + 0.5) / (df[tok] + 0.5))
            f = tf[tok]
            score += idf * (f * (k1 + 1)) / (f + k1 * (1 - b + b * dl / avgdl))
        results.append(
            Chunk(
                path=path,
                start_line=s,
                end_line=e,
                text=body,
                score=round(score, 4),
                snippet=_snippet(body, q_tokens),
            )
        )
    results.sort(key=lambda c: (-c.score, c.path, c.start_line))
    return results[:k]


def stats(index_file: Path | None = None) -> dict:
    index = load_index(index_file, missing_ok=True)
    path = Path(index_file) if index_file else index_path()
    return {
        "ok": True,
        "corpus": corpus_dir().as_posix(),
        "index": path.as_posix(),
        "index_bytes": path.stat().st_size if path.exists() else 0,
        "built_at": index.get("built_at") or None,
        "documents": len(index["docs"]),
        "chunks": sum(len(d.get("chunks") or []) for d in index["docs"]),
    }


# --------------------------------------------------------------------- CLI


def main(argv: list[str] | None = None) -> int:
    # Windows 控制台默认 GBK，中文与 ⬜ 之类的符号会乱码甚至抛 UnicodeEncodeError。
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass

    ap = argparse.ArgumentParser(description="本地知识库：建索引 / 检索（IF-07）")
    ap.add_argument("--root", help="语料根目录（默认 VOXDESK_KB_DIR 或本仓 docs/）")
    ap.add_argument("--index", help="索引文件路径（默认 data/kb/index.json）")
    ap.add_argument("--build", action="store_true", help="增量建索引")
    ap.add_argument("--force", action="store_true", help="丢弃旧索引全量重建")
    ap.add_argument("--search", metavar="QUERY", help="检索")
    ap.add_argument("-k", type=int, default=DEFAULT_K, help=f"返回条数（默认 {DEFAULT_K}）")
    ap.add_argument("--stats", action="store_true", help="看索引状态")
    args = ap.parse_args(argv)

    root = Path(args.root) if args.root else None
    idx = Path(args.index) if args.index else None
    try:
        if args.build:
            print(json.dumps(build_index(root, idx, force=args.force), ensure_ascii=False, indent=2))
        if args.search:
            hits = search(args.search, args.k, idx)
            if not hits:
                print("没有检索到（不要编造，按 REQ-F-089 明说没记过）")
            for i, hit in enumerate(hits, 1):
                print(f"{i}. [{hit.score}] {hit.ref()}\n   {hit.snippet}")
        if args.stats or not (args.build or args.search):
            print(json.dumps(stats(idx), ensure_ascii=False, indent=2))
    except KbError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
