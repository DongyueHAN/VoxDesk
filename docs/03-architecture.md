# 03 · 架构

| 字段 | 值 |
| --- | --- |
| 文档 | `docs/03-architecture.md` |
| 版本 | v0.3.0 |
| 状态 | 草案 |
| 更新 | 2026-11-11 22:05 +08:00 |
| 生效范围 | 组件划分、交互流程、状态、领域模型 |

> **本版变化**：逻辑分层由"9 个平铺组件"改为 **5 层 + 2 个跨层基础件**；语音链路由"云"改为"本机"；会话模型由"全双工"改为"半双工 + 通道仲裁"。

---

## 1. 架构原则

| # | 原则 | 含义 | 违反的典型症状 |
| --- | --- | --- | --- |
| 1 | **单向数据流** | 音频 → 文本 → 意图 → 执行 → 文本 → 音频，不回环 | 组件互相直调，改一处崩三处 |
| 2 | **一切能力皆工具** | 开程序、调 API、查笔记，走同一套 Tool 接口 | if-else 越写越长 |
| 3 | **状态可持久化** | 会话、任务、审计全落库，进程可随时死 | 重启后任务消失，无法复盘 |
| 4 | **危险操作默认拦截** | 白名单 + 风险分级 + 二次确认 | 一句"删了吧"把目录删了 |
| 5 | **模型可替换** | 编排只依赖抽象接口，不绑厂商 | 换模型要改半个项目 |
| 6 | **离线优先** | 任何组件不得隐含依赖公网 | 断网即残废 |

## 2. C4-L1 系统上下文

```mermaid
%% diagram: CTX-01 系统上下文 | updated: 2026-10-26
flowchart LR
    U(["用户<br/>语音输入 / 语音输出"])
    SYS["VoxDesk<br/>桌面语音智能体<br/>（全本地）"]
    LLM["本地推理服务<br/>Ollama / llama.cpp<br/>localhost"]
    OS["Windows 操作系统<br/>进程 / 文件 / 音频设备"]
    VAULT["Obsidian Vault<br/>本地 .md 文件"]
    HARNESS["外部 Agent Harness<br/>CLI 子进程"]
    API["第三方 API<br/>天气 / 搜索（可选）"]

    U -->|"说话 / 按键"| SYS
    SYS -->|"播报"| U
    SYS <-->|"HTTP · 本机回环"| LLM
    SYS -->|"启动进程 / 读写文件 / 采集音频"| OS
    SYS <-->|"读 / 写 / 打开"| VAULT
    SYS <-->|"spawn · 流式事件"| HARNESS
    SYS -.->|"可选：仅联网类工具"| API
```

> 唯一的虚线是外部 API——它在离线时**允许失败**，且必须有降级话术。

## 3. C4-L2 容器图

5 层 + 2 个基础件，同进程；只有推理服务是独立进程（便于换引擎）。

```mermaid
%% diagram: C4-01 容器图 | updated: 2026-10-26
flowchart TB
    subgraph EDGE["① 端侧"]
        FE["CMP-01 语音前端<br/>采集 · 降噪 · VAD · KWS/PTT · ASR"]
        TTS["CMP-07 播报器<br/>本地 TTS · 分句流式 · 打断"]
    end
    subgraph DIALOG["② 对话层"]
        GW["CMP-02 会话网关<br/>半双工状态机 · 通道仲裁"]
        CE["CMP-03 认知引擎<br/>分流 · 上下文 · 生成"]
    end
    subgraph EXEC["③ 执行层"]
        TR["CMP-04 工具运行时<br/>注册表 · 策略 · 审批"]
        AR["CMP-05 Agent 执行体<br/>计划 · 执行 · 观察"]
        SC["CMP-06 任务调度器<br/>cron · 延时"]
    end
    subgraph INTEL["④ 智能层"]
        LLM["CMP-10 本地推理服务<br/>Ollama · 模型管理"]
    end
    subgraph ACCESS["⑤ 接入层"]
        HB["CMP-11 Harness 桥"]
        KB["CMP-12 知识接入<br/>Obsidian · 向量检索"]
    end
    DB[("CMP-09 存储与审计<br/>SQLite + 向量表")]
    UI["CMP-08 托盘控制台"]

    U(["用户"]) -- "语音" --> FE
    FE -- "文本" --> GW
    GW <--> CE
    CE <--> LLM
    CE <--> TR
    CE <--> AR
    AR <--> TR
    CE <--> HB
    CE <--> KB
    SC -- "到期派发" --> AR
    SC <--> DB
    GW <--> DB
    TR -- "审计" --> DB
    TR -- "进程 / 文件" --> OS[["操作系统"]]
    TR -. "HTTPS（可选）" .-> EXT[["外部 API"]]
    HB <-->|"spawn / 事件流"| H[["Agent Harness"]]
    KB <-->|"文件 / URI"| V[["Obsidian Vault"]]
    GW -- "回复文本" --> TTS
    TTS -- "声音" --> U
    UI <--> GW
```

