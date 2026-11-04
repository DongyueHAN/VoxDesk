# VoxDesk · 桌面语音助手

> 按住一个键说句话，它**听懂、回答、念出来**。全流程跑在自己的 Windows 电脑上，不依赖任何语音云服务。
>
> **实测：ASR 218ms · 首 token 681ms · 到首字 ≈1.05s · 打包后 463MB（模型内置）**

`Windows 10/11 x64` · `Python 3.11` · `ONNX Runtime` · `CPU 即可，不需要独显` · `GPL-3.0`

---

## 它是什么

一个**本地化程度很高**的语音对话应用：

- **语音不出本机**——识别（ASR）与播报（TTS）都在本地跑，模型是 226MB + 60MB 的 ONNX 文件
- **按一下就能用**——`F2` 按下说话、松开出结果，不挑窗口焦点，不装驱动
- **能打包发人**——`build.ps1` 生成 463MB 的免安装目录，双击 exe 就能跑

当前分支接的是 **DeepSeek API**（只把**文本**发出去，音频不出本机）；主线版本接本地 Ollama，可完全离线。差异见下表。

## 立刻试用

```powershell
git clone https://github.com/<you>/VoxDesk.git
cd VoxDesk\demo

uv sync                                         # 装依赖（自动装 Python 3.11）
Copy-Item .env.example .env                     # 填 DEEPSEEK_API_KEY=
uv run python scripts/voice_chat.py             # 按住 F2 说话
```

没有 key 也能先看链路：

```powershell
uv run python scripts/voice_chat.py --file ..\audio\out\corpus\01.wav --mock
```

## 能力

| 能力 | 实测 / 说明 |
| --- | --- |
| 中文流式识别 | sherpa-onnx Paraformer，**首字 218ms**，标点自动补 |
| 对话 | DeepSeek Chat，SSE 流式，**首 token 681ms** |
| 语音播报 | Piper 本地合成，**实时因子 0.026**；分句 + 缓存，同句第二次直接命中 |
| 打断 | `stop()` 后 **12–39ms** 真静音 |
| 断句（VAD） | Silero VAD，50 句验收 **切错 0 条**，起点误差 64ms |
| 降噪 | 谱减 + bypass 开关；0 dB 白噪下端点错误 **1 → 0** |
| 免安装分发 | PyInstaller 打包 **463MB**，模型内置，双击即用 |

## 它是怎么搭的

```mermaid
%% diagram: ROOT-01 整体链路 | updated: 2026-11-05
flowchart LR
    MIC(["麦克风"]) --> A["audio<br/>Silero VAD · 流式 ASR"]
    A -->|"text"| L["LLM<br/>DeepSeek API（本分支）<br/>Ollama + Qwen3（主线）"]
    L -->|"reply"| T["tts<br/>Piper · 分句 · 缓存 · 打断"]
    T --> SPK(["扬声器"])
```

三个目录各是一块可独立验收的切片：

| 目录 | 内容 | 验收 |
| --- | --- | --- |
| `audio/` | 采集、VAD 端点、降噪、PTT、流式 ASR | 50 句切错 0；首字 218ms |
| `tts/` | Piper 播报、分句、缓存、打断、引擎可替换 | 首音 56ms；打断 12ms |
| `demo/` | 把两者拼成一轮对话，LLM 适配 + 打包 | 到首字 ≈1.05s；exe 463MB |

每个目录都有自己的 README，写清了踩过的坑与实测数据：

- [`demo/README.md`](demo/README.md) — 功能、用法、后续方向
- [`audio/README.md`](audio/README.md) — 端点/降噪的实测与"64 点上下文"坑
- [`tts/README.md`](tts/README.md) — 分句/缓存/打断，以及"换引擎不改调用方"的证明

## 环境要求

| 项 | 要求 |
| --- | --- |
| 系统 | Windows 10/11 x64 |
| Python | 3.11（`uv` 自动安装） |
| 硬件 | 有麦克风即可，CPU 跑得动 |
| 网络 | 只有调 API 时需要；`--mock` 完全离线 |
| 磁盘 | 源码 + 模型约 400MB；打包产物 463MB |

## 打包成免安装应用

```powershell
cd demo
.\build.ps1
```

