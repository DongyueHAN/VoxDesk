# ADR-0003 · 调度采用 APScheduler + SQLite JobStore

| 字段 | 值 |
| --- | --- |
| 状态 | 已提议 |
| 日期 | 2026-10-20 12:12 +08:00 |
| 相关 | REQ-F-030、REQ-F-031、REQ-F-033 |

## 背景

需要支持"20 分钟后提醒我"（一次性延时）与"每天九点"（周期）两类任务，且进程重启后任务不能丢。候选：

- **A**：自研轮询（每分钟扫表）
- **B**：APScheduler + `SQLAlchemyJobStore`
- **C**：Celery + Redis/RabbitMQ

## 决策

采用 **B**。JobStore 直接复用主库的 SQLite 文件，不引入第二个存储。

## 理由

1. APScheduler 原生支持 `DateTrigger` / `CronTrigger`，语义与需求一一对应。
2. JobStore 落库即获得持久化，"重启不丢"不需要自己实现。
3. Celery 需要 broker 与被调进程，单机场景属于明确的过度设计。

## 后果

- **正面**：代码量小；cron 表达式可读；调试时能直接看表。
- **负面**：APScheduler 与异步事件循环混用需谨慎（用 `AsyncIOScheduler`）。
- **注意**：必须设 `misfire_grace_time`，否则关机错过的任务会被静默丢弃。

## 备选为何不选

- 自研轮询：看似简单，实则要自己处理时区、DST、并发与补跑，坑比想象多。
- Celery：为分布式而生，单机引入只会增加部署与排障成本。