### 3.1 组件职责

| ID | 组件 | 职责（一句话） | 关键输入 → 输出 |
| --- | --- | --- | --- |
| CMP-01 | 语音前端 | 把声音变成一句可靠的文本 | 音频帧 → `text` |
| CMP-02 | 会话网关 | 管住"这一轮走到哪了"，并仲裁音频通道 | 事件 → 状态迁移 |
| CMP-03 | 认知引擎 | 决定"这句话该干什么"并组织语言 | 上下文 + `text` → `Decision` |
| CMP-04 | 工具运行时 | 唯一真正"动手"的地方 | `tool_call` → `ToolResult` |
| CMP-05 | Agent 执行体 | 把复合任务拆成可执行步骤 | 任务描述 → 步骤与结论 |
| CMP-06 | 任务调度器 | 记住"什么时候该叫醒谁" | cron / delay → 到点派发 |
| CMP-07 | 播报器 | 把文本变成声音，且能被按键叫停 | `text` → 音频流 |
| CMP-08 | 托盘控制台 | 让人看得见它在干嘛 | 状态 / 配置 |
| CMP-09 | 存储与审计 | 保证一切可追溯、可恢复 | 事件 → 持久化 |
| **CMP-10** | **本地推理服务** | 把模型跑起来，并管理其生命周期 | `messages + tools` → 流式 token |
| **CMP-11** | **Harness 桥** | 把复杂任务翻译成对 harness 的调用 | 任务 → 摘要事件流 |
| **CMP-12** | **知识接入** | 把本地笔记变成可检索的知识 | 查询 → 片段 + 引用 |

### 3.2 关键接口

| ID | 接口 | 定义方 | 说明 |
| --- | --- | --- | --- |
| IF-01 | `SpeechToText(audio_stream) -> text_stream` | CMP-01 | 流式，首字优先 |
| IF-02 | `Understand(context, text) -> Decision` | CMP-03 | `Decision` ∈ {chat, tool_call, plan, schedule, delegate, clarify} |
| IF-03 | `Execute(tool_name, args) -> ToolResult` | CMP-04 | 成功 / 失败 / 需确认 三态 |
| IF-04 | `Schedule(cron \| delay, payload) -> job_id` | CMP-06 | 持久化后返回 |
| IF-05 | `Speak(text_stream) -> PlaybackHandle` | CMP-07 | `flush()` 可中断 |
| **IF-06** | **`Delegate(task, workdir) -> event_stream`** | **CMP-11** | **摘要级事件，非逐字** |
| **IF-07** | **`Search(query, k) -> Chunk[]`** | **CMP-12** | **带来源路径与行号** |
| **IF-08** | **`Chat(messages, tools) -> token_stream`** | **CMP-10** | **OpenAI 兼容** |

## 4. 核心流程

### 4.1 FLOW-04 端侧音频链路（半双工的核心）

半双工的本质不是"不能同时"，而是**一个显式的通道仲裁器**：任一时刻只允许上行或下行之一活跃。

