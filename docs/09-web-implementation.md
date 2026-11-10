# 09 · 当前实现验收记录（VoxDesk-Web w0.6）

| 字段 | 值 |
| --- | --- |
| 文档 | `docs/09-web-implementation.md` |
| 版本 | v1.0 |
| 状态 | 现行 |
| 更新 | 2026-11-10 20:55 +08:00 |
| 生效范围 | 记录 `D:\VoxDesk` 在 `7e77b2e` 之后的实际实现状态；不改 02/04/05 的任何结论 |

> 本文只回答一件事：**代码仓现在到底是什么、能跑什么、和原设计差在哪。**
> 实测口径：2026-11-10 20:50 本机 Windows 11 + `D:\VoxDesk\demo\.venv` 的 Python 3.11。

## 1. 一句话结论

代码仓已从"桌面语音 demo"演化为一个**浏览器语音应用（VoxDesk-Web w0.6）**：
浏览器采集音频 → 本地 ASR → DeepSeek（`deepseek-flash`）+ 联网工具 → 本地 Piper 播报 → 本地 JSON 会话。

原框架（`audio/`、`tts/`、`demo/`）仍在仓库里，但**当前启动路径已不经过它们**（见 README 末尾的边界说明）。

## 2. 验收方法

| 步骤 | 命令 | 期望 |
| --- | --- | --- |
| 1 | `git log --oneline 7e77b2e..HEAD` | 4 个新提交（w0.6 + 表情 + 文档） |
| 2 | `.\start.ps1` | 打印"模型就绪"与端口 |
| 3 | `GET /api/health` | `ok:true`，ASR/TTS 已加载，store 统计正常 |
| 4 | `POST /api/chat {"text":"…","speak":false}` | 返回 reply、model、timings |
| 5 | `GET /api/chats` | 会话列表（本机已有 6 条） |

## 3. 验收结果

### 3.1 通过项

| 项 | 实测 |
| --- | --- |
| `/api/health` | `200`；`{"ok":true,"default_model":"deepseek-flash","api_key":true,"asr_loaded":true,"tts_loaded":true,"search":"deepseek","store":{"active":6,...}}` |
| `/api/chat`（文字，不朗读） | `200`；reply 正常；`llm_ms=2109`；`model=deepseek-flash`；`tool_rounds=0` |
| 会话持久化 | `data/chats` 已有 6 条，`active_bytes=18432` |
| 冷启动 | 本次 `ASR 737.7ms · TTS 3280.5ms · 总 4019ms`（与 README 声称的 0.9s + 3.5–3.8s 一致） |

### 3.2 观察到的偏差（不是失败，是文档要对齐）

| 偏差 | 现象 | 影响 |
| --- | --- | --- |
| `first_token_ms` 为 `null` | `/api/chat` 返回 `"first_token_ms": null` | 说明当前 LLM 调用是**非流式**；"首 token"指标暂时不可测 |
| 冷启动波动大 | 同一台机器另一次冷启动为 `ASR 1788ms · TTS 9725ms · 总 11.5s` | 受磁盘缓存/杀软影响，README 的固定数字需加"波动范围" |
| 无自动化测试 | `git ls-files` 无 `test_*.py` | 回归靠手测；`docs/DEVELOPING.md` 要求的能力尚未落地 |
| `/api/status`、`/api/sessions` 不存在 | 404 | 我按旧接口猜的路径无效；实际是 `/api/chats` |

