# 正常开发指南（DEVELOPING）

> 目标：从“能演示”升级为“能维护、能回归、能交接”。
> 适用仓库：`D:\VoxDesk`，当前分支 `web/w0.6`。
> 先读 README 的文档顺序，再按本文执行。

## 1. 开工前基线

```powershell
cd D:\VoxDesk
git status --short
git branch --show-current
git log --oneline -5

.\start.ps1
Invoke-RestMethod http://127.0.0.1:8800/api/health
```

基线必须满足：

- `ok=true`
- `asr_loaded=true`
- `tts_loaded=true`
- `api_key=true`
- 浏览器能打开 `http://127.0.0.1:8800/`

如果基线失败，先修环境；不要在坏基线上叠功能。

## 2. 分支与提交

### 推荐流程

```text
web/w0.6（默认/集成分支）
  └─ feat/<topic>  或  fix/<topic>
       └─ PR → review → merge
```

- 一个分支只做一件事；不要把“换模型 + 改 UI + 改存储”塞进一个 PR。
- 默认分支不直接堆实验代码；至少保留一个可回滚提交。
- 提交信息写“为什么”，不要只写“update”。
- 禁止 `git add -A`；显式 add 文件。
- 不提交：模型、`data/`、`out/`、`.env`、`*.wav`、`defense/`、缓存、截图产物。

### 版本

- 可演示节点用 `w0.x` tag；正式开发用语义化版本。
- 每次发布写 changelog：新增、修复、破坏性变更、已知问题。
- 版本记录维护在 [`CHANGELOG.md`](../../CHANGELOG.md)。

## 3. 本地质量门

每次改动至少运行：

```powershell
# Python 语法
& 'D:\VoxDesk\demo\.venv\Scripts\python.exe' -m py_compile `
  server.py voice_app.py llm.py search.py store.py prompts.py paths.py

# 前端语法
node --check static\app.js

# 快速 smoke
$body = @{ text='你好'; web=$false; speak=$false; mode='general' } | ConvertTo-Json -Compress
Invoke-RestMethod http://127.0.0.1:8800/api/chat -Method Post `
  -ContentType 'application/json; charset=utf-8' `
  -Body ([Text.Encoding]::UTF8.GetBytes($body))
```

涉及音频/TTS 时再测：

- `/api/asr`：16k 单声道 PCM，返回 `text` 非空；
- `/api/chat` + `speak=true`：返回 `audio`，且文件存在；
- 浏览器：F2、F3、朗读、停止、陪伴模式表情。

> 只跑 `py_compile` 不等于功能验证；必须给实测数字或明确写“未验证”。

## 4. 测试矩阵

| 层 | 当前手段 | 正常开发应补 |
| --- | --- | --- |
| 存储 | 临时目录测 30/100/1MB | pytest：上限、归档 FIFO、原子写、损坏 JSON |
| LLM | 真实 API 手测 | mock `DeepSeekChat`；工具循环/超时/空回复 |
| ASR | 固定 wav 手测 | CER 集、静音/短音频/长音频 |
| TTS | 合成一次听 | 文本切分、特殊字符、失败回退 |
| API | `Invoke-RestMethod` | 契约测试：字段、状态码 400/404/409/413/502 |
| UI | Chrome CDP + 假麦克风 | Playwright/Cypress：F2/F3、表情、归档、错误态 |
| 安全 | 人工检查 | SSRF、路径穿越、密钥泄漏、限流 |

### 最低回归清单（每次改核心链路）

1. 文字对话；
2. F2 录音 → ASR → 回答；
3. `speak=true` 有 wav；
4. 刷新后会话仍在；
5. 归档/恢复/删除；
6. 陪伴模式表情状态；
7. 409/413 边界提示。

## 5. 代码与契约

- `server.py`：只做 HTTP/路由/序列化；业务放 `voice_app.py`。
- `voice_app.py`：编排；不要把工具循环塞进路由。
- `llm.py`：只负责 DeepSeek 请求；新增分类/工具要有超时和异常语义。
- `store.py`：所有文件写走同一把锁；schema 变化要写迁移/兼容策略。
- `search.py`：URL 校验、超时、缓存、错误必须可区分。
- `static/app.js`：无框架；新增状态要有默认值/历史恢复/错误态。
- API 新增字段优先向后兼容；删除/重命名字段要升版本并更新前端。

## 6. 依赖与模型

- `requirements.txt` 目前是范围约束；正常发布应锁精确版本（`pip freeze`/uv lock）。
- 记录模型来源、版本、大小、许可、SHA256；不要只写“模型已复制”。
- `audio/models`、`tts/models` 不入库；新机器需下载/复制并校验。
- 模型升级必须做效果对比（CER、TTS 主观/客观、启动时间、内存）。
- 不要把 `.env`、API key、模型权重打进安装包。

## 7. 可观测性

当前只有 stdout 请求日志。正常开发至少补：

- 请求 ID、会话 ID、阶段耗时（ASR/LLM/工具/TTS）；
- 错误分类：配置/网络/限流/模型/存储；
- 不记录完整用户文本/音频（隐私）；
- `/api/health` 增加模型版本、队列/最近错误（不泄露 key）。

## 8. 发布与回滚

1. 合并 feature 分支；
2. 跑回归清单；
3. 打 tag、写 changelog；
4. 构建源码 ZIP/安装包（不含模型/数据/key）；
5. 在干净目录解压 + 配置 + 启动验证；
6. 保留上一版 tag 与离线 ZIP，出问题可回滚。

首次安装/现场配置见 [`PUBLISH.md`](PUBLISH.md)；不要假设“模型在 GitHub 里”。

## 9. 文档与 ADR

| 改动 | 必须更新 |
| --- | --- |
| API/数据流/线程 | `ARCHITECTURE.md` |
| 能力/实测数字 | `STATUS.md` |
| 新坑/绕过旧坑 | `PITFALLS.md` |
| 计划/优先级 | `PLAN.md` |
| 架构/模型/存储取舍 | `DECISIONS.md` |
| 模型/缩写 | `GLOSSARY.md` |
| 发布流程 | `PUBLISH.md` |

新增架构决策时在 `DECISIONS.md` 追加一条 ADR，不要只写在聊天记录里。

## 10. 正常开发检查表

- [ ] 基线与 `/api/health` 通过
- [ ] 改动范围单一、有 issue/目标
- [ ] 测试/回归命令已跑，数字已记录
- [ ] 错误路径（超时、空结果、失败）已处理
- [ ] 无密钥/模型/数据/产物入库
- [ ] 文档与 ADR 已同步
- [ ] 有回滚方案
- [ ] PR 描述包含：改了什么、为什么、怎么测、风险

## 11. 当前已知质量缺口

- Web 端没有自动化测试；UI 仍靠 CDP 手工脚本。
- 没有 CI、没有依赖锁文件、没有 schema 版本。
- 单用户/无鉴权；若暴露到局域网必须加认证/TLS。
- `web_fetch` 需要补 SSRF 防护（见 `SECURITY.md`）。
- 时间问题 18s、无流式；陪伴表情依赖额外 DeepSeek 分类调用。
