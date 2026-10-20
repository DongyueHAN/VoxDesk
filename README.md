# VoxDesk · 桌面语音智能体

> 一个跑在 PC 上的语音对话 Agent：听懂人话 → 开程序 → 调 API → 排定时任务 → 跑多步自动化。
> **本仓库是工程文档仓库，架构先于代码。** 原型阶段以图交付，不含实现。

| 项 | 值 |
| --- | --- |
| 当前版本 | **v0.1.0（草案，待评审）** |
| 文档定稿 | 2026-10-20 12:12 +08:00 |
| 当前阶段 | M0 · 文档基线 |
| 代码状态 | 无代码，仅架构设计与图 |
| 仓库根 | `full-deplux dialogue system/` |

---

## 1. 一句话讲清这个项目

不是复刻小爱同学，而是借它的**功能形态**，做一个能在自己电脑上干活儿的语音入口：
说话 → 理解 → **真的把事办了**（开程序 / 调接口 / 定闹钟 / 跑一段自动化），再把结果说给你听。

参考对象：

- **小爱同学** —— 功能形态与技能体系的参照（能力边界、技能路由、定时提醒、设备控制）
- **OpenClaw** —— 交互范式与系统分层的参照（Gateway / Agent Runtime / Tools / Cron / 审批）

详见 [docs/06-reference-landscape.md](docs/06-reference-landscape.md)。

## 2. 文档地图

| 文件 | 内容 | 状态 |
| --- | --- | --- |
| [docs/00-spec.md](docs/00-spec.md) | **文档规范**：版本、时间戳、编号、图规范、更新流程 | 待确认 |
| [docs/01-scope.md](docs/01-scope.md) | 范围、场景、非目标 | 草案 |
| [docs/02-requirements.md](docs/02-requirements.md) | 需求池 REQ-F/N/C + 验收标准 | 草案 |
| [docs/03-architecture.md](docs/03-architecture.md) | 架构：C4 分层、时序、状态机、类图 | 草案 |
| [docs/04-tech-stack.md](docs/04-tech-stack.md) | 技术栈选型与取舍 | 草案 |
| [docs/05-roadmap.md](docs/05-roadmap.md) | 里程碑拆解 M0–M6 | 草案 |
| [docs/06-reference-landscape.md](docs/06-reference-landscape.md) | 小爱 / OpenClaw / 竞品 功能与技术对照 | 草案 |
| [docs/adr/](docs/adr/) | 架构决策记录 | — |
| [CHANGELOG.md](CHANGELOG.md) | 版本变更流水（含时间戳与 commit） | 现行 |

## 3. 怎么读

1. 先读 [docs/00-spec.md](docs/00-spec.md)，确认这份文档怎么维护；
2. 再读 [docs/01-scope.md](docs/01-scope.md)，确认做到哪、不做什么；
3. 架构图在 [docs/03-architecture.md](docs/03-architecture.md)；
4. 想看"这活儿怎么拆、多久做完"，去 [docs/05-roadmap.md](docs/05-roadmap.md)。

## 4. 版本记录

| 版本 | 时间 | 摘要 |
| --- | --- | --- |
| v0.1.0 | 2026-10-20 12:12 +08:00 | 建立文档规范、范围、需求池、架构基线、技术栈、里程碑拆解 |

完整流水见 [CHANGELOG.md](CHANGELOG.md)。
