# 08 · 开源调研：选型与拆解

| 字段 | 值 |
| --- | --- |
| 文档 | `docs/08-oss-shortlist.md` |
| 版本 | v0.5.1 |
| 状态 | 草案（仓库层筛选，未做实测） |
| 更新 | 2026-11-05 01:40 +08:00 |
| 生效范围 | 用哪些开源项目、为什么不用别的、按什么顺序读、何时停 |

> **本文并入原 `10-study-route.md`（v0.5.3，2026-10-29）**：那份文档的「读哪几站 / 三遍读法 / 何时停 / 动手边界 / 节奏」成为本文 §4–§8。
> **合并理由**：两份文档描述同一批仓库，事实（stars / 许可 / 活跃度 / 形态）却各存一份——这正是 v0.6.0 那次"三种说法"的根因。现在**一个仓库只出现一次**，选型与阅读用同一张表的两列表达。

> **数据口径**：仓库数字为 **2026-10-27** 通过 GitHub REST API 拉取的快照；TTS 补充核实在 **2026-11-05**。
> 许可取自 `license.spdx_id`，`NOASSERTION` 表示许可证文件非标准、需人工核对。
> **star 只反映关注度，不反映适配度**——「选型」与「阅读」两列才是判断。

---

## 0. 结论先行

| 需求 | 首选 | 备选 | 不选但值得读代码 |
| --- | --- | --- | --- |
| **语音转文字** | `k2-fsa/sherpa-onnx` | `modelscope/FunASR`（中文优先）、`SYSTRAN/faster-whisper`（质量优先） | `KoljaB/RealtimeSTT`（学它的 VAD 分段） |
| **系统调用原语** | `pywinauto` + `UIAutomation` | `pywin32`（Win32 API 直调） | `pyautogui`（已停更，别用） |
| **桌面 GUI agent** | `CursorTouch/Windows-MCP` | `microsoft/UFO`、`lahfir/agent-desktop` | `bytedance/UI-TARS-desktop`（读架构） |
| **CLI harness（委托对象）** | `openai/codex` | `OpenHands`、`gemini-cli` | `openinterpreter`（已转 Rust） |
| **TTS 引擎** | `piper1-gpl`（实时） | `CosyVoice`（音质，M6） | `GPT-SoVITS`（学"应用形态"） |
| **整体参考架构** | `openclaw/openclaw` | — | — |

**一句话**：STT 用 sherpa-onnx 一把梭；系统能力用"原语库自己编排 + MCP 对外暴露"；harness 先接 codex 的 CLI；TTS 用 Piper 跑通、CosyVoice 提音质。

### 0.1 五个关键发现

| # | 发现 | 影响 |
| --- | --- | --- |
| 1 | **Piper 原仓库已归档**（`rhasspy/piper`，2025-08-26），继任 `OHF-Voice/piper1-gpl` 转 **GPL-3.0**，且 README 正在**公开招募维护者** | 个人使用无碍；开源分发需评估；长期维护有风险 |
| 2 | `openWakeWord` 最近提交 2025-12-30，近一年未更新 | 唤醒方案需备选（sherpa-onnx 自带 KWS） |
| 3 | `pyautogui` 停更两年（2024-08） | 桌面自动化不能以它为主方案 |
| 4 | **MCP 已成为系统能力的事实标准**（Windows-MCP、playwright-mcp、servers 91k 星） | `CMP-04 工具运行时` 应原生支持 MCP |
| 5 | `openclaw/openclaw` 已 39.3 万星 | 参照系选对了；它的分层值得逐层拆 |

---

## 1. 语音转文字

### 1.1 引擎与框架

