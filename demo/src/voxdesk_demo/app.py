"""把三个切片拼成一轮对话：ASR → LLM（DeepSeek）→ TTS。

这是**临时 demo**，只在分支 `demo/deepseek-voice` 上：
主线（`docs/13-M2process.md` 的 S5）要接的是本地 Ollama + Qwen3-4B，
这里换成云 API 为了先跑通"能对话"的体感，不并入主线。

拼的是已有的三个件：
    voxdesk_audio.StreamingASR   （S4）
    voxdesk_tts.TTSService       （S1/S2）
    voxdesk_demo.DeepSeekChat    （本分支新增）
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from voxdesk_audio import StreamingASR
from voxdesk_tts import PiperEngine, TTSService

# 三个切片各有自己的 models/ 目录，这里统一从仓库根找，
# 这样在任何 cwd 下运行都能找到模型（demo 从 demo/ 启动时尤其重要）
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ASR_DIR = REPO_ROOT / "audio" / "models" / "sherpa-onnx-streaming-paraformer-bilingual-zh-en"
DEFAULT_PIPER_MODEL = REPO_ROOT / "tts" / "models" / "zh_CN-huayan-medium.onnx"

SYSTEM_PROMPT = (
    "你是一个简洁的中文语音助手。回答控制在两句话以内，"
    "不要使用 Markdown、列表、代码块或表情符号，因为你说的会被念出来。"
)


@dataclass
class Turn:
    user_text: str
    reply_text: str
    asr_ms: float
    first_token_ms: float | None
    llm_ms: float | None
    tts_ms: float | None

    @property
    def total_ms(self) -> float:
        return self.asr_ms + (self.llm_ms or 0) + (self.tts_ms or 0)

    def __str__(self) -> str:
        parts = [f"ASR {self.asr_ms:.0f}ms"]
        if self.first_token_ms is not None:
            parts.append(f"首token {self.first_token_ms:.0f}ms")
        if self.llm_ms is not None:
            parts.append(f"LLM {self.llm_ms:.0f}ms")
        if self.tts_ms is not None:
            parts.append(f"TTS {self.tts_ms:.0f}ms")
        return "  ".join(parts)


class VoiceChat:
    def __init__(
        self,
        asr: StreamingASR | None = None,
        tts: TTSService | None = None,
        llm=None,
        mock: bool = False,
        system_prompt: str = SYSTEM_PROMPT,
        cache_dir: str = "cache",
        model_dir=None,
        asr_model_dir=None,
    ) -> None:
        self.asr = asr or StreamingASR(asr_model_dir or DEFAULT_ASR_DIR)
        piper_model = model_dir or DEFAULT_PIPER_MODEL
        engine = PiperEngine(piper_model, warmup=True)
        self.tts = tts or TTSService(engine, cache_dir=cache_dir)
        self.llm = llm
        self.mock = mock or llm is None
        self.system_prompt = system_prompt
        self.history: list[dict[str, str]] = []

    # ------------------------------------------------------------------ 一轮

    def handle_audio(self, audio: np.ndarray) -> Turn:
        start = time.perf_counter()
        asr_result = self.asr.transcribe(audio)
        asr_ms = (time.perf_counter() - start) * 1000
        user_text = asr_result.text.strip()

        if not user_text:
            return Turn(user_text="", reply_text="", asr_ms=asr_ms, first_token_ms=None, llm_ms=None, tts_ms=None)

        reply, first_token_ms, llm_ms = self._ask(user_text)

        tts_ms: float | None = None
        if reply:
            t0 = time.perf_counter()
            self.tts.speak(reply)
            self.tts.wait(timeout=120)
            tts_ms = (time.perf_counter() - t0) * 1000

        return Turn(
            user_text=user_text,
            reply_text=reply,
            asr_ms=asr_ms,
            first_token_ms=first_token_ms,
            llm_ms=llm_ms,
            tts_ms=tts_ms,
        )

    # ------------------------------------------------------------------ 内部

    def _ask(self, text: str) -> tuple[str, float | None, float | None]:
        if self.mock:
            return f"（模拟）我听到你说：{text}", None, None

        messages = [
            {"role": "system", "content": self.system_prompt},
            *self.history[-6:],
            {"role": "user", "content": text},
        ]
        reply = self.llm.chat(messages)
        self.history.extend(
            [{"role": "user", "content": text}, {"role": "assistant", "content": reply.text}]
        )
        return reply.text, reply.first_token_ms, reply.total_ms

    def close(self) -> None:
        self.tts.close()
