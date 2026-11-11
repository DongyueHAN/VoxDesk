# 04 · 开源项目与实际产品

| 字段 | 值 |
| --- | --- |
| 文档 | `docs/04-oss-and-products.md` |
| 版本 | v0.5.0 |
| 状态 | 现行 |
| 更新 | 2026-11-12 00:15 +08:00 |
| 生效范围 | 外部世界的地图 + **七个角度的取舍**。链条第 1 段：本文（事实）→ `05`（机制）→ `06`（决策） |

> **位置**：组 B · **选型链 1/3**（事实）：外面有什么、代价 → 下接 `05`

> 这份文档做两件事：**列清单**（外部有什么）+ **讲代价**（每环节怎么选、七角度横向对照）。
> 它**不替 `06` 做决定**——决定在链的第三段。
> 来源：2026-11-11 对作者收藏夹（原 87 条书签）的重分类，展示 107 条（含 20 条跨类重复）；
> 原始清单与分类口径见 `调研/Neuro整理/Neuro收藏分类整理.md`（**不入库**，见 `00-spec` §13）。

## 0. 怎么读

| 记号 | 含义 |
| --- | --- |
| **现役** | 已进 `06` 的选型，且代码仓有实现 |
| **候选** | 进过评估，未定或作备选 |
| **待评估** | 只在清单里，还没碰 |
| **已排除** | 评估后否掉，原因见 `06` §8 |
| **多类：亦见 x.x** | 同一仓库覆盖多个环节，在每类里都出现一次 |

### 0.1 七个取舍角度

`§2` 每类末尾的「怎么选」都按这七个角度写；`§4` 再把它们横向拉平成 7 张表。

| 角度 | 问什么 | 判定口径 |
| --- | --- | --- |
| **效果** | 这一环的"好"怎么度量 | CER / MOS / 唤醒率 / tool 合法率 |
| **时延** | 首字、首包、首 token | 同机实测，必须标环境 |
| **资源** | 内存 / 显存 / CPU | 常驻峰值 |
| **许可** | 能不能商用、会不会传染 | Apache / MIT / GPL / 非商业 |
| **集成成本** | 胶水代码量、依赖重量 | 几行能跑起来 |
| **可替换性** | 换掉它要不要改调用方 | 接口是否稳定、是否绑生态 |
| **维护活跃度** | 还活着吗 | 最近提交 / 发版 / 商业背书 |

> **「学习与简历价值」不单独成表**：它是本项目的真实约束，但只在个别条目里注明，
> 且**只有这一维允许"不选最优"**——必须写清理由，别让它污染另外七个角度的结论。

**时效**：本文是快照，不是承诺。star / 许可 / 活跃度都会变——引用前按 `AGENTS` §6 重测，别把本文当"最新"。

## 1. 语音链路 13 个环节与我方现状

| 环节 | 我方现状 | 落在哪 |
| --- | --- | --- |
| VAD | **现役** Silero VAD v5（ONNX） | `CMP-01` · `06` §3.2 |
| KWS | **待评估**（`REQ-F-005` 为 P1，`08` S6 未开工） | `02` F-005 |
| ASR | **现役** sherpa-onnx + Paraformer | `CMP-01` · `06` §3.7 |
| LLM | **待定**（云端 DeepSeek / 本机 Ollama 两条路） | `CMP-10` · `05` |
| TTS | **现役** Piper；确定迭代 CosyVoice2 | `CMP-07` · `06` §3.4 |
| Codec | 待评估，未进路线 | — |
| SVC（歌声转换） | 不在范围 | `01` §5 非目标 |
| 全双工 | **P3**（`ADR-0006` 半双工先行） | `02` F-008 / F-013 |
| 文本前端（TN / 标点） | 待评估，当前用 ASR 自带标点 | — |
| 评测 Eval | 部分：CER 口径与样本集已定 | `06` §3.7 |
| AI VTuber / Agent 整合 | 长期意图，不进当前里程碑 | `README` §1.1 |
| 训练与部署工具链 | 部分：PyInstaller 打包在用 | `06` §7 |
| 模型库与组织入口 | **现役** ModelScope（Paraformer 权重） | `06` §3.7 |
## 2. 开源项目与开源模型