| 仓库 | ★ | 语言 | 许可 | 最近提交 | 选型 | 阅读 |
| --- | --- | --- | --- | --- | --- | --- |
| [k2-fsa/sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) | 15,532 | C++ | Apache-2.0 | 2026-10-26 | **首选**（ASR + TTS + VAD + 降噪 + 说话人） | 对照：只读 `examples/` 与 Python API |
| [modelscope/FunASR](https://github.com/modelscope/FunASR) | 20,831 | Python | MIT | 2026-10-22 | 备选（中文强，流式 + VAD + 标点一条龙） | 对照：`AutoModel` 组合式 API |
| [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper) | 26,194 | Python | MIT | 2026-10-25 | 备选（质量兜底，非流式） | 翻目录 |
| [KoljaB/RealtimeSTT](https://github.com/KoljaB/RealtimeSTT) | 10,211 | Python | MIT | 2026-10-23 | 不作为依赖 | **精读**：VAD + 分段逻辑 |
| [openai/whisper](https://github.com/openai/whisper) | 111,358 | Python | MIT | 2026-08-31 | 不选（参考实现，非流式，CPU 慢） | 翻目录：30 秒滑窗 + token 化多任务 |
| [ggml-org/whisper.cpp](https://github.com/ggml-org/whisper.cpp) | 54,695 | C++ | MIT | 2026-10-19 | 不选（C/C++ 移植，纯 CPU 可跑） | 翻目录 |
| [m-bain/whisperX](https://github.com/m-bain/whisperX) | 24,870 | Python | BSD-2 | 2026-10-22 | 不选（词级时间戳 + 说话人分离） | 不读 |
| [alphacep/vosk-api](https://github.com/alphacep/vosk-api) | 15,203 | Jupyter | Apache-2.0 | 2026-10-15 | 不选（老牌轻量，中文一般） | 不读 |
| [Vaibhavs10/insanely-fast-whisper](https://github.com/Vaibhavs10/insanely-fast-whisper) | 13,056 | Jupyter | Apache-2.0 | 2025-10-25 | 不选（**近一年未更新**） | 不读 |
| [wenet-e2e/wenet](https://github.com/wenet-e2e/wenet) | 5,250 | Python | Apache-2.0 | 2026-10-26 | 不选（生产级流式，工程化高） | 不读 |
| [PaddlePaddle/PaddleSpeech](https://github.com/PaddlePaddle/PaddleSpeech) | 12,698 | Python | Apache-2.0 | 2026-08-12 | 不选（中文全流程，更新变慢） | 不读 |
| [NVIDIA-NeMo/Speech](https://github.com/NVIDIA-NeMo/Speech) | 18,622 | Python | Apache-2.0 | 2026-10-27 | 不选（工业级，偏训练，重） | 不读 |

### 1.2 语音应用（读"怎么编排"，不读模型）

| 仓库 | ★ | 语言 | 许可 | 最近提交 | 形态 | 阅读 |
| --- | --- | --- | --- | --- | --- | --- |
| [yan5xu/ququ](https://github.com/yan5xu/ququ) | 2,300 | Python + Electron | Apache-2.0 | 2026-10-24 | 中文听写，FunASR + LLM 两段式 | **精读**：技术栈与本项目几乎同构 |
| [cjpais/Handy](https://github.com/cjpais/Handy) | 34,900 | Rust + Tauri | MIT | 2026-10-25 | 跨平台听写，完全离线 | **精读**：单一职责的教科书 |
| [QwenAudio/SenseVoice](https://github.com/QwenAudio/SenseVoice) | 9,600 | Python | MIT | 2026-10-20 | ASR + 情感/事件，非自回归 | 翻目录：模型如何被服务化 |
| [OpenWhispr/openwhispr](https://github.com/OpenWhispr/openwhispr) | 10,200 | TypeScript | MIT | 2026-10-26 | Electron 听写 + 会议转写 + 笔记 | 翻目录：看产品终态 |

### 1.3 判断

**首选 sherpa-onnx**，三个理由：

1. **一个库覆盖端侧全部需求**——ASR、TTS、VAD、降噪，省掉跨库胶水
2. **ONNX + C++ 核心 + Python 绑定**，CPU 不需要 GPU，与"8 GB 也能跑"一致
3. **Apache-2.0 + 持续活跃**（2026-10-26），比一堆停更的语音项目可靠

**FunASR 作中文备选**：它的 Paraformer 正是 `04-tech-stack.md` 选定的模型，流式 + VAD + 标点是完整方案；若 sherpa-onnx 中文不达标，整体切换成本可控。

**faster-whisper 作质量兜底**：非流式、延迟高，但准确率稳，适合"说完再转"的离线批处理。

**不选 whisper 原版**：PyTorch 依赖重、非流式、CPU 慢——它适合当参考实现和模型来源。

---

## 2. 系统调用与 harness

"调用系统软件接口"这件事，社区分成了四层。**理解分层比记项目名重要**：

```
┌─ 协议层 ── MCP servers / playwright-mcp        ← 把能力标准化暴露给 LLM
├─ 编排层 ── codex / OpenHands / UI-TARS         ← 决定"下一步做什么"
├─ agent 层 ─ Windows-MCP / UFO / agent-desktop   ← 看屏幕、点按钮
└─ 原语层 ── pywin32 / pywinauto / UIAutomation   ← 真正调系统 API
```

### 2.1 原语层：直接调 Windows 接口

| 仓库 | ★ | 语言 | 许可 | 最近提交 | 选型 | 阅读 |
| --- | --- | --- | --- | --- | --- | --- |
| [pywinauto/pywinauto](https://github.com/pywinauto/pywinauto) | 6,231 | Python | BSD-3 | 2026-10-23 | **首选**（窗口/控件级，UIA + Win32 双后端） | **精读**：M3 直接要用 |
| [mhammond/pywin32](https://github.com/mhammond/pywin32) | 5,633 | C++ | 无标准许可 | 2026-10-21 | 备选（Win32 全量绑定） | 对照 |
| [yinkaisheng/UIAutomation](https://github.com/yinkaisheng/Python-UIAutomation-for-Windows) | 3,592 | Python | Apache-2.0 | 2026-06-02 | 备选（UIA 轻量封装） | 翻目录 |
| [AutoHotkey/AutoHotkey](https://github.com/AutoHotkey/AutoHotkey) | 13,369 | C++ | GPL-2.0 | 2026-10-25 | 不选（可被 spawn 调用的宏脚本） | 不读 |
| [asweigart/pyautogui](https://github.com/asweigart/pyautogui) | 12,740 | Python | BSD-3 | **2024-08-20** | 不选（**停更两年**，坐标点击必错位） | 不读 |

### 2.2 桌面 agent 层：看得懂界面、点得准按钮

| 仓库 | ★ | 语言 | 许可 | 最近提交 | 选型 | 阅读 |
| --- | --- | --- | --- | --- | --- | --- |
| [CursorTouch/Windows-MCP](https://github.com/CursorTouch/Windows-MCP) | 10,459 | Python | MIT | 2026-10-26 | **首选**（MCP 计算机操作服务） | 对照 |
| [lahfir/agent-desktop](https://github.com/lahfir/agent-desktop) | 1,824 | Rust | Apache-2.0 | 2026-10-27 | 备选（**无障碍树**优先，动作可重放） | **精读**：思路最正确 |
| [microsoft/UFO](https://github.com/microsoft/UFO) | 10,096 | Python | MIT | 2026-10-23 | 备选（Windows GUI agent） | 翻目录 |
| [bytedance/UI-TARS-desktop](https://github.com/bytedance/UI-TARS-desktop) | 39,393 | TypeScript | Apache-2.0 | 2026-10-09 | 不选（TS 全家桶，体量大） | 翻目录：分层值得看 |
| [OpenAdaptAI/OpenAdapt](https://github.com/OpenAdaptAI/OpenAdapt) | 1,830 | Python | MIT | 2026-10-25 | 不选（录制→复现） | 不读 |
| [screenpipe/screenpipe](https://github.com/screenpipe/screenpipe) | 22,084 | Rust | NOASSERTION | 2026-10-27 | 不选（持续录屏 + 检索） | 不读 |

### 2.3 CLI harness 层：把复杂任务交出去

| 仓库 | ★ | 语言 | 许可 | 最近提交 | 选型 | 阅读 |
| --- | --- | --- | --- | --- | --- | --- |
| [openai/codex](https://github.com/openai/codex) | 131,073 | Rust | Apache-2.0 | 2026-10-27 | **首选**（CLI + 流式 + 非交互，适合 subprocess） | **精读**：M5 委托对象 |
| [google-gemini/gemini-cli](https://github.com/google-gemini/gemini-cli) | 108,560 | TypeScript | Apache-2.0 | 2026-10-27 | 备选 | 翻目录 |
| [OpenHands/OpenHands](https://github.com/OpenHands/OpenHands) | 91,957 | TypeScript | MIT | 2026-10-27 | 备选（全功能平台，容器化） | 不读 |
| [QwenLM/qwen-code](https://github.com/QwenLM/qwen-code) | 28,740 | TypeScript | Apache-2.0 | 2026-10-27 | 备选（中文生态友好） | 翻目录 |
| [Aider-AI/aider](https://github.com/Aider-AI/aider) | 49,770 | Python | Apache-2.0 | 2026-05-22 | 不选（diff 驱动结对编程） | 不读 |
| [SWE-agent/SWE-agent](https://github.com/SWE-agent/SWE-agent) | 20,648 | Python | MIT | 2026-10-26 | 不选（学术向，issue → patch） | 不读 |
| [openinterpreter/openinterpreter](https://github.com/openinterpreter/openinterpreter) | 68,694 | **Rust** | Apache-2.0 | 2026-10-11 | 不选（已重写为 Rust） | 不读 |

### 2.4 协议层与浏览器

| 仓库 | ★ | 语言 | 许可 | 最近提交 | 选型 | 阅读 |
| --- | --- | --- | --- | --- | --- | --- |
| [modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers) | 91,595 | TypeScript | NOASSERTION | 2026-10-27 | **首选**（MCP 官方参考实现） | 对照 |
| [microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp) | 38,682 | TypeScript | Apache-2.0 | 2026-10-22 | 备选（浏览器自动化 MCP） | 不读 |
| [openclaw/openclaw](https://github.com/openclaw/openclaw) | **393,169** | TypeScript | MIT | 2026-10-27 | **参照系**（不是依赖） | **精读**：分层逐层拆 |
| [pipecat-ai/pipecat](https://github.com/pipecat-ai/pipecat) | 16,842 | Python | BSD-2 | 2026-10-27 | 不选（会藏起编排逻辑） | 翻目录：读它的抽象 |
| [livekit/agents](https://github.com/livekit/agents) | 14,950 | Python | Apache-2.0 | 2026-10-27 | 不选（依赖 LiveKit 服务） | 不读 |
| [browser-use/browser-use](https://github.com/browser-use/browser-use) | 119,246 | Python | MIT | 2026-10-27 | 不选（浏览器专用） | 不读 |

### 2.5 判断

- **原语层**：`pywinauto` 性价比最高——UIA（现代应用）与 Win32（老应用）双后端，还能拿控件树。**不要用 pyautogui 做主方案**：坐标点击在不同 DPI / 分辨率下必然错位。
- **agent 层**：要立刻能用 → `Windows-MCP`；要稳定可控 → `agent-desktop` 的无障碍树思路，但要自己接；要学架构 → `UI-TARS` 与 `UFO`，别当依赖。
- **harness 层**：`codex` 作首个委托对象——CLI + 流式 + 非交互，Apache-2.0 干净。
- **协议层**：MCP 是事实标准，`CMP-04` 应原生支持。

---

## 3. TTS 引擎

### 3.1 候选与物种

| 仓库 | ★ | 许可 | 物种 | 中文 | 选型 | 阅读 |
| --- | --- | --- | --- | --- | --- | --- |
| [OHF-Voice/piper1-gpl](https://github.com/OHF-Voice/piper1-gpl) | 6,161 | **GPL-3.0** | 引擎（轻，ONNX 60 MB） | ✅ `zh_CN-huayan` | **首选**（S2 已上线） | **精读**：最小完整闭环 |
| [QwenAudio/CosyVoice](https://github.com/QwenAudio/CosyVoice) | 24,287 | Apache-2.0 | 引擎（全栈，0.5B） | ✅ 9 语种 + 18 方言 | 备选（**M6 音质上限**） | 对照：`cli/`、`frontend/` |
| [myshell-ai/MeloTTS](https://github.com/myshell-ai/MeloTTS) | 7,683 | MIT | 引擎 | ✅ | 备选（许可干净，**停更近两年**） | 不读 |
| [hexgrad/kokoro](https://github.com/hexgrad/kokoro) | 9,699 | Apache-2.0 | 模型 | ⚠️ 中文弱 | 备选（英文场景） | 翻目录 |
| [thewh1teagle/kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx) | 2,800 | MIT | 运行时 | ⚠️ 同上 | 备选 | 对照：ONNX 部署形态 |
| [snakers4/silero-models](https://github.com/snakers4/silero-models) | 6,162 | **CC BY-NC 4.0** | 模型库 | ❌ **无中文** | 不选（语种 + 非商用） | 翻目录：`models.yml` 的组织 |
| [RVC-Boss/GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS) | 64,830 | MIT | **应用**（WebUI + 克隆） | ✅ 中英日韩粤 | 不选（形态不对，见 §3.3） | 翻目录：看"应用形态" |
| [coqui-ai/TTS](https://github.com/coqui-ai/TTS) | 46,151 | MPL-2.0 | 框架 | — | 不选（公司已关停） | 不读 |
| [unslothai/unsloth](https://github.com/unslothai/unsloth) | 79,047 | Apache-2.0 | **训练/运行平台** | — | 不选（不合成语音） | 不读：但它能 `unsloth start dsh`，M5 可参考 |

> 另有 **`snakers4/silero-vad`**（6,000+★，MIT）——不是 TTS，是 `CMP-01` 已选定的 VAD 组件，归 `04` §3.2。

### 3.2 物种判断（先分类，再比性能）

| 物种 | 判据 | 例子 |
| --- | --- | --- |
| **引擎** | `pip install` 完就能 `synth(text) -> wav`，不拖界面 | `piper1-gpl`（CLI / Python / C++ / HTTP）；`CosyVoice`（全栈） |
| **应用** | 有 WebUI、有训练与标注流程，顺手能出声 | `GPT-SoVITS`（WebUI + 切分 + 标注 + UVR5） |
| **模型库** | 只给权重和 `apply_tts()`，前后端自己搭 | `silero-models`（`torch.hub`） |
| **训练平台** | 能把 TTS 模型训得更小更快，但不负责合成 | `unsloth` |

**唯一硬判据**：能不能直接实现 `TTSEngine.synth(text, out_path) -> None`，且不把整个 WebUI 拖进来。
五个仓库里只有 `piper1-gpl` 与 `CosyVoice` 达标；区别不在"能不能替换"，在**代价**。

### 3.3 场景对比

| 场景 | SAPI（S1） | **Piper（S2）** | CosyVoice（M6） | GPT-SoVITS | silero-models |
| --- | --- | --- | --- | --- | --- |
| 中文实时播报 | ✅ 但机械 | ✅ **CPU 最优** | ✅ 质量最优，需 GPU | ⚠️ 需 GPU | ❌ 无中文 |
| 首音 < 1.5 s | ✅ | ✅ 56–169 ms | ✅ 150 ms（GPU） | ❌ CPU RTF 0.53 | —— |
| 用自己的声音播报 | ❌ | ❌ | ✅ 零样本克隆 | ✅ 5 s 零样本 | ❌ |
| 中文质量（CER↓ / SS↑） | 低 | 中 | **1.21 / 78.0** | 高 | —— |
| 语种 | 中英 | 中英等 | **9 + 18 方言** | 中英日韩粤 | 多语种，无中文 |
| 许可 | 系统自带 | ⚠️ GPL-3.0 | ✅ Apache-2.0 | ✅ MIT | ❌ 非商用 |
| 部署 | 0 | 60 MB | 数 GB + GPU | 数 GB | 数百 MB |

> 速度数字的**唯一口径**是 `04` §3.4（首包 / RTF 实测）与本表脚注（README 原数）；两处冲突时以实测为准。

**为什么 S2 不改 GPT-SoVITS**：它的 RTF 0.028 是 **4060Ti** 的数，同一份 README 里 CPU（M4）是 **0.526**——10 秒音频要 5.3 秒合成，"首音 1.5 s"直接不成立。

**为什么现在也不改 CosyVoice**：150 ms 是 GPU + 双向流式的前提；且流式输出要先扩 `synth_chunks()`（`09` §3.3），等于把"换引擎"变成"换架构"。

**结论**：S2 维持 Piper；Piper 是"实时对话"的引擎，GPT-SoVITS 是"内容生产"的引擎，两者 RTF 差两个数量级。

### 3.4 什么情况下 CosyVoice 会变成正确答案

| 触发条件 | 用法 | 前提 |
| --- | --- | --- |
| 中文音质成为验收项 | 替换 Piper 作为默认播报 | GPU 上首包 ≤ 400 ms（`09` §11.4） |
| 要做"用我自己的声音播报" | 零样本克隆，离线预生成 + 缓存 | M6 之后，且显存够（8 GB 需与 LLM 串行） |

### 3.5 顺带核实

1. **Piper 的继任者也在招维护者**——README 顶部写着 "looking for maintainers"（2026-11-05）。`04` §10 已登记。
2. **CosyVoice 仓库 5 个月没提交**（最后 push 2026-05-25）。M6 按"当前版本可用"评估，不指望修 bug。
3. **CosyVoice 的 0.5B 与 GPT-SoVITS 的"数 GB"不是一回事**——前者单模型 0.5B（下载 1–2 GB），后者 PyTorch + 多组件。

---

## 4. 读哪几站

### 4.1 两条路，别混着走

| 路径 | 目标 | 读什么 |
| --- | --- | --- |
| **A. 语音应用**（听写、助手、转写） | 学会"怎么把引擎编排成产品" | §1.2 的四个应用 + §1.1 的 FunASR / whisper / silero-models |
| **B. TTS 引擎** | 学会"文本怎么变成声音" | §3.1 的 Piper → kokoro-onnx → CosyVoice |

本项目的 TTS 模块属于 **B 的编排层**：不需要懂声学模型，需要懂**接口边界**。

### 4.2 路径 A：七个仓库的顺序

| 顺序 | 仓库 | 为什么在这一站 | 只看什么 | 别看什么 |
| --- | --- | --- | --- | --- |
| **1** | `ququ` | 中文、Electron + Python、用 uv、技术栈几乎同构 | 目录结构、`funasr` 怎么被 Node 调用、两段式怎么串 | 前端样式、二维码 |
| **2** | `Handy` | 单一职责教科书：热键/录音/VAD/转写/粘贴各管一段 | 模块切分、状态流转、失败提示 | Rust 语法细节 |
| **3** | `FunASR` | `AutoModel(model=..., vad_model=...)` 是"引擎可插拔"范本 | 组合式 API、流式 vs 离线 | 训练脚本、benchmark |
| **4** | `SenseVoice` | 看"模型如何被服务化" | 长音频分块、并发、部署封装 | 情感/事件论文细节 |
| **5** | `whisper` | 看"参考实现"的边界 | 30 秒窗口、token 化多任务 | 模型内部 |
| **6** | `silero-models` | 看"一个仓库怎么组织多语言多版本模型" | `models.yml`、一行 API | 语种表 |
| **7** | `OpenWhispr` | 产品终态长什么样（不是教材） | 功能清单、技术栈 | 全部代码 |

**节奏**：1 精读（2–3 天）+ 2 对照（各半天）+ 其余只翻目录与 README。
**不要从 whisper 开始**——它最"不像应用"，容易让人以为语音项目就是调模型。

### 4.3 路径 B：TTS 三个站

| 顺序 | 仓库 | 学到什么 | 读哪里 |
| --- | --- | --- | --- |
| **1** | `piper1-gpl` | **最小完整闭环**：文本 → 音素 → 声学模型 → 声码器 → WAV | `src/` 的 pipeline、voices 文件组织 |
| **2** | `kokoro-onnx` | 小模型的**部署形态**：ONNX + 音色文件 + 一句 API | `kokoro_onnx/__init__.py` |
| **3** | `CosyVoice` | 工业级：流式、克隆、文本前端 | `cli/`、`frontend/` |

**为什么 Piper 第一**：它是唯一"花两小时能看懂全流程"的实现；kokoro 的模型藏在权重里，CosyVoice 在 Windows 上装不动。
**学习对象 ≠ 依赖对象**：`sherpa-onnx` 自带 TTS 也能用，它是 C++ 部署库，不必进学习主线。

---

## 5. 三遍读法（对任何仓库都适用）

| 遍 | 时长 | 做什么 | 产出 |
| --- | --- | --- | --- |
| 第一遍 | 30 分钟 | README + 目录树 + 找入口（`main` / `cli` / `__init__`） | 画出"输入从哪进、输出从哪出" |
| 第二遍 | 2 小时 | **跟一条数据走完全程**：一句文本 → … → 一个 WAV | 一张时序图（手画即可） |
| 第三遍 | 1 小时 | 只看接口与错误处理：签名、异常分支、超时 | 一份"接口契约"笔记 |

**不要逐行读**：逐行的收益在第 3 小时趋近于零，"跟一条数据"的收益是线性的。

## 6. 什么时候可以停止阅读

能**不看源码**回答这 6 个问题，就可以动手：

1. 文本进来的第一道处理是什么（清洗？正则？音素化？）
2. 单次合成的最大输入是多少，超了怎么切
3. 输出是文件还是流，采样率与位深是多少
4. 首包延迟由哪几段构成，哪段最大
5. 有哪几类失败（模型缺失、OOM、非法字符），分别怎么兜底
6. 接口边界在哪：谁拥有缓冲、谁拥有播放、谁负责中断

答不上来，说明你在读**模型内部**——回到入口文件，别往下钻。

## 7. 动手的边界：写编排层，不写模型层

| 层 | 要不要自己写 | 说明 |
| --- | --- | --- |
| 模型推理 | ❌ 绝不 | 复现 VITS/FastSpeech 是论文级工程量，且不会更好 |
| 文本前端（规范化/分句） | ✅ 要写 | 中文数字、标点、缩写，是体验的分水岭 |
| 引擎适配 | ✅ 要写 | 把不同引擎统一成 `synth(text) -> wav` |
| 播放与中断 | ✅ 要写 | 队列、flush、状态回调 |
| 缓存 | ✅ 要写 | 同一句不重复合成 |
| 服务编排 | ✅ 要写 | `speak()` / `stop()` / 事件 |

> 一句话：**开源项目给你的是"引擎"，你要造的是"管线"。**

## 8. 边读边写的节奏（按冲刺，不按周）

> 刻度对齐 `12-M1process.md`：用 `S0–S3`，**不用"第 N 周"**——周是学习刻度、冲刺是交付刻度，混用会再次出现"三份文档三种说法"。

| 冲刺 | 读 | 写 | 验收 |
| --- | --- | --- | --- |
| **S0** 出声 | 不读（SAPI 是标准库） | 环境 + SAPI 念一句话 | 耳朵听到中文 |
| **S1** 可交付 | 不读（抄 `09` §7 自己的骨架） | 切句 + 队列 + 缓存 + `stop()` | `09` §8 的 B-1..B-4 |
| **S2** 换引擎 | `piper1-gpl` 的 synthesis 入口 + voices | `PiperEngine`，调用方不改 | C-1 离线、C-2 可替换 ✅ |
| **S3** 端侧前端 | `silero-vad` API + `RealtimeSTT` 分段 | 回调 → 队列 → VAD 端点 | 50 句端点切错 < 5 条 |
| M2 之后 | FunASR 组合 API、Ollama tool calling | 接进 `CMP-07` | 首音 ≤ 2.8 s |

**读完再写 = 永远不写。** 正确顺序是"读一层、写一层、卡住了回去读"。

---

## 9. 集成路线（谁在哪一步进来）

| 里程碑 | 用到的开源项目 | 怎么用 |
| --- | --- | --- |
| M1 端侧音频 | `silero-vad`、`sounddevice`；参考 `RealtimeSTT` 的分段 | 只读代码，不直接依赖 |
| M2 模型闭环 | **`sherpa-onnx`**（ASR + 降噪）、`piper1-gpl`（TTS）、`ollama`、`openWakeWord`（KWS，2026-11-05 从 M1 移入） | 直接依赖 |
| M3 工具执行 | `pywinauto`（窗口/控件）、`pywin32`（进程） | 封装成 `ToolSpec` |
| M5 接入层 | **`openai/codex`**（CLI 委托）、`markdown` 文件直读 | `HarnessAdapter` 首个实现 |
| M6 增强 | `Windows-MCP`（MCP 暴露）、`agent-desktop`（无障碍树）、`CosyVoice`（音质） | 可选扩展 |

## 10. 未覆盖与待验证

| 项 | 说明 |
| --- | --- |
| **未做实测** | 本文只做仓库层筛选（活跃度、许可、形态），延迟与准确率数字来自 README 或本项目实测 |
| 未覆盖商业/闭源 | Azure Speech、讯飞、火山，与"本地优先"冲突 |
| 中文效果排序 | 需要自建测试集才能定论，star 不能代替 CER |
| MCP 生态稳定性 | 协议仍在演进，M3 时重新评估 |
| 许可核对深度 | 只看了仓库级 LICENSE，未逐模型/音色核对（权重许可常与代码不同） |

## 11. 采集记录

| 项 | 值 |
| --- | --- |
| 仓库快照 | 2026-10-27 14:30–14:40 +08:00 |
| TTS 补充核实 | 2026-11-05 00:18–00:45 +08:00（五份 README） |
| 接口 | GitHub REST API v3（未认证，core 60 req/h，search 10 req/min） |
| 字段 | `stargazers_count` / `license.spdx_id` / `pushed_at` / `archived` / `language` |
| 已知偏差 | `NVIDIA/NeMo` 重定向至 `NVIDIA-NeMo/Speech`；`FunAudioLLM/CosyVoice` 重定向至 `QwenAudio/CosyVoice` |
| 合并记录 | 2026-11-05 并入原 `10-study-route.md` v0.5.3（九份 README 速览见附录 A） |

---

## 附录 A · 九份 README 速览（各 ≤140 字）

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
