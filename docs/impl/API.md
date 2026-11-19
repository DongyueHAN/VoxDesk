# 接口契约（API）

> 版本：w0.7 · 更新：2026-11-19 · 归属：实现区
>
> **本文件是 HTTP 接口的唯一权威。**
> - `ARCHITECTURE.md` 只描述数据流与线程模型，不再抄接口表；
> - 规范区 `docs/system/docs/03-architecture.md` §3.2 的 `IF-01`~`IF-10` 是**组件级抽象**，
>   到 HTTP 的映射见本文 §6；
> - 校验规则：本文登记的 `/api/*` 端点必须与 `server.py` 的路由 **1:1**（当前 **15 个**）。
>   改路由不更新本文，视为文档未完成（`AGENTS.md` §6）。

## 0. 通用约定

| 项 | 值 |
| --- | --- |
| 基础 URL | `http://127.0.0.1:8800`（`server.py --host/--port` 可改，默认仅回环） |
| 协议 | `HTTP/1.0`（`BaseHTTPRequestHandler` 默认；**无 keep-alive、无 chunked**） |
| 请求编码 | JSON 一律 UTF-8；二进制端点直接读裸 body |
| 响应编码 | `application/json; charset=utf-8`，文件端点用各自 MIME |
| 响应头 | 所有响应带 `Cache-Control: no-store`；**无 CORS 头**（同源访问） |
| 鉴权 | **无**。单用户本机应用；`--host 0.0.0.0` 等于把接口暴露到局域网 |
| 时间格式 | ISO 8601 带偏移，秒精度，固定 `+08:00`（`2026-11-19T19:00:00+08:00`） |
| 并发模型 | 每请求一线程；TTS/ASR 串行化，存储加锁，LLM/Search 无共享状态 |
| 请求体上限 | JSON `131072` B（128KB）；音频 `2097152` B（2MB） |

**错误信封**：所有非 2xx 返回

```json
{ "error": "人类可读的中文原因", "type": "ChatNotFound" }
```

`type` 只在有异常类型时出现（`StoreError` 子类名、`DeepSeekError`、`ValueError`）；路由级 404 只有 `error`。

> ⚠️ `speak` / `web` 走 `bool(body.get(...))`，**必须是 JSON 布尔**。
> 传字符串 `"false"` 会被判为 `true`（非空字符串为真）——这是现有实现的行为，见 §8。

## 1. 端点总表（15）

| # | 方法 | 路径 | 用途 | 成功码 |
| --- | --- | --- | --- | --- |
| 1 | GET | `/api/health` | 运行时状态（模型/ASR/TTS/key/存储） | 200 |
| 2 | GET | `/api/chats` | 会话列表（活跃或归档） | 200 |
| 3 | POST | `/api/chats` | 新建空会话 | **201** |
| 4 | GET | `/api/chats/<id>` | 单个会话完整 JSON | 200 |
| 5 | PATCH | `/api/chats/<id>` | 改标题 | 200 |
| 6 | DELETE | `/api/chats/<id>` | 删除（活跃或归档） | 200 |
| 7 | POST | `/api/chats/<id>/archive` | 归档（满 100 自动清最旧） | 200 |
| 8 | POST | `/api/chats/<id>/restore` | 从归档恢复 | 200 |
| 9 | POST | `/api/asr` | 16k PCM16 → 文本 | 200 |
| 10 | POST | `/api/chat` | 一轮对话（可选 TTS + 音色） | 200 |
| 11 | GET | `/api/wav/<name>` | 取 TTS 生成的 wav | 200 |
| 12 | POST | `/api/timbre` | PCM16 → 音色参数 | 200 |
| 13 | GET | `/api/timbre/<name>` | 已注册 wav 的音色参数 | 200 |
| 14 | GET | `/api/avatar` | `IF-10` 契约（渲染器未定） | 200 |
| 15 | POST | `/api/ocr` | `IF-09` 契约（**未实现**） | **501** |

**非 API 的 HTTP 面**：`GET /` `/index.html` `/app` `/app.html` → `app.html`；`GET /voice` `/voice.html` → `voice.html`；`GET /app.css` `/app.js` `/favicon.ico`；`GET /static/<...>` → `static/` 内文件。
`/static/*` 的契约是**只服务 `static/` 目录内的文件**，当前实现未做该约束（见 §8）。

## 2. 端点详解

### 2.1 `GET /api/health`

无参数。响应：

