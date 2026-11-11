# 10 · 读代码与写代码：Intent → Specification → Implement

| 字段 | 值 |
| --- | --- |
| 文档 | `docs/10-code-reading.md` |
| 版本 | v1.1.0 |
| 状态 | 现行 |
| 更新 | 2026-11-11 23:20 +08:00 |
| 生效范围 | 面向本项目（`D:\VoxDesk` / VoxDesk-Web）的阅读与实现方法；不含具体业务结论 |

> **位置**：组 D · **实践 4/4**：怎么读、怎么写（方法不随版本过期）

> 面向"vibe coding 生成了代码，但不知道它从哪来"的情况。
> 目标：让你能**从意图反推规范、从规范读懂代码、从规范写出代码**。

## 1. 为什么 vibe coding 会失控

Agent 生成代码时的默认路径是：`Intent → Implement`（跳过 Specification）。
代码能跑，但**契约藏在实现里**——没有接口签名、没有数据形状、没有失败模式。
后果是：改一个地方就崩；换个 agent 就要从头猜；人读不懂"为什么这么写"。

工程上的骨架是三段：

```
Intent（要什么，人话）
   ↓ 翻译
Specification（可验收的契约：接口 / 数据 / 边界 / 失败）
   ↓ 实现
Implement（满足契约的最小代码）
   ↓ 验证
Evidence（实测数字 / 测试）
```

**Specification 是唯一能被人和 agent 同时读懂的一层**。文档仓（本仓）负责 Intent 与部分 Spec；
代码仓的 `docs/ARCHITECTURE.md` 负责实现侧 Spec；代码是 Spec 的一个实现。

## 2. 三段式怎么写（模板）

### 2.1 Intent（一句话，可被否定）

> 例：**"浏览器按住 F2 说话，松开后把这段音频变成文字，填进输入框。"**

合格标准：有主语、有触发、有结果、能判断真假。不合格的 Intent："做一个语音功能。"

### 2.2 Specification（一张契约卡）

| 要素 | 例（`POST /api/asr`） |
| --- | --- |
| 输入 | `application/octet-stream`：PCM，16kHz，单声道，int16，小端；或 WAV 头 |
| 输出 | `{"text": "...", "first_char_ms": 120, "total_ms": 900}` |
| 前置条件 | 模型已加载；音频长度 ≤ 60s |
| 后置条件 | 文本已去空白；不修改任何会话状态 |
| 失败模式 | 空音频 → 400；模型未加载 → 503；解码失败 → 415 |
| 性能预算 | 6.5s 音频 ≤ 1.2s 返回 |
| 不做 | 不做标点恢复（由模型内置）；不落盘 |

**这张表就是你和 agent 的合同。** 有了它，实现可以换、模型可以换，行为不变。

### 2.3 Implement（最小代码）

规则：**只做契约卡里的事**；超出的部分（日志、重试、缓存）要么写进契约，要么不做。
写完后用探针验证，再补测试。

## 3. 怎么读一个陌生模块（五步法）

以 `voice_app.py` 的 `chat()` 为例：

1. **找入口**：谁调它？（`server.py` 的 `POST /api/chat`）
2. **看签名**：`chat(*, conversation_id, text, mode, speak, web, source, asr_ms) -> dict`
   —— 关键字参数说明它是"编排函数"，不是工具函数。
3. **圈依赖**：它读了什么、写了什么？（读 `store` 的历史、调 `llm`、写 `store`、调 `synth_wav`）
4. **找分支**：`if not text`、`if speak`、`if web` —— 这些分支就是**隐含的 Spec**。
5. **对实测**：调一次接口，把返回字段映射回代码里的 dict 键。

**三问法**（每个函数都问）：

- 它**承诺**什么？（返回值/副作用）
- 它**依赖**什么？（外部状态/IO）
- 它**失败**时怎样？（抛出/返回空/静默）

## 4. 本仓库逐模块读法（tts 之外）

**模块清单以代码仓 `docs/ARCHITECTURE.md` 为准**，这里只给"按什么顺序读"：