### 2.1 VAD 语音活动检测

| 项目 | 说明 | 链接 |
| --- | --- | --- |
| silero-vad | 企业级预训练 VAD，ONNX / TorchScript 双份权重、毫秒级端点判定，基本是语音前端的默认选型。**多类：亦见 2.12** | https://github.com/snakers4/silero-vad |
| FunASR | 阿里通义系语音工具链，一条流水线内含 VAD + ASR + 标点 + 说话人分离，还能起 OpenAI 兼容 / MCP 服务。**多类：亦见 2.3、2.9** | https://github.com/modelscope/FunASR |
| FunASR 中文说明 | 上一条的中文 README，安装、服务化、流式推理示例都在这里。**多类：亦见 2.3** | https://github.com/modelscope/FunASR/blob/main/README_zh.md |
| sherpa-onnx | next-gen Kaldi + onnxruntime 的全离线工具集，VAD / ASR / TTS / 说话人 / 增强一套打通，覆盖嵌入式、Android、iOS、鸿蒙、树莓派与 12 种语言绑定。**多类：亦见 2.3、2.5、2.12** | https://github.com/k2-fsa/sherpa-onnx |
| FSMN VAD（ModelScope） | 达摩院 FSMN 端点检测，中文通用 16k，就是 FunASR 的默认 VAD 权重 | https://www.modelscope.cn/models/iic/speech_fsmn_vad_zh-cn-16k-common-pytorch |
| Paraformer 长音频版（ModelScope） | VAD + ASR + 标点三合一的 Paraformer 大模型，主打中文长音频离线识别。**多类：亦见 2.3、2.9** | https://www.modelscope.cn/models/iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch |

**怎么选**：看端点延迟与"把词切断"的平衡，以及有没有现成 ONNX 权重；准确率不是瓶颈。
**我们停在哪**：Silero VAD v5，端侧成熟、CPU 够快；代价是它要 64 样本上下文（576 点而非 512）。
**换掉它**：换 TEN-VAD 要改 Stage 的帧长假设，端点误差得重测（现有 50 句基线作废）。

### 2.2 KWS 关键词唤醒

| 项目 | 说明 | 链接 |
| --- | --- | --- |
| Saymore | Windows 纯本地中文语音输入，自带自定义唤醒词（关键词检出）+ 离线识别 + 书面润色 + 邮件整理。**多类：亦见 2.3、2.4** | https://github.com/frankzch/Saymore |

> ⚠️ 缺口：这一夹里**没有独立的 KWS 模型仓库**（Porcupine、snowboy、WeNet-KWS 之类一个都没有），只有「唤醒词」这一个功能点。要自建唤醒词得另找清单。

**怎么选**：核心成本是**误唤醒率**（不是唤醒率）；端侧常驻还带功耗与隐私代价。
**我们停在哪**：只有 PTT；`08` S6 未开工，清单里也没有独立的唤醒词模型（见 §6 缺口）。
**换掉它**：从 PTT 换成常驻 KWS，等于重定义"什么时候开始听"，`SM-01` 状态机要跟着改。

### 2.3 ASR 语音识别

