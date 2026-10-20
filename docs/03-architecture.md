# 03 · 架构

| 字段 | 值 |
| --- | --- |
| 文档 | `docs/03-architecture.md` |
| 版本 | v0.1.0 |
| 状态 | 草案 |
| 更新 | 2026-10-20 12:12 +08:00 |
| 生效范围 | 组件划分、交互流程、状态、领域模型 |

---

## 1. 架构原则

五条原则，后续所有设计冲突都拿它们裁决：

| # | 原则 | 含义 | 违反的典型症状 |
| --- | --- | --- | --- |
| 1 | **事件驱动、单向数据流** | 音频 → 文本 → 意图 → 工具 → 文本 → 音频，不回环 | 组件互相直接调用，改一处崩三处 |
| 2 | **一切能力皆工具** | 开程序、调 API、查文件，全部走同一套 Tool 接口 | if-else 越写越长，新增能力必改编排 |
| 3 | **状态可持久化** | 会话、任务、审计全部落库，进程可随时死 | 重启后任务消失，无法复盘 |
| 4 | **危险操作默认拦截** | 白名单 + 风险分级 + 二次确认 | 一句"删了吧"把目录删了 |
| 5 | **模型可替换** | 编排层只依赖抽象接口，不绑厂商 | 换模型要改半个项目 |

## 2. C4-L1 系统上下文

```mermaid
%% diagram: CTX-01 系统上下文 | updated: 2026-10-20
flowchart LR
    U(["用户<br/>语音输入 / 语音输出"])
    SYS["VoxDesk<br/>桌面语音智能体"]
    LLM["LLM 服务<br/>意图 / 工具选择 / 生成"]
    SPEECH["语音服务<br/>ASR / TTS"]
    OS["Windows 操作系统<br/>进程 / 文件 / 通知"]
    API["第三方 API<br/>天气 / 搜索 / 日历"]

    U -->|"说话 / 按键"| SYS
    SYS -->|"播报"| U
    SYS -->|"HTTPS"| LLM
    SYS -->|"HTTPS / 流式"| SPEECH
    SYS -->|"启动进程 / 读写文件"| OS
    SYS -->|"HTTPS"| API
```

## 3. C4-L2 容器图

九个组件，全部跑在同一个进程空间内（单机部署，不做服务拆分）。

```mermaid
%% diagram: C4-01 容器图 | updated: 2026-10-20
flowchart TB
    subgraph HOST["本机 PC · Windows 11 · 单进程"]
        direction TB
        FE["CMP-01 语音前端<br/>采集 · VAD · 流式 ASR · 热键"]
        GW["CMP-02 会话网关<br/>会话 · 轮次 · 状态机 · 打断"]
        CE["CMP-03 认知引擎<br/>上下文组装 · LLM 编排 · 回复生成"]
        TR["CMP-04 工具运行时<br/>注册表 · 执行 · 策略 · 审批"]
        AR["CMP-05 Agent 执行体<br/>计划 · 执行 · 观察 · 修正"]
        SC["CMP-06 任务调度器<br/>cron · 延时 · 到期派发"]
        TTS["CMP-07 播报器<br/>TTS 合成 · 播放队列 · 打断"]
        UI["CMP-08 托盘控制台<br/>状态 · 设置 · 日志查看"]
        DB[("CMP-09 存储与审计<br/>SQLite · 会话/任务/工具调用")]
    end

    U(["用户"]) -- "语音" --> FE
    FE -- "文本" --> GW
    GW <--> CE
    CE <--> TR
    CE <--> AR
    AR <--> TR
    SC -- "到期派发" --> AR
    SC <--> DB
    GW <--> DB
    TR -- "写审计" --> DB
    TR -- "进程 / 文件" --> OS[["操作系统"]]
    TR -- "HTTPS" --> EXT[["外部 API"]]
    GW -- "回复文本" --> TTS
    TTS -- "声音" --> U
    UI <--> GW
```

### 3.1 组件职责

