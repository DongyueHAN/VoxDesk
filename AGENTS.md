# AGENTS.md · VoxDesk-Web 操作规约

> 给**没有上下文的新对话**用。先读 `README.md`，再按下面顺序读四份文档，然后就能开工。

## 1. 这个仓库是什么

- **浏览器版语音对话应用**，目标是快速演示，**不是**原框架的正式实现。
- 原框架在 `D:\VoxDesk`（另有系统文档仓），**外部目录只读**；本仓库已把 `tts/`、`audio/`
  的源码与所需模型合并进来（模型本地复制但 gitignore）。
- 允许“先跑通、后补设计”；新目录/新模块优先保持轻量，不要整仓复制外部内容。

## 2. 入口（按顺序读，约 10 分钟）

| 顺序 | 文件 | 解决什么 |
| --- | --- | --- |
| 1 | `README.md` | 是什么、怎么跑 |
| 2 | `docs/ARCHITECTURE.md` | 当前数据流、接口、存储、线程模型 |
| 3 | `docs/STATUS.md` | 现在能跑什么、数字是多少、缺什么 |
| 4 | `docs/PITFALLS.md` | 46 个坑，别重踩 |
| 5 | `docs/PLAN.md` | 下一步做什么、怎么算做完 |

## 3. 硬约束（改代码前必须知道）

1. **采样率 16k、单声道、float32/Int16**：进 `voxdesk_audio.StreamingASR` 的数据必须是 16k 单声道。
2. **WAV 是边界**：TTS 只产出文件，播放由浏览器负责；服务端不播声音。
3. **音频/TTS 源码在本仓库**：`audio/src`、`tts/src` 保持原模块名与布局；模型在
   `audio/models`、`tts/models`（gitignore）。外部 `D:\VoxDesk` 只读，不再作为运行源码路径。
4. **Piper 引擎非线程安全**：`voice_app.py` 用 `_tts_lock` 串行化 `synth()`，别去掉。
5. **依赖环境**：优先本仓库 `.venv`；没有则复用 `D:\VoxDesk\demo\.venv`（含 sherpa-onnx / piper / soundcard）。
6. **密钥不进仓库**：`.env` 在 `.gitignore` 里；本目录 `.env` 优先，`D:\VoxDesk\demo\.env` 兜底。

## 4. 验证（不用打开浏览器也能测）

```powershell
# 起服务（模型在本地，首次约 5s 预热）
cd D:\VoxDesk-Web; .\start.ps1

# 健康检查 & 文字对话
Invoke-RestMethod "http://127.0.0.1:8800/api/health" | ConvertTo-Json
$body = @{ text = "你好"; web = $false; speak = $true } | ConvertTo-Json -Compress
Invoke-RestMethod "http://127.0.0.1:8800/api/chat" -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Body ([Text.Encoding]::UTF8.GetBytes($body))
# 期望：reply 非空、audio 是 /api/wav/xxx.wav、llm_ms/tts_ms 有值

# 会话
Invoke-RestMethod "http://127.0.0.1:8800/api/chats" | ConvertTo-Json -Depth 3

# 页面
Invoke-WebRequest "http://127.0.0.1:8800/" -UseBasicParsing | Select-Object StatusCode
```

改完必须给出**新的实测数字**（ASR / LLM / TTS 或页面延迟），否则不算完成。

## 5. 提交与版本

```
w0.x: <一句话> @ <ISO8601>
```

- 每完成一个可演示的步骤打一个 tag（`w0.1`、`w0.2`…），保留"哪一步是能跑的"。
- 一次提交只做一件事；不要把 `out/`、`data/`、`.env`、`*.wav`、模型带进去。
- 禁止 `git add -A`。

## 6. 文档同步（唯一要求）

改动若涉及下列任一项，**同一次提交里**更新对应文档，否则下个对话会读到错的：

| 改了 | 更新 |
| --- | --- |
| 接口（`/api/*`）或数据流 | `docs/ARCHITECTURE.md` §4 |
| 能跑的功能 / 实测数字 | `docs/STATUS.md` |
| 踩到新坑或绕过旧坑 | `docs/PITFALLS.md` |
| 计划增减 | `docs/PLAN.md` |

## 7. 禁止事项

| 禁止 | 原因 |
| --- | --- |
| 修改 `D:\VoxDesk` 里的代码 | 那是原框架，回填要单独评估 |
| 引入前端框架 / 构建工具 | 目标是无构建静态页面（app.html/css/js） |
| 引入 Python Web 框架（FastAPI 等） | 标准库够用；装包会拖慢迭代 |
| 提交模型 / 大二进制 | 模型已本地复制但 gitignore，不要提交 |
| 提交 `.env`、`out/`、`data/`、`*.wav` | 密钥与运行产物 |