| 项目 | 说明 | 链接 |
| --- | --- | --- |
| Whisper | OpenAI 的大规模弱监督多语种识别，通用基线，什么都先拿它跑一遍 | https://github.com/openai/whisper |
| SenseVoice | 小体量多语种识别（中/粤/英/日/韩），同时输出语种、情绪与音频事件，端侧友好。**多类：亦见 2.12** | https://github.com/QwenAudio/SenseVoice |
| Fun-ASR（中文说明） | QwenAudio 新一代 Fun-ASR 文档，流式与离线同源 | https://github.com/QwenAudio/Fun-ASR/blob/main/README_zh.md |
| WeNet | 工业级端到端识别工具包，中文社区自训流式模型的常用底座 | https://github.com/wenet-e2e/wenet |
| FunASR | 识别 + VAD + 标点 + 说话人分离的整条流水线，落地最省事。**多类：亦见 2.1、2.9** | https://github.com/modelscope/FunASR |
| FunASR 中文说明 | 中文文档版。**多类：亦见 2.1** | https://github.com/modelscope/FunASR/blob/main/README_zh.md |
| Paraformer 长音频版（ModelScope） | 中文长音频一站式出稿。**多类：亦见 2.1、2.9** | https://www.modelscope.cn/models/iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch |
| sherpa-onnx | 端侧识别部署首选，一套模型横跨 PC / 手机 / 嵌入式。**多类：亦见 2.1、2.5、2.12** | https://github.com/k2-fsa/sherpa-onnx |
| OpenWhispr | 桌面听写应用：本地 Parakeet / Whisper + 云端 BYOK，隐私优先、跨平台 | https://github.com/OpenWhispr/openwhispr |
| ququ | 开源免费的 Wispr Flow 替代：FunASR 本地模型 + 可配置 LLM 的中文桌面语音工作流。**多类：亦见 2.4** | https://github.com/yan5xu/ququ |
| Handy | 完全离线的开源语音转文字工具，可扩展 | https://github.com/cjpais/Handy |
| Saymore | 本地中文听写 + 润色，Windows 原生。**多类：亦见 2.2、2.4** | https://github.com/frankzch/Saymore |
| vocotype-cli | 隐私优先的端侧语音输入：快捷键实时转写并注入当前应用，支持 MCP、自定义替换词典、录音视频转写 | https://github.com/233stone/vocotype-cli |
| AtomType | Rust + Tauri 的纯离线语音输入法，主打「动口不动 code」的编码场景。**多类：亦见 2.12** | https://github.com/hu-qi/AtomType |
| FlashVoice | macOS / Windows 本地优先语音输入：端侧 SenseVoice + 全局输入 + 文件转写 + 可选 AI 校对。**多类：亦见 2.4** | https://github.com/harry0703/FlashVoice |

**怎么选**：中文口语 + 流式首字 + 全离线，三者同时满足的很少；CER 必须用**自己的样本**测。
**我们停在哪**：sherpa-onnx + Paraformer，首字 39ms；但 50 句 CER **24.3%**，未达标。
**换掉它**：换 FunASR 要重做流式边界与标点，"500ms 尾巴静音"这类坑要重踩一遍。

### 2.4 LLM 大语言模型

| 项目 | 说明 | 链接 |
| --- | --- | --- |
| unsloth | 本地运行与微调 LLM / 扩散模型的 UI，GGUF、MLX、量化加速齐活，小显存做角色 LoRA 的首选。**多类：亦见 2.12** | https://github.com/unslothai/unsloth |
| ZerolanLiveRobot | LLM 驱动的 AI VTuber：ASR / TTS / OCR / CV 全链路，能直播也能陪你打 Minecraft，目录结构值得直接抄。**多类：亦见 2.5、2.11** | https://github.com/AkagawaTsurunaki/ZerolanLiveRobot |
| AI-Vtuber | 多后端 LLM（ChatGPT / Claude / 千问 / Ollama…）驱动的虚拟主播，含 TTS 与变声编排、弹幕互动。**多类：亦见 2.5、2.7、2.11** | https://github.com/Ikaros-521/AI-Vtuber |
| ququ | FunASR 听写 → 大模型处理 → 回填的完整链路，最简「ASR + LLM」串联样例。**多类：亦见 2.3** | https://github.com/yan5xu/ququ |
| Saymore | 听写之后用 LLM 做书面润色 / 邮件整理。**多类：亦见 2.2、2.3** | https://github.com/frankzch/Saymore |
| FlashVoice | 可选 AI 校对，等于「ASR + 轻量 LLM」的最小实现。**多类：亦见 2.3** | https://github.com/harry0703/FlashVoice |
| MoneyPrinterTurbo | 大模型 + 自动化工作流，从主题 / 关键词一键生成高清短视频 | https://github.com/harry0703/MoneyPrinterTurbo |

