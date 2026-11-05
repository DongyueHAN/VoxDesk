"""DeepSeek 官方 Search / Fetch API 的工具执行层。

只做只读网络请求，不保存网页。模型通过函数工具调用：
    web_search(query) -> 标题/摘要/日期/URL
    web_fetch(url)    -> 网页 Markdown 正文（用于核实实时时钟等）
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections import OrderedDict
from urllib.parse import urlparse

from llm import get_api_key, load_env

BASE_URL = "https://api.deepseek.com"
SEARCH_PATH = "/v1/tools/search"
FETCH_PATH = "/v1/tools/fetch"
CACHE_TTL = 300.0
CACHE_MAX = 64
MAX_CONTENT = 6000


class SearchError(RuntimeError):
    pass


class DeepSeekSearch:
    def __init__(self, api_key: str | None = None, timeout: float = 30.0) -> None:
        load_env()
        self.api_key = api_key or get_api_key()
        self.timeout = timeout
        self._cache: OrderedDict[tuple[str, str], tuple[float, dict]] = OrderedDict()

    # ------------------------------------------------------------------ 网络

    def _post(self, path: str, payload: dict) -> dict:
        if not self.api_key:
            raise SearchError("没有 API key，无法联网搜索")
        req = urllib.request.Request(
            f"{BASE_URL}{path}",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310 - 固定 https
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            raise SearchError(f"搜索 HTTP {exc.code}：{detail}") from exc
        except urllib.error.URLError as exc:
            raise SearchError(f"搜索网络错误：{exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise SearchError("搜索返回的不是 JSON") from exc
        if not isinstance(data, dict):
            raise SearchError("搜索返回格式异常")
        return data

    def _cached(self, kind: str, key: str, producer) -> dict:
        now = time.monotonic()
        hit = self._cache.get((kind, key))
        if hit and now - hit[0] < CACHE_TTL:
            self._cache.move_to_end((kind, key))
            return hit[1]
        value = producer()
        self._cache[(kind, key)] = (now, value)
        self._cache.move_to_end((kind, key))
        while len(self._cache) > CACHE_MAX:
            self._cache.popitem(last=False)
        return value

    # ------------------------------------------------------------------ API

    def search(self, query: str, count: int = 5) -> list[dict]:
        query = " ".join(str(query or "").split())
        if not query:
            raise SearchError("搜索词为空")
        query = query[:128]
        count = max(1, min(5, int(count or 5)))

        def run() -> dict:
            return self._post(
                SEARCH_PATH,
                {"query": query, "count": count, "need_content": False},
            )

        data = self._cached("search", f"{count}:{query}", run)
        results = data.get("results") or []
        return [r for r in results if isinstance(r, dict)][:count]

    def fetch(self, url: str) -> dict:
        url = str(url or "").strip()
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc or "@" in parsed.netloc:
            raise SearchError("web_fetch 只接受不含用户名密码的 http/https URL")
        if len(url) > 8192:
            raise SearchError("URL 过长")

        # 实时时钟页面常被上游缓存。加一个一次性查询参数，抓取仍显示原始 URL。
        from urllib.parse import parse_qsl, urlencode, urlunparse

        query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k != "_voxdesk_ts"]
        query.append(("_voxdesk_ts", str(int(time.time() * 1000))))
        request_url = urlunparse(parsed._replace(query=urlencode(query)))
        # 不缓存 fetch：实时页面必须每次重新抓取。
        return self._post(FETCH_PATH, {"url": request_url})

    # ------------------------------------------------------------------ 工具

    def execute_tool(self, name: str, arguments: dict) -> tuple[str, list[dict]]:
        """返回 (给模型的工具结果文本, 来源列表)。异常会转换成工具错误文本。"""
        try:
            if name == "web_search":
                query = str(arguments.get("query") or "").strip()
                results = self.search(query, 5)
                if not results:
                    return "搜索没有返回结果。", []
                lines = []
                sources = []
                for i, item in enumerate(results, 1):
                    title = str(item.get("title") or "").strip()
                    url = str(item.get("url") or "").strip()
                    summary = str(item.get("summary") or item.get("snippet") or "").strip()
                    date = str(item.get("date") or "").strip()
                    lines.append(
                        f"[{i}] 标题：{title}\n日期：{date or '未知'}\n摘要：{summary[:600]}\nURL：{url}"
                    )
                    if url:
                        sources.append(
                            {
                                "title": title or url,
                                "url": url,
                                "snippet": summary[:240],
                                "date": date,
                            }
                        )
                return "\n\n".join(lines), sources

            if name == "web_fetch":
                url = str(arguments.get("url") or "").strip()
                page = self.fetch(url)
                title = str(page.get("title") or "").strip()
                content = str(page.get("content") or "").strip()
                if not content:
                    return f"页面没有可读正文：{url}", [{"title": title or url, "url": url, "snippet": ""}]
                return (
                    f"页面标题：{title or '(无标题)'}\nURL：{url}\n\n{content[:MAX_CONTENT]}",
                    [{"title": title or url, "url": url, "snippet": content[:240]}],
                )

            return f"未知工具：{name}", []
        except SearchError as exc:
            return f"工具调用失败：{exc}", []
        except Exception as exc:  # noqa: BLE001 - 工具错误应回填给模型而不是打断整轮
            return f"工具调用异常：{type(exc).__name__}: {exc}", []


def dedupe_sources(sources: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for item in sources:
        url = str(item.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        out.append(item)
    return out
