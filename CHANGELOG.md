# Changelog

本项目从快速 demo 进入正常开发后，发布记录以本文 + Git tag 为准。
格式参考 Keep a Changelog；版本号按需使用 `w0.x` / SemVer。

## [w0.7] - 2026-11-12

### Added

- **系统文档并入本仓**：`docs/system/` 以 `git subtree` 引入（保留文档历史），形成"一个仓两个区"
- `docs/system/docs/adr/ADR-0011-single-repo.md`：合仓决策，取代 `ADR-0010`（两仓独立）
- 根 `README.md` 增加 Intent 段（两入口 · 一脑子 · 三出口）与两区说明

### Changed

- 代码仓原有 10 份实现文档从 `docs/*.md` 移到 **`docs/impl/*.md`**，内容未改
- 根 `AGENTS.md` 改为"一个仓两个区"：代码行为以根文件为准，文档格式以 `docs/system/AGENTS.md` 为准
- `REQ-C-001` 由"只交付架构与图"改为"**文档区**只交付架构与图"
- `00-spec` §3 目录树标注"以文档区根为基准"

### Removed

- `demo.mp4`（33MB 演示视频）从工作区与索引移除；历史仍在，需要时从历史取

---
## [Unreleased]

### Added

- **`docs/impl/API.md`**：HTTP 接口契约手册——15 个 `/api/*` 端点的请求/响应字段、状态码矩阵、数据模型、`IF-01~10` 到 HTTP 的映射，成为接口的**唯一权威**
- 正常开发文档：`docs/impl/DEVELOPING.md`、`docs/impl/SECURITY.md`、`docs/impl/DECISIONS.md`、`docs/impl/GLOSSARY.md`
- README 文档阅读顺序与 Agent 开工规则

### Changed

- `ARCHITECTURE.md` §4 删除重复的接口表（已过期：缺 `/api/ocr`、`/api/avatar`，并写了不存在的 `timings` 字段），改为指向 `API.md` 并只保留跨接口约定
- `AGENTS.md` §2/§6、`README.md` 文档顺序、`DEVELOPING.md` §9 登记 `API.md`
- 发布流程改为以本仓主仓库 + GitHub Desktop 为准
- 明确 `web_fetch` SSRF、鉴权、CI、依赖锁定等待办

### Known issues

- `GET /static/*` 未校验路径是否越出 `static/` 目录，`..` 段可读到仓库内任意文件（已实测）；待独立 fix PR
- `server.py` 的 `server_version` 仍为 `VoxDeskWeb/0.5`，与 `w0.7` 版本线不一致；待 chore PR

### Fixed

- 无（待补）

## [w0.6] - 2026-11-06

### Added

- 浏览器语音对话：文字 / F2 麦克风 / F3 桌面音频
- Paraformer ASR、DeepSeek `deepseek-flash`、Piper TTS
- 多轮会话、JSON 存储、30/100/1MB 上限与归档
- `web_search` / `web_fetch` 工具与来源
- 通用 / 陪伴模式
- 陪伴像素表情：默认 / 合作愉快 / ??? / 对不起
- 表情改为提取白色像素、主题色点阵
- 陪伴语气分类（DeepSeek，positive/neutral/negative）
- `/voice` 声纹可视化

### Changed

- F3 从“按住”改为“按一下开始、再按一下停止”
- README 增加文档顺序、Agent 规则、正常开发说明

### Known issues

- 时间问题约 18s；无流式/打断
- 桌面音频兼容性未全矩阵验证
- 单用户、无鉴权
- `web_fetch` SSRF 防护不完整
- 无自动化测试 / CI / 依赖锁文件

## 更早版本

- w0.5：合并语音链路、通用/陪伴、存储、联网
- w0.4：希尔伯特阶数扩展 + 伪残影
- w0.3：声纹可视化
- w0.2：并发/预热与文档体系
- w0.1：文字 → DeepSeek → Piper → 浏览器播放