```json
{
  "ok": true,
  "model": "deepseek-flash",
  "default_model": "deepseek-flash",
  "api_key": true,
  "asr_loaded": true,
  "tts_loaded": true,
  "search": "deepseek",
  "store": {
    "active": 7, "archive": 0,
    "active_bytes": 19239, "archive_bytes": 0,
    "limits": { "active": 30, "archive": 100, "bytes": 1048576 }
  }
}
```

| 字段 | 说明 |
| --- | --- |
| `model` | 最近一次实际使用的模型 ID；**未发起过对话时为 `null`** |
| `api_key` | 是否读到了 `DEEPSEEK_API_KEY`（只返回布尔，不回显内容） |
| `asr_loaded` / `tts_loaded` | 模型是否已常驻（启动即预热，正常恒为 `true`） |

### 2.2 会话

#### `GET /api/chats`

| 参数 | 位置 | 取值 | 默认 |
| --- | --- | --- | --- |
| `archived` | query | `1` / `true` / `yes` → 归档；其余 → 活跃 | `0` |

响应：`{ items: ChatMeta[], stats, limits }`，`items` 按 `updated_at` 倒序。
`ChatMeta` = `{id, title, mode, created_at, updated_at, message_count, bytes}`。
损坏的 JSON 文件被静默跳过，不报错。

#### `POST /api/chats`

请求 `{ "mode": "general" | "companion" }`（可省略，非法值归 `general`）。
响应 **201**，返回完整 `Chat`（`messages: []`）。
错误：`409 ChatLimit`（活跃已达 30 条）。

#### `GET /api/chats/<id>`

`<id>` 必须是 32 位小写 hex（`^[0-9a-f]{32}$`），否则 `404 ChatNotFound`。
可选 `?archived=1` 从归档目录读（返回体多一个 `archived_at`）。
响应：完整 `Chat`。错误：`404`、`500 StoreError`（读失败/格式异常）。

#### `PATCH /api/chats/<id>`

请求 `{ "title": "..." }`。标题经 `_title_from` 归一：压缩空白、**截断到 24 字**、空值 → `新对话`。
响应：更新后的完整 `Chat`。只作用于活跃会话。

#### `DELETE /api/chats/<id>`

会同时尝试活跃与归档两个目录。响应 `{ id, removed: ["active"|"archive"...], stats }`；
两处都不存在 → `404 ChatNotFound`。

#### `POST /api/chats/<id>/archive`

请求体空。响应 `{ id, purged: [id...], stats, limits: {active, archive} }`。
`purged` = 因归档满 100 条而被删的最旧归档 id。先写归档再删活跃，中途失败不丢数据。
错误：`404`（不在活跃区）。

#### `POST /api/chats/<id>/restore`

请求体空。响应 `{ id, stats }`。
错误：`404`（不在归档区）、`409 ChatLimit`（活跃已满，恢复不自动挤掉别人）。

### 2.3 `POST /api/asr`

| 项 | 值 |
| --- | --- |
| 请求体 | **裸 PCM**：16kHz、单声道、小端 `int16`（非 WAV、非 multipart） |
| 上限 | `Content-Length ≤ 2MB`；有效音频 0.1s（3200B）～ 30s |
| 响应 | `{ text, asr_ms, first_char_ms, audio_s }` |

`text` 可能为空串（静音/未识别）；`first_char_ms` 在流式不可用时为 `null`。
错误：`400`（空 body / 太短 / 超 30s）、`413`（超 2MB）。

> 奇数长度会被截掉尾字节（`int16` 对齐），不报错。

### 2.4 `POST /api/chat`

请求（JSON，≤128KB）：

| 字段 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `text` | string | — | **必填**，≤4000 字；空 → `400` |
| `conversation_id` | string | `""` | 省略则新建会话，并在响应里返回新 id |
| `mode` | string | `general` | `general` / `companion`；**已有会话时以存储的 mode 为准** |
| `speak` | bool | `true` | 是否合成语音 |
| `web` | bool | `true` | 是否挂载 `web_search` / `web_fetch` 工具 |
| `source` | string | `text` | `mic` / `desktop` / `text`，非法值归 `text`，仅影响存档字段 |
| `asr_ms` | number | `0` | 上游 ASR 耗时，仅透传进存档 |

响应（`voice_app.chat` 的结果 + 路由后处理）：