**怎么选**：原生 tool calling > 中文口语 > 量化衰减 > 许可（完整判据见 `05` §2.2）。
**我们停在哪**：本机 Qwen3-4B 是候选、运行时尚待定；B 线用云端 DeepSeek。
**换掉它**：换模型不改调用方（`IF-08` OpenAI 兼容），但 prompt 与工具 schema 要重调。

### 2.5 TTS 语音合成

| 项目 | 说明 | 链接 |
| --- | --- | --- |
| GPT-SoVITS | 1 分钟语音即可 few-shot 克隆，社区生态最活跃的中文音色方案。**多类：亦见 3.1（整合包教程）、3.2（在线 Demo）** | https://github.com/RVC-Boss/GPT-SoVITS |
| GPT-SoVITS 模型合集（ModelScope） | 社区整合的 GPT-SoVITS 权重合集，省得自己翻底模 | https://www.modelscope.cn/models/aihobbyist/GPT-SoVITS_Model_Collection |
| CosyVoice | 多语种大语音生成模型，推理 / 训练 / 部署全栈能力 | https://github.com/QwenAudio/CosyVoice |
| Fun-CosyVoice3-0.5B-2512（ModelScope） | CosyVoice 3 的 0.5B 开源权重，官方可用版本 | https://www.modelscope.cn/models/FunAudioLLM/Fun-CosyVoice3-0.5B-2512 |
| silero-models | 开箱即用的预训练 TTS，多语言、轻量、易部署 | https://github.com/snakers4/silero-models |
| piper1-gpl | 快速本地神经 TTS 引擎，端侧 / 嵌入式实时朗读合适 | https://github.com/OHF-Voice/piper1-gpl |
| VoiceStudio | 全本地 ElevenLabs 替代：克隆、音色设计、视频配音、听写、有声书，646 种语言。**多类：亦见 2.3（转写能力）** | https://github.com/debpalash/VoiceStudio |
| Matcha-TTS | ICASSP 2024 的条件流匹配快速 TTS 架构，声学模型层面的参考 | https://github.com/shivammehta25/Matcha-TTS |
| sherpa-onnx | 自带 TTS 前端与多语言声学模型，端侧一条龙。**多类：亦见 2.1、2.3、2.12** | https://github.com/k2-fsa/sherpa-onnx |
| AI-Vtuber | 接 edge-tts / VITS / elevenlabs / bark / bert-vits2 多套 TTS，适合对比音色。**多类：亦见 2.4、2.7、2.11** | https://github.com/Ikaros-521/AI-Vtuber |
| ZerolanLiveRobot | 直播场景下的 TTS 调度与口型对齐可参考。**多类：亦见 2.4、2.11** | https://github.com/AkagawaTsurunaki/ZerolanLiveRobot |

**怎么选**：首包延迟与音质互斥；**许可坑最多**（piper1-gpl 是 GPL-3.0，会传染整个仓）。
**我们停在哪**：Piper（RTF 0.026、首音 56–169ms），音质偏平；已定迭代 CosyVoice2。
**换掉它**：CosyVoice2 要多吃 2–3GB 显存，分句策略与打断逻辑要重写。

### 2.6 语音编解码 Codec

| 项目 | 说明 | 链接 |
| --- | --- | --- |
| FunCodec | 面向研究的音频量化工具包，TTS / 音乐生成的下游基础件 | https://github.com/modelscope/FunCodec |
| AcademiCodec | 学术向开源音频编解码模型 | https://github.com/yangdongchao/AcademiCodec |

**怎么选**：只在"要不要自研流式传输/压缩"时才相关；不自研就整类跳过。
**我们停在哪**：不用——音频不出本机，单机进程内直接传 PCM，没有带宽约束。
**换掉它**：将来做远程或移动端才回来读这一类。

### 2.7 歌声转换 / 变声 SVC

