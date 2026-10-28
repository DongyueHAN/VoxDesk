# VoxDesk · 桌面语音智能体

> 一个跑在 PC 上的语音对话 Agent：**全本地推理，断网可用**。听懂人话 → 开程序 → 查笔记 → 排定时任务 → 把复杂活儿转给编码 agent。
> **本仓库是工程文档仓库，架构先于代码。** 原型阶段以图交付，不含实现。

| 项 | 值 |
| --- | --- |
| 当前版本 | **v0.4.0（+ TTS 模块设计，准备开工）** |
| 文档定稿 | 2026-10-28 14:35 +08:00 |
| 当前阶段 | M0.5 · TTS 模块（第一个可交付切片） |
| 代码状态 | 待开工：三阶段路线与接口契约已定 |
| 关键技术决策 | 本地优先、半双工先行、自研语音管线、委托 harness |

---

## 1. 一句话讲清这个项目

借小爱同学的**功能形态**、OpenClaw 的**工程分层**，做一个能在自己电脑上干活儿的语音入口：
说话 → 理解 → **真的把事办了**（开程序 / 查笔记 / 定闹钟 / 把难活转给 agent），再把结果说给你听。

**差异化**：小爱离不开云，OpenClaw 离不开云模型，这个项目**用嘴、离线、在本机干活**。

参考对象：

- **小爱同学** —— 功能形态与端侧工程（唤醒、降噪、技能路由、定时提醒）
- **OpenClaw** —— 系统分层与生态集成（Gateway / Runtime / Tools / Cron / 审批）

详见 [docs/06-reference-landscape.md](docs/06-reference-landscape.md)。

## 2. 文档地图

| 文件 | 内容 | 状态 |
| --- | --- | --- |
| [docs/00-spec.md](docs/00-spec.md) | **文档规范**：版本、时间戳、编号、图规范、更新流程 | 待确认 |
| [docs/01-scope.md](docs/01-scope.md) | 范围、场景、非目标、成功标准 | v0.2.0 |
| [docs/02-requirements.md](docs/02-requirements.md) | 需求池 60 条（REQ-F/N/C）+ 验收标准 | v0.2.0 |
| [docs/03-architecture.md](docs/03-architecture.md) | 架构：5 层、C4、6 张流程图、状态机、类图 | v0.2.0 |
| [docs/04-tech-stack.md](docs/04-tech-stack.md) | **技术栈**：语言、框架、端侧四项、接入层 | v0.2.0 |
| [docs/05-roadmap.md](docs/05-roadmap.md) | 里程碑拆解 M0–M7 | v0.2.0 |
| [docs/06-reference-landscape.md](docs/06-reference-landscape.md) | 小爱 / OpenClaw / 竞品 对照 | v0.2.0 |
| [docs/07-model-layer.md](docs/07-model-layer.md) | **模型层**：选型、运行时、内存预算、工具调用可靠性 | v0.2.0 |
| [docs/08-oss-shortlist.md](docs/08-oss-shortlist.md) | **开源选型**：STT 与系统调用 harness 候选、许可与活跃度 | v0.3.0 |
| [docs/09-tts-module.md](docs/09-tts-module.md) | **TTS 模块**：语言、架构、接口、三阶段实施与首日代码 | v0.4.0 |
| [docs/adr/](docs/adr/) | 架构决策记录（9 份） | — |
| [CHANGELOG.md](CHANGELOG.md) | 版本变更流水（含时间戳） | 现行 |

## 3. 怎么读

1. 先读 [docs/01-scope.md](docs/01-scope.md)，确认做到哪、不做什么；
2. 架构图在 [docs/03-architecture.md](docs/03-architecture.md)；
3. 选型理由在 [docs/04-tech-stack.md](docs/04-tech-stack.md) 与 [docs/07-model-layer.md](docs/07-model-layer.md)；
4. 想知道"为什么这么定"，翻 [docs/adr/](docs/adr/)；
5. 这活儿怎么拆、多久做完，看 [docs/05-roadmap.md](docs/05-roadmap.md)。

## 4. 版本记录

| 版本 | 时间 | 摘要 |
| --- | --- | --- |
| v0.4.0 | 2026-10-28 14:35 +08:00 | 新增 TTS 模块设计：三阶段路线、WAV 为界的接口契约、首日可跑代码 |
| v0.3.0 | 2026-10-27 14:40 +08:00 | 新增开源选型清单（STT/系统调用）；核查出 Piper 归档转 GPL 等三项维护性风险 |
| v0.2.0 | 2026-10-26 14:30 +08:00 | 转向本地优先；半双工先行；新增端侧四项、模型层、接入层；需求 39→60 条 |
| v0.1.0 | 2026-10-20 12:12 +08:00 | 建立文档规范、范围、需求池、架构基线、技术栈、里程碑拆解 |

完整流水见 [CHANGELOG.md](CHANGELOG.md)。