```json
{
  "conversation_id": "8396d6d284a74e6bb3cbde503dc34b28",
  "reply": "……",
  "sources": [{ "title": "…", "url": "https://…", "snippet": "…", "date": "" }],
  "audio": "/api/wav/ab12cd34ef56.wav",
  "tts_ms": 412.7,
  "tts_error": null,
  "llm_ms": 1180.0,
  "first_token_ms": null,
  "tool_rounds": 1,
  "model": "deepseek-flash",
  "emotion": "neutral",
  "emotion_ms": 0.0,
  "web": true,
  "mode": "general",
  "timbre": { "ok": true, "vector": [0.1, "…"], "label": "偏亮" },
  "timbre_ms": 18.4
}
```

| 字段 | 说明 |
| --- | --- |
| `audio` | 裸文件名被改写成 `/api/wav/<name>` 可直接播放的 URL；`speak=false` 或 TTS 失败时为 `null` |
| `tts_error` | TTS 失败原因；**失败不丢文字**，仍是 200 |
| `first_token_ms` | **恒为 `null`**：当前 LLM 调用非流式，首 token 不可测 |
| `emotion` / `emotion_ms` | 仅 `companion` 模式做语气分类（多一次极短 LLM 调用）；`general` 恒为 `neutral` / `0.0` |
| `timbre` / `timbre_ms` | **仅当 `audio` 非空时出现**；音色分析失败时 `timbre: null` + `timbre_error` |
| `sources` | 已按 URL 去重；`title` ≤160 字、`snippet` ≤240 字 |

错误：

| 码 | 触发 |
| --- | --- |
| 400 | `text` 为空 / 超 4000 字 / JSON 非法 / 非对象 / body 超 128KB / `asr_ms` 非数字 |
| 404 | `conversation_id` 找不到 |
| 409 | 活跃会话已满（新建时） |
| 413 | 目标会话将超 1MB（`capacity_guard` **在调模型之前**就拦） |
| 502 | `DeepSeekError`：网络、鉴权、模型拒答 |

> 上下文窗口：最近 20 条消息、合计 ≤12000 字；更早的轮次不进入 prompt。
> 新建会话后若 LLM 抛错，服务端会**删除这个空会话**，不留残骸。

### 2.5 音色

#### `POST /api/timbre`

裸 PCM16（同 `/api/asr` 的格式与 2MB 上限）。响应为 `TimbreResult`（见 §4）。
错误：`400`（空 body）、`413`（超 2MB）。

#### `GET /api/timbre/<name>`

按 wav 注册表查名（只认 `/api/chat` 生成过的名字）。响应 `TimbreResult`。
错误：`404`（未注册或文件已被淘汰）、`500`（分析异常）。

### 2.6 契约占位

#### `GET /api/avatar`（`IF-10`）

200，返回契约而非数据：

```json
{
  "interface": "IF-10", "component": "CMP-14", "work_package": "WP5",
  "renderer": "undecided (DEC-003)", "sink": "NullAvatar",
  "emotions": ["neutral", "happy", "confused", "angry", "surprised"]
}
```

这是"接口已定、渲染器未定"的显式信号（`avatar.py`）。真正的驱动走进程内 `avatar.emit()`，
**不经 HTTP**。

#### `POST /api/ocr`（`IF-09`）

**501**，且响应体就是 OCR 的契约：

```json
{
  "error": "not_implemented",
  "interface": "IF-09", "component": "CMP-13", "work_package": "WP2",
  "available": false,
  "sources": ["screen", "camera", "file"],
  "confidence_warn": 0.6,
  "blocked_by": "DEC-007"
}
```

调用方应把 501 当作"能力未上线"，不要当作错误重试。

## 3. 状态码矩阵

| 码 | 语义 | 典型触发 |
| --- | --- | --- |
| 200 | 成功 | 除新建会话外的全部 |
| 201 | 已创建 | `POST /api/chats` |
| 400 | 请求不合法 | 空 body、音频太短/超 30s、`text` 为空或超长、JSON 非法/非对象、body 超限、`asr_ms` 非数字 |
| 404 | 不存在 | 路由未匹配、`<id>` 非 32 hex、会话不存在、wav 未注册 |
| 409 | 容量冲突 | 活跃会话满 30（新建/恢复/对话新建） |
| 413 | 体积超限 | 音频 >2MB、单会话将超 1MB |
| 500 | 服务端错误 | 存储读写失败、会话文件格式异常、未捕获异常 |
| 501 | 未实现 | `POST /api/ocr` |
| 502 | 上游失败 | `DeepSeekError`（网络/鉴权/模型） |

## 4. 数据模型

