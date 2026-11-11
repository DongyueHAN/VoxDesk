# VoxDesk

> 一个跑在自己电脑上的**多模态助手**：**两入口 · 一脑子 · 三出口**。
> 说话或截屏进来，接本地知识库与大模型，声音出去、形象同步动、该动手时动手。

## 这个项目要做什么（Intent）

```
入口 ① ASR  语音 → 文本   ┐
入口 ② OCR  图像 → 文本   ┘→  脑子：LLM + 本地知识库  →  出口 ① TTS   说（可定制音色）
                                                        出口 ② 皮套人 演
                                                        出口 ③ 类 agent 做
```

**现在的实现进度：只有“说”这一路（入口 ① → 脑子 → 出口 ①）跑通了。**
看（OCR）、演（皮套人）、做（agent 输出）都还停在规范阶段，代码未落地——见 [`docs/system/docs/08-M2process.md`](docs/system/docs/08-M2process.md) §0 的进度看板。

完整意图与边界：[`docs/system/docs/01-scope.md`](docs/system/docs/01-scope.md)；
需求 93 条：[`docs/system/docs/02-requirements.md`](docs/system/docs/02-requirements.md)；
架构 14 组件：[`docs/system/docs/03-architecture.md`](docs/system/docs/03-architecture.md)。

## 这个仓有两个区

| 区 | 路径 | 放什么 | 谁读 |
| --- | --- | --- | --- |
| **规范区** | `docs/system/` | Intent / 范围 / 需求 / 架构 / 选型链 / 路线 / 决策 / 分工 | 想改设计的人、agent 开工前 |
| **实现区** | `docs/impl/` | 状态、坑、实现决策、开发流程、发布说明 | 要改代码的人 |
| **代码** | 仓根 | `server.py`、`voice_app.py`、`static/` … | — |

> 一条规矩：**同一事实只写在一边**。实测数字与接口签名在 `docs/impl/`；规范与决策在 `docs/system/`。

## 项-值

| 项 | 值 |
| --- | --- |
| 项目 | **VoxDesk**（当前实现：VoxDesk-Web） |
| 版本 | **w0.6** |
| 形态 | 本地 Web 应用：浏览器 + 单进程 Python 服务 |
| 生成模型 | DeepSeek **`deepseek-flash`**（V4.1-Flash-1017） |
| ASR | Paraformer（sherpa-onnx，16k 单声道） |
| TTS | Piper `zh_CN-huayan-medium`（本地 ONNX） |
| 技术栈 | Python 标准库 `http.server` + 原生 HTML/CSS/JS |
| 页面 | `/` 语音对话 · `/voice` 声纹可视化 |
| 会话存储 | 本机 JSON：`data/chats`、`data/archive` |
| 存储上限 | 30 活跃 / 100 归档 / 单会话 1MB |
| 运行环境 | Windows 10/11；Chrome / Edge；Python 3.11 |
| 启动 | `.\start.ps1`，默认 `http://127.0.0.1:8800/` |
| 联网工具 | `web_search` / `web_fetch`（DeepSeek Search/Fetch API） |
| 许可 | 继承上游 GPL-3.0 代码；第三方依赖见“许可” |

## 它现在能做什么

- **通用模式**：会话列表、消息流、文字输入、麦克风、桌面音频、朗读/联网开关。
- **陪伴模式**：同一套存储和接口，但文字输入隐藏，只允许语音。
- **语音输入**：
  - `F2` **按住**麦克风说话，松开自动停止并发送；
  - `F3` **按一下开始、再按一下停止**桌面音频；
  - 热键仅在页面聚焦时有效，也可直接点按钮。
- **多轮对话**：服务端按 `conversation_id` 读取历史，语音和文字轮次都会保存。
- **联网回答**：模型调用 `web_search` / `web_fetch`，回答带可点击来源；
  时间、新闻等实时问题不注入服务端时钟，也不预制答案。
- **朗读**：默认开启，可关闭；Piper 生成 wav，浏览器播放，可停止。
- **本地会话**：刷新/重启后保留；支持归档、恢复、删除；
  30 活跃 / 100 归档 / 单会话 1MB，归档满自动清理最旧归档。
- **声纹可视化**：`/voice` 展示希尔伯特波形、音色映射和伪残影。

### 实测（本机）