| 项目 | 说明 | 链接 |
| --- | --- | --- |
| whisper-vits-svc | 歌声转换 / 歌声克隆核心引擎（whisper 内容编码 + VITS-SVC） | https://github.com/PlayVoice/whisper-vits-svc |
| AI-Song-Cover-RVC | 一站式 RVC 翻唱工具链（Colab）：扒音频、分离人声、训练、推理 | https://github.com/ardha27/AI-Song-Cover-RVC |
| 千早爱音 RVC 音色分享（B 站） | 现成 RVC 音色 + 使用演示，可直接拿来做二次元角色音色 | https://www.bilibili.com/video/BV1E5F1z6EgR/ |
| AI-Vtuber | 内置 so-vits-svc / DDSP-SVC 变声链路，直播实时变声可直接复用。**多类：亦见 2.4、2.5、2.11** | https://github.com/Ikaros-521/AI-Vtuber |

**怎么选**：与"变声 / 翻唱"绑定，不是语音助手的必需项。
**我们停在哪**：`01` §5 已列为非目标。
**换掉它**：只有做角色音色克隆才需要，属长期意图（智能生命），不进当前里程碑。

### 2.8 全双工对话语音

| 项目 | 说明 | 链接 |
| --- | --- | --- |
| SoulX-Duplug（training-code 分支） | 全双工实时对话的「流式状态预测」插件式模块，带训练代码 | https://github.com/Soul-AILab/SoulX-Duplug/tree/training-code |
| Soul AI Lab（组织） | SoulX-Duplug 及后续全双工工作的官方入口 | https://github.com/Soul-AILab |
| soulx-duplug-eval | Duplug 的评测代码与脚本 | https://github.com/time-northern/soulx-duplug-eval |
| SoulX-Duplug 模型合集（HuggingFace） | 官方权重合集，拿来就能推理 | https://huggingface.co/collections/Soul-AILab/soulx-duplug |
| fullduplex-topic-materials | 全双工交互大模型课题资料汇编（ICASSP 2026 HumDial Challenge Track 2） | https://github.com/DongyueHAN/fullduplex-topic-materials |

> 对应论文见 3.3；评测相关另见 1.10。

**怎么选**：AEC + 常开麦克风 + 双工状态机三件事一起做，是独立量级。
**我们停在哪**：`ADR-0006` 半双工先行，全双工 P3。
**换掉它**：推翻 `ADR-0006` 属方向性变更，要新 ADR + MAJOR（`00-spec` §11.2）。

### 2.9 文本前端与后处理（TN / 标点）

| 项目 | 说明 | 链接 |
| --- | --- | --- |
| chinese_text_normalization | 中文文本正则化（TN / ITN），TTS 前端和 ASR 后处理都绕不开 | https://github.com/speechio/chinese_text_normalization |
| FunASR | 流水线自带标点恢复与文本规整，可直接复用其模块。**多类：亦见 2.1、2.3** | https://github.com/modelscope/FunASR |
| Paraformer 长音频版 | 标点已内嵌进模型，长音频一次性出稿。**多类：亦见 2.1、2.3** | https://www.modelscope.cn/models/iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch |

**怎么选**：只在"TTS 念错数字/符号/英文"成为实际问题时才需要。
**我们停在哪**：用 ASR 自带的标点（Paraformer 内嵌），没有单独做 TN。
**换掉它**：换 TTS 引擎时要重看这一层——数字、英文、符号的读法各不相同。

### 2.10 评测 Eval 与数据集

| 项目 | 说明 | 链接 |
| --- | --- | --- |
| CV3-Eval | CosyVoice 3 的评测代码与指标实现 | https://github.com/QwenAudio/CV3-Eval |
| soulx-duplug-eval | 全双工状态预测的评测脚本。**多类：亦见 2.8** | https://github.com/time-northern/soulx-duplug-eval |

**怎么选**：先有**自己的样本集**，再谈指标；别人的评测脚本只能借实现，不能借结论。
**我们停在哪**：CER 口径与 30/15/15 样本集已定（`06` §3.7），但还没跑。
**换掉它**：换 ASR 或 TTS 都必须用同一套样本重测，否则数字不可比。

### 2.11 AI VTuber / Agent 整合