| 顺序 | 读什么 | 读完能回答 |
| --- | --- | --- |
| 1 | `server.py` 的 `do_GET/do_POST` 分支 | 一次请求怎么进来、落到哪个函数 |
| 2 | `voice_app.py` 的 `chat()` | ASR → LLM → 存储 → TTS 怎么串起来 |
| 3 | `llm.py` + `search.py` | 工具循环最多几轮、结果怎么回填 |
| 4 | `store.py` + `prompts.py` | 数据落在哪、人设与工具 schema 在哪 |

**读法示例（`server.py`）**：

```text
do_POST
 ├─ /api/asr   → read body → voice_app.transcribe(raw) → json
 ├─ /api/chat  → read json → voice_app.chat(...)       → json
 └─ 其它        → 404
```

把这段伪代码写出来，就掌握了 `server.py` 的全部路由。

## 5. 从工具文档提取接口规范（Implement 的最佳实践）

拿到一份 API 文档（DeepSeek、天气、任何 HTTP 服务）时，**只抄五样东西**：

| # | 提取项 | 落在哪 |
| --- | --- | --- |
| 1 | 端点 + 方法 + 鉴权方式 | 常量（`BASE_URL`、`KEY_ENV`） |
| 2 | 请求体 schema（必填/可选/类型/上限） | 构造 payload 的函数 |
| 3 | 响应体 schema（真正要用的字段） | 解析函数（只取需要的键） |
| 4 | 错误码与语义（401/429/5xx） | 异常映射 |
| 5 | 超时、重试、限流 | 客户端构造函数参数 |

然后按四步落地：

1. **先写探针**：`Invoke-RestMethod` / `curl` 手动打一次，保存真实响应样本；
2. **再写适配器**：一个类/函数把"外部 JSON"转成"内部 dataclass"（`llm.py` 的 `ChatReply`、`search.py` 的 `execute_tool`）；
3. **失败优先**：先写 401/超时/空响应的分支，再写成功路径；
4. **契约测试**：断言"字段存在且类型对"，不要断言具体文案（文案会变）。

**反模式**：把外部字段名散落在业务代码里（`resp["choices"][0]["delta"]["content"]` 到处都是）——
一旦 API 改版，要改十处。适配器只允许有一处知道外部字段名。

## 6. 写代码的七步清单

1. 写 Intent（一句话，可被否定）；
2. 写契约卡（输入/输出/失败/预算/不做）；
3. 找现成的相似实现（本仓库里通常已有：ASR、TTS、store、工具循环）；
4. 写最小实现（≤ 50 行，先不做优化）；
5. 跑探针（真实请求，记录数字）；
6. 补边界（空输入、超时、并发、重复调用）；
7. 同步文档（`ARCHITECTURE` 接口 / `STATUS` 数字 / `PITFALLS` 新坑）。

## 7. 三个练习（由易到难）

| # | 任务 | 练什么 | 验收 |
| --- | --- | --- | --- |
| 1 | 加 `GET /api/echo?text=...` | 路由 + 参数解析 + 返回 JSON | `curl` 返回原文 |
| 2 | 给 `/api/chat` 加 `stream=true`，用 SSE 逐字返回 | 契约变更 + 流式解析 + 前端消费 | 首字 ≤1.5s 出现在页面 |
| 3 | 给 `/api/chat` 加"停止"：服务端记住请求 id，前端 POST 取消 | 并发 + 状态管理 + 幂等 | 停止后 300ms 内不再增字 |

做完任一题，把"契约卡 + 实测数字"写进代码仓 `docs/`，这个循环就闭合了。

## 8. 与本仓库现有文档的关系

| 文档 | 提供哪一段 |
| --- | --- |
| 本仓 `docs/01-scope.md` / `02-requirements.md` | Intent（要什么、优先级） |
| 本仓 `docs/03-architecture.md` / `09-web-implementation.md` | Specification（系统级契约与现状） |
| 代码仓 `docs/ARCHITECTURE.md` | Specification（模块级接口与不变式） |
| 代码仓代码 | Implement |
| 代码仓 `docs/STATUS.md` | Evidence（实测数字） |

读的顺序：**Intent → 系统 Spec → 模块 Spec → Code → Evidence**；写的时候反过来。
