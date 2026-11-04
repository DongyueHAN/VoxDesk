"""DeepSeek Chat API 的最小客户端（只用标准库）。

为什么不用 `openai` SDK：这个 demo 只要一个 POST + SSE 解析，标准库足够；
少一个依赖，就少一个"换台电脑装不上"的可能。

流式的目的不是炫技，是**量首 token 延迟**——那是 S5 的硬指标（≤1.2s）。

配置来源（优先级从高到低）：
    1. 显式传参（`--key` / 构造参数）
    2. 进程环境变量（`$env:DEEPSEEK_API_KEY = "..."`，只活当前窗口）
    3. `.env` 文件（当前目录 → demo/ → 仓库根，**不覆盖已存在的变量**）

`.env` 已在根 `.gitignore` 里（`.env` + `.env.*`），不会被提交。
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"
KEY_ENV = "DEEPSEEK_API_KEY"
MODEL_ENV = "DEEPSEEK_MODEL"
BASE_URL_ENV = "DEEPSEEK_BASE_URL"


class DeepSeekError(RuntimeError):
    """网络 / 鉴权 / 协议错误，统一成一种异常，方便 CLI 兜底。"""


@dataclass(frozen=True)
class ChatReply:
    text: str
    first_token_ms: float | None
    total_ms: float
    model: str

    @property
    def chars_per_second(self) -> float:
        return len(self.text) / (self.total_ms / 1000) if self.total_ms else float("nan")


def env_file_candidates() -> list[Path]:
    """按优先级列出可能存在的 .env。"""
    here = Path(__file__).resolve()
    return [
        Path.cwd() / ".env",  # 你在哪个目录启动，就先看那里
        here.parents[2] / ".env",  # demo/.env
        here.parents[3] / ".env",  # 仓库根/.env
    ]


def load_env_file(paths: list[Path] | None = None) -> list[str]:
    """把 .env 里的 KEY=VALUE 读进 os.environ（**已有变量不覆盖**）。

    返回真正被设置的变量名，方便调试时确认"到底从哪读到的"。
    """
    loaded: list[str] = []
    for path in paths if paths is not None else env_file_candidates():
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
                loaded.append(key)
    return loaded


class DeepSeekChat:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        load_env_file()

        key = api_key or os.environ.get(KEY_ENV, "")
        if not key:
            raise DeepSeekError(
                f"没有 API key：设置环境变量 {KEY_ENV}、传 --key，"
                f"或复制 demo/.env.example 为 demo/.env 后填入"
            )

        self.api_key = key
        self.model = model or os.environ.get(MODEL_ENV) or DEFAULT_MODEL
        self.base_url = (base_url or os.environ.get(BASE_URL_ENV) or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout

    # ------------------------------------------------------------------ 公开

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        stream: bool = True,
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> ChatReply:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        if stream:
            return self._chat_stream(payload)
        return self._chat_once(payload)

    # ------------------------------------------------------------------ 内部

    def _request(self, payload: dict) -> urllib.request.addinfourl:
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "text/event-stream" if payload.get("stream") else "application/json",
            },
            method="POST",
        )
        try:
            return urllib.request.urlopen(req, timeout=self.timeout)  # noqa: S310 - 固定 https 域名
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            raise DeepSeekError(f"HTTP {exc.code}：{detail}") from exc
        except urllib.error.URLError as exc:
            raise DeepSeekError(f"网络错误：{exc.reason}") from exc

    def _chat_once(self, payload: dict) -> ChatReply:
        start = time.perf_counter()
        with self._request(payload) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        total_ms = (time.perf_counter() - start) * 1000
        text = data["choices"][0]["message"]["content"].strip()
        return ChatReply(text=text, first_token_ms=None, total_ms=total_ms, model=data.get("model", self.model))

    def _chat_stream(self, payload: dict) -> ChatReply:
        start = time.perf_counter()
        first_token_ms: float | None = None
        pieces: list[str] = []

        with self._request(payload) as resp:
            for raw in resp:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                body = line[5:].strip()
                if body == "[DONE]":
                    break
                try:
                    chunk = json.loads(body)
                except json.JSONDecodeError:
                    continue
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta", {}).get("content") or ""
                if not delta:
                    continue
                if first_token_ms is None:
                    first_token_ms = (time.perf_counter() - start) * 1000
                pieces.append(delta)

        total_ms = (time.perf_counter() - start) * 1000
        return ChatReply(
            text="".join(pieces).strip(),
            first_token_ms=first_token_ms,
            total_ms=total_ms,
            model=self.model,
        )