| 项目 | 说明 | 链接 |
| --- | --- | --- |
| ZerolanLiveRobot | 最接近 Neuro-sama 形态的开源实现：LLM + ASR + TTS + OCR + CV 全链路。**多类：亦见 2.4、2.5** | https://github.com/AkagawaTsurunaki/ZerolanLiveRobot |
| AI-Vtuber | 直播弹幕互动的虚拟主播框架，接 B 站 / 抖音 / YouTube 等平台。**多类：亦见 2.4、2.5、2.7** | https://github.com/Ikaros-521/AI-Vtuber |

> 这一类是「把 1.1–1.7 拼成一个人」的参考实现。想自研的话，先把这两个仓库的目录结构读完，再决定哪些环节自己写。

**怎么选**：这是"把前面的环境拼成一个人"的参考实现，不是可替换组件。
**我们停在哪**：只当读法参考，不进里程碑；长期意图（智能生命）挂在这里。
**换掉它**：不适用——它给的是形态，不是接口。

### 2.12 训练与部署工具链

| 项目 | 说明 | 链接 |
| --- | --- | --- |
| esaxx-rs | SentencePiece 底层后缀数组算法库（Rust 绑定），分词 / 子词训练的底层件 | https://github.com/Narsil/esaxx-rs |
| unsloth | 单卡微调 + 量化导出，角色 LoRA 的省显存方案。**多类：亦见 2.4** | https://github.com/unslothai/unsloth |
| sherpa-onnx | 端侧部署主力：一套模型跨 PC / 手机 / 嵌入式。**多类：亦见 2.1、2.3、2.5** | https://github.com/k2-fsa/sherpa-onnx |
| AtomType | Rust + Tauri 桌面壳参考：端侧模型怎么塞进安装包。**多类：亦见 2.3** | https://github.com/hu-qi/AtomType |

**怎么选**：部署形态决定工具链（PyInstaller / Tauri / docker），不是先选工具再想形态。
**我们停在哪**：PyInstaller 打包（exe 464MB），够用且不引入新语言。
**换掉它**：换 Tauri 要重写外壳，Python 侧还得留 sidecar。

### 2.13 模型库与组织入口

| 入口 | 说明 | 链接 |
| --- | --- | --- |
| ModelScope 组织 · FunAudioLLM | 通义语音系列（FunASR / CosyVoice / Fun-ASR…）官方组织页 | https://www.modelscope.cn/organization/FunAudioLLM |
| ModelScope 组织 · iic | 达摩院语音实验室组织页，Paraformer / FSMN-VAD 等基础模型都在这里 | https://www.modelscope.cn/organization/iic |
| ModelScope 首页 | 模型检索总入口 | https://www.modelscope.cn/home |
| GitHub · modelscope | ModelScope 官方代码组织 | https://github.com/modelscope |
| GitHub · QwenAudio | Qwen 音频线（SenseVoice / CosyVoice / Fun-ASR）代码组织 | https://github.com/QwenAudio |

---

**怎么选**：权重从哪来、许可怎么查、版本怎么锁——三件事比"哪个库更快"更影响长期维护。
**我们停在哪**：ModelScope 取权重 + sherpa-onnx 转换；版本靠 digest 锁。
**换掉它**：换源要重做下载脚本与 digest 校验，历史模型不可复现。

## 3. 实际产品

### 3.1 语音合成 / 配音 / 朗读

| 产品 | 说明 | 链接 |
| --- | --- | --- |
| CosyVoice 在线版 | 官方在线 TTS + 声音克隆，用来快速试音色最省事 | https://cosyvoice.org/zh/ |
| Kitta Audio | 商用 AI 配音与声音克隆平台（中文界面），有完整 API | https://kittaaudio.com/zh |
| Fish Audio | 在线 TTS + 免费语音克隆，社区音色多 | https://fish.audio/zh-CN/app/ |
| ElevenReader | ElevenLabs 的朗读 App，长文听读体验可作交互参考 | https://elevenreader.io/ |

**学**：试听与音色库的组织方式、参数暴露多少给用户。**不学**：产品与订阅。

### 3.2 开源模型在线体验（托管 Demo）

