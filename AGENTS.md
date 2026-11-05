# AGENTS.md · 给编码 agent 的操作规约（系统文档仓）

> 本文件管**"怎么在这个仓库里干活"**；`docs/00-spec.md` 管**"文档本身长什么样"**。冲突时以 `00-spec.md` 为准。

## 1. 这个仓库是什么

- **纯文档仓库**：方向、范围、需求、架构设计、选型、里程碑、ADR。**不写实现代码**（`REQ-C-001`）。
- **唯一权威源**是 `docs/`：聊天记录、口头结论、散碎笔记都不算数，落进 `docs/` 才算数（`00-spec.md` §2）。
- **不重复代码仓的事实**：实测数字、接口签名、已实现清单以代码仓 `D:\VoxDesk` 的 `docs/STATUS.md` / `docs/ARCHITECTURE.md` 为准，本仓只引用不抄写。

## 2. 每次改动的固定顺序

1. 改 `docs/` 正文；
2. 刷新该文档头部的 `版本` 与 `更新`；
3. `CHANGELOG.md` **顶部**追加条目（版本 + 时间 + 变更点 + 关联 ID）；
4. 涉及需求时更新追踪矩阵；
5. 若动了文档集合（新增/退役），同步 `README.md` 的文档地图与 `docs/00-spec.md` §3 目录树；
6. `git add <明确路径>` → `git commit`（格式见 §3）；
7. MINOR 及以上打 annotated tag。

## 3. commit 格式

```
<type>(<scope>): <中文摘要> [vX.Y.Z] @ <ISO8601>
```

- `type` ∈ `docs` / `feat` / `fix` / `chore` / `adr`
- `scope` ∈ `spec` / `scope` / `req` / `arch` / `stack` / `roadmap` / `ref` / `process` / `meta`
- 一次 commit 只做一件事；时间一律 `Asia/Shanghai`，ISO 8601

## 4. 禁止事项

| 禁止 | 原因 |
| --- | --- |
| 改历史时间戳、改已发布 CHANGELOG 条目 | 时间是证据 |
| 删除或重排任何 ID（`REQ-` / `CMP-` / `IF-` / `ADR-` / `CHG-`） | ID 永不复用 |
| 直接改写状态为 `生效` 的 ADR 结论 | 要推翻 → 新开 ADR（`00-spec.md` §11） |
| 动未跟踪的个人笔记 | `想法and调研and开会/`、`README-team.md` 属作者私有 |
| `git add -A` / `git add .` | 会误收上述笔记与研究资料 |
| 贴截图、用 PlantUML/draw.io | 图必须 Mermaid、可 diff（`00-spec.md` §2） |
| 把 `HumDial-Challenge-调研/`、`小爱同学-调研/` 的 PDF 搬进本仓库 | 体积与隐私；已被 `.gitignore` 排除 |
| 在本仓写"代码怎么实现" | 那是代码仓 `docs/ARCHITECTURE.md` 的职责 |

## 5. 环境

- **Windows 11 + PowerShell**（`REQ-C-005`）；路径用原生 `D:\...`
- **Python 3.11 + uv**（仅当需要跑校验脚本时）；`uv run`，不装全局 Python
- 本机实测：`uv 0.13.5`，PATH 上没有 Python

## 6. 改前先看这三个指针

| 指针 | 位置 |
| --- | --- |
| 当前阶段与冲刺 | `README.md` §3 进度 + `docs/08-M2process.md` |
| 未决项 | `CHANGELOG.md` 最新条目里的"仍需你决定" |
| 外部边界 | `docs/adr/ADR-0010-two-repo-boundary.md`（两仓独立，只保留概念层接缝） |

## 7. 写作口径

- 正文中文，技术名词保留英文原词，首次出现给中文解释
- 需求写"系统能……"，不写"用户想要……"
- 数字必须带来源与时间；外部仓库的数字引用前重测
- 一份文档只回答一个问题；写不下就拆文件

## 8. 交接要求

任何一次"阶段性完成"的提交，必须满足：

1. `README.md` §3 进度表与实际一致；
2. 新写的设计/决策能追溯到 `docs/` 的某一份文件；
3. 退役的文档进了 `docs/archive/` 且 `docs/archive/README.md` 写明原因；
4. `CHANGELOG.md` 有对应条目。

做不到就别提交。