| 环节 | 数值 |
| --- | --- |
| ASR（6.5s 音频） | 868–953ms；首字 98–154ms |
| 文本对话 | 1.2–1.6s（LLM 0.9–1.3s） |
| TTS（5–6s 语音） | 0.38–0.90s |
| 新闻类实时检索 | 约 6s；1 轮工具 |
| 时钟问题 | 约 18s；search + fetch 两轮 |
| 冷启动 | ASR 约 0.9s + TTS 3.5–3.8s |

### 当前边界

- 回答是整段返回，**没有 token 流式输出**，也还没有 barge-in。
- 浏览器不能注册系统级全局热键；F2/F3 仅在页面聚焦时有效。
- 桌面音频依赖 `getDisplayMedia`，需要共享时勾选“系统音频”。
- ASR 未接自动 VAD，准确率尚未用自有语料重新验收。
- 单用户、无鉴权；模型和 Python 环境目前偏本机，换机需要额外准备。

## 架构

```text
┌──────────────────────────── 浏览器 ────────────────────────────┐
│ static/app.html + app.css + app.js                             │
│   ├─ 文字输入 / F2 麦克风 / F3 桌面音频                        │
│   ├─ WebAudio：重采样 16k、单声道、PCM16                       │
│   └─ fetch API + <audio> 播放 wav                              │
└───────────────┬────────────────────────────────────────────────┘
                │ HTTP / JSON / PCM
┌───────────────▼──────────────── 本地 Python 单进程 ────────────┐
│ server.py       路由、静态资源、/api/*                         │
│ voice_app.py    ASR → LLM → 存储 → TTS 编排                    │
│ llm.py          deepseek-flash + 工具循环（≤ 3 轮）            │
│ search.py       Search/Fetch API 执行 + 缓存 + cache-bust      │
│ store.py        data/chats、data/archive、30/100/1MB           │
│ prompts.py      system prompt + web 工具 schema                │
│ timbre.py       音色分析（/voice）                             │
└───────┬──────────────────────┬──────────────────────┬──────────┘
        │                      │                      │
        ▼                      ▼                      ▼
  本地 ASR/TTS 模型        DeepSeek API          data/*.json
  audio/models            Chat Completions      chats / archive
  tts/models              Search / Fetch
```

一次 `/api/chat` 的路径：

```text
POST /api/chat
  → VoiceApp.chat
  → 读最近多轮历史
  → prompts.system_prompt(mode)
  → deepseek-flash
       ├─ 需要实时信息：web_search → web_fetch → sources
       └─ 不需要：直接回答
  → 追加 user/assistant 到 data/chats/<id>.json
  → speak=true：Piper 合成 out/<id>.wav
  → 返回 {reply, sources, audio, timings}
```

关键边界：

- 音频、ASR/TTS 模型、会话 JSON 在本地；
- 只有文本和检索 query 出网；
- TTS 引擎串行化，JSON 使用 `tmp + os.replace` 原子写；
- 工具循环最多 3 轮，来源去重。

## 目录

```text
VoxDesk-Web/
├─ server.py              HTTP 路由、静态资源、/api/*
├─ voice_app.py           ASR → LLM → 存储 → TTS 编排
├─ llm.py                 DeepSeek Chat 客户端 + 工具循环
├─ search.py              Search / Fetch API 执行
├─ store.py               会话 JSON、上限、归档
├─ prompts.py             系统提示词 + 工具 schema
├─ paths.py               本仓库模型 / 数据路径
├─ timbre.py              音色分析
├─ loopback.py            WASAPI loopback（桌面音频备选）
├─ start.ps1              启动脚本
├─ requirements.txt       Python 依赖清单
├─ static/
│  ├─ app.html / app.css / app.js   语音对话应用
│  └─ voice.html                    声纹可视化
├─ audio/                 ASR 源码 + 模型（结构不变）
├─ tts/                   TTS 源码 + 模型（结构不变）
├─ data/                  会话与归档（gitignore）
├─ docs/
│  ├─ system/             规范区：Intent / 需求 / 架构 / 选型 / 路线 / 决策 / 分工（13 份）
│  └─ impl/               实现区：状态、坑、实现决策、开发流程、发布
└─ out/                   运行时 wav / 临时产物（gitignore）
```

## 快速开始

### 1. 准备环境