| 产品 | 说明 | 链接 |
| --- | --- | --- |
| GPT-SoVITS WebUI（HF Space） | 不装环境，浏览器里直接试 GPT-SoVITS 的克隆效果 | https://lj1995-gpt-sovits-proplus.hf.space/ |

**学**：用来快速对比音质（同一句话跑几个 Demo）。**不学**：不做依赖，随时会关站。

### 3.3 AI 内容生成（图像 / 视频）

| 产品 | 说明 | 链接 |
| --- | --- | --- |
| 即梦 AI | 字节的图像 / 视频生成，立绘、素材、短视频都能出 | https://jimeng.jianying.com/ |
| Midjourney | 高质量图像生成，立绘与场景参考 | https://www.midjourney.com/home |

**学**：只作形态参考。**不学**：与语音链路无关，不进范围。

### 3.4 通用大模型平台

| 产品 | 说明 | 链接 |
| --- | --- | --- |
| OpenAI | 模型与研究官网，API 能力与定价的基准参照 | https://openai.com/zh-Hans-CN/ |

**学**：云 API 是 B 线的现用后端。**不学**：不做平台迁移，也不引第二套 SDK。

### 3.5 待确认

| 条目 | 说明 | 链接 |
| --- | --- | --- |
| icccall（登录页） | 标题只有「登录」，页面抓取无有效内容；从域名看像呼叫 / 会议类产品，**需人工确认后归位** | https://test.icccall.com/ |

---

**学**：未归类，等有人核对归属再动。

## 4. 七个角度的横向对照

前面按环节看，这里按角度横着切。**每一格只写能拿到证据的东西**，拿不到就写"未测"。

### 4.1 效果

| 环节 | 判据 | 现状 | 目标 |
| --- | --- | --- | --- |
| ASR | 自建 50 句 CER | **24.3%** ❌ | ≤ 12%（`02` §1.10） |
| TTS | 主观 MOS | Piper 偏平 | CosyVoice2 论文 CER 1.21（**未复现**） |
| VAD | 端点误差 | 64ms / 50 句 0 误 | `archive/12` 基线 |
| KWS | 唤醒率 / 误唤醒 | **未测** | ≥95% / ≤1 次·h（`REQ-F-005`） |
| LLM | tool calling 合法率 | **未测** | ≥ 8/10（`08` S5） |

### 4.2 时延

| 指标 | 现值 | 来源 |
| --- | --- | --- |
| ASR 首字 | **39ms** | `08` S4 实测 |
| TTS 首音 | **56–169ms** | 代码仓 `STATUS.md` |
| LLM 首 token | ≈0.9s（CPU 4B，估算非实测） | `08` §3 预算 |
| 端到端首音 | ≈1.05s（demo，非全链路） | `08` §3 |
| 闸门 | S5 ≤1.2s；S7 目标 3.0s / 保底 3.5s | `08` §2、§5 |

### 4.3 资源

| 组件 | 4B 方案 | 备注 |
| --- | --- | --- |
| VAD + KWS | 0.07 GB | Silero + openWakeWord |
| ASR | 0.90 GB | Paraformer 流式 |
| TTS | 0.15 GB | Piper；换 CosyVoice2 另加 2–3GB **显存** |
| LLM | 2.5 GB | Qwen3-4B Q4_K_M |
| 运行时 + 其他 | 0.80 GB | Python / CUDA / SQLite |
| **合计** | **≈ 4.7 GB** | 16GB 机器舒适，8GB 只够 4B |

### 4.4 许可

| 组件 | 许可 | 只影响自己还是传染全仓 |
| --- | --- | --- |
| Piper（piper1-gpl） | **GPL-3.0** | **传染**——本仓因此是 GPL-3.0 |
| Silero VAD | MIT | 只影响自己 |
| CosyVoice2 | Apache-2.0 | 只影响自己 |
| Gemma3 | Gemma Terms | 非标准条款，已排除 |
| 音色 / 权重 | **逐模型核对** | 仓库级 LICENSE 不算数 |

### 4.5 集成成本

