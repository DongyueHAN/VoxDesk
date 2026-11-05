# VoxDesk · 桌面语音智能体（代码仓）

> 本地优先的语音助手：说一句话，它听懂、回答、念出来；后续目标是开程序、查笔记、排定时任务。
> **本仓库只放能跑的代码。** 架构设计与决策记录在另一个文档仓（见文末）。

| 项 | 值 |
| --- | --- |
| 版本 | **v1.0**（2026-11-05） |
| 已实现 | `tts` 播报切片 · `audio` 音频前端（采集/降噪/VAD/PTT/ASR） · `demo` 一轮对话 + 免安装打包 |
| 未实现 | 本地 LLM（Ollama）、会话网关、工具执行、调度、唤醒词 |
| 目标机 | Windows 11 · 16GB RAM · RTX 4060 Laptop 8GB |

## 它现在能做什么

| 能力 | 实测 | 怎么验 |
| --- | --- | --- |
| **断句**（Silero VAD） | 50 句语料切错 **0** 条，起点误差 64ms | `cd audio && uv run python scripts/accept_s3.py` |
| **降噪**（谱减，可 bypass） | 0dB 白噪下端点错误 1 → 0；干净音频上略降，默认关 | `uv run python scripts/denoise_ab.py` |
| **听写**（sherpa-onnx 流式 Paraformer） | 首字 **39ms**，RTF 0.060，自有 TTS 语料 CER 24.3% | `uv run python scripts/asr_cer.py` |
| **播报**（Piper） | 首音 **56–169ms**，RTF **0.026**，打断 **12–39ms** 真静音 | `cd tts && uv run python scripts/accept_s1.py --engine piper` |
| **一轮对话**（仅 demo 分支） | 到首字 **≈1.05s**（ASR 218ms + 首 token 681ms + 合成） | `cd demo && uv run python scripts/demo_one.py` |
| **免安装打包**（仅 demo 分支） | PyInstaller onedir，**464MB**，模型内置，双击运行 | `cd demo && .\build.ps1` |

## 架构（实现视角）

```mermaid
%% diagram: IMPL-01 代码层数据流 | updated: 2026-11-05
flowchart LR
    MIC["麦克风 / loopback"] --> CAP["audio.capture<br/>16k 单声道 · 32ms 帧"]
    CAP --> DEN["audio.denoise<br/>谱减 · 可 bypass"]
    DEN --> VAD["audio.vad + segmenter<br/>端点检测"]
    VAD --> ASR["audio.asr<br/>StreamingASR"]
    ASR --> APP["demo.app<br/>一轮编排"]
    APP --> LLM["demo.llm<br/>DeepSeek / 未来 Ollama"]
    LLM --> TTS["tts.service<br/>分句 · 缓存 · 队列"]
    TTS --> PLAY["tts.player<br/>播放 + 打断"]
    PLAY --> SPK([扬声器])
```

三个包职责与接口契约见 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)。

## 目录

```
VoxDesk/
├─ tts/      播报切片：TTSEngine 协议 · SAPI/Piper 双引擎 · 分句 · 缓存 · 打断
├─ audio/    音频前端：采集 · 降噪 · VAD 端点 · PTT · 流式 ASR
├─ demo/     把上面两者拼成一轮对话（仅 demo 分支）：LLM 适配 · CLI · 打包
└─ docs/     给人和 agent 的实现文档：架构 / 状态 / 交接
```

每个切片自带 `README.md`（实现细节与实测数据）与 `tests/`。

## 快速开始

```powershell
git clone https://github.com/DongyueHAN/VoxDesk.git
cd VoxDesk

# 1) 装依赖（uv 会自动装 Python 3.11）
cd audio; uv sync; cd ..\tts; uv sync; cd ..

# 2) 下载模型（约 290MB；国内自动走 hf-mirror）
cd demo; uv sync; uv run python scripts\fetch_models.py

# 3) 验证（任选其一）
cd ..\audio; uv run python scripts\vad_live.py           # 对着麦克风说话，打印断句
cd ..\tts;   uv run python scripts\say.py --text "你好"   # 让它念一句
```

模型不随仓库分发：ASR 的 `encoder.int8.onnx` 有 157.8MB，超过 GitHub 单文件 100MB 限制。

## 分支约定

| 分支 | 用途 | 内容 |
| --- | --- | --- |
| `master` | 主线：本地 Ollama + 离线 | `tts/` `audio/` |
| `demo/deepseek-voice` | 演示：云端 LLM + 一轮对话 + 打包 | 额外含 `demo/` |

演示分支不并入主线（主线要离线与隐私）。差异与取舍见 [`demo/README.md`](demo/README.md)。

## 文档导航

接手这个仓库时按顺序读：

| 顺序 | 文件 | 给谁 | 内容 |
| --- | --- | --- | --- |
| 1 | 本文件 | 人 | 是什么、能做什么、怎么跑 |
| 2 | [`AGENTS.md`](AGENTS.md) | agent | 规则、入口、禁止事项、验证命令 |
| 3 | [`docs/STATUS.md`](docs/STATUS.md) | 人 + agent | 已实现/未实现、实测数字、下一步 |
| 4 | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | 人 + agent | 模块、接口、数据流、不变式 |
| 5 | [`docs/HANDOFF.md`](docs/HANDOFF.md) | agent | 交接清单、已知坑、未决问题 |

**为什么做这个项目**、范围与非目标、需求池、选型理由、ADR —— 在另一个文档仓
（`full-deplux dialogue system`，本地 `D:\Obsidian\Geist\Project\full-deplux dialogue system`）。

## 许可

[GPL-3.0](LICENSE)：`tts/` 链接了 GPL-3.0 的 `piper-tts`，分发打包产物即属衍生作品。
上游组件与模型许可见 [`docs/HANDOFF.md`](docs/HANDOFF.md) 第 5 节。