```mermaid
%% diagram: FLOW-04 音频通道 | updated: 2026-10-26
flowchart LR
    subgraph UP["上行（聆听）"]
        M["麦克风 16k"] --> NR["降噪<br/>RNNoise / DFN3"]
        NR --> VAD["VAD<br/>Silero"]
        VAD -->|"有人说话"| KWS{"唤醒 / PTT?"}
        KWS -->|"命中"| ASR["流式 ASR<br/>Paraformer"]
        ASR --> TXT["文本"]
    end
    subgraph DOWN["下行（播报）"]
        R["回复文本"] --> SPLIT["按标点分句"]
        SPLIT --> TTSN["TTS<br/>Piper"]
        TTSN --> SPK["扬声器"]
    end
    ARB{"通道仲裁<br/>CMP-02"}
    TXT --> ARB
    ARB -->|"思考完成"| R
    ARB -.->|"播报中：麦克风关闭"| M
    KEY["热键按下"] -->|"flush()"| SPK
    KEY -->|"立即转聆听"| M
```

**三个关键设计**：

1. **播报时麦克风关闭** → 不需要 AEC，这是半双工最大的工程红利
2. **热键是全局的逃生口** → 任何时刻按下都能停止播报并转入聆听
3. **ASR 只走一次** → 不做"边说边识别边说"的回环，避免自激

### 4.2 FLOW-01 主链路（一次即时执行）

```mermaid
%% diagram: FLOW-01 主链路 | updated: 2026-10-26
sequenceDiagram
    autonumber
    actor U as 用户
    participant FE as CMP-01 语音前端
    participant GW as CMP-02 会话网关
    participant CE as CMP-03 认知引擎
    participant LLM as CMP-10 推理服务
    participant TR as CMP-04 工具运行时
    participant OS as 操作系统
    participant TTS as CMP-07 播报器
    participant DB as CMP-09 存储

    U->>FE: 按住热键说"打开记事本"
    FE->>FE: 降噪 → VAD → 流式 ASR
    FE->>GW: "打开记事本"
    GW->>DB: 写入 Turn(user)
    GW->>CE: Understand(context, text)
    CE->>LLM: Chat(messages, tools)
    LLM-->>CE: Decision = tool_call(open_app)
    CE->>TR: Execute("open_app", {name:"notepad"})
    TR->>TR: 白名单校验 + 风险分级
    TR->>OS: CreateProcess("notepad.exe")
    OS-->>TR: pid
    TR->>DB: 审计(工具/参数/耗时/结果)
    TR-->>CE: ToolResult(ok)
    CE->>LLM: 生成确认话术
    LLM-->>CE: "记事本已经打开了"
    CE-->>GW: 回复文本
    GW->>TTS: Speak(text)
    TTS-->>U: 播报
    GW->>DB: 写入 Turn(assistant) + 时延埋点
```

### 4.3 FLOW-02 定时任务

```mermaid
%% diagram: FLOW-02 定时任务 | updated: 2026-10-26
sequenceDiagram
    autonumber
    actor U as 用户
    participant GW as CMP-02 会话网关
    participant CE as CMP-03 认知引擎
    participant SC as CMP-06 调度器
    participant DB as CMP-09 存储
    participant AR as CMP-05 执行体
    participant TTS as CMP-07 播报器

    U->>GW: "每天早上九点总结科技新闻"
    GW->>CE: Understand(...)
    CE->>CE: Decision = schedule, cron="0 9 * * *"
    CE->>SC: Schedule(cron, prompt)
    SC->>DB: INSERT Task + 计算 next_run
    SC-->>CE: job_id
    CE-->>GW: "记下了，每天九点"
    GW->>TTS: Speak(确认)

    Note over SC: 次日 09:00（离线也可触发）
    SC->>DB: 查询到期任务
    SC->>AR: dispatch(task)
    AR->>AR: 多步执行（可选委托 harness）
    AR->>TTS: Speak(结果)
    TTS-->>U: 主动播报
    SC->>DB: 更新执行记录
```

### 4.4 FLOW-05 委托 Harness

