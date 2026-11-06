"""DeepSeek Chat 客户端：多轮、函数工具（web_search / web_fetch）与非流式调用。

模型默认 `deepseek-flash`（官方版本 DeepSeek-V4.1-Flash-1017；`deepseek-v4.1`
不是 API 接受的模型 ID）。不注入当前时间，实时信息由模型调用工具获得。

配置优先级：
    1) 构造参数
    2) 环境变量
    3) 本目录 .env
    4) D:\\VoxDesk\\demo\\.env（只读兜底）
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from paths import ENV_FILES

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-flash"
KEY_ENV = "DEEPSEEK_API_KEY"
MODEL_ENV = "DEEPSEEK_MODEL"
BASE_URL_ENV = "DEEPSEEK_BASE_URL"


class DeepSeekError(RuntimeError):
    pass


@dataclass
class ChatReply:
    text: str
    tool_calls: list[dict] = field(default_factory=list)
    first_token_ms: float | None = None
    total_ms: float = 0.0
    model: str = DEFAULT_MODEL
    usage: dict | None = None


@dataclass
class AgentReply:
    text: str
    sources: list[dict] = field(default_factory=list)
    tool_rounds: int = 0
    first_token_ms: float | None = None
    llm_ms: float = 0.0
    model: str = DEFAULT_MODEL
    usage: dict | None = None


def load_env() -> None:
    """读取 .env（已有环境变量不覆盖）。不打印任何密钥。"""
    for path in ENV_FILES:
        try:
            text = Path(path).read_text(encoding="utf-8")
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


def get_api_key() -> str:
    load_env()
    return os.environ.get(KEY_ENV, "")


class DeepSeekChat:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float = 90.0,
    ) -> None:
        load_env()
        self.api_key = api_key or os.environ.get(KEY_ENV, "")
        if not self.api_key:
            raise DeepSeekError(f"没有 API key：请在 {ENV_FILES[0]} 写 {KEY_ENV}=sk-...")
        self.model = model or os.environ.get(MODEL_ENV) or DEFAULT_MODEL
        self.base_url = (base_url or os.environ.get(BASE_URL_ENV) or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout

    # ------------------------------------------------------------------ 单次

    def chat(
        self,
        messages: list[dict],
        *,
        tools: list[dict] | None = None,
        max_tokens: int = 900,
        temperature: float = 0.7,
    ) -> ChatReply:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
            # 语音链路优先低延迟；需要思考时可在配置里关掉这一行。
            "thinking": {"type": "disabled"},
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        start = time.perf_counter()
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310 - 固定域名
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:400]
            raise DeepSeekError(f"DeepSeek HTTP {exc.code}：{detail}") from exc
        except urllib.error.URLError as exc:
            raise DeepSeekError(f"DeepSeek 网络错误：{exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise DeepSeekError("DeepSeek 返回的不是 JSON") from exc
        total_ms = (time.perf_counter() - start) * 1000

        choices = data.get("choices") or []
        if not choices:
            raise DeepSeekError(f"DeepSeek 没有 choices：{str(data)[:300]}")
        message = choices[0].get("message") or {}
        text = (message.get("content") or "").strip()
        tool_calls = message.get("tool_calls") or []
        return ChatReply(
            text=text,
            tool_calls=tool_calls,
            first_token_ms=None,  # 非流式只能测总耗时
            total_ms=total_ms,
            model=data.get("model", self.model),
            usage=data.get("usage"),
        )

    # ------------------------------------------------------------------ 工具循环

    def complete_with_tools(
        self,
        messages: list[dict],
        *,
        tools: list[dict] | None = None,
        execute_tool=None,
        max_rounds: int = 3,
        max_tokens: int = 900,
    ) -> AgentReply:
        """执行“模型请求工具 → 服务端执行 → 回填 → 再请求”的循环。

        `execute_tool(name, arguments) -> (content: str, sources: list[dict])`
        """
        if execute_tool is None:
            raise ValueError("execute_tool 不能为空")

        start = time.perf_counter()
        working = list(messages)
        sources: list[dict] = []
        rounds = 0

        for _ in range(max_rounds):
            reply = self.chat(working, tools=tools, max_tokens=max_tokens)
            if not reply.tool_calls:
                if not reply.text:
                    raise DeepSeekError("模型没有返回文本")
                return AgentReply(
                    text=reply.text,
                    sources=_dedupe_sources(sources),
                    tool_rounds=rounds,
                    first_token_ms=reply.first_token_ms,
                    llm_ms=(time.perf_counter() - start) * 1000,
                    model=reply.model,
                    usage=reply.usage,
                )

            working.append(
                {
                    "role": "assistant",
                    "content": reply.text or None,
                    "tool_calls": reply.tool_calls,
                }
            )
            for call in reply.tool_calls:
                fn = call.get("function") or {}
                name = str(fn.get("name") or "")
                raw_args = fn.get("arguments") or "{}"
                try:
                    arguments = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
                except (json.JSONDecodeError, TypeError, ValueError):
                    arguments = {}
                try:
                    content, found = execute_tool(name, arguments)
                except Exception as exc:  # noqa: BLE001 - 工具异常回填，不打断整轮
                    content, found = f"工具执行异常：{type(exc).__name__}: {exc}", []
                if found:
                    sources.extend(found)
                working.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id", ""),
                        "content": content[:12000],
                    }
                )
            rounds += 1

        # 工具轮次用尽：强制模型在没有工具的情况下给出最终回答
        final = self.chat(working, tools=None, max_tokens=max_tokens)
        if not final.text:
            raise DeepSeekError("工具调用后模型仍未返回文本")
        return AgentReply(
            text=final.text,
            sources=_dedupe_sources(sources),
            tool_rounds=rounds,
            first_token_ms=final.first_token_ms,
            llm_ms=(time.perf_counter() - start) * 1000,
            model=final.model,
            usage=final.usage,
        )


def _dedupe_sources(sources: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for item in sources:
        url = str(item.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        out.append(
            {
                "title": str(item.get("title") or url)[:160],
                "url": url,
                "snippet": str(item.get("snippet") or "")[:240],
                "date": str(item.get("date") or ""),
            }
        )
    return out
