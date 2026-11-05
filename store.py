"""本地会话存储：JSON 文件、活跃/归档、上限与自动清理。

目录：
    data/chats/<id>.json      活跃（最多 30）
    data/archive/<id>.json    归档（最多 100；新归档时自动删最旧）

规则（按用户确认）：
- 单会话文件 ≤ 1MB；到上限禁止追加，提示归档并新开。
- 活跃到 30 条：不自动删除，新建返回 409，由前端提示归档/删除。
- 归档到 100 条：新归档发生时自动删除最旧归档。
- 活跃会话永不被自动删除。
"""

from __future__ import annotations

import json
import os
import re
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from paths import ARCHIVE_DIR, CHATS_DIR, ensure_dirs

MAX_ACTIVE = 30
MAX_ARCHIVE = 100
MAX_CHAT_BYTES = 1024 * 1024
ID_RE = re.compile(r"^[0-9a-f]{32}$")
TZ = timezone(timedelta(hours=8))


class StoreError(RuntimeError):
    status = 500


class ChatNotFound(StoreError):
    status = 404


class ChatLimit(StoreError):
    status = 409


class ChatFull(StoreError):
    status = 413


def now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def _title_from(text: str) -> str:
    line = " ".join(str(text or "").split()).strip()
    if not line:
        return "新对话"
    return line[:24]