```mermaid
%% diagram: FLOW-05 委托执行 | updated: 2026-10-26
sequenceDiagram
    autonumber
    actor U as 用户
    participant GW as CMP-02 会话网关
    participant CE as CMP-03 认知引擎
    participant HB as CMP-11 Harness 桥
    participant H as Agent Harness
    participant TTS as CMP-07 播报器

    U->>GW: "把这个仓库的测试补一下"
    GW->>CE: Understand
    CE->>CE: Decision = delegate（超出本地能力边界）
    CE->>HB: Delegate(task, workdir)
    HB->>H: spawn(cli, prompt)
    loop 每 10–20 秒聚合一次事件
        H-->>HB: 事件流
        HB-->>CE: 摘要（"改了 3 个文件"）
        CE->>TTS: 播报进度（≤ 1 句）
    end
    H-->>HB: final
    HB-->>CE: 结果摘要
    CE->>TTS: 播报结论 + 询问是否查看详情
```

### 4.5 FLOW-06 知识检索

```mermaid
%% diagram: FLOW-06 笔记检索 | updated: 2026-10-26
flowchart LR
    Q["用户提问"] --> R{"路由"}
    R -->|"关键词"| G["ripgrep 全文"]
    R -->|"语义"| V["向量检索<br/>sqlite-vec"]
    G --> M["合并去重<br/>RRF"]
    V --> M
    M --> TOP["Top-5 片段"]
    TOP --> CTX["拼入上下文"]
    CTX --> ANS["LLM 生成回答<br/>附笔记路径"]
```

### 4.6 FLOW-03 Agent 执行体（ReAct 多步计划）

`FLOW-01` 只覆盖"一次工具调用就结束"的情形；需要**多轮 思考 → 行动 → 观察**的请求（`REQ-F-040`~`REQ-F-043`）由 `CMP-05` 接管，
决策依据见 `ADR-0004`。`CMP-03` 只决定"要 plan"，不亲自执行循环。

```mermaid
%% diagram: FLOW-03 Agent 执行 | updated: 2026-11-11
sequenceDiagram
    autonumber
    actor U as 用户
    participant GW as CMP-02 会话网关
    participant CE as CMP-03 认知引擎
    participant AR as CMP-05 Agent 执行体
    participant TR as CMP-04 工具运行时
    participant AU as CMP-09 存储与审计
    participant TTS as CMP-07 播报器

    U->>GW: "查三个 AI 会议并整理成三条"
    GW->>CE: Understand(context, text)
    CE->>CE: Decision = plan（单步工具调用不足以完成）
    CE->>AR: Plan(task)
    loop 步数 ≤ 8 且总时长 ≤ 60s（ADR-0004 硬性上限）
        AR->>AR: Thought：下一步做什么
        AR->>TR: Act：Execute(tool_name, args)
        TR-->>AR: Observation：ToolResult
        AR->>AU: 记录 step（可回放）
        opt 命中危险操作
            TR-->>CE: 需确认
            CE->>TTS: Speak("即将删除 X，确认吗")
            U->>GW: "确认"
            GW->>TR: 放行
        end
    end
    AR-->>CE: 汇总结论（≤ 3 句）
    CE->>TTS: Speak(结论)
    TTS-->>U: 播报
```

**硬性上限**（`ADR-0004`）：步数 ≤ 8、总时长 ≤ 60 s；任一上限触发即中止，并播报"已经做了 N 步，还差什么"，
不静默失败。危险操作**不因"写在计划里"而免确认**——确认点仍在 `CMP-04` 执行前（同 `FLOW-01` 规则）。

### 4.7 SM-01 会话状态机（半双工）

```mermaid
%% diagram: SM-01 状态机 | updated: 2026-10-26
stateDiagram-v2
    [*] --> Idle
    Idle --> Listening: 热键 / 唤醒
    Listening --> Thinking: VAD 断句
    Listening --> Idle: 松开且无语音 / 超时
    Thinking --> Speaking: Decision = chat
    Thinking --> ToolCalling: Decision = tool_call
    Thinking --> Planning: Decision = plan
    Thinking --> Delegating: Decision = delegate
    ToolCalling --> Thinking: 结果回填
    ToolCalling --> WaitingConfirm: 危险操作
    WaitingConfirm --> ToolCalling: 确认
    WaitingConfirm --> Idle: 拒绝 / 超时
    Planning --> ToolCalling: 单步执行
    Planning --> Speaking: 汇总
    Delegating --> Speaking: 摘要播报
    Speaking --> Idle: 播完
    Speaking --> Listening: 热键打断（flush）
    ToolCalling --> Idle: 热键取消
```

