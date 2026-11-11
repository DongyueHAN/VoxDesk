# 已退役文档（archive）

> 这里存的是**原件**，不删内容：目的只有一个——需要"当时为什么这么定"的细节时能查到。
> **日常交接不需要读这里**；下面写清每份为什么退役、现在该看哪里。

| 文件 | 原编号 | 退役原因 | 现在看哪里 |
| --- | --- | --- | --- |
| [`08-oss-shortlist.md`](08-oss-shortlist.md) | 08 | 开源调研清单（26KB，含 star/许可/活跃度快照）。选型结论已固化，数据会过期 | `04-tech-stack.md`（结论与前因）+ `docs/adr/` |
| [`09-tts-module.md`](09-tts-module.md) | 09 | TTS 模块的实现设计（接口、三阶段、教学代码）。实现已完成，代码与实测在代码仓 | 代码仓 `tts/README.md` + `docs/ARCHITECTURE.md` §2 |
| [`11-peer-repo-crosscheck.md`](11-peer-repo-crosscheck.md) | 11 | 同伴仓库的一次性核查（12 条不一致）。该仓库已不参与本项目 | `docs/adr/ADR-0010-two-repo-boundary.md` |
| [`12-M1process.md`](12-M1process.md) | 12 | M1 已完成；其中的三轴节奏、闸门、五条不变式是通用规则，仍然有效 | `README.md` §5 阅读路径 + 代码仓 `docs/HANDOFF.md` §4 |

## 保留但不在主路径上的文档

| 文件 | 为什么还留着 |
| --- | --- |
| [`../06-oss-and-products.md`](../06-oss-and-products.md) | 开源件与成品清单，解释"外面有什么"；体积小、不常变（2026-11-11 由 `06-reference-landscape.md` 重写而来） |

## 规则

- 退役 = `git mv` 到本目录 + 在这里登记一行 + 全局搜索并修正引用；**不删除文件**。
- 本目录内的文档不再更新版本号与日期；它们冻结在退役那一刻。
- 新增退役文档时，同时在 `docs/00-spec.md` §3 的目录树里登记 `archive/`。
