# AGENTS.md · 给编码 agent 的操作规约

> 本文件管**"怎么在这个仓库里干活"**；`docs/00-spec.md` 管**"文档本身长什么样"**。两者冲突时以 `00-spec.md` 为准。

## 1. 仓库是什么

- **纯文档仓库**：原型阶段以图交付，不写实现代码（`REQ-C-001`）。唯一例外是 `docs/09-tts-module.md` 里的教学级示例代码。
- **唯一权威源**：`docs/`。聊天记录、口头结论、散碎笔记都不算数，落进 `docs/` 才算数（`00-spec.md` §2）。
- **流水**：`CHANGELOG.md`，只追加、不改写。

## 2. 每次改动的固定顺序

1. 改 `docs/` 正文；
2. 刷新该文档头部的 `版本` 与 `更新`；
3. `CHANGELOG.md` **顶部**追加条目（版本 + 时间 + 变更点 + 关联 ID）；
4. 涉及需求时更新追踪矩阵；
5. `git add <明确路径>` → `git commit`（格式见 §3）；
6. MINOR 及以上打 annotated tag。

## 3. commit 格式

```
<type>(<scope>): <中文摘要> [vX.Y.Z] @ <ISO8601>
```

- `type` ∈ `docs` / `feat` / `fix` / `chore` / `adr`；`scope` ∈ `spec` / `scope` / `req` / `arch` / `stack` / `roadmap` / `ref` / `peer`
- 一次 commit 只做一件事；**禁止**"顺手改一下"混提交
- 时间一律 `Asia/Shanghai`，ISO 8601

## 4. 禁止事项

| 禁止 | 原因 |
| --- | --- |
| 改历史时间戳、改已发布 CHANGELOG 条目 | 时间是证据 |
| 删除或重排任何 ID（`REQ-` / `CMP-` / `IF-` / `ADR-` / `CHG-`） | ID 永不复用 |
| 直接改写状态为 `生效` 的 ADR 结论 | 要推翻 → 新开 ADR，见 `00-spec.md` §11 |
| 动未跟踪的个人笔记 | `想法.md`、`产品调研.md`、`技术栈调研.md`、`开源软件调研.md`、`语音转文字.md`、`开会记录.md` 属作者私有 |
| `git add -A` / `git add .` | 会误收上述笔记 |
| 贴截图、用 PlantUML/draw.io | 图必须 Mermaid、可 diff（`00-spec.md` §2） |
| 把 `papers_archive` 的 PDF 搬进本仓库 | 体积与隐私；引用只写路径 |

## 5. 环境

- **Windows 11 + PowerShell**（`REQ-C-005`）；路径用原生 `D:\...`
- **Python 3.11 + uv**（`04-tech-stack.md` §1.4）；`uv run` 跑脚本，不装全局 Python
- 本机实测：`uv 0.13.5`，**PATH 上没有 Python**；缺解释器时 `uv python install 3.11`

## 6. 改前先看这三个指针

| 指针 | 位置 |
| --- | --- |
| 当前阶段 | `README.md` 顶部（当前 M0.5 · TTS 切片，M1 未开工） |
| 未决项 | `CHANGELOG.md` 最新的"仍需你决定" |
| 外部边界 | `docs/adr/ADR-0010-two-repo-boundary.md`（与同伴仓库完全独立） |

## 7. 写作口径

- 正文中文，技术名词保留英文原词，首次出现给中文解释
- 需求写"系统能……"，不写"用户想要……"
- 数字必须带来源与时间；来自外部仓库的数字**引用前重测**（`docs/11` §2.3 有 6 条前车之鉴）
