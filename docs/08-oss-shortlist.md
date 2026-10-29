# 08 · 开源项目选型清单

| 字段 | 值 |
| --- | --- |
| 文档 | `docs/08-oss-shortlist.md` |
| 版本 | v0.3.3 |
| 状态 | 草案（仓库层筛选，未做实测） |
| 更新 | 2026-10-29 15:10 +08:00 |
| 生效范围 | 语音转文字（STT）与系统调用（harness）的开源候选 |

> **数据口径**：2026-10-27 通过 GitHub REST API 逐仓库拉取，star / 许可 / 最近提交均为当时快照。
> 许可字段取自 GitHub API 的 `license.spdx_id`，`NOASSERTION` 表示许可证文件非标准、需人工核对。
> **star 数只反映关注度，不反映适配度**——下面的"结论"列才是判断。

---

## 0. 结论先行

| 需求 | 首选 | 备选 | 不选但值得读代码 |
| --- | --- | --- | --- |
| **语音转文字** | `k2-fsa/sherpa-onnx` | `modelscope/FunASR`（中文优先）、`SYSTRAN/faster-whisper`（质量优先） | `KoljaB/RealtimeSTT`（学它的 VAD 分段） |
| **系统调用原语** | `pywinauto` + `UIAutomation` | `pywin32`（Win32 API 直调）、AutoHotkey（脚本化） | `pyautogui`（已停更） |
| **桌面 GUI agent** | `CursorTouch/Windows-MCP` | `microsoft/UFO`、`lahfir/agent-desktop` | `bytedance/UI-TARS-desktop`（体量大，读架构） |
| **CLI harness（委托对象）** | `openai/codex` | `OpenHands`、`google-gemini/gemini-cli` | `openinterpreter`（已转 Rust 重写） |
| **协议层** | `modelcontextprotocol/servers` | `microsoft/playwright-mcp` | `browser-use`（浏览器专用） |
| **整体参考架构** | `openclaw/openclaw` | — | — |

**一句话**：STT 用 sherpa-onnx 一把梭（ASR + TTS + VAD + 降噪都在里面）；系统能力用"原语库自己编排 + MCP 对外暴露"；harness 先接 codex 的 CLI。

---

## 1. A 类：语音转文字

### 1.1 端到端引擎（拿来即用）

