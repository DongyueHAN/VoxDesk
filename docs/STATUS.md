# 实现状态

> 最后对齐：2026-11-05 · 版本 v1.0 · 以 `git tag` 与本文表格为准。
> 里程碑定义在文档仓 `docs/05-roadmap.md`；本文只记"现在真正跑着什么、数字是多少"。

## 1. 里程碑进度

| 阶段 | 内容 | 状态 |
| --- | --- | --- |
| **M0** | 立项、范围、架构基线 | ✅ |
| **M1** | 音频前端（采集 / 降噪 / VAD 端点 / PTT） | ✅ 完成 |
| **M2** | S4 识别 ✅ · S5 本地 LLM ⬜ · S6 唤醒词 ⬜ · S7 串联 ⬜ | 🟡 进行中（1/4） |
| M3–M7 | 工具执行 / 调度 / 知识接入 / 多步任务 / 音质升级 | ⬜ 未开工 |

## 2. 已实现功能（可复现）

| 模块 | 功能 | 实测数字 | 复现命令 |
| --- | --- | --- | --- |
| `tts` | SAPI 合成（兜底引擎） | RTF 0.009 | `uv run python scripts/accept_s1.py --engine sapi` |
| `tts` | Piper 合成（主力） | 首音 **56–169ms**，RTF **0.026** | `uv run python scripts/bench_engines.py` |
| `tts` | 分句 + 缓存 + 队列 | 同句第二次命中缓存（不重合成） | `uv run python scripts/accept_s1.py` |
| `tts` | 打断 | **12–39ms** 真静音 | 同上（`stop()` 段） |
| `audio` | 采集（回调式，16k 单声道） | 32ms 帧，无丢帧 | `uv run python scripts/vad_live.py` |
| `audio` | VAD 端点 | 50 句语料 **切错 0**，起点误差 64ms | `uv run python scripts/accept_s3.py` |
| `audio` | 降噪（谱减 + bypass） | 0dB 白噪下切错 1 → 0 | `uv run python scripts/denoise_ab.py` |
| `audio` | PTT 全局热键 | 按住即录，松开停 | `uv run python scripts/vad_live.py --ptt f2` |
| `audio` | 流式 ASR | 首字 **39ms**，RTF 0.060，CER 24.3%* | `uv run python scripts/asr_cer.py` |
| `demo` | 一轮对话（ASR→LLM→TTS） | 首 token **681ms**，到首字 **≈1.05s** | `cd demo && uv run python scripts/demo_one.py` |
| `demo` | 系统声音输入（loopback） | 抓到播报音频，峰值 0.97 | `uv run python scripts/voice_chat.py --source loopback --seconds 4` |
| `demo` | 打包 | onedir **464MB**，双击可运行 | `cd demo && .\build.ps1` |

\* CER 24.3% 是在**自有 TTS 语料**上测的（音色单一，偏悲观）；真人语料未系统评测。

测试：`tts` 13 个、`audio` 15 个单元测试，全绿。

## 3. 未实现（按优先级）

| 项 | 阻塞在哪 | 计划 |
| --- | --- | --- |
| **本地 LLM（S5）** | 未接 Ollama；无工具调用 | M2 下一项，目标首 token ≤1.2s |
| **唤醒词（S6）** | 未选型落地 | 可滑到 M3 |
| **端到端串联（S7）** | 依赖 S5 | 目标"说一句话 3.5s 内听到回答" |
| 会话网关（CMP-02） | 未开工 | 半双工状态机 + 通道仲裁 |
| 工具执行（CMP-04） | 未开工 | 风险分级 + 二次确认 |
| 任务调度（CMP-06） | 未开工 | cron / 延时 / 重启恢复 |
| 知识接入（CMP-12） | 未开工 | Obsidian 检索 |
| 托盘控制台（CMP-08） | 未开工 | 看得见它在干嘛 |

## 4. 已知技术债

| 债 | 影响 | 处理建议 |
| --- | --- | --- |
| `demo` 只有一轮对话 | 多轮会丢上下文 | 加滚动摘要 + 6 条历史上限 |
| 拒绝路径未做 | 识别为空时只是跳过 | 加"没听清"话术 |
| ASR 模型 226MB | 首次启动慢（~0.5s 加载） | 可换小模型或常驻 |
| 单元测试不覆盖 `demo` | 改动靠手测 | 补 `VoiceChat` 的假引擎测试 |
| 打包 464MB | 分发体积大 | 模型外置 + 首次下载 |

## 5. 下一步（可直接开工）

1. **S5 本地 LLM**：Ollama 起 `qwen3:4b`，写 `OllamaChat` 实现 `chat()`，接进 `VoiceChat`；验收首 token ≤1.2s + 10 条指令工具调用合法 ≥8。
2. **S7 串联**：常开麦（VAD 自动断句）+ 播报期间不采集；验收端到端 ≤3.5s。
3. **多轮**：把 `VoiceChat.history` 换成摘要 + 窗口。
4. **补测试**：`demo` 用假 LLM + 假 TTS 跑通 `handle_audio`。

每项的验收口径与预算见文档仓 `docs/13-M2process.md`。
