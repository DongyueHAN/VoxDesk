# 模型与术语表（GLOSSARY）

> 给开发、答辩、交接共用。先区分“本地开源模型”和“云端非开源模型”。

## 1. 当前使用的模型 / 运行时

| 类别 | 模型 / 权重 | 运行时 | 许可 | 状态 | 说明 |
| --- | --- | --- | --- | --- | --- |
| ASR | Paraformer `sherpa-onnx-streaming-paraformer-bilingual-zh-en`（`encoder.int8.onnx` + `decoder.int8.onnx`） | `sherpa-onnx` + ONNX Runtime | Apache-2.0 | **主链路启用** | 16k 单声道、中英双语；约 237MB |
| VAD | Silero VAD v5 `silero_vad.onnx` | ONNX Runtime | 见上游 | **已放置，主链路未启用** | 约 2.3MB；当前 F2/F3 手动切分 |
| TTS | Piper `zh_CN-huayan-medium` | `piper1-gpl` + ONNX Runtime | Piper GPL-3.0；voice 许可见上游 | **主链路启用** | 22.05kHz、单女声、约 60MB |
| LLM | DeepSeek `deepseek-flash` | 云端 API | **非开源权重** | **主链路启用** | V4.1-Flash-1017；Chat Completions |
| 音色分析 | 无神经网络模型 | Python/NumPy 统计 | 本项目 | `/voice` 使用 | 80D log-mel + 频带统计；未加载 CAM++ |

补充：

- `sherpa-onnx`、`ONNX Runtime` 是推理运行时，不是模型。
- 当前**没有使用** CosyVoice、Whisper、BGE、CLIP、Qwen0.8B。
- 模型文件不随仓库分发，放在 `audio/models`、`tts/models`。
- 说话人/情绪分类：陪伴模式用 DeepSeek 极短分类调用，不加载本地情绪模型。

## 2. 术语与英文缩写

### 语音 / 音频

| 缩写 | 英文全称 | 中文全称 | 项目中的含义 |
| --- | --- | --- | --- |
| ASR | Automatic Speech Recognition | 自动语音识别 | 浏览器 PCM → 文字 |
| TTS | Text-to-Speech | 文本转语音 | 回答文字 → Piper wav |
| VAD | Voice Activity Detection | 语音活动检测 | 判断人声/静音；当前未接主链路 |
| PCM | Pulse Code Modulation | 脉冲编码调制 | 未压缩数字音频采样 |
| PCM16 | 16-bit Pulse Code Modulation | 16 位脉冲编码调制 | 16k/单声道/16bit 上传格式 |
| WAV | Waveform Audio File Format | 波形音频文件格式 | Piper 输出文件 |
| VITS | Variational Inference with adversarial learning for end-to-end Text-to-Speech | 变分推断与对抗学习的端到端语音合成 | Piper 声学模型路线 |
| Fbank | Filter Bank | 滤波器组特征 | 音色分析前端 |
| log-mel | Logarithmic Mel Spectrogram | 对数梅尔频谱 | 80D 音色特征 |
| CER | Character Error Rate | 字错误率 | ASR 评测指标 |
| RTF | Real-Time Factor | 实时率 | 处理耗时 / 音频时长 |

### 模型 / 架构

| 缩写 | 英文全称 | 中文全称 | 项目中的含义 |
| --- | --- | --- | --- |
| LLM | Large Language Model | 大语言模型 | DeepSeek `deepseek-flash` |
| API | Application Programming Interface | 应用程序编程接口 | `/api/*`、DeepSeek API |
| ONNX | Open Neural Network Exchange | 开放神经网络交换格式 | ASR/TTS 模型格式 |
| C4 | Context, Containers, Components, Code | C4 架构模型（上下文/容器/组件/代码） | 架构图分层 |
| SSE | Server-Sent Events | 服务器发送事件 | P2 流式文字输出方案 |
| RAG | Retrieval-Augmented Generation | 检索增强生成 | P3 记忆/知识扩展 |
| ADR | Architecture Decision Record | 架构决策记录 | `docs/DECISIONS.md` |
| SSRF | Server-Side Request Forgery | 服务端请求伪造 | `web_fetch` 需要防护的风险 |

### Web / 数据

| 缩写 | 英文全称 | 中文全称 | 项目中的含义 |
| --- | --- | --- | --- |
| HTTP | Hypertext Transfer Protocol | 超文本传输协议 | 浏览器 ↔ 本地服务 |
| HTTPS | Hypertext Transfer Protocol Secure | 安全超文本传输协议 | 本地服务 ↔ DeepSeek |
| JSON | JavaScript Object Notation | JavaScript 对象表示法 | 会话文件格式 |
| UUID | Universally Unique Identifier | 通用唯一识别码 | 会话文件名 |
| UI | User Interface | 用户界面 | 浏览器对话界面 |

> 战队名（BLG、DK、T1、KC）不是通用缩写；答辩演示中出现的 LPL/LCK/BO5/S16 属于电竞语境，不应写进工程术语。
