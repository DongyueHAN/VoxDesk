# VoxDesk-Web · 浏览器语音对话（w0.6）

> 说一句话 / 打一句话 → DeepSeek → 文字 + 语音。
> 本仓库已把 `D:\VoxDesk` 的 **tts / audio 源码与模型** 合并进来；外部原框架只读，不再修改。

| 项 | 值 |
| --- | --- |
| 版本 | **w0.6**：通用/陪伴 + 麦克风/桌面音频（F2 按住、F3 切换）+ 多轮 + 本地会话 + 联网工具 + TTS |
| 模型 | DeepSeek **`deepseek-flash`**（V4.1-Flash-1017） |
| 技术 | Python 标准库 `http.server` + 单页 HTML/CSS/JS（无框架、无构建） |
| 页面 | `/` 对话应用 · `/voice` 声纹可视化 |
| ASR / TTS | 本仓库 `audio/`、`tts/`（源码 + 模型） |
| 存储 | 本机 `data/chats`、`data/archive`（JSON，gitignore） |

## 跑起来

```powershell
cd D:\VoxDesk-Web
.\start.ps1
# http://127.0.0.1:8800/
```

- `start.ps1` 优先使用本仓库 `.venv`；没有则复用 `D:\VoxDesk\demo\.venv`（已装依赖）。
- 模型已复制到 `audio/models/`、`tts/models/`（约 289MB，gitignore；不提交）。
- API key 可放本目录 `.env`，或复用 `D:\VoxDesk\demo\.env` 的 `DEEPSEEK_API_KEY`。

## 当前功能

- **通用模式**：左侧会话列表 + 消息流 + 文字输入 + 麦克风 + 桌面音频 + 朗读/联网开关。
- **陪伴模式**：继承同一套存储和接口，但**只允许语音输入**（文字框隐藏）。
- **语音输入**：`F2` **按住**麦克风；`F3` **按一下开始、再按一下停止**桌面音频；仅页面聚焦时。松开/停止后 → `/api/asr` → 自动发送。
- **多轮**：服务端按 `conversation_id` 读取历史；语音/文字轮次都保存。
- **联网**：模型通过 `web_search` / `web_fetch` 工具调用 DeepSeek 官方 Search/Fetch API；
  时间问题也必须实时检索，**不注入服务端时间、不预制回答**。
- **朗读**：默认开，可关；Piper 生成 wav，浏览器播放，可停止。
- **存储上限**：30 条活跃 / 100 条归档 / 单会话 1MB；活跃满提示，1MB 提示归档并新开；
  归档满自动删除最旧归档。
- **声纹可视化**：`/voice` 保留 w0.3/w0.4 的希尔伯特 + 音色 + 伪残影。

## 数据流

```text
浏览器 app.html
  ├─ 文字 / F2 按住麦克风 / F3 切换桌面音频
  ├─ WebAudio → 16k PCM16 → POST /api/asr
  ├─ POST /api/chat {conversation_id, text, mode, speak, web}
  ▼
server.py
  ├─ store.py     读最近多轮、写 user/assistant JSON
  ├─ prompts.py   DSH 风格提示词 + web 工具
  ├─ llm.py       deepseek-flash；最多 3 轮工具循环
  │    ├─ web_search → https://api.deepseek.com/v1/tools/search
  │    └─ web_fetch  → https://api.deepseek.com/v1/tools/fetch（实时页面加 cache-bust）
  ├─ voice_app.py Piper 合成（speak=true）
  └─ data/chats/<id>.json
  ▼
{reply, sources, audio, timings} → 页面渲染 + 可选播放
```

## 本地存储规则

| 项 | 值 | 到达上限 |
| --- | --- | --- |
| 活跃会话 | 30 | 新建被拒，提示归档/删除 |
| 单会话 | 1MB | 禁止追加，提示归档并新开 |
| 归档会话 | 100 | 新归档时自动删除最旧归档 |

- 删除/归档/恢复都在界面左侧；活跃会话不会被自动删除。
- 不保存 wav；朗读按文本重新合成。
- `data/`、`audio/models/`、`tts/models/`、`out/` 均在 `.gitignore`。

## 实测（本机）

| 环节 | 数值 |
| --- | --- |
| 模型启动预热 | ASR 约 0.9s + TTS 3.5–3.8s（含真合成） |
| ASR（6.5s 音频） | 868–953ms；首字 98–154ms |
| 文本对话 | 1.2–1.6s（LLM 0.9–1.3s） |
| TTS（5–6s 语音） | 0.38–0.90s |
| 时间问题（联网） | 约 18s（2 次工具调用：search + fetch），回答可核对、带 5 个来源 |
| 页面 | `/` 4.7KB、`app.css` 15.4KB、`app.js` 28.2KB、`/voice` 48.7KB |
| 存储边界 | 30 活跃/100 归档/1MB 均已用临时目录测试 |

> 时间问题较慢是当前已知问题：模型先 search 再 fetch 实时时钟页；P2 会优化。

## 目录

```text
VoxDesk-Web/
├─ server.py          HTTP 路由、静态资源、/api/*
├─ voice_app.py       ASR → DeepSeek（工具）→ Piper 编排
├─ llm.py             deepseek-flash 客户端 + 工具循环
├─ search.py          DeepSeek Search/Fetch API 工具执行
├─ store.py           data/chats、data/archive、上限/归档
├─ prompts.py         DSH 风格提示词与工具 schema
├─ paths.py           本仓库模型/数据路径
├─ loopback.py        demo 的 WASAPI loopback（桌面音频备选）
├─ audio/             从 D:\VoxDesk 复制的源码 + 模型（结构不变）
├─ tts/               从 D:\VoxDesk 复制的源码 + 模型（结构不变）
├─ static/app.html/css/js   新对话应用（通用/陪伴）
├─ static/voice.html  声纹可视化
├─ data/              会话与归档（gitignore）
├─ requirements.txt   依赖清单（从 demo venv 提取）
└─ docs/
```

## 边界 / 下一步

- 浏览器**无法注册系统级全局热键**；F2（按住）/F3（切换）仅页面聚焦时有效。
- 桌面音频依赖 `getDisplayMedia` 共享系统音频；不支持时保留 WASAPI loopback 备选。
- 当前回答是**整段返回**，不是 token 流；打断/边生成边播放在 P2。
- Vtuber 模式本轮不实现。
- 模型/ASR/TTS 均为本地路径；依赖 venv 暂用外部 demo 环境，`requirements.txt` 可自建。
- DSH 提示词参考：[system-prompt 文档](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/subsystems/system-prompt.zh.md)。

## 文档地图

| 文件 | 回答什么 |
| --- | --- |
| [`AGENTS.md`](AGENTS.md) | 规则、验证命令、禁止事项 |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | 当前数据流、接口、存储、线程模型 |
| [`docs/STATUS.md`](docs/STATUS.md) | 能跑什么、实测、缺口 |
| [`docs/PITFALLS.md`](docs/PITFALLS.md) | 坑与对策（共 46 条） |
| [`docs/PLAN.md`](docs/PLAN.md) | P1 结果与 P2 计划 |
| [`docs/PUBLISH.md`](docs/PUBLISH.md) | 上传到 GitHub 新分支的步骤 |
