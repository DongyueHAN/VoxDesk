# Changelog

本项目从快速 demo 进入正常开发后，发布记录以本文 + Git tag 为准。
格式参考 Keep a Changelog；版本号按需使用 `w0.x` / SemVer。

## [Unreleased]

### Added

- 正常开发文档：`docs/DEVELOPING.md`、`docs/SECURITY.md`、`docs/DECISIONS.md`、`docs/GLOSSARY.md`
- README 文档阅读顺序与 Agent 开工规则

### Changed

- 发布流程改为以 `D:\VoxDesk` 主仓库 + GitHub Desktop 为准
- 明确 `web_fetch` SSRF、鉴权、CI、依赖锁定等待办

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