class ConversationStore:
    def __init__(self, active_dir: Path = CHATS_DIR, archive_dir: Path = ARCHIVE_DIR) -> None:
        ensure_dirs()
        self.active_dir = Path(active_dir)
        self.archive_dir = Path(archive_dir)
        self.active_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    # ------------------------------------------------------------------ 基础

    def _dir(self, archived: bool) -> Path:
        return self.archive_dir if archived else self.active_dir

    def _path(self, chat_id: str, archived: bool) -> Path:
        if not ID_RE.match(chat_id or ""):
            raise ChatNotFound("会话 id 不合法")
        return self._dir(archived) / f"{chat_id}.json"

    def _load(self, chat_id: str, archived: bool) -> dict:
        path = self._path(chat_id, archived)
        if not path.exists():
            raise ChatNotFound("会话不存在")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StoreError(f"读取会话失败：{exc}") from exc
        if not isinstance(data, dict) or not isinstance(data.get("messages"), list):
            raise StoreError("会话文件格式异常")
        return data

    def _write(self, data: dict, archived: bool) -> int:
        chat_id = str(data.get("id") or "")
        path = self._path(chat_id, archived)
        payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        if len(payload) > MAX_CHAT_BYTES:
            raise ChatFull(f"单会话已达 {MAX_CHAT_BYTES // 1024}KB 上限，请归档并新开")
        tmp = self._dir(archived) / f".{chat_id}.{uuid.uuid4().hex[:6]}.tmp"
        try:
            tmp.write_bytes(payload)
            os.replace(tmp, path)
        finally:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
        return len(payload)

    def _meta(self, path: Path) -> dict:
        data = json.loads(path.read_text(encoding="utf-8"))
        messages = data.get("messages") or []
        return {
            "id": data.get("id"),
            "title": data.get("title") or "新对话",
            "mode": data.get("mode") or "general",
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
            "message_count": len(messages),
            "bytes": path.stat().st_size,
        }

    # ------------------------------------------------------------------ 查询

    def list(self, archived: bool = False) -> dict:
        with self._lock:
            items = []
            for path in self._dir(archived).glob("*.json"):
                try:
                    items.append(self._meta(path))
                except (OSError, json.JSONDecodeError):
                    continue
            items.sort(key=lambda x: str(x.get("updated_at") or ""), reverse=True)
            return {
                "items": items,
                "stats": self.stats(),
                "limits": {
                    "active": MAX_ACTIVE,
                    "archive": MAX_ARCHIVE,
                    "bytes": MAX_CHAT_BYTES,
                },
            }

    def stats(self) -> dict:
        active = list(self.active_dir.glob("*.json"))
        archive = list(self.archive_dir.glob("*.json"))
        return {
            "active": len(active),
            "archive": len(archive),
            "active_bytes": sum(p.stat().st_size for p in active),
            "archive_bytes": sum(p.stat().st_size for p in archive),
            "limits": {
                "active": MAX_ACTIVE,
                "archive": MAX_ARCHIVE,
                "bytes": MAX_CHAT_BYTES,
            },
        }

    def get(self, chat_id: str, archived: bool = False) -> dict:
        with self._lock:
            return self._load(chat_id, archived)

    # ------------------------------------------------------------------ 写入

    def create(self, mode: str = "general", title: str = "新对话") -> dict:
        with self._lock:
            active = list(self.active_dir.glob("*.json"))
            if len(active) >= MAX_ACTIVE:
                raise ChatLimit(f"活跃对话已达 {MAX_ACTIVE} 条，请先归档或删除")
            chat_id = uuid.uuid4().hex
            stamp = now_iso()
            data = {
                "id": chat_id,
                "title": title or "新对话",
                "mode": mode if mode in ("general", "companion") else "general",
                "created_at": stamp,
                "updated_at": stamp,
                "messages": [],
            }
            self._write(data, archived=False)
            return data

    def append_turns(self, chat_id: str, user: dict, assistant: dict) -> dict:
        with self._lock:
            data = self._load(chat_id, archived=False)
            messages = data.setdefault("messages", [])
            messages.append(user)
            messages.append(assistant)
            if data.get("title") in (None, "", "新对话"):
                data["title"] = _title_from(user.get("text", ""))
            data["updated_at"] = now_iso()
            self._write(data, archived=False)
            return data

    def capacity_guard(self, chat_id: str, incoming_bytes: int = 24000) -> None:
        """在调用模型前做一次粗略容量检查，避免生成完才发现无法保存。"""
        with self._lock:
            path = self._path(chat_id, archived=False)
            if not path.exists():
                raise ChatNotFound("会话不存在")
            if path.stat().st_size + max(0, incoming_bytes) > MAX_CHAT_BYTES:
                raise ChatFull(f"单会话已达 {MAX_CHAT_BYTES // 1024}KB 上限，请归档并新开")

    def rename(self, chat_id: str, title: str) -> dict:
        with self._lock:
            data = self._load(chat_id, archived=False)
            data["title"] = _title_from(title)
            data["updated_at"] = now_iso()
            self._write(data, archived=False)
            return data

    def delete(self, chat_id: str) -> dict:
        with self._lock:
            removed = []
            for archived in (False, True):
                path = self._path(chat_id, archived)
                if path.exists():
                    path.unlink()
                    removed.append("archive" if archived else "active")
            if not removed:
                raise ChatNotFound("会话不存在")
            return {"id": chat_id, "removed": removed, "stats": self.stats()}

    # ------------------------------------------------------------------ 归档

    def archive(self, chat_id: str) -> dict:
        with self._lock:
            data = self._load(chat_id, archived=False)
            self._dir(True).mkdir(parents=True, exist_ok=True)

            archived = sorted(
                self.archive_dir.glob("*.json"),
                key=lambda p: p.stat().st_mtime,
            )
            purged: list[str] = []
            while len(archived) >= MAX_ARCHIVE:
                oldest = archived.pop(0)
                try:
                    purged.append(oldest.stem)
                    oldest.unlink()
                except OSError:
                    break

            data["archived_at"] = now_iso()
            data["updated_at"] = data.get("updated_at") or now_iso()
            # 先写归档，再删活跃，避免中途丢失
            target = self.archive_dir / f"{chat_id}.json"
            payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
            tmp = self.archive_dir / f".{chat_id}.{uuid.uuid4().hex[:6]}.tmp"
            try:
                tmp.write_bytes(payload)
                os.replace(tmp, target)
            finally:
                try:
                    tmp.unlink(missing_ok=True)
                except OSError:
                    pass
            self._path(chat_id, archived=False).unlink(missing_ok=True)
            return {
                "id": chat_id,
                "purged": purged,
                "stats": self.stats(),
                "limits": {"active": MAX_ACTIVE, "archive": MAX_ARCHIVE},
            }

    def restore(self, chat_id: str) -> dict:
        with self._lock:
            data = self._load(chat_id, archived=True)
            if len(list(self.active_dir.glob("*.json"))) >= MAX_ACTIVE:
                raise ChatLimit(f"活跃对话已达 {MAX_ACTIVE} 条，请先归档或删除")
            data.pop("archived_at", None)
            data["updated_at"] = now_iso()
            self._write(data, archived=False)
            self._path(chat_id, archived=True).unlink(missing_ok=True)
            return {"id": chat_id, "stats": self.stats()}