```text
Chat      { id: hex32, title, mode: "general"|"companion",
            created_at, updated_at, messages: Message[], archived_at? }

Message   用户      { role:"user", text, source:"mic"|"desktop"|"text",
                     asr_ms: int, created_at }
          助手      { role:"assistant", text, sources: Source[], tool_rounds: int,
                     tts: bool, model, first_token_ms: null, llm_ms: int,
                     emotion, created_at }

Source    { title: ≤160, url, snippet: ≤240, date }

ChatMeta  { id, title, mode, created_at, updated_at, message_count, bytes }

Limits    { active: 30, archive: 100, bytes: 1048576 }

TimbreResult {
  ok, duration_ms, sample_rate, rms, peak, active_ratio, note, centroid_hz,
  rolloff_hz, centroid_band, bandwidth, flatness, flux_db, temporal_std,
  bands: { low, mid, high }, vector: number[8], hue, saturation, lightness,
  color, accent, label, source
}
```

静音输入返回 `TimbreResult` 的零值形态（`silent: true`、`label: "静音"`），不报错。

## 5. 跨接口不变量

1. **原子写**：会话文件先写临时文件再 `os.replace`，读不到半截 JSON。
2. **上限**：30 活跃 / 100 归档 / 单会话 1MB；活跃**永不**自动删除，归档满自动删最旧。
3. **wav 注册表**：只保留最近 **20** 个；被淘汰后 `/api/wav/<name>` 与 `/api/timbre/<name>` 变 404。
4. **不存音频**：会话 JSON 只存文本、来源、耗时；朗读靠文本重新合成。
5. **工具预算**：`web` 开启时最多 3 轮工具调用，之后强制无工具收尾。
6. **密钥不外泄**：`/api/health` 只回布尔；错误信息里不出现 key。

## 6. 组件接口 → HTTP 映射

| 组件接口（规范区） | HTTP 落点 | 状态 |
| --- | --- | --- |
| `IF-01 SpeechToText` | `POST /api/asr` | 已实现（**批式**，非流式） |
| `IF-05 Speak` | `/api/chat` 的 `audio` + `GET /api/wav/<name>` | 已实现（整段，非流式） |
| `IF-08 Chat` | 进程内 `llm.py`，**不对外暴露** | 已实现（非流式） |
| `IF-09 Recognize` | `POST /api/ocr` | 契约占位（501） |
| `IF-10 DriveAvatar` | `GET /api/avatar` 查契约；驱动走进程内 `emit()` | 契约占位（`NullAvatar`） |
| `IF-07 Search`（`CMP-12` 知识接入） | **未暴露**；内核已落（`kb.py`，CLI 可跑），规划落点 `POST /api/kb/search` | 内核完成 / HTTP 待 P2 |

## 7. 变更规则

- **加字段**：向后兼容，直接加，可只改本文。
- **删字段 / 改语义 / 改状态码**：视为破坏性变更 → 升版本 + 同步 `static/app.js` + 在 `CHANGELOG.md` 标 **Breaking**。
- **新增端点**：先改本文（契约先行），再写路由；PR 里两者必须在同一提交。
- **端点集合必须 1:1**：删掉路由要同时删本文条目，否则视为不一致。
- 改完必须更新 `ARCHITECTURE.md` §4 的指针小节（如果跨接口约定有变）与 `STATUS.md` 的能力表。

## 8. 已知偏差（待修，勿照抄本文之外的旧描述）

| # | 偏差 | 影响 | 处置 |
| --- | --- | --- | --- |
| 1 | `server.py` 的 `server_version` 仍写 `VoxDeskWeb/0.5`，而版本线已是 `w0.7` | 响应头/日志版本不可信 | chore PR 统一版本号 |
| 2 | `GET /static/*` 未校验解析后的路径仍在 `static/` 内，`..` 段可越出目录读到仓库内任意文件（已实测 200） | 本机单用户下可读 `.env` / `data/chats/*.json`；`--host 0.0.0.0` 时风险放大 | 独立 fix PR：解析后做 `static/` 包含性检查 + 补 SECURITY/PITFALLS |
| 3 | `speak` / `web` 用 `bool()` 强转，字符串 `"false"` 被判真 | 前端若传字符串会静默失效 | 明确要求 JSON 布尔；或改显式解析（破坏性小，可随手修） |
| 4 | 旧 `ARCHITECTURE.md` §4 表缺 `/api/ocr`、`/api/avatar`，且写的 `timings` 字段**根本不存在**（实际是扁平 `llm_ms`/`tts_ms`/`first_token_ms`） | 消费方按旧表写代码会踩空 | 已在本 PR 删除该表，改为指向本文 |
