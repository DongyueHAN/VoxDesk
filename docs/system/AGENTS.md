# AGENTS.md · 给编码 agent 的操作规约（系统文档仓）

> **本文件与 `README.md` 是本仓库的最高约定。**
> `README` 管"这个项目是什么"（给人看），本文件管"在这个仓库里怎么干活"（给 agent 看）。
> `docs/00-spec.md` 是**下位细则**，只定义文档长什么样（字段、编号、图、模板）；
> **两类规则冲突时，以本文件与 `README.md` 为准**，然后把 `00-spec` 改过来——不能让下位规则反过来管上位。

## 1. 这个仓库是什么

- **文档区**（`docs/system/`）：方向、范围、需求、架构、选型、里程碑、ADR；**不写实现代码**（`REQ-C-001` 已随之改写）。
- **唯一权威源是 `docs/`**：聊天记录、口头结论、散碎笔记都不算数，落进 `docs/` 才算数。
- **不重复代码区的事实**：实测数字、接口签名、模块清单以 `docs/impl/STATUS.md` / `docs/impl/ARCHITECTURE.md` 为准，这里只引用、不抄写。

## 2. 每次改动的固定顺序

1. 改 `docs/` 正文；
2. 刷新该文档头部的 `版本` 与 `更新`；
3. `CHANGELOG.md` **顶部**追加条目（版本 + 时间 + 变更点 + 关联 ID）；
4. 涉及需求时更新 `02` §5 的追踪矩阵；
5. 若动了文档集合（新增 / 改名 / 退役），同步 `README.md` 文档地图与 `00-spec` §3 目录树；
6. `git add <明确路径>` → `git commit`（格式见 §3）；
7. MINOR 及以上打 annotated tag。

## 3. commit 与版本

```
<type>(<scope>): <中文摘要> [vX.Y.Z] @ <ISO8601>
```

| 项 | 取值 |
| --- | --- |
| `type` | `docs` / `feat` / `fix` / `chore` / `adr` |
| `scope` | `spec` / `scope` / `req` / `arch` / `stack` / `roadmap` / `ref` / `process` / `meta` |
| 时间 | 一律 `Asia/Shanghai`，ISO 8601 |

- 一次 commit 只做一件事，不许"顺手改一下"混提交。
- **版本号三位的含义**（MAJOR / MINOR / PATCH）见 `00-spec` §5.1——那是编号语义，不是流程。
- **tag 只在 MINOR 及以上打**；PATCH 靠 commit 追溯。

## 4. 禁止事项

| 禁止 | 原因 |
| --- | --- |
| 改历史时间戳、改已发布的 CHANGELOG 条目 | 时间是证据 |
| 删除或重排任何 ID（`REQ-` / `CMP-` / `IF-` / `ADR-` / `CHG-`） | ID 永不复用 |
| 直接改写状态为 `生效` 的 ADR 结论 | 要推翻 → 新开 ADR（`00-spec` §11） |
| 贴截图、用 PlantUML / draw.io / Excalidraw | 图必须 Mermaid、可 diff |
| `git add -A` / `git add .` | 会误收作者私有笔记与研究资料 |
| 动 `灵感与开会/`、`调研/` | 两者都被 `.gitignore` 排除，属作者私有 |
| 在本仓写"代码怎么实现" | 那是代码仓 `docs/ARCHITECTURE.md` 的职责 |
| 把 `调研/` 下的 PDF / HTML 搬进仓库 | 体积与隐私 |

## 5. 环境

- **Windows 11 + PowerShell**（`REQ-C-005`）；路径用原生 `D:\...`
- **Python 3.11 + uv**（仅在要跑校验脚本时）；`uv run`，不装全局 Python

## 6. 数字纪律

- 数字必须带**来源与时间**；外部仓库 / 第三方的数字，引用前先重测。
- 状态、覆盖率、通过率这类"看起来客观"的数，宁可写"未测"，也不许估。

## 7. 动手前先看这几个指针

| 指针 | 位置 |
| --- | --- |
| 当前阶段与冲刺 | `README.md` §3 进度 + `docs/08-M2process.md` |
| 未决项 | `docs/11-decisions.md` §1（`DEC-0xx`）——唯一索引；`CHANGELOG` 里的 `### 未决事项` 只是历史快照 |
| 怎么分工 | `docs/12-team-and-workpackages.md`（6 个工作包 + 接口契约） |
| 外部边界 | `docs/adr/ADR-0010-two-repo-boundary.md` |

## 8. 什么时候算"阶段性完成"

做不到就别提交：

1. `README.md` §3 与 `docs/07-roadmap.md` §1 的状态逐行一致；
2. 新写的设计 / 决策能追溯到 `docs/` 某一份文件；
3. 退役文档进 `docs/archive/`，并在 `docs/archive/README.md` 写明原因；
4. `CHANGELOG.md` 有对应条目。