| 组件 | 装起来要几步 | 判断 |
| --- | --- | --- |
| sherpa-onnx | `pip install` + 一行推理 | 低 |
| Piper | 下 `.onnx` + `.json` + 自己写分句 | 中 |
| Ollama | 一条命令 | 低 |
| FunASR | 装 torch + 起服务 | 高 |
| CosyVoice2 | 装环境 + 吃显存 | 高 |

### 4.6 可替换性

| 接口 | 换引擎要不要改调用方 | 验证情况 |
| --- | --- | --- |
| ASR `SpeechToText` | 不改 | 已验证（zipformer → paraformer） |
| TTS `TTSEngine` | 不改 | 已验证（SAPI → Piper） |
| LLM `Chat` | 不改（OpenAI 兼容） | 待验证 |
| 唤醒词 | **要改**（与状态机耦合） | 未做 |

### 4.7 维护活跃度

| 项目 | 观察（2026-11-11） |
| --- | --- |
| sherpa-onnx | k2-fsa 主力维护，发版频繁 |
| Silero VAD | 稳定，更新慢但不影响使用 |
| Piper | 维护中；GPL 分支需注意 |
| CosyVoice | 通义团队，迭代快 |
| openWakeWord | 活跃 |

> 这一列最不可靠——**引用前重测**（`AGENTS` §6）。
## 5. 明确不学

| 不学 | 原因 |
| --- | --- |
| 唤醒词**常驻**（作为唯一入口） | 误唤醒率、功耗、隐私三重成本。**但不等于不做 KWS**：`REQ-F-005` 仍保留 P1 的可选唤醒入口，与 PTT 并存，实现在 `08` S6 |
| 多渠道接入 | 单人单机，一个入口足够；多加渠道只是增加适配工作量 |
| 多 Agent 编排 | 单任务场景用不上，且显著抬高标准 |
| 沙箱隔离 | 本机单用户，用"白名单 + 审批"性价比更高 |
| 设备生态 / 智能家居 | 需要硬件与生态，与项目目标无关 |

> 产品对照的**结论**只留在这五行；论证过程在 `adr/`（`ADR-0002` 工具注册、`ADR-0003` 调度、`ADR-0008` 委托），本文不展开。

## 6. 缺口（2026-11-11 整理时发现）

| 缺口 | 影响 | 建议动作 |
| --- | --- | --- |
| KWS 只有 1 条，**没有独立唤醒词模型** | `08` S6 没有现成件可抄 | 补 openWakeWord / Porcupine / WeNet-KWS 清单后再开 S6 |
| 缺**说话人识别 / 声纹** | `CMP-01` 无法回答"谁在说" | 单用户阶段不需要，多人场景再补（P3） |
| 缺 **AEC / 降噪**独立仓库 | `06` §3.3 只有谱减可用 | 补 RNNoise / DTLN / speexdsp 对比 |
| 缺**流式 ASR runtime** 独立件 | 现役只有 sherpa-onnx 一条路 | 与 FunASR runtime 对比后定（`06` §3.7） |
| 缺 **Live2D / 口型驱动** | "智能生命"形态缺一半（表情、口型、动作） | 只与长期意图相关，暂不排期 |

## 7. 分工与阅读链

**本仓的选型链是三段，顺序固定，不要跳读**：

```
06（本文）：外面有什么 + 各自代价      ← 事实
   ↓
07：模型这一层怎么跑起来                ← 机制
   ↓
04：现版本决定（选谁、为什么、参数）     ← 决策
```

| 文档 | 回答的问题 | 在链上的位置 |
| --- | --- | --- |
| `04`（本文） | **外面有什么**：开源件 + 实际产品 + 七个角度的代价 | 第 1 段（事实） |
| `05-model-layer.md` | **模型怎么跑**：量化、运行时、显存、工具调用可靠性 | 第 2 段（机制） |
| `06-tech-stack.md` | **我们选了谁**：结论 + 参数 + 理由 | 第 3 段（决策） |
| `02-requirements.md` | **我们要做到什么** | 链外：需求来源 |
| `03-architecture.md` | **内部怎么搭** | 链外：结构 |
| `调研/`（不入库） | 原始书签与未整理素材 | 链外：原料 |
