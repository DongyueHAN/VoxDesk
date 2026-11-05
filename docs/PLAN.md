# 计划方向（PLAN）

> 更新时间：2026-11-06 01:00 · 当前基线 **w0.6**
> 产品：**浏览器本地语音对话助手——麦克风/桌面音频 → 文字 → DeepSeek → 文字 + 语音。**
> P1 已完成；下一步 P2（流式/打断/桌面音频与稳定性）。Vtuber 本轮不实现。

## 0. 已确认决策

| # | 决策 | 落地 |
| --- | --- | --- |
| 1 | 复制源码；`tts/`、`audio/` 结构不变；demo 可复用内容进顶级；模型复制进本仓库 | 已复制源码 + 288.7MB 模型（gitignore） |
| 2 | 会话存储：服务端 `data/*.json` | `store.py` / `data/chats`、`data/archive` |
| 3 | 30 条活跃、100 条归档、单会话 1MB；到上限提示 | 已实现并测试 |
| 4 | 页面聚焦时 F2 按住麦克风 / F3 切换桌面录音 | 已实现；F3 再按停止；桌面音频需共享时勾选 |
| 5 | 联网默认全模式开；时间问题也走 web_search | 已实现；时间走 search + fetch，不注入时钟 |
| 6 | 前端拆 `app.html + app.css + app.js` | 已实现，无构建 |
| 7 | 本轮不实现 Vtuber | 未实现 |

## 1. 目标任务流（已落地）

```text
F2 / F3 / 文字
  → 浏览器 getUserMedia / getDisplayMedia
  → WebAudio 16k PCM16 → POST /api/asr（StreamingASR，尾静音）
  → 用户文本 → data/chats/<id>.json（追加 user）
  → 读取最近多轮 → system prompt
  → deepseek-flash：需要实时信息时调用 web_search / web_fetch
       → DeepSeek Search API / Fetch API（fetch 带 cache-bust）
  → reply + sources → 保存 assistant
  → speak=true：Piper 合成 wav → 浏览器播放
```

**未做时间注入**：时间问题由模型工具获得；工具失败就如实说明，不编造。

## 2. 合并架构（已落地）

- `audio/`、`tts/`：源码与模型复制进本仓库，`src` 布局和模块名不变；
- `demo` 的可复用内容：`llm.py`（合并）、`loopback.py`、`paths.py`、`app.py`（改造为 `voice_app.py`）；
  CLI/打包脚本不进入 Web 运行路径；
- 外部 `D:\VoxDesk` 只读，未修改；
- 运行时通过 `paths.install_sys_path()` 引入本仓库 `tts/src`、`audio/src`；
- 模型路径本仓库；`.gitignore` 排除 `audio/models/`、`tts/models/`、`data/`、`out/`；
- 依赖暂用外部 demo venv，`requirements.txt` 已提供；P2 可建本地 `.venv`。

## 3. 需求状态

### 3.1 两种模式（完成）

- 通用：侧栏会话、文字/麦克风/桌面音频、朗读/联网开关、来源、耗时。
- 陪伴：同存储，文字输入隐藏，仅语音；回答更短。
- 热键只在页面聚焦时（浏览器限制）。

### 3.2 本地存储与上限（完成）

- `data/chats/<uuid>.json`（≤30）、`data/archive/<uuid>.json`（≤100）。
- 单会话 ≤1MB；活跃满/单会话满提示；归档满自动删最旧归档。
- 手动归档/恢复/删除；活跃永不自动删除。

### 3.3 多轮 + 当前时间 + 联网（完成）

- 多轮：按 `conversation_id` 读历史；文字和语音轮次都保存。
- 时间/实时信息：模型调用 `web_search`；摘要不足时 `web_fetch` 实时页面；
  抓取 URL 加 `_voxdesk_ts` 防缓存。实测可回答到分钟（约 18s）。
- `deepseek-flash` = DeepSeek-V4.1-Flash-1017；`deepseek-v4.1` 不是合法 API ID。
- 内置 Responses `web_search` 仅 v4-pro，故用 Search API 函数工具。
- 联网关闭时移除 tools；模型会说明无法确认实时信息。

### 3.4 Vtuber（未实现）

保留后续设计：64×64 像素网格、TTS 音量驱动嘴型、回答情绪驱动表情/调色板；
希尔伯特 `4^k` 索引用于像素显现。**本轮不写代码。**

## 4. P1 结果（w0.5）

| 项 | 结果 |
| --- | --- |
| ASR | 6.5s 音频 868–953ms；首字 98–154ms |
| 文本对话 | 1.2–1.6s |
| TTS | 0.38–0.90s（5–6s 语音） |
| 时间问题 | 约 18s；search + fetch 两轮；答案与实时页一致；5 个来源 |
| 存储边界 | 30 活跃 / 1MB / 100 归档测试通过 |
| UI | 通用/陪伴、文字、F2 按住/F3 切换语音、TTS 播放/停止、来源 chips、归档列表 |
| 模型 | 本地 `audio/`、`tts/` + 288.7MB 模型；外部只读 |

已知问题：整段返回（无流式）、时间问题慢、桌面音频未真机验证、依赖外部 venv、
ASR 准确率未重新验收。

## 5. P2 · 流式 + 稳定性（下一轮）

1. **SSE 流式文字**：`/api/chat/stream` 发 `meta/delta/sources/audio/done`；
   页面逐字显示。
2. **分句 TTS / 边生成边播**：先合成第一句就播；停止时 abort。
3. **打断**：停止按钮中止 LLM/TTS/播放。
4. **桌面音频验证**：Chrome/Edge 系统音频共享；失败时接 `loopback.py` 备选。
5. **时间问题优化**：减少一次模型往返（搜索工具内附带实时页内容，或缓存时钟页）；
   目标 ≤8s。
6. **归档/上限 UI**：1MB 前预警、归档并新开一键操作、归档清理 toast。
7. **本地 venv / 部署**：按 requirements 建 `.venv`，start.ps1 优先本仓库。
8. **ASR 复测**：用现有语料测 CER/首字，记录新数字。

## 6. P3 · 后续（不排期）

- Vtuber 模式（先静态像素角色 + 嘴型/表情，再做希尔伯特 ↔ 像素双向原型）。
- 多轮摘要/长期记忆；移动端；本地 Ollama 切换；回填原框架清单。

## 7. 风险与边界

| 风险 | 说明 |
| --- | --- |
| 浏览器热键 | 仅页面聚焦；系统级需原生壳 |
| 桌面音频 | 依赖 `getDisplayMedia` 系统音频勾选；备选 WASAPI |
| 时间延迟 | 18s；P2 优化 |
| 搜索成本 | Search/Fetch 按成功请求计费；已有缓存/开关 |
| 模型/API 变化 | 模型 ID、工具支持以官方文档为准 |
| 隐私 | 音频本地；文字与搜索 query 发 DeepSeek；不存音频 |
| GPL | tts 依赖 Piper GPL-3.0；复制/分发保留声明 |
| 依赖 | 当前用外部 demo venv；本地 venv 待建 |

## 8. 历史

- `w0.1` 文字→DeepSeek→Piper；`w0.2` 并发/预热。
- `w0.3` `/voice` 声纹可视化；`w0.4` 阶数扩展 + 伪残影。
- `w0.5` 本次：合并源码/模型、通用/陪伴、ASR、多轮存储、联网工具、TTS 开关。
