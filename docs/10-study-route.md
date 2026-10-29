# 10 · 开源项目拆解路线

| 字段 | 值 |
| --- | --- |
| 文档 | `docs/10-study-route.md` |
| 版本 | v0.5.3 |
| 状态 | 草案 |
| 更新 | 2026-10-29 15:10 +08:00 |
| 生效范围 | 如何拆解一个语音类开源项目、按什么顺序读、何时停止阅读 |

---

## 0. 先纠一个偏：这批仓库里只有 2 个是 TTS

| 仓库 | 实际类别 | 一句话 |
| --- | --- | --- |
| `openai/whisper` | **ASR 模型** | 参考实现，30 秒滑窗 + token 化多任务 |
| `OpenWhispr/openwhispr` | **ASR 应用（产品）** | 听写 + 会议转写 + 笔记 + 云同步，Electron 全家桶 |
| `QwenAudio/SenseVoice` | **ASR + 情感/事件** | 非自回归，快，中粤英日韩 |
| `cjpais/Handy` | **ASR 应用（桌面）** | 热键 → VAD → Whisper/Parakeet → 粘贴，单一职责 |
| `modelscope/FunASR` | **ASR 工具包** | 工业级，VAD/标点/说话人可组合 |
| `snakers4/silero-models` | **TTS 模型仓库** | 含 TTS，但**不含中文**，且 CC BY-NC 4.0 |
| `yan5xu/ququ` | **ASR 应用（中文）** | 中文听写，FunASR + LLM 两段式 |
| `QwenAudio/CosyVoice` | **TTS 引擎** | LLM 式 TTS，9 语种 + 18 方言，零样本克隆 |
| `snakers4/silero-vad` | **VAD 组件** | 端点检测，30ms 块 <1ms，TorchScript / ONNX |

**结论**：清单主体是「**语音应用**」的阅读阶梯，另有两个引擎/组件（CosyVoice、silero-vad）。
只想要 TTS，直接走 §3；只想要 VAD，`silero-vad` 就是本项目 `CMP-01` 的既定选择。

### 0.1 九份 README 速览（各 ≤140 字）

| 仓库 | 总结 |
| --- | --- |
| `whisper` | OpenAI 通用语音识别模型，MIT。单 Transformer 以 token 化多任务统一识别、翻译、语种判定；六档模型 39M–1.55G，30 秒滑窗推理，依赖 PyTorch 与 ffmpeg，提供 CLI 与 Python API。 |
| `OpenWhispr` | Electron 桌面听写应用，MIT。热键说话即在上光标处粘贴，可本地（whisper.cpp / sherpa-onnx）或云端转写；另含 AI agent、会议转写与说话人分离、笔记协作与 MCP 接口。 |
| `SenseVoice` | QwenAudio 的语音基础模型，MIT。非自回归端到端，支持中粤英日韩识别，兼做情感识别与音频事件检测；较 Whisper-Small 快 5 倍以上，附微调脚本与多语言服务化部署。 |
| `Handy` | Rust + Tauri 的跨平台听写应用，MIT，完全离线。热键录音，Silero VAD 滤静音，Whisper（GPU）或 Parakeet（CPU）转写，结果直接粘贴到当前输入框。 |
| `FunASR` | 阿里工业级语音识别工具包，MIT。覆盖离线、流式与边缘部署；VAD、标点、说话人、情感模型可按 `AutoModel` 组合，提供 OpenAI 兼容服务与多语言客户端。 |
| `silero-models` | Silero 的 TTS 模型仓库（v3–v5），一行代码调用、CPU 推理快、音色多；覆盖俄语及突厥、高加索、印度语系等，无中文；许可 CC BY-NC 4.0，仅限非商用。 |
| `ququ` | 面向中文的开源听写工具，Wispr Flow 免费替代。Electron 界面 + 本地 FunASR（Paraformer、FSMN-VAD、CT-Transformer）识别，再由可配置 LLM 润色纠错，F2 唤醒、自动粘贴，Apache-2.0。 |
| `CosyVoice` | 阿里 FunAudioLLM 的 LLM 式 TTS，Apache-2.0。CosyVoice3（0.5B）覆盖 9 语种与 18+ 中文方言，支持零样本克隆、双向流式（150ms）、拼音/CMU 发音修正与指令控制。 |
| `silero-vad` | Silero 的预训练语音活动检测器，MIT、体积小。30ms 音频块单线程耗时不足 1ms，提供 TorchScript 与 ONNX 两种后端；一行 `get_speech_timestamps` 即可得到语音区间。 |

## 1. 两条路，别混着走

| 路径 | 目标 | 该读什么 |
| --- | --- | --- |
| **A. 语音应用**（听写、助手、转写） | 学会"怎么把引擎编排成产品" | 上面那 7 个 |
| **B. TTS 引擎** | 学会"文本怎么变成声音" | Piper / kokoro-onnx / CosyVoice |

你当前的项目（VoxDesk 的 TTS 模块）属于 **B 的编排层**：不需要懂声学模型，需要懂**接口边界**。

## 2. 路径 A：七个仓库的阅读顺序