- Windows 10/11
- Python 3.11
- Chrome / Edge 最新版
- 约 289MB 的 ASR/TTS 模型（仓库不提交模型）

```powershell
cd D:\VoxDesk-Web
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

如果本机已有可用环境，`start.ps1` 会优先使用本目录 `.venv`，否则回退到
`D:\VoxDesk\demo\.venv`。

### 2. 放好模型

```text
audio/models/sherpa-onnx-streaming-paraformer-bilingual-zh-en/
audio/models/silero_vad.onnx
tts/models/zh_CN-huayan-medium.onnx
```

模型不随仓库分发；从已有基线复制或按上游说明下载。

### 3. 配置 DeepSeek Key

在项目根目录创建 `.env`：

```dotenv
DEEPSEEK_API_KEY=sk-...
```

也可以使用 `D:\VoxDesk\demo\.env` 中已有的 key。

### 4. 启动

```powershell
.\start.ps1
```

打开：

```text
http://127.0.0.1:8800/
```

健康检查：

```text
http://127.0.0.1:8800/api/health
```

正常应包含：

```json
{
  "ok": true,
  "default_model": "deepseek-flash",
  "api_key": true,
  "asr_loaded": true,
  "tts_loaded": true
}
```

### 5. 试用

1. 输入“你好，用一句话介绍你自己”，按 Enter；
2. 按住 `F2` 说一句话，松开；
3. 关闭“朗读”，按 `F3` 开始桌面录音，再按一次停止；
4. 打开“联网”，问“现在是北京时间几点？”，等待来源；
5. 刷新页面，确认会话仍在；
6. 切换“陪伴”模式，确认只能语音输入。

## 文档阅读顺序（开发者 / Agent）

### 先读规范区（决定“该不该做、做成什么样”）

| 顺序 | 文档 | 解决什么 |
| --- | --- | --- |
| S1 | [`docs/system/README.md`](docs/system/README.md) | 文档区门面：四组 13 份怎么读 |
| S2 | [`docs/system/docs/01-scope.md`](docs/system/docs/01-scope.md) | 做什么、不做什么、**两入口三出口** |
| S3 | [`docs/system/docs/03-architecture.md`](docs/system/docs/03-architecture.md) | 14 个组件、10 个接口、8 条流程 |
| S4 | [`docs/system/docs/11-decisions.md`](docs/system/docs/11-decisions.md) | 什么还悬着（`DEC-0xx`）——动架构前必查 |

### 再读实现区（决定“怎么改代码”）

> 这是正常开发仓库，不是一次性 demo。先读文档，再改代码；不要只看 README 就直接开工。

| 顺序 | 文档 | 解决什么 | 什么时候读 |
| --- | --- | --- | --- |
| 1 | [`README.md`](README.md) | 项目是什么、能做什么、怎么跑 | 每次开工前 |
| 2 | [`docs/impl/ARCHITECTURE.md`](docs/impl/ARCHITECTURE.md) | 数据流、接口、存储、线程模型 | 改任何链路前 |
| 3 | [`docs/impl/STATUS.md`](docs/impl/STATUS.md) | 当前能力、实测数字、已知缺口 | 判断“现在到底能做什么” |
| 4 | [`docs/impl/PITFALLS.md`](docs/impl/PITFALLS.md) | 46 个坑与修正 | 改音频/模型/前端/存储前 |
| 5 | [`docs/impl/PLAN.md`](docs/impl/PLAN.md) | P1 结果、P2/P3 优先级 | 排期和拆任务前 |
| 6 | [`docs/impl/DEVELOPING.md`](docs/impl/DEVELOPING.md) | 正常开发流程：分支、测试、依赖、发布 | 写第一行代码前 |
| 7 | [`docs/impl/SECURITY.md`](docs/impl/SECURITY.md) | 密钥、隐私、SSRF、数据、许可 | 动网络/文件/密钥前 |
| 8 | [`docs/impl/DECISIONS.md`](docs/impl/DECISIONS.md) | 关键架构决策与取舍 | 想改架构/换模型前 |
| 9 | [`docs/impl/GLOSSARY.md`](docs/impl/GLOSSARY.md) | 模型、运行时、英文缩写 | 读架构/写答辩/交接前 |
| 10 | [`docs/impl/PUBLISH.md`](docs/impl/PUBLISH.md) | GitHub 分支、安装包、发布 | 发布/演示前 |
| 11 | [`docs/impl/HANDOFF.md`](docs/impl/HANDOFF.md) | 原框架历史交接 | 只在追溯原框架时读，**不是当前 Web 规范** |

> 版本记录：[`CHANGELOG.md`](CHANGELOG.md)（代码版本线）。**文档区有自己的版本线**：[`docs/system/CHANGELOG.md`](docs/system/CHANGELOG.md)。发布前先看 `docs/impl/PUBLISH.md`。
>
> 当前 Web 运行路径是根目录的 `server.py`、`voice_app.py`、`static/`；`demo/`、`audio/scripts/`、
> `VoxDeskVoice/` 属于原框架历史内容，不是当前 Web 的启动路径，除非任务明确要求兼容原框架。

### Agent 开工规则

1. **先看仓库状态**：`git status --short`、当前分支、最近提交；不要在有未提交改动时直接覆盖。
2. **按上表顺序读文档**，至少读 1–6；不要用旧对话里的路径/结论替代当前文档。
3. **先复现基线**：启动服务，检查 `/api/health`；不能复现基线就不改功能。
4. **先计划后编码**：涉及架构、模型、存储、API 的改动，先写 `docs/impl/DECISIONS.md` 或任务拆分。
5. **最小改动**：一次只解决一个问题；不要顺手重构无关模块，不要批量重写前端。
6. **不碰受保护边界**：模型文件、`data/`、`.env`、`out/`、`defense/` 不入库；不提交大二进制。
7. **必须验证**：`py_compile`、`node --check`、API smoke test；改了 UI 要跑浏览器验证；改了存储要测边界。
8. **同步文档**：接口/数据流改 ARCHITECTURE；能力/数字改 STATUS；新坑改 PITFALLS；计划改 PLAN；架构取舍改 DECISIONS。
9. **正常开发走分支 + PR**：不要直接在默认分支堆改动；一次 PR 只做一件事，说明测试与风险。
10. **不伪造结果**：没有实测数字就写“未验证”；没有工具来源就说“无法确认”。

### 正常开发 vs 急速 demo

| 维度 | 急速 demo | 正常开发 |
| --- | --- | --- |
| 分支 | 直接改 | feature branch + PR/review |
| 测试 | 手点一下 | unit + API + UI + regression |
| 依赖 | 能跑就行 | 锁定版本、记录模型哈希/许可 |
| 数据 | 本地 JSON 随便写 | schema/版本/迁移/备份 |
| 安全 | 本机单用户 | 鉴权、限流、SSRF、密钥管理 |
| 发布 | 直接覆盖 | tag、changelog、回滚方案 |

正式流程和检查清单见 [`docs/impl/DEVELOPING.md`](docs/impl/DEVELOPING.md)。

## 致谢 Acknowledgements

本项目建立在以下开源工作和平台之上：

- **[VoxDesk](https://github.com/DongyueHAN/VoxDesk)**：原始语音框架、`audio/` / `tts/` 源码与 demo 基线；
- **[sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx)**：Paraformer 流式 ASR 推理；
- **[Piper](https://github.com/rhasspy/piper)**：本地中文 TTS；
- **[Silero VAD](https://github.com/snakers4/silero-vad)**：语音活动检测模型（项目内可选）；
- **[DeepSeek](https://platform.deepseek.com/)**：`deepseek-flash` 与 Search / Fetch API；
- **[DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness)**：系统提示词分层结构的参考。

感谢原 VoxDesk 项目与上述开源作者。VoxDesk-Web 不是 VoxDesk 官方发行版。

## 许可

- 本仓库包含从 **VoxDesk** 合并的 `audio/`、`tts/` 代码；上游采用 **GPL-3.0**，
  因此这部分及整体分发需遵守 GPL-3.0；GitHub 分支根目录保留上游 `LICENSE`。
- **Piper** 采用 GPL-3.0；使用/再分发 `tts/` 时需保留其版权与许可声明。
- `sherpa-onnx`、Paraformer、Silero VAD 等依赖和模型权重遵循各自上游许可证；
  模型文件不随本仓库分发。
- **DeepSeek API** 的调用与生成内容受 DeepSeek 服务条款和隐私政策约束。
- 公开再分发前请保留 `LICENSE`、版权声明与第三方 NOTICE，并自行核对模型权重许可。
