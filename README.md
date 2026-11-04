# VoxDesk · 桌面语音智能体

> **本地优先、断网可用**的语音助手：说一句话，它开程序、查笔记、排定时任务，把难活转给编码 agent，再把结果说出来。
>
> 本仓库放**能跑的代码**；架构、需求与决策记录在另建的文档仓（C4 图 / 60 条需求 / ADR / 里程碑验收数据）。
>
> **当前进度：M1 音频前端完成，ASR 单点跑通，下一步接本地 LLM。**

`Windows 11 x64` · `Python 3.11` · `ONNX Runtime` · `全本地推理` · `GPL-3.0`

---

## 现在做到哪了

| 阶段 | 内容 | 状态 |
| --- | --- | --- |
| **M1** 音频前端 | 采集 → 降噪 → VAD 断句 → PTT 热键 | ✅ 完成 |
| **S4** 语音识别 | sherpa-onnx 流式 Paraformer（中文） | ✅ 单点跑通 |
| **S5** 本地 LLM | Ollama + Qwen3-4B（工具调用） | ⬜ 下一步 |
| **S6** 唤醒词 | openWakeWord | ⬜ |
| **S7** 串联 | 语音 → 回答 的闭环 | ⬜ |
| M3–M6 | 工具执行 / 定时任务 / Obsidian / 音质升级 | ⬜ |

> 进度以本仓库的 git tag 为准；每个里程碑的验收项与实测数字在文档仓里逐条记录。

## 已经跑通的四个能力

| 能力 | 实测 | 怎么验 |
| --- | --- | --- |
| **断句**（VAD） | 50 句合成语料 **切错 0 条**，起点误差 64ms；静音尾 300–600ms 均可用 | `audio/scripts/accept_s3.py` |
| **降噪**（可 bypass） | 0 dB 白噪下端点错误 **1 → 0**；干净音频上略降，所以默认关 | `audio/scripts/denoise_ab.py` |
| **听写**（ASR） | 首字 **39ms**，实时因子 0.060；自有 TTS 语料 CER 24.3%（偏悲观，真人样本可读） | `audio/scripts/asr_cer.py` |
| **播报**（TTS） | 首音 **56–169ms**，实时因子 **0.026**，打断 **12–39ms** 真静音 | `tts/scripts/accept_s1.py --engine piper` |

## 目录

```
VoxDesk/
├─ audio/   端侧音频前端：采集 · 降噪 · VAD 端点 · PTT · 流式 ASR
├─ tts/     播报切片：Piper 合成 · 分句 · 缓存 · 队列 · 打断 · 引擎可替换
└─ demo/    （仅存在于 demo 分支）把上面两者拼成一轮对话的演示
```

每个目录都有自己的 README，写清了实测数据与踩过的坑：

- [`audio/README.md`](audio/README.md) — 端点/降噪的验收，以及"Silero ONNX 需要 64 点上下文"那个不报错的坑
- [`tts/README.md`](tts/README.md) — 分句/缓存/打断，以及"换引擎不改调用方"的证明（`service.py` 零改动）

## 快速验证

```powershell
# 1) 端侧音频：对着麦克风说话，终端打印每句话的起止
cd audio
uv sync
uv run python scripts/vad_live.py

# 2) 播报：让机器念一段
cd ..\tts
uv sync
uv run python scripts/say.py --engine piper --text "你好，我是 VoxDesk。"

# 3) 听写：把一个 wav 转成文本
cd ..\audio
uv run python scripts/asr_file.py out\corpus\01.wav
```

## 技术选型（一句话版）

| 层 | 选择 | 为什么 |
| --- | --- | --- |
| 语音识别 | **sherpa-onnx + Paraformer** | ONNX / CPU 可跑 / 中文流式，一个库覆盖 ASR+VAD+降噪 |
| 断句 | **Silero VAD**（2.3MB ONNX） | 32ms 帧、CPU 上 <1ms，噪声下稳定 |
| 播报 | **Piper**（piper1-gpl） | 首包最低、直接吐 WAV；实测首音 56ms |
| 降噪 | 自研谱减 + bypass | PyPI 上没有可用的 RNNoise 轮子；稳态噪声够用 |
| LLM | **Ollama + Qwen3-4B**（计划中） | 本地、OpenAI 兼容、工具调用原生 |
| 编排 | 自研 asyncio 管线 | 要展示的是编排，不是配置框架 |
| 打包 | PyInstaller | 免安装分发，模型内置 |

## 路线

- **M2 收尾**：接本地 LLM（S5）→ 唤醒词（S6）→ 端到端闭环（S7），目标"拔网线说一句话，3.5s 内听到回答"
- **M3**：工具执行（开程序 / HTTP API）+ 风险分级与二次确认
- **M4**：定时任务（cron / 延时 / 重启恢复）
- **M5**：接入 Obsidian 检索与编码 agent（harness 桥）
- **M6**：多步任务、托盘、音质升级（CosyVoice）

## 不做

| 不做 | 原因 |
| --- | --- |
| 全双工 / 回声消除 | 独立量级（AEC + 双工状态机），列为 P3 可选项 |
| 训练 / 微调模型 | 工程价值在编排与端侧落地，不在训练 |
| 图形界面（除托盘） | 交互主通道是语音 |

## 关于 demo 分支

另有一条 `demo/deepseek-voice` 分支：把 LLM 换成云端 API，拼成"语音 → 识别 → 回答 → 播报"的可运行演示（含 463MB 免安装包）。
**它不并入主线**——主线要的是离线与隐私，demo 只用于先看到对话体感。

## 许可与致谢

本仓库代码采用 **[GPL-3.0](LICENSE)**。核心原因：`tts/` 链接了 GPL-3.0 的 `piper-tts`，分发打包产物即属衍生作品。

主要依赖与许可：

| 组件 | 用途 | 许可 |
| --- | --- | --- |
| [OHF-Voice/piper1-gpl](https://github.com/OHF-Voice/piper1-gpl) | TTS 引擎 | GPL-3.0 |
| [k2-fsa/sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) | 流式 ASR 运行时 | Apache-2.0 |
| [snakers4/silero-vad](https://github.com/snakers4/silero-vad) | 端点检测 | MIT |
| [microsoft/onnxruntime](https://github.com/microsoft/onnxruntime) | 推理后端 | MIT |
| [sounddevice](https://github.com/spatialaudio/python-sounddevice) / PortAudio | 音频 I/O | MIT |
| [keyboard](https://github.com/boppreh/keyboard) | 全局热键 | MIT |
| [PyInstaller](https://pyinstaller.org/) | 打包 | GPL-2.0 + bootloader exception |

模型权重不随仓库分发（`.gitignore` 已忽略），其许可以上游模型页为准——**Piper 的中文音色许可是逐个声明的，商用前请自行核对**。

> 说明：这是个人求职项目，重点在**端侧工程与系统编排**；所有数字都来自本机实测，复现命令写在各目录 README 里。
