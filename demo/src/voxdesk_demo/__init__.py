"""临时 demo：语音 → ASR → DeepSeek → TTS。

**只在分支 `demo/deepseek-voice` 上**。主线 S5 用的是本地 Ollama + Qwen3-4B，
这里为了先跑通对话体感换成云 API，不并入 main。
"""

from .app import SYSTEM_PROMPT, Turn, VoiceChat
from .llm import ChatReply, DeepSeekChat, DeepSeekError

__all__ = ["ChatReply", "DeepSeekChat", "DeepSeekError", "SYSTEM_PROMPT", "Turn", "VoiceChat"]
__version__ = "0.1.0"
