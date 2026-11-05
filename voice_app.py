"""Web 版语音对话编排：ASR → 多轮 DeepSeek（工具）→ 可选 Piper TTS。"""

from __future__ import annotations

import re
import threading
import time
import uuid

import numpy as np

import paths

paths.install_sys_path()

from llm import AgentReply, DeepSeekChat, DeepSeekError, get_api_key  # noqa: E402
from prompts import TOOLS, system_prompt  # noqa: E402
from search import DeepSeekSearch  # noqa: E402
from store import ConversationStore  # noqa: E402
from voxdesk_audio import StreamingASR  # noqa: E402
from voxdesk_tts import PiperEngine  # noqa: E402

SR = 16000
MAX_AUDIO_SECONDS = 30
MAX_TEXT_CHARS = 4000
HISTORY_MESSAGES = 20
HISTORY_CHARS = 12000


def clean_for_tts(text: str) -> str:
    """去掉 Markdown/来源标记/URL，留下适合朗读的短文本。"""
    s = str(text or "")
    s = re.sub(r"```.*?```", "", s, flags=re.S)
    s = re.sub(r"`([^`]*)`", r"\1", s)
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"https?://\S+", "", s)
    s = re.sub(r"\[\d+\]", "", s)
    s = re.sub(r"^[#>*\-+\s]+", "", s, flags=re.M)
    s = re.sub(r"[*_~]{1,3}", "", s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{2,}", "。", s)
    s = s.strip()
    return s[:1200]


class VoiceApp:
    def __init__(self) -> None:
        paths.ensure_dirs()
        self.store = ConversationStore()
        self.search = DeepSeekSearch()
        self._llm: DeepSeekChat | None = None
        self._asr: StreamingASR | None = None
        self._tts: PiperEngine | None = None
        self._asr_lock = threading.Lock()
        self._tts_lock = threading.Lock()

    # ------------------------------------------------------------------ 模型

    def warmup(self) -> dict:
        t0 = time.perf_counter()
        self.asr()
        asr_ms = (time.perf_counter() - t0) * 1000
        t0 = time.perf_counter()
        tts = self.tts()
        # 真正合成一次，触发 Piper 的懒加载
        with self._tts_lock:
            tts.synth("你好", paths.OUT_DIR / "_warm.wav")
        tts_ms = (time.perf_counter() - t0) * 1000
        return {"asr_ms": round(asr_ms, 1), "tts_ms": round(tts_ms, 1)}

    def asr(self) -> StreamingASR:
        if self._asr is None:
            self._asr = StreamingASR(paths.ASR_MODEL_DIR)
        return self._asr

    def tts(self) -> PiperEngine:
        if self._tts is None:
            self._tts = PiperEngine(paths.PIPER_MODEL, warmup=True)
        return self._tts

    def llm(self) -> DeepSeekChat:
        if self._llm is None:
            self._llm = DeepSeekChat()
        return self._llm

    # ------------------------------------------------------------------ ASR

    def transcribe(self, raw: bytes) -> dict:
        if not raw:
            raise ValueError("没有收到音频数据")
        raw = raw[: len(raw) // 2 * 2]
        if len(raw) < 3200:
            raise ValueError("音频太短（至少 0.1 秒）")
        if len(raw) > MAX_AUDIO_SECONDS * SR * 2:
            raise ValueError(f"音频超过 {MAX_AUDIO_SECONDS} 秒")

        samples = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
        t0 = time.perf_counter()
        with self._asr_lock:
            result = self.asr().transcribe(samples)
        total_ms = (time.perf_counter() - t0) * 1000
        return {
            "text": result.text.strip(),
            "asr_ms": round(total_ms, 1),
            "first_char_ms": round(result.first_char_ms, 1) if result.first_char_ms is not None else None,
            "audio_s": round(result.audio_s, 2),
        }

    # ------------------------------------------------------------------ 对话

    def chat(
        self,
        *,
        conversation_id: str = "",
        text: str = "",
        mode: str = "general",
        speak: bool = True,
        web: bool = True,
        source: str = "text",
        asr_ms: float | None = None,
    ) -> dict:
        text = str(text or "").strip()
        if not text:
            raise ValueError("text 为空")
        if len(text) > MAX_TEXT_CHARS:
            raise ValueError(f"单条消息超过 {MAX_TEXT_CHARS} 字")
        mode = mode if mode in ("general", "companion") else "general"

        if conversation_id:
            chat = self.store.get(conversation_id)
            mode = chat.get("mode") or mode
        else:
            chat = self.store.create(mode=mode)
            conversation_id = chat["id"]

        created_new = not chat.get("messages")
        try:
            self.store.capacity_guard(conversation_id)

            messages = [{"role": "system", "content": system_prompt(mode)}]
            if not web:
                messages.append(
                    {
                        "role": "system",
                        "content": "本次会话的联网工具已关闭。不要声称你查询了网页；实时信息无法确认时请直接说明。",
                    }
                )

            history = self._recent_history(chat.get("messages") or [])
            messages.extend(history)
            messages.append({"role": "user", "content": text})

            t0 = time.perf_counter()
            if web:
                agent: AgentReply = self.llm().complete_with_tools(
                    messages,
                    tools=TOOLS,
                    execute_tool=self.search.execute_tool,
                    max_rounds=3,
                )
            else:
                reply = self.llm().chat(messages)
                if not reply.text:
                    raise DeepSeekError("模型没有返回文本")
                agent = AgentReply(
                    text=reply.text,
                    sources=[],
                    tool_rounds=0,
                    llm_ms=reply.total_ms,
                    model=reply.model,
                    usage=reply.usage,
                )
            llm_ms = (time.perf_counter() - t0) * 1000
        except Exception:
            if created_new:
                try:
                    self.store.delete(conversation_id)
                except Exception:  # noqa: BLE001 - 清理失败不掩盖原始错误
                    pass
            raise

        stamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        user_msg = {
            "role": "user",
            "text": text,
            "source": source if source in ("mic", "desktop", "text") else "text",
            "asr_ms": round(asr_ms or 0),
            "created_at": stamp,
        }
        assistant_msg = {
            "role": "assistant",
            "text": agent.text,
            "sources": agent.sources,
            "tool_rounds": agent.tool_rounds,
            "tts": bool(speak),
            "model": agent.model,
            "first_token_ms": agent.first_token_ms,
            "llm_ms": round(llm_ms),
            "created_at": stamp,
        }
        self.store.append_turns(conversation_id, user_msg, assistant_msg)

        audio = None
        tts_ms = 0.0
        tts_error = None
        if speak:
            try:
                audio, tts_ms = self.synth_wav(agent.text)
            except Exception as exc:  # noqa: BLE001 - TTS 失败不丢文字
                tts_error = f"{type(exc).__name__}: {exc}"

        return {
            "conversation_id": conversation_id,
            "reply": agent.text,
            "sources": agent.sources,
            "audio": audio,
            "tts_ms": round(tts_ms, 1),
            "tts_error": tts_error,
            "llm_ms": round(llm_ms),
            "first_token_ms": agent.first_token_ms,
            "tool_rounds": agent.tool_rounds,
            "model": agent.model,
            "web": bool(web),
            "mode": mode,
        }

    def _recent_history(self, stored: list[dict]) -> list[dict]:
        usable = [
            m
            for m in stored
            if m.get("role") in ("user", "assistant") and str(m.get("text") or "").strip()
        ][-HISTORY_MESSAGES:]
        selected: list[dict] = []
        budget = HISTORY_CHARS
        for msg in reversed(usable):
            content = str(msg.get("text") or "")
            if len(content) > budget:
                break
            selected.append({"role": msg["role"], "content": content})
            budget -= len(content)
        selected.reverse()
        return selected

    # ------------------------------------------------------------------ TTS

    def synth_wav(self, text: str) -> tuple[str, float]:
        spoken = clean_for_tts(text)
        if not spoken:
            raise ValueError("可朗读文本为空")
        name = f"{uuid.uuid4().hex[:12]}.wav"
        path = paths.OUT_DIR / name
        with self._tts_lock:
            t0 = time.perf_counter()
            self.tts().synth(spoken, path)
            ms = (time.perf_counter() - t0) * 1000
        return name, ms

    # ------------------------------------------------------------------ 状态

    def status(self) -> dict:
        return {
            "ok": True,
            "model": self._llm.model if self._llm else None,
            "default_model": "deepseek-flash",
            "api_key": bool(get_api_key()),
            "asr_loaded": self._asr is not None,
            "tts_loaded": self._tts is not None,
            "search": "deepseek",
            "store": self.store.stats(),
        }