| ID | 组件 | 职责（一句话） | 关键输入 → 输出 |
| --- | --- | --- | --- |
| CMP-01 | 语音前端 | 把声音变成一句文本 | 音频帧 → `text` |
| CMP-02 | 会话网关 | 管住"这一轮对话走到哪了" | `text` / 工具结果 → 状态与下一步 |
| CMP-03 | 认知引擎 | 决定"这句话该干什么"并组织语言 | 上下文 + `text` → 意图 / 工具调用 / 回复 |
| CMP-04 | 工具运行时 | 唯一真正"动手"的地方 | `tool_call` → `result` |
| CMP-05 | Agent 执行体 | 把复合任务拆成可执行步骤 | 任务描述 → 步骤序列与结论 |
| CMP-06 | 任务调度器 | 记住"什么时候该叫醒谁" | cron / delay → 到点派发 |
| CMP-07 | 播报器 | 把文本变成声音，且能被叫停 | `text` → 音频流 |
| CMP-08 | 托盘控制台 | 让人看得见它在干嘛 | 状态 / 配置 |
| CMP-09 | 存储与审计 | 保证一切可追溯、可恢复 | 事件 → 持久化 |

### 3.2 关键接口

| ID | 接口 | 定义方 | 说明 |
| --- | --- | --- | --- |
| IF-01 | `SpeechToText(audio_stream) -> text_stream` | CMP-01 | 流式，首字优先 |
| IF-02 | `Understand(context, text) -> Decision` | CMP-03 | `Decision` ∈ {chat, tool_call, plan, clarify} |
| IF-03 | `Execute(tool_name, args) -> ToolResult` | CMP-04 | 统一成功/失败/需确认三态 |
| IF-04 | `Schedule(cron \| delay, payload) -> job_id` | CMP-06 | 持久化后返回 |
| IF-05 | `Speak(text_stream) -> playback_handle` | CMP-07 | 可中断 |

## 4. 核心流程

### 4.1 FLOW-01 主链路（一次即时执行）

```mermaid
%% diagram: FLOW-01 主链路 | updated: 2026-10-20
sequenceDiagram
    autonumber
    actor U as 用户
    participant FE as CMP-01 语音前端
    participant GW as CMP-02 会话网关
    participant CE as CMP-03 认知引擎
    participant TR as CMP-04 工具运行时
    participant OS as 操作系统 / 外部 API
    participant TTS as CMP-07 播报器
    participant DB as CMP-09 存储

    U->>FE: 按住热键说"打开记事本"
    FE->>FE: VAD 断句 + 流式 ASR
    FE->>GW: "打开记事本"
    GW->>DB: 写入 Turn(user)
    GW->>CE: Understand(context, text)
    CE->>CE: LLM 判定 Decision = tool_call
    CE->>TR: Execute("open_app", {name:"notepad"})
    TR->>TR: 白名单校验 + 风险分级
    TR->>OS: CreateProcess("notepad.exe")
    OS-->>TR: pid
    TR->>DB: 写审计(工具/参数/耗时/结果)
    TR-->>CE: ToolResult(ok)
    CE-->>GW: "记事本已经打开了"
    GW->>DB: 写入 Turn(assistant)
    GW->>TTS: Speak(text)
    TTS-->>U: 语音播报
```

### 4.2 FLOW-02 定时任务（创建 → 触发）

```mermaid
%% diagram: FLOW-02 定时任务 | updated: 2026-10-20
sequenceDiagram
    autonumber
    actor U as 用户
    participant GW as CMP-02 会话网关
    participant CE as CMP-03 认知引擎
    participant SC as CMP-06 调度器
    participant DB as CMP-09 存储
    participant AR as CMP-05 Agent 执行体
    participant TTS as CMP-07 播报器

    U->>GW: "每天早上九点总结科技新闻"
    GW->>CE: Understand(...)
    CE->>CE: Decision = schedule, cron = "0 9 * * *"
    CE->>SC: Schedule(cron, prompt)
    SC->>DB: INSERT Task + 计算 next_run
    SC-->>CE: job_id
    CE-->>GW: "记下了，每天九点"
    GW->>TTS: Speak(确认)

    Note over SC: 次日 09:00
    SC->>DB: 轮询到期任务（或 APScheduler 回调）
    SC->>AR: dispatch(task)
    AR->>AR: 多步执行（搜索 → 摘要 → 组织口播稿）
    AR->>TTS: Speak(结果)
    TTS-->>U: 主动播报
    SC->>DB: 更新执行记录
```