产物 `demo\dist\VoxDeskVoice\`：双击 `VoxDeskVoice.exe`；分发给别人时压缩整个文件夹，对方填好 `.env` 即可。

## 这个分支与主线的差异

| 项 | 本分支（demo） | 主线 |
| --- | --- | --- |
| LLM | DeepSeek API | Ollama + Qwen3-4B（离线） |
| 隐私 | 文本出本机 | 全本地 |
| 首 token | 681ms（实测） | 目标 ≤1.2s |
| 目的 | 先看到"能对话"的体感 | 按文档逐步落地 |

主线的架构、需求、选型与决策记录在**另建的文档仓**（`full-deplux dialogue system`）：C4 架构图、60 条需求、ADR 决策、以及每个里程碑的验收数据。

## 路线

- **近期**：常开麦 + VAD 自动断句（免按键）、流式播报（首段合成完就播）、`Esc` 打断
- **中期**：本地/云端一键切换、多轮记忆、工具调用（开程序 / 查天气）、托盘常驻
- **不做**：全双工与回声消除（独立量级）、自研模型、重写 GUI

## 致谢 / Acknowledgements

这个项目站在一堆开源工作的肩膀上。**没有它们的许可与文档，这条链路跑不起来**：

| 组件 | 在本项目里干什么 | 许可 |
| --- | --- | --- |
| [OHF-Voice/piper1-gpl](https://github.com/OHF-Voice/piper1-gpl) | TTS 引擎（文本 → 22.05kHz WAV） | **GPL-3.0** |
| [k2-fsa/sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) | 流式 ASR 运行时（Paraformer 推理） | Apache-2.0 |
| [snakers4/silero-vad](https://github.com/snakers4/silero-vad) | 端点检测（VAD） | MIT |
| [microsoft/onnxruntime](https://github.com/microsoft/onnxruntime) | ONNX 推理后端 | MIT |
| [PortAudio](https://www.portaudio.com/) / [sounddevice](https://github.com/spatialaudio/python-sounddevice) | 音频采集与播放 | MIT |
| [numpy](https://numpy.org/) | 帧处理与重采样 | BSD-3-Clause |
| [keyboard](https://github.com/boppreh/keyboard) | 全局热键（按住说话） | MIT |
| [pywin32](https://github.com/mhammond/pywin32) | Windows COM（SAPI 兜底引擎） | PSF-2.0 |
| [PyInstaller](https://pyinstaller.org/) | 打包成免安装 exe | GPL-2.0 + bootloader exception |

**模型权重**（不随仓库分发，`.gitignore` 已忽略）：

| 模型 | 来源 | 许可说明 |
| --- | --- | --- |
| `sherpa-onnx-streaming-paraformer-bilingual-zh-en` | k2-fsa 发布的 ONNX 转换版，源自 ModelScope `damo/speech_paraformer_asr_nat-zh-cn-…-online` | 模型页标注 Apache-2.0；**商用前请自行复核** |
| `silero_vad.onnx` | silero-vad 仓库 | MIT |
| `zh_CN-huayan-medium.onnx` | rhasspy/piper-voices 音色库 | **Piper 音色许可是逐个声明的，本仓库未逐一核对**；商用或再分发前请查该音色的 `voices.json` 条目 |

**服务依赖**：对话能力使用 [DeepSeek API](https://platform.deepseek.com/)（受其服务条款约束，仅文本出本机）。主线的本地版本用 [Ollama](https://ollama.com/) + Qwen3。

> 说句实在话：**音色许可这一格我没敢写成"MIT"或"Apache"**——Piper 的音色是社区各自发布的，仓库级 LICENSE 盖不住它们。真要商用，这一格必须逐个查。

## 许可证

**本仓库代码采用 [GPL-3.0](LICENSE)**（全文见仓库根目录的 `LICENSE`，与 gnu.org 发布版逐字一致）。

### 为什么不是 MIT

不是不想，是**不能**：

- `tts/` 与 `demo/` 直接 `import piper`（`piper-tts`，**GPL-3.0**）；
- 打包出来的 `VoxDeskVoice.exe` 把这个库连同模型一起分发，属于**分发衍生作品**；
- 那种情况下，整个分发物必须遵守 GPL-3.0（提供源码、保留许可声明）。

**写 MIT 会与事实不符**——懂行的面试官一眼就能看出"MIT 仓库里 bundle 了 GPL 引擎"是自相矛盾的。

### 这意味着什么

| 你可以 | 你需要 |
| --- | --- |
| 随便读、跑、改、自己用 | 分发时附上源码与 GPL-3.0 声明 |
| 商用（自用或内部） | 分发修改版时同样开源（传染性） |
| 二次开发后开源 | 保留原作者署名与本许可 |

### 只想复用不依赖 Piper 的部分？

`audio/` 切片（采集 / VAD / 降噪 / ASR）**不碰 Piper**，是我从零写的。如果你只想要它，
可以按 **MIT** 单独取用——在这条 issue/邮件里说明用途即可，我按 MIT 单独授权。

### 未来可能改许可

如果主线把 TTS 换成 Apache-2.0 / MIT 的引擎（`CosyVoice`、`sherpa-onnx` 自带 TTS、`MeloTTS`），
Piper 一移除，整仓就可以平移到 **Apache-2.0**。这条路径已经记在文档仓的 `08` 与 `09` 里。

## 说明

这是个人求职项目：重点在**端侧工程与系统编排**，不在训练模型。
所有数字都来自本机实测，出处与复现命令写在各目录的 README 里。
