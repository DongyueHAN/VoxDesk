# ADR-0011 · 系统文档与代码合入同一仓库（取代 ADR-0010）

| 字段 | 值 |
| --- | --- |
| 状态 | 生效 |
| 日期 | 2026-11-12 02:30 +08:00 |
| 相关 | `ADR-0010`、`REQ-C-001`、`docs/system/AGENTS.md`、`REQ-N-002` |

## 背景

`ADR-0010` 定的是"系统文档仓与代码仓完全独立，只保留概念层接缝"。当时成立：文档仓是纯规范，代码仓是纯实现，两边各自演进。

半年后三个事实推翻了它：

1. **合成成本开始高于隔离收益**：改一个选型要在两个仓各提交一次，`CHANGELOG` 两条版本线各记一遍；
2. **门面重复**：两个 `README.md`、两个 `AGENTS.md`，新 agent 必须两份都读才知道该看哪个；
3. **事实漂移**：文档说"实测数字在代码仓 `docs/STATUS.md`"，但代码仓的 `STATUS.md` 一直没跟上 `v2.0.0` 的两入口三出口，
   规范与实现已经对不上——**隔离本身就是漂移的温床**。

## 决策

**把系统文档仓作为 `docs/system/` 子树并入代码仓**，形成一个仓、两个区：

| 区 | 路径 | 职责 |
| --- | --- | --- |
| **规范区** | `docs/system/` | Intent / 范围 / 需求 / 架构 / 选型链 / 路线 / 决策 / 分工 |
| **实现区** | `docs/impl/` | 状态、坑、实现决策、开发流程、发布说明 |
| **代码** | 仓根 | `server.py`、`voice_app.py`、`static/` … |

- 文档历史用 `git subtree` 保留（`bfe6f6d` 引入 `docs/system/`）；
- 两条 `CHANGELOG` 版本线**不合并**：根 `CHANGELOG.md` 记代码，`docs/system/CHANGELOG.md` 记规范；
- 根 `README.md` 与 `AGENTS.md` 重写为总门面，文档区仍有自己的 `docs/system/README.md` / `AGENTS.md`。

## 理由

- **一个 checkout 拿到全部**：clone 下来既能跑，也能查"为什么这么设计"；
- **引用变成相对路径**：`docs/system/` 里的 `D:\VoxDesk` 全部改为本仓相对路径，链接校验能机器跑；
- **保留历史**：`subtree` 而非拷贝，`git log docs/system/docs/01-scope.md` 仍能看到逐版演进。

## 代价

| 代价 | 说明 |
| --- | --- |
| **两个 AGENTS 要同时维护** | 代码行为以根 `AGENTS.md` 为准，文档格式以 `docs/system/AGENTS.md` 为准；冲突时按这个分派 |
| **`subtree` 的合并噪音** | 将来从旧文档仓更新要 `git subtree pull`，不是普通 merge |
| **仓库变大** | 代码 + 文档 + 两份历史；实测文本压缩后约 0.3MB，可接受 |
| **Obsidian 断链** | 文档离开 vault（`D:\Obsidian\Geist\Projects\...`），Obsidian 内的相对链接不再解析——文档区以 Markdown 相对路径为准，不再依赖 vault |

## 后续

- `ADR-0010` 标 `已取代（by ADR-0011，2026-11-12）`；
- `REQ-C-001` 由"只交付架构与图"改为"**文档区**只交付架构与图，实现只在代码区"；
- 旧的独立文档仓不再更新，作为历史归档保留。