> 注意：**没有** `Speaking → Listening` 的"语音打断"路径，那是全双工；半双工下打断只由热键触发。

### 4.8 DM-01 领域类图

```mermaid
%% diagram: DM-01 领域模型 | updated: 2026-10-26
classDiagram
    direction LR
    class Session {
        +str id
        +datetime started_at
        +SessionState state
        +str summary
        +append(turn)
        +close()
    }
    class Turn {
        +str id
        +Role role
        +str text
        +int latency_ms
    }
    class Decision {
        +Kind kind
        +str reply
        +ToolCall[] calls
    }
    class ToolCall {
        +str name
        +dict args
        +str status
        +int duration_ms
    }
    class ToolSpec {
        +str name
        +str description
        +dict schema
        +RiskLevel risk
    }
    class ToolResult {
        +bool ok
        +dict data
        +str message
    }
    class Task {
        +str id
        +str cron
        +str prompt
        +bool enabled
        +next_run()
    }
    class Job {
        +str id
        +datetime fire_at
        +JobState status
    }
    class ModelProfile {
        +str name
        +str digest
        +int num_ctx
        +float temperature
    }
    class NoteChunk {
        +str path
        +int start_line
        +str text
        +float[] embedding
    }
    class AuditEvent {
        +datetime ts
        +str trace_id
        +str action
        +dict payload
    }

    Session "1" *-- "*" Turn : 包含
    Turn "1" --> "0..1" Decision : 产出
    Decision "1" --> "*" ToolCall : 发起
    ToolCall --> ToolResult : 返回
    ToolCall ..> ToolSpec : 依循
    Task "1" --> "*" Job : 派生
    Decision ..> ModelProfile : 使用
    ToolCall ..> AuditEvent : 记录
```

## 5. 数据模型

| 表 | 关键字段 | 用途 |
| --- | --- | --- |
| `sessions` | id, started_at, state, summary | 会话生命周期 |
| `turns` | id, session_id, role, text, latency_ms | 对话流水 |
| `tool_calls` | id, turn_id, name, args_json, status, duration_ms | 工具执行记录 |
| `tasks` | id, cron, prompt, enabled, created_at | 用户定义的周期任务 |
| `jobs` | id, task_id, fire_at, status, result | 触发实例 |
| `audit_events` | ts, trace_id, action, payload_json | 审计与排障 |
| **`note_chunks`** | path, start_line, text, embedding | Obsidian 检索（向量存 `sqlite-vec` 虚表） |

## 6. 时延预算

| 环节 | CPU 4B | GPU 8B | 说明 |
| --- | --- | --- | --- |
| 断句（VAD 静音判定） | 600 ms | 600 ms | 配置项，半双工最大固定开销 |
| ASR 首字 | 400 ms | 350 ms | 流式 |
| LLM 首 token | 900 ms | 400 ms | **CPU 上的头号瓶颈** |
| 工具执行 | 200 ms | 200 ms | 本地启动类 |
| TTS 首包 | 200 ms | 200 ms | Piper 分句流式 |
| **首音合计** | **≈ 2.3 s** | **≈ 1.75 s** | 留 0.5–1s 余量 |

> 若开唤醒词，热键路径省掉 ~0，但用户"说唤醒词→等待"的体感会额外增加 300–500ms。

## 7. 演进：全双工怎么接进来

当前架构不封死全双工，路径清晰：

| 步骤 | 改动 | 影响面 |
| --- | --- | --- |
| 1 | `CMP-01` 增加 `AECStage`（回声消除） | 端侧 |
| 2 | `CMP-02` 状态机增加 `BargedIn` 事件，允许 `Speaking → Listening` | 网关 |
| 3 | 播报时麦克风保持开启，VAD 持续运行 | 通道仲裁 |
| 4 | TTS 支持"边说边被截断"（半句 flush） | 播报器 |

**不在本项目范围内**，列为 P3。写在这里是为了说明：半双工不是妥协，是**分阶段降低风险**。
