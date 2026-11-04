"""DeepSeek Chat API 的最小客户端（只用标准库）。

为什么不用 `openai` SDK：这个 demo 只要一个 POST + SSE 解析，标准库足够；
少一个依赖，就少一个"换台电脑装不上"的可能。

流式的目的不是炫技，是**量首 token 延迟**——那是 S5 的硬指标（≤1.2s）。
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"
KEY_ENV = "DEEPSEEK_API_KEY"


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


class DeepSeekChat:
    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 60.0,
    ) -> None:
        key = api_key or os.environ.get(KEY_ENV, "")
        if not key:
            raise DeepSeekError(f"没有 API key：设置环境变量 {KEY_ENV}，或传 --key")
        self.api_key = key
        self.model = model
        self.base_url = base_url.rstrip("/")
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
