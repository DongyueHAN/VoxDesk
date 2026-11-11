# VoxDesk · 系统文档仓

> **这个仓库回答"为什么做、做成什么样"，代码仓回答"实际做成什么样"。**
> 原型阶段以图与文字交付，不写实现代码（`REQ-C-001`）；想跑起来看代码仓。

| 项 | 值 |
| --- | --- |
| 版本 | **v1.3.0**（2026-11-11 悬空引用与图 ID 校正；v1.2.0 = 龙骨 + 选型决策落地） |
| 当前阶段 | **双线**：A 线（原框架）M2 收尾；B 线（Web）已跑到 w0.6，见 `09` |
| 代码仓 | `D:\VoxDesk`（`master` 主线 · `demo/deepseek-voice` 演示） |
| 权威源 | 本仓 `docs/`；聊天记录与口头结论不算数 |

## 1. 龙骨：Intent → Specification → Implement

这个仓库、代码仓、以及每一次改动，都挂在同一条骨架上。**先立意图，再写规范，最后才是代码。**

### 1.1 Intent（为什么做、为谁做）

| 层 | Intent |
| --- | --- |
| **项目意图** | 一份**求职简历项目**：用来证明端侧工程与系统编排能力 |
| **个人意图** | 一个**边学边做**的项目：每加一块就学会一块，不追求一次做对 |
| **市场意图** | 结合**兴趣与真实需求**：本地优先的语音入口，能开程序、查笔记、排任务 |
| **长期意图** | 最终做成一个**类似 neuro-sama 的"智能生命"**：能持续在场、有记忆、有性格 |

> Intent 会变，Spec 跟着变，代码最后变。**顺序不能倒**——先写代码再补意图，就会得到"能跑但不知道为什么"的仓库（本项目的 Web 线已经出现过一次）。

### 1.2 Specification（本仓的职责）

| 文档 | 给出的规范 |
| --- | --- |
| `docs/01-scope.md` | 范围与非目标（什么不做） |
| `docs/02-requirements.md` | 可验收的需求（P0–P3 + 验收标准） |
| `docs/03-architecture.md` | 系统级契约：分层、时序、状态机 |
| `docs/04-tech-stack.md` | 选型与理由（用什么造） |
| `docs/05-roadmap.md` | 里程碑与验收口径（先造哪个） |
| `docs/07-model-layer.md` | 模型层契约：预算、运行时、工具调用可靠性 |
| `docs/09-web-implementation.md` | 实现现状的验收记录（B 线） |
| `docs/10-code-reading.md` | 怎么读、怎么写：本次方法的操作手册 |

### 1.3 Implement 与 Evidence（代码仓的职责）

| 层 | 位置 |
| --- | --- |
| **Implement** | 代码仓 `D:\VoxDesk`：`audio/`、`tts/`、`server.py`、`voice_app.py` 等 |
| **Evidence** | 代码仓 `docs/STATUS.md` 的实测数字；`docs/PITFALLS.md` 的坑 |

### 1.4 两个仓库怎么分工

| 仓库 | 管什么 | 谁读 | 入口 |
| --- | --- | --- | --- |
| **系统仓（本仓）** | Intent + Specification：范围、需求、架构、选型、里程碑、ADR | 人（定方向）、agent（理解约束） | 本文件 §1 → `docs/01-scope.md` → `docs/03-architecture.md` |
| **代码仓** `D:\VoxDesk` | Implement + Evidence：能跑的代码、实测数字、交接清单 | 人（跑起来）、agent（改代码） | 代码仓 `README.md` → `docs/STATUS.md` → `docs/HANDOFF.md` |

一条规矩：**同一事实只写在一边**。实测数字与接口以代码仓为准；范围、需求与决策以本仓为准。

## 2. 全局方向（一屏读完）

做一个**跑在自己电脑上的语音入口**：说话 → 理解 → 真的把事办了（开程序 / 查笔记 / 定闹钟 / 把难活转给编码 agent）→ 说给你听。

三条约束（**注意：第 1 条是终态目标，不是当前阶段的验收条件**）：

1. **本地优先（终态）**：最终要断网可用；但 **B 线现阶段允许云端推理**（DeepSeek），因为本地 LLM 尚未接入。A 线继续按离线目标推进（`ADR-0005`）。
2. **半双工先行**：全双工与 AEC 列为 P3，不在当前范围（`ADR-0006`、`REQ-F-013`）。
3. **自己编排、不自研模型**：价值在端侧工程与系统编排，不在训练（`01-scope.md`）。