| 顺序 | 仓库 | 为什么在这一站 | 只看什么 | 别看什么 |
| --- | --- | --- | --- | --- |
| **1** | `ququ`（2.3k★） | 中文、Electron + Python、用 uv、和你技术栈几乎同构 | 目录结构、`funasr` 服务怎么被 Node 调用、"两段式"（ASR→LLM）怎么串 | 前端样式、微信二维码那些 |
| **2** | `Handy`（34.9k★） | 单一职责的教科书：热键/录音/VAD/转写/粘贴各管一段 | 模块切分、状态流转、失败提示 | Rust 语法细节（读不懂不影响理解结构） |
| **3** | `FunASR`（20.9k★） | `AutoModel(model=..., vad_model=...)` 是"引擎可插拔"的范本 | 组合式 API、流式 vs 离线两条路径 | 训练脚本、benchmark 复现 |
| **4** | `SenseVoice`（9.6k★） | 看"模型如何被服务化"（长音频分块、并发、部署） | 长音频分段策略、服务封装 | 情感/事件识别的论文细节 |
| **5** | `whisper`（111k★） | 看"参考实现"的边界，理解为什么要另写 whisper.cpp | 30 秒窗口、token 化的多任务设计 | PyTorch 模型内部 |
| **6** | `silero-models`（6.1k★） | 看"一个仓库怎么组织多语言多版本模型"（`models.yml`） | 模型注册表、一行 API 的设计 | 俄语/突厥语语种表 |
| **7** | `OpenWhispr`（10.2k★） | 产品终态长什么样；但它不是教材 | 功能清单、技术栈（whisper.cpp + sherpa-onnx + llama.cpp） | 全部代码 |

**节奏建议**：1 精读（ququ，2–3 天）+ 2 对照（Handy、FunASR，各半天）+ 其余只翻目录与 README。
**不要**从 whisper 开始——它是最"不像应用"的那个，容易让人误以为语音项目就是调模型。

## 3. 路径 B：TTS 的三个站

| 顺序 | 仓库 | 学到什么 | 读哪里 |
| --- | --- | --- | --- |
| **1** | `rhasspy/piper` → `OHF-Voice/piper1-gpl` | **最小完整闭环**：文本 → 音素 → 声学模型 → 声码器 → WAV | `src/` 的 pipeline、`voices.json` 的组织 |
| **2** | `thewh1teagle/kokoro-onnx` | 现代小模型的**部署形态**：ONNX + 音色文件 + 一句 API | `kokoro_onnx/__init__.py`、模型加载 |
| **3** | `QwenAudio/CosyVoice` | 工业级：流式、克隆、前端文本正则 | `cosyvoice/cli/`、`frontend/` |

**为什么 Piper 第一**：它是唯一一个"你花两小时能看懂全流程"的 TTS 实现；kokoro 的模型代码藏在权重里，CosyVoice 的依赖在 Windows 上装不动。

> **学习对象 ≠ 依赖对象。** `09` 的阶段 C 用 `piper1-gpl` 落地，但若不想引入第二个引擎，`sherpa-onnx` 自带的 TTS 也能用。它是 C++ 部署库，**不必进这条学习主线**——读 `examples/` 与 Python API 就够。

## 4. 三遍读法（对任何仓库都适用）

| 遍 | 时长 | 做什么 | 产出 |
| --- | --- | --- | --- |
| 第一遍 | 30 分钟 | 读 README + 目录树 + 找入口文件（`main` / `cli` / `__init__`） | 画出"输入从哪进、输出从哪出" |
| 第二遍 | 2 小时 | **跟一条数据走完全程**：一句文本 → … → 一个 WAV | 一张时序图（手画即可） |
| 第三遍 | 1 小时 | 只看接口与错误处理：函数签名、异常分支、超时 | 一份"接口契约"笔记 |

**不要逐行读。** 逐行读的收益在第 3 小时趋近于零，而"跟一条数据"的收益是线性的。

## 5. 什么时候可以停止阅读、开始写？

能**不看源码**回答下面 6 个问题，就可以动手了：

1. 文本进来的第一道处理是什么（清洗？正则？音素化？）
2. 单次合成的最大输入是多少，超了怎么切
3. 输出是文件还是流，采样率与位深是多少
4. 首包延迟由哪几段构成，哪段最大
5. 有哪几类失败（模型缺失、OOM、非法字符），分别怎么兜底
6. 接口边界在哪：谁拥有缓冲、谁拥有播放、谁负责中断

答不上来，说明你在读**模型内部**——回到入口文件，别往下钻。

## 6. 动手的边界：写编排层，不写模型层

| 层 | 你要不要自己写 | 说明 |
| --- | --- | --- |
| 模型推理 | ❌ 绝不 | 复现 VITS/FastSpeech 是论文级工程量，且不会更好 |
| 文本前端（规范化/分句） | ✅ 要写 | 中文数字、标点、缩写，是真实体验的分水岭 |
| 引擎适配 | ✅ 要写 | 把不同引擎统一成 `synth(text) -> wav` |
| 播放与中断 | ✅ 要写 | 队列、flush、状态回调 |
| 缓存 | ✅ 要写 | 同一句不重复合成 |
| 服务编排 | ✅ 要写 | `speak()` / `stop()` / 事件 |

> 一句话：**开源项目给你的是"引擎"，你要造的是"管线"。**

## 7. 边读边写的最小节奏

| 周 | 读 | 写 | 验收 |
| --- | --- | --- | --- |
| 第 1 周 | ququ 的目录 + 入口 | 自己的 `TTSEngine` + `Player` 骨架（SAPI） | 能播报、能停止 |
| 第 2 周 | Piper 的 pipeline | 切句 + 队列 + 缓存 | 500 字首声 < 1.5s |
| 第 3 周 | `piper1-gpl` 的入口与 voices 文件 | 换引擎（不改调用方） | 拔网线仍可用 |
| 第 4 周 | FunASR 的组合 API | 把 TTS 接进 CMP-07 | 与主链路对齐 |

**读完再写 = 永远不写。** 正确顺序是"读一层、写一层、卡住了回去读"。