| 项目 | Stars | 语言 | 许可 | 最近提交 | 定位 |
| --- | --- | --- | --- | --- | --- |
| [openai/whisper](https://github.com/openai/whisper) | 111,358 | Python | MIT | 2026-08-31 | 参考实现，非流式，GPU 友好 |
| [ggml-org/whisper.cpp](https://github.com/ggml-org/whisper.cpp) | 54,695 | C++ | MIT | 2026-10-19 | C/C++ 移植，纯 CPU 可跑，含流式示例 |
| [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper) | 26,194 | Python | MIT | 2026-10-25 | CTranslate2 加速，CPU 上最快之一 |
| [m-bain/whisperX](https://github.com/m-bain/whisperX) | 24,870 | Python | BSD-2 | 2026-10-22 | 词级时间戳 + 说话人分离 |
| [alphacep/vosk-api](https://github.com/alphacep/vosk-api) | 15,203 | Jupyter | Apache-2.0 | 2026-10-15 | 轻量离线，老牌，中文模型一般 |
| [Vaibhavs10/insanely-fast-whisper](https://github.com/Vaibhavs10/insanely-fast-whisper) | 13,056 | Jupyter | Apache-2.0 | 2025-10-25 | 批处理加速，**已近一年未更新** |
| [k2-fsa/sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) | 15,532 | C++ | Apache-2.0 | 2026-10-26 | **ASR + TTS + VAD + 降噪 + 说话人** 全家桶 |
| [KoljaB/RealtimeSTT](https://github.com/KoljaB/RealtimeSTT) | 10,211 | Python | MIT | 2026-10-23 | **VAD + 流式 STT 一体化**，最贴近本项目形态 |

### 1.2 中文优先的框架

| 项目 | Stars | 语言 | 许可 | 最近提交 | 定位 |
| --- | --- | --- | --- | --- | --- |
| [modelscope/FunASR](https://github.com/modelscope/FunASR) | 20,831 | Python | MIT | 2026-10-22 | 中文强，**流式 ASR + VAD + 标点** 一条龙 |
| [wenet-e2e/wenet](https://github.com/wenet-e2e/wenet) | 5,250 | Python | Apache-2.0 | 2026-10-26 | 生产级流式，工程化程度高 |
| [PaddlePaddle/PaddleSpeech](https://github.com/PaddlePaddle/PaddleSpeech) | 12,698 | Python | Apache-2.0 | 2026-08-12 | 中文全流程（ASR/TTS/标点） |
| [NVIDIA-NeMo/Speech](https://github.com/NVIDIA-NeMo/Speech) | 18,622 | Python | Apache-2.0 | 2026-10-27 | 工业级框架，重，偏训练 |

### 1.3 选型判断

**首选 sherpa-onnx**，三个理由：

1. **一个库覆盖我们端侧的全部需求**——ASR、TTS、VAD、降噪（`speech enhancement`），省掉跨库胶水
2. **ONNX + C++ 核心，Python 绑定**，CPU 上不需要 GPU，与"8GB 机器也能跑"的目标一致
3. **Apache-2.0 + 持续活跃**（最近提交 2026-10-26），比一堆停更的 TTS 项目可靠

**FunASR 作为中文备选**：它的 Paraformer 正是我们 `04-tech-stack.md` 里选定的模型，流式 + VAD + 标点是一套完整方案。若 sherpa-onnx 的中文效果不达标，整体切 FunASR 的成本可控。

**faster-whisper 作为质量兜底**：非流式、延迟高，但准确率稳，适合"说完再转"的离线批处理场景（如整理会议记录）。

**不选 whisper 原版**：PyTorch 依赖重、非流式、CPU 慢——它更适合当参考实现和模型来源。

> **注意**：`04-tech-stack.md` 里写的是"Paraformer + sherpa-onnx"，本文档验证了这个组合的两个上游都活跃，结论不变。

---

## 2. B 类：系统调用与 harness

"调用系统软件接口"这件事，开源社区分成了四层。理解分层比记项目名重要：

```
┌─ 协议层 ── MCP servers / playwright-mcp        ← 把能力标准化暴露给 LLM
├─ 编排层 ── codex / OpenHands / UI-TARS         ← 决定"下一步做什么"
├─ agent 层 ─ Windows-MCP / UFO / agent-desktop   ← 看屏幕、点按钮
└─ 原语层 ── pywin32 / pywinauto / UIAutomation   ← 真正调系统 API
```

### 2.1 原语层：直接调 Windows 接口

| 项目 | Stars | 语言 | 许可 | 最近提交 | 能力 |
| --- | --- | --- | --- | --- | --- |
| [pywinauto/pywinauto](https://github.com/pywinauto/pywinauto) | 6,231 | Python | BSD-3 | 2026-10-23 | **窗口/控件级操作**，支持 UIA 与 Win32 两种后端 |
| [mhammond/pywin32](https://github.com/mhammond/pywin32) | 5,633 | C++ | 无标准许可 | 2026-10-21 | Win32 API 全量绑定（进程、注册表、COM） |
| [yinkaisheng/UIAutomation](https://github.com/yinkaisheng/Python-UIAutomation-for-Windows) | 3,592 | Python | Apache-2.0 | 2026-06-02 | 微软 UIAutomation 的轻量封装 |
| [AutoHotkey/AutoHotkey](https://github.com/AutoHotkey/AutoHotkey) | 13,369 | C++ | GPL-2.0 | 2026-10-25 | 宏与自动化脚本（可被我们 spawn 调用） |
| [asweigart/pyautogui](https://github.com/asweigart/pyautogui) | 12,740 | Python | BSD-3 | **2024-08-20** | 坐标级鼠标键盘，**已停更两年** |

**判断**：`pywinauto` 是性价比最高的原语——它同时支持 UIA（现代应用）与 Win32（老应用），且能拿到控件树。**不要用 pyautogui 做主方案**：坐标点击在不同 DPI / 分辨率下必然错位。

### 2.2 桌面 agent 层：看得懂界面、点得准按钮

| 项目 | Stars | 语言 | 许可 | 最近提交 | 定位 |
| --- | --- | --- | --- | --- | --- |
| [CursorTouch/Windows-MCP](https://github.com/CursorTouch/Windows-MCP) | 10,459 | Python | MIT | 2026-10-26 | **Windows 上的 MCP 计算机操作服务**，开箱即用 |
| [microsoft/UFO](https://github.com/microsoft/UFO) | 10,096 | Python | MIT | 2026-10-23 | 微软的 Windows GUI agent（UFO³） |
| [lahfir/agent-desktop](https://github.com/lahfir/agent-desktop) | 1,824 | Rust | Apache-2.0 | 2026-10-27 | **走无障碍树**而非截图，动作可重放 |
| [OpenAdaptAI/OpenAdapt](https://github.com/OpenAdaptAI/OpenAdapt) | 1,830 | Python | MIT | 2026-10-25 | 录制人类操作 → 复现 |
| [bytedance/UI-TARS-desktop](https://github.com/bytedance/UI-TARS-desktop) | 39,393 | TypeScript | Apache-2.0 | 2026-10-09 | 多模态 GUI agent 全家桶（模型 + 客户端） |
| [screenpipe/screenpipe](https://github.com/screenpipe/screenpipe) | 22,084 | Rust | NOASSERTION | 2026-10-27 | 持续录屏 + 检索，做"记忆"用 |

**判断**：

- 要**立刻能用** → `Windows-MCP`（MCP 协议，直接挂到任意支持 MCP 的 harness 上）
- 要**稳定可控** → `agent-desktop` 的"无障碍树优先、截图兜底"思路最正确，但要自己接
- 要**学架构** → `UI-TARS-desktop` 与 `UFO` 的分层值得读，但别把它们当依赖（体量大、技术栈是 TS）

### 2.3 CLI harness 层：把复杂任务交出去

| 项目 | Stars | 语言 | 许可 | 最近提交 | 定位 |
| --- | --- | --- | --- | --- | --- |
| [openai/codex](https://github.com/openai/codex) | 131,073 | Rust | Apache-2.0 | 2026-10-27 | 终端里的编码 agent，**最适合当委托对象** |
| [google-gemini/gemini-cli](https://github.com/google-gemini/gemini-cli) | 108,560 | TypeScript | Apache-2.0 | 2026-10-27 | 同形态，Google 系 |
| [OpenHands/OpenHands](https://github.com/OpenHands/OpenHands) | 91,957 | TypeScript | MIT | 2026-10-27 | 全功能 agent 平台，可跑在容器里 |
| [openinterpreter/openinterpreter](https://github.com/openinterpreter/openinterpreter) | 68,694 | **Rust** | Apache-2.0 | 2026-10-11 | 已重写为 Rust，"给开源模型的编码 agent" |
| [Aider-AI/aider](https://github.com/Aider-AI/aider) | 49,770 | Python | Apache-2.0 | 2026-05-22 | 结对编程，diff 驱动 |
| [QwenLM/qwen-code](https://github.com/QwenLM/qwen-code) | 28,740 | TypeScript | Apache-2.0 | 2026-10-27 | 中文生态友好 |
| [SWE-agent/SWE-agent](https://github.com/SWE-agent/SWE-agent) | 20,648 | Python | MIT | 2026-10-26 | 学术向，issue → patch |

**判断**：`codex` 作首个委托对象。理由是 CLI + 流式输出 + 非交互模式，适合被 `subprocess` 驱动；且 Apache-2.0 干净。

### 2.4 协议层与浏览器

| 项目 | Stars | 语言 | 许可 | 最近提交 | 定位 |
| --- | --- | --- | --- | --- | --- |
| [modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers) | 91,595 | TypeScript | NOASSERTION | 2026-10-27 | MCP 官方参考实现集合 |
| [microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp) | 38,682 | TypeScript | Apache-2.0 | 2026-10-22 | 浏览器自动化 MCP server |
| [browser-use/browser-use](https://github.com/browser-use/browser-use) | 119,246 | Python | MIT | 2026-10-27 | 浏览器 agent 库，生态最大 |
| [pipecat-ai/pipecat](https://github.com/pipecat-ai/pipecat) | 16,842 | Python | BSD-2 | 2026-10-27 | 语音 agent 框架（我们不用，但读它） |
| [livekit/agents](https://github.com/livekit/agents) | 14,950 | Python | Apache-2.0 | 2026-10-27 | 实时语音 agent 框架，依赖 LiveKit 服务 |
| [openclaw/openclaw](https://github.com/openclaw/openclaw) | **393,169** | TypeScript | MIT | 2026-10-27 | 我们的整体参照系 |

---

## 3. 五个关键发现

| # | 发现 | 影响 |
| --- | --- | --- |
| 1 | **Piper 原仓库已归档**（`rhasspy/piper`，2025-08-26），继任 [`OHF-Voice/piper1-gpl`](https://github.com/OHF-Voice/piper1-gpl) 改为 **GPL-3.0** | TTS 选型要重新评估许可；个人使用无碍，开源分发需注意 |
| 2 | `openWakeWord` 最近提交 2025-12-30，近一年未更新 | 唤醒词方案需备选（sherpa-onnx 自带 KWS） |
| 3 | `pyautogui` 停更两年（2024-08） | 桌面自动化不能以它为主方案 |
| 4 | **MCP 已成为系统能力的事实标准**（Windows-MCP、playwright-mcp、servers 91k 星） | 我们的 `CMP-04 工具运行时` 应原生支持 MCP |
| 5 | `openclaw/openclaw` 已 39.3 万星 | 参照系选对了；它的分层值得逐层拆 |

### 3.1 TTS 备选（顺带核实）

| 项目 | Stars | 许可 | 最近提交 | 备注 |
| --- | --- | --- | --- | --- |
| [QwenAudio/CosyVoice](https://github.com/QwenAudio/CosyVoice) | 24,144 | Apache-2.0 | 2026-05-25 | 效果最好，吃资源，M6 目标 |
| [OHF-Voice/piper1-gpl](https://github.com/OHF-Voice/piper1-gpl) | 6,044 | **GPL-3.0** | 2026-10-25 | 延迟最低，许可需注意 |
| [myshell-ai/MeloTTS](https://github.com/myshell-ai/MeloTTS) | 7,683 | MIT | 2024-12-24 | 许可干净，但停更近两年 |
| [hexgrad/kokoro](https://github.com/hexgrad/kokoro) | 9,699 | Apache-2.0 | 2025-08-06 | 音质好，中文音色少 |
| [coqui-ai/TTS](https://github.com/coqui-ai/TTS) | 46,151 | MPL-2.0 | 2024-08-16 | 公司已关停，仅作参考 |

**建议**：M1 仍用 piper1-gpl（个人使用不涉及分发，GPL 无实际约束），但在 `04-tech-stack.md` 标注许可风险；若将来要开源，切 CosyVoice（Apache-2.0）或 MeloTTS（MIT）。

### 3.2 按语言各选一个首选（2026-10-28 复核）

| 语言 | 首选 | 备选 | 为什么 |
| --- | --- | --- | --- |
| **英文** | [hexgrad/kokoro](https://github.com/hexgrad/kokoro)（9.7k★，Apache-2.0）+ 运行时 [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx)（2.8k★，MIT，2026-09 仍更新） | piper1-gpl | 82M 参数，音质/体积比最好，CPU 可实时；主仓库 2025-08 后停更，但权重稳定、ONNX 运行时活着 |
| **中文** | [QwenAudio/CosyVoice](https://github.com/QwenAudio/CosyVoice)（24.2k★，Apache-2.0，2026-05 更新） | MeloTTS（MIT，CPU 可跑） | 中文效果第一梯队，支持流式与零样本克隆；代价是 0.5B 模型，CPU 实时性差 |

**两点提醒**：

1. **Kokoro 的中文支持很弱**——它解决的是"英文播报"，不解决本项目的中文主场景
2. **CosyVoice 在无独显的机器上 RTF 可能 > 1**（比实时慢），演示会卡；纯 CPU 时先用 MeloTTS 或 sherpa-onnx 自带的 `vits-zh` 顶住，M6 再上 CosyVoice

> 另：`2noise/ChatTTS`（40.0k★，中文很"口语化"）代码为 **AGPL-3.0**，若将来开源分发需评估传染性，故未列入首选。

---

## 4. 与工程文档的联动

| 文档 | 需要的改动 | 状态 |
| --- | --- | --- |
| `04-tech-stack.md` §3.4 | Piper 行改为 piper1-gpl，标注 GPL-3.0 与原仓库归档 | ✅ 本次已改 |
| `04-tech-stack.md` §10 | 风险表补"TTS 许可与维护性" | ✅ 本次已改 |
| `02-requirements.md` REQ-C-004 | 许可核对范围从"模型"扩到"模型 + 语音引擎" | ⚪ 评审后不改：原文"模型与组件"已覆盖引擎 |
| `03-architecture.md` §3 | `CMP-04` 的定位补一句"原生支持 MCP" | ⚪ 评审后不改：MCP 经 `ToolSpec` 适配进 `IF-03`，不改变分层 |
| 同伴仓库 `papers_archive/_evaluation_scripts/` | 16 个 HumDial 评测脚本纳入本文档候选 | ⚪ 2026-10-29 决定**不进**：`08` 是工程选型清单，评测脚本属调研资产（见 `11` §8） |
| `09-tts-module.md` §1.1 | 引擎表与本文档冲突（写的是 sherpa-onnx 为目标） | ✅ 2026-10-29 已改：改为"上线 piper1-gpl / 音质上限 CosyVoice" |
| `09-tts-module.md` §3 | 协议只支持文件输出，装不下流式引擎 | ✅ 2026-10-29 已补 §3.3 边界说明 |

---

## 5. 集成路线（谁在哪一步进来）

| 里程碑 | 用到的开源项目 | 怎么用 |
| --- | --- | --- |
| M1 端侧音频 | `silero-vad`、`openWakeWord`、`sounddevice`；参考 `RealtimeSTT` 的分段逻辑 | 只读代码，不直接依赖 |
| M2 模型闭环 | **`sherpa-onnx`**（ASR + 降噪）、`piper1-gpl`（TTS）、`ollama` | 直接依赖 |
| M3 工具执行 | `pywinauto`（窗口/控件）、`pywin32`（进程） | 封装成 `ToolSpec` |
| M5 接入层 | **`openai/codex`**（CLI 委托）、`markdown` 文件直读 | `HarnessAdapter` 首个实现 |
| M6 增强 | `Windows-MCP`（MCP 暴露）、`agent-desktop`（无障碍树方案） | 可选扩展 |

---

## 6. 未覆盖与待验证

| 项 | 说明 |
| --- | --- |
| **未做实测** | 本文档只做仓库层筛选（活跃度、许可、形态），没有跑过延迟与准确率 |
| 未覆盖商业/闭源 | Azure Speech、讯飞、火山等，与"本地优先"定位冲突 |
| 中文效果排序 | 需要自建测试集才能定论，star 数不能代替 CER |
| MCP 生态的稳定性 | 协议仍在演进，需在 M3 时重新评估 |
| 许可核对深度 | 只看了仓库级 LICENSE，未逐模型/音色核对（权重许可常与代码不同） |

---

## 7. 采集记录

| 项 | 值 |
| --- | --- |
| 采集时间 | 2026-10-27 14:30–14:40 +08:00 |
| 接口 | GitHub REST API v3（未认证，core 60 req/h，search 10 req/min） |
| 请求数 | 约 45 次仓库查询 + 3 次搜索 |
| 字段 | `stargazers_count` / `license.spdx_id` / `pushed_at` / `archived` / `language` |
| 已知偏差 | `NVIDIA/NeMo` 已重定向至 `NVIDIA-NeMo/Speech`；`FunAudioLLM/CosyVoice` 已重定向至 `QwenAudio/CosyVoice` |