参考对象：小爱同学（功能形态与端侧工程）、OpenClaw（系统分层与生态集成），详见 `docs/06-reference-landscape.md`。

## 3. 进度

| 里程碑 | 内容 | 状态 |
| --- | --- | --- |
| M0 | 立项、范围、架构、需求 | ✅ |
| M1 | 音频前端（采集 / 降噪 / VAD / PTT） | ✅ |
| **M2** | S4 识别 ✅ · **S5 本地 LLM** ⬜ · S6 唤醒词 ⬜ · S7 串联 ⬜ | 🟡 1/4 |
| M3 | 工具执行 + 风险分级 | ⬜ |
| M4 | 定时任务 | ⬜ |
| M5 | Obsidian 知识接入 / 编码 agent 桥 | ⬜ |
| M6 | 多步任务、托盘、音质升级 | ⬜ |

实测数字（播报 RTF 0.026、端点 0/50、ASR 首字 39ms 等）在代码仓 `docs/STATUS.md`，本仓不复述。

## 4. 文档地图

| 文件 | 回答什么问题 |
| --- | --- |
| [`docs/00-spec.md`](docs/00-spec.md) | 文档规范：版本、时间戳、编号、图规范、ADR 生命周期 |
| [`docs/01-scope.md`](docs/01-scope.md) | 范围、场景、非目标、成功标准 |
| [`docs/02-requirements.md`](docs/02-requirements.md) | 需求池 67 条（`REQ-*`）+ Intent/Requirements 讨论 |
| [`docs/03-architecture.md`](docs/03-architecture.md) | **权威架构**：C4、6 条流程（`FLOW-01`~`06`）、半双工状态机、领域类图 |
| [`docs/04-tech-stack.md`](docs/04-tech-stack.md) | 技术栈与选型理由（含端侧四项） |
| [`docs/05-roadmap.md`](docs/05-roadmap.md) | 里程碑拆解 M0–M7 |
| [`docs/06-reference-landscape.md`](docs/06-reference-landscape.md) | 小爱 / OpenClaw / 竞品对照 |
| [`docs/07-model-layer.md`](docs/07-model-layer.md) | 模型层：选型、运行时、内存预算、工具调用可靠性 |
| [`docs/08-M2process.md`](docs/08-M2process.md) | **A 线冲刺**：M2 的 S4–S7、闸门、时延/显存预算 |
| [`docs/09-web-implementation.md`](docs/09-web-implementation.md) | **当前实现验收**：VoxDesk-Web w0.6 的接口、能力、偏差 | 
| [`docs/10-code-reading.md`](docs/10-code-reading.md) | **读/写代码方法**：Intent → Specification → Implement |
| [`docs/adr/`](docs/adr/) | 10 份架构决策记录（`ADR-0001`…`0010`） |
| [`docs/archive/`](docs/archive/README.md) | 已退役文档（08/09/11/12 原件，仅备查） |
| [`CHANGELOG.md`](CHANGELOG.md) | 变更流水（只追加，是"何时改了什么"的唯一记录） |

## 5. 怎么读（两条路径）

**agent 接手（约 10 分钟）**

1. 本文 §2 方向与 §1 分工；
2. `docs/01-scope.md` —— 不做什么比做什么更重要；
3. `docs/03-architecture.md` §2–§3 —— 记住 5 层 12 组件与主链路；
4. `docs/08-M2process.md` —— 当前冲刺的闸门与预算；
5. 需要改代码时，转到代码仓的 `AGENTS.md` 与 `docs/HANDOFF.md`。

**人了解（约 30 分钟）**

本文 → `docs/01-scope.md` → `docs/05-roadmap.md` → `docs/03-architecture.md`（只看图）→ 代码仓 `README.md`。

## 6. 变更与版本

- 版本流水见 [`CHANGELOG.md`](CHANGELOG.md)；git tag 标记发布（`v0.0` = 重构前基线，`v1.0` = 本次重构后）。
- 研发顺序：**改正文 → 刷新文档头 → 追加 CHANGELOG → 提交 → MINOR+ 打 tag**（`AGENTS.md` §2）。
- 退役文档不删内容，移入 `docs/archive/` 并在 [`docs/archive/README.md`](docs/archive/README.md) 说明退役原因。