### 4.3 FLOW-03 多步智能体任务

```mermaid
%% diagram: FLOW-03 多步任务 | updated: 2026-10-20
flowchart LR
    A["接收任务描述"] --> B["生成计划<br/>steps[]"]
    B --> C{"还有剩余步骤?"}
    C -- 是 --> D["执行单步工具调用"]
    D --> E["观察结果"]
    E --> F{"结果符合预期?"}
    F -- 是 --> C
    F -- 否 --> G["重规划 / 放弃"]
    G --> C
    C -- 否 --> H["汇总并播报"]
    D -. "超步数上限" .-> I["终止并告知原因"]
```

> 循环范式本质是 ReAct（Reason → Act → Observe），但用**步数上限 + 时长上限**兜底，避免在开放式目标上打转。

### 4.4 SM-01 会话状态机

```mermaid
%% diagram: SM-01 会话状态机 | updated: 2026-10-20
stateDiagram-v2
    [*] --> Idle
    Idle --> Listening: 热键 / 唤醒
    Listening --> Thinking: VAD 断句
    Listening --> Idle: 取消 / 静音超时
    Thinking --> Speaking: Decision = chat
    Thinking --> ToolCalling: Decision = tool_call
    Thinking --> Planning: Decision = plan
    ToolCalling --> Thinking: 结果回填
    ToolCalling --> WaitingConfirm: 危险操作
    WaitingConfirm --> ToolCalling: 用户确认
    WaitingConfirm --> Idle: 拒绝 / 超时
    Planning --> ToolCalling: 单步执行
    Planning --> Speaking: 汇总完成
    Speaking --> Idle: 播完
    Speaking --> Listening: 用户打断
    ToolCalling --> Idle: 用户说"取消"
```

### 4.5 DM-01 领域类图

```mermaid
%% diagram: DM-01 领域模型 | updated: 2026-10-20
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
    class AuditEvent {
        +datetime ts
        +str trace_id
        +str action
        +dict payload
    }
    class ToolSpec {
        +str name
        +str description
        +dict schema
        +RiskLevel risk
    }

    Session "1" *-- "*" Turn : 包含
    Turn "1" --> "0..1" Decision : 产出
    Decision "1" --> "*" ToolCall : 发起
    ToolCall --> ToolResult : 返回
    ToolCall ..> ToolSpec : 依循
    Task "1" --> "*" Job : 派生
    ToolCall ..> AuditEvent : 记录
```

## 5. 数据模型

| 表 | 关键字段 | 用途 |
| --- | --- | --- |
| `sessions` | id, started_at, state, summary | 会话生命周期 |
| `turns` | id, session_id, role, text, latency_ms | 对话流水 |
| `tool_calls` | id, turn_id, name, args_json, status, duration_ms | 工具执行记录 |
| `tasks` | id, cron, prompt, enabled, created_at | 用户定义的周期任务 |
| `jobs` | id, task_id, fire_at, status, result | 具体触发实例 |
| `audit_events` | ts, trace_id, action, payload_json | 审计与排障 |

## 6. 时延预算（REQ-N-001 的分解）

| 环节 | 目标 | 说明 |
| --- | --- | --- |
| 断句（VAD 静音判定） | 300 ms | 可调 500–800ms，是"自然度"与"响应快"的直接权衡 |
| ASR 首字 | 400 ms | 流式返回，不等整句 |
| LLM 首 token | 600 ms | 意图判定与回复生成可并行 |
| 工具执行 | 300 ms | 本地启动类，不含网络 |
| TTS 首包 | 400 ms | 流式合成，边合成边播 |
| **合计（首音）** | **≈ 2.0 s** | 留 0.5s 余量 |

> 这张表是全双工项目里最值钱的工程资产：**任何"响应慢"的抱怨，都能拆到具体环节去定位**。

## 7. 与 M6 的可选延伸

当前架构不排斥全双工：CMP-01 换成流式双工前端、CMP-02 的状态机增加 `BargedIn` 事件即可。但**不在本项目范围内**，仅作为架构可演进性的说明。
