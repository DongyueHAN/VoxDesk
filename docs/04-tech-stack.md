# 04 · 技术栈

| 字段 | 值 |
| --- | --- |
| 文档 | `docs/04-tech-stack.md` |
| 版本 | v0.1.0 |
| 状态 | 草案 |
| 更新 | 2026-10-20 12:12 +08:00 |
| 生效范围 | 选型、替代方案、不选的理由 |

> 选型原则：**单机能跑、依赖可控、每一层都能换**。不追求"最先进"，追求"讲得清为什么"。

---

## 1. 总览

| 层 | 选型 | 备选 | 理由 |
| --- | --- | --- | --- |
| 语言 | Python 3.11+ | Node/TS、Go | 语音与 LLM SDK 生态最全；原型迭代快 |
| 音频采集 | `sounddevice` | `pyaudio` | 基于 PortAudio，Windows 下稳定，异步友好 |
| VAD | `silero-vad` | `webrtcvad` | 准确率明显更好，ONNX 推理无需 GPU |
| 热键 | `keyboard` | `pynput` | 全局热键最简单；需要管理员权限的场景另说 |
| ASR | 云厂商流式接口 | `faster-whisper`（本地） | 云侧首字更快；本地版留作离线降级 |
| LLM | OpenAI 兼容接口（DeepSeek / Qwen / GPT） | 本地 Ollama | 一套 SDK 多家可用，切换零成本 |
| 工具协议 | 内置 Tool Registry + JSON Schema | MCP | 见 ADR-0002：先内置，MCP 作扩展 |
| TTS | `edge-tts` 起步 | 火山 / Azure / 本地 | 免费、音色自然、无需备案；商用再换 |
| 调度 | APScheduler + SQLAlchemy JobStore | 自研轮询、Celery | 单机 cron 够用；Celery 属过度设计 |
| 存储 | SQLite + SQLModel | PostgreSQL | 单机零运维；SQLModel 兼顾 ORM 与 Pydantic |
| 配置 | `pydantic-settings` + `.env` | YAML | 类型校验 + 环境变量覆盖 |
| 日志 | `loguru`（JSON sink） | 标准 logging | 结构化日志开箱即用 |
| 托盘 | `pystray` + `Pillow` | PyQt | 只做状态与菜单，轻量优先 |
| 测试 | `pytest` + 录制回放（mock LLM） | — | 语音链路必须能脱网回归 |

## 2. 分层说明

### 2.1 接入层（可替换点）

三个适配器接口，全部只依赖抽象：

```
ASRProvider.speech_to_text(stream) -> AsyncIterator[str]
LLMProvider.chat(messages, tools) -> Decision | AsyncIterator[str]
TTSProvider.speak(text_stream) -> PlaybackHandle
```

换厂商 = 换实现类 + 改一行配置。**这是整个技术栈里最该守住的设计**。

### 2.2 执行层

- 工具用 `dataclass` 声明：`name / description / parameters(JSON Schema) / risk / handler`
- 启动进程用 `subprocess.Popen`，不 `shell=True`（防注入）
- 文件操作限定在工作目录白名单内，越界直接拒绝
- 所有执行包一层超时（默认 30s）

### 2.3 编排层

- LLM 用 **function calling**，而非让模型输出自由文本再正则——后者在中文口语上极不稳定
- 系统提示词外置为模板文件，便于 A/B 对比
- 上下文策略：最近 N 轮原文 + 更早内容的滚动摘要（避免 token 爆炸）

### 2.4 调度层

- APScheduler 的 `SQLAlchemyJobStore` 直接复用同一个 SQLite 文件
- 延时任务用 `DateTrigger`，周期任务用 `CronTrigger`
- **重启恢复**是硬指标：`misfire_grace_time` + 启动时补跑漏掉的任务

## 3. 明确不选的东西

| 不选 | 原因 |
| --- | --- |
| 微服务 / 消息队列 | 单机单用户，拆服务只会增加故障面 |
| Electron / Web 前端 | 交互主通道是语音，GUI 只做托盘 |
| LangChain 全家桶 | 抽象层过厚，调试困难；核心链路自己写反而更短 |
| 本地大模型（初期） | 8GB 内存跑不出可用体验，云端 API 更现实 |
| 唤醒词（初期） | 误唤醒与常驻功耗是独立课题，PTT 足够验证链路 |
| Docker | 需要访问宿主机的程序与音频设备，容器化得不偿失 |

## 4. 依赖风险

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| 云 ASR 限流/涨价 | 主链路不可用 | 保留 `faster-whisper` 本地实现 |
| `edge-tts` 非官方接口 | 随时可能失效 | 抽象成 `TTSProvider`，备选火山/Azure |
| 全局热键被安全软件拦截 | 无法唤起 | 提供托盘点击与快捷键双入口 |
| 麦克风独占 | 采集失败 | 启动时自检并给出明确提示 |
| Windows 中文路径 | 文件操作异常 | 全链路用 `pathlib`，不拼字符串 |