## 4. 实际接口面（从代码读出，非文档转述）

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/`、`/voice` | 主页面 / 声纹可视化 |
| GET | `/api/health` | 模型与存储健康 |
| GET | `/api/chats`、`/api/chats/<id>` | 会话列表 / 单条 |
| GET | `/api/wav/<id>`、`/api/timbre/<id>` | 播放 wav / 音色分析 |
| POST | `/api/asr` | 原始 PCM → 文本 |
| POST | `/api/chat` | 一轮对话（可朗读、可联网） |
| POST | `/api/chats`、`/api/chats/<id>/archive`、`/archive/<id>/restore` | 新建 / 归档 / 恢复 |
| PATCH / DELETE | `/api/chats/<id>` | 重命名 / 删除 |

## 5. 模块与职责

| 文件 | 职责 | 关键技术 |
| --- | --- | --- |
| `server.py` | 路由、静态资源、错误处理 | `http.server.ThreadingHTTPServer` |
| `voice_app.py` | ASR → LLM → 存储 → TTS 的编排 | 惰性加载、`clean_for_tts`、情感分类 |
| `llm.py` | Chat Completions 客户端 + 工具循环 | SSE/JSON、工具最多 3 轮 |
| `search.py` | Search / Fetch API 执行 | 缓存 + cache-bust、结果去重 |
| `store.py` | 会话 JSON、30/100/1MB 上限 | `tmp + os.replace` 原子写 |
| `prompts.py` | 系统提示词 + 工具 schema | 模式化 prompt、JSON Schema |
| `timbre.py` | 声纹/音色分析 | 希尔伯特变换、FFT |
| `static/app.js` | 录音、重采样、请求、播放 | WebAudio、PCM16、`<audio>` |

## 6. 能力覆盖情况（对照 12 个组件）

| 组件 | 原定 | 现状 | 判定 |
| --- | --- | --- | --- |
| `CMP-01` 语音前端 | 采集/降噪/VAD/KWS/ASR | 浏览器采集 + 本地 ASR；**未接 VAD 自动断句** | 🟡 部分 |
| `CMP-07` 播报器 | 分句/缓存/队列/打断 | Piper 合成 + 浏览器播放 + 停止按钮；**无分句流式** | 🟡 部分 |
| `CMP-02` 会话网关 | 半双工状态机 | 无；靠按住/松开与按钮 | ⬜ |
| `CMP-03` 认知引擎 | 分流/上下文/生成 | 单轮式编排 + 两模式（通用/陪伴）；多轮历史 | 🟡 部分 |
| `CMP-04/05/06` | 工具/Agent/调度 | 只有 `web_search` / `web_fetch` 两个工具 | 🟡 极少 |
| `CMP-10` 推理 | 本地 Ollama | **云端 DeepSeek（deepseek-flash）** | ❌ 偏离本地优先 |
| `CMP-11/12` | Harness / Obsidian | 无 | ⬜ |
| `CMP-08/09` | 托盘 / 审计 | 无托盘；有本地 JSON 会话（非审计） | ⬜ |

## 7. 与原设计的关键偏离

1. **推理出网**：`ADR-0005`（本地优先）在 Web 线被绕过——回答依赖 DeepSeek；只有 ASR/TTS 在本地。
2. **形态变化**：桌面应用 → 浏览器应用；全局热键只能在页面聚焦时生效。
3. **范围扩张**：多了联网工具、陪伴模式、声纹可视化、会话存储——这些在 02 需求池里**没有对应条目**。
4. **范围收缩**：VAD 自动断句、KWS、打断、工具执行、调度都没有。

## 8. 对系统文档的结论

- `04-tech-stack.md` 与 `02-requirements.md` 的"待确认"仍然悬空（见 `05-roadmap.md` §5），**但实现已经跑到文档前面**；
- 因此 `05-roadmap.md` 的"M0 收尾 → v1.0 冻结 → 进入 M1"已不符合事实：M1/M2 的部分能力被 Web 线部分覆盖；
- 建议（需需求方批准后再动 `05`）：把里程碑改为"双线"——
  - **A 线（原框架）**：按 05 继续 M2 收尾（S5 本地 LLM / S7 串联）；
  - **B 线（Web 线）**：以 `09` 为基线补 VAD、流式、打断，再决定是否回填 A 线。

## 9. 风险清单

| 风险 | 说明 | 建议 |
| --- | --- | --- |
| 无测试 | 无 `test_*.py`，改动靠手测 | 先补 `/api/chat` 与 `store` 的单测 |
| 无鉴权 | 单用户本机；`127.0.0.1` 可接受，暴露到局域网危险 | 加 token 或绑定回环 |
| SSRF | `web_fetch` 抓任意 URL | 限制协议/内网段（`SECURITY.md` 已提） |
| 密钥 | `.env` 在本机 | 已在 `.gitignore`；确认无提交历史 |
| 模型许可 | Piper 音色许可需逐个核对 | 发布前按 `08` 与 README 许可节处理 |
