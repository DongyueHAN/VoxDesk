# AGENTS.md · 代码仓操作规约

> 给进入**代码仓**（`D:\VoxDesk`）的编码 agent。先读根 `README.md`，再读本文件。
> 设计侧的规约（文档格式、ID、ADR 生命周期）在文档仓的 `AGENTS.md` + `docs/00-spec.md`，不在这里重复。

## 1. 这个仓库是什么

- **只放能跑的代码**：`tts/`（播报）、`audio/`（音频前端）、`docs/`（实现文档）。
- `demo/` 只存在于分支 `demo/deepseek-voice`，是"一轮对话 + 打包"的演示，**不并入主线**。
- 权威在代码本身：文档写的是"当前代码长什么样"，代码变了文档必须跟着改（顺序见 §4）。

## 2. 入口（按顺序读）

| 顺序 | 文件 | 读它解决什么 |
| --- | --- | --- |
| 1 | `README.md` | 项目是什么、能做什么、怎么跑 |
| 2 | `docs/STATUS.md` | 做到哪了、数字是多少、下一步做什么 |
| 3 | `docs/ARCHITECTURE.md` | 模块、接口、不变式、扩展点 |
| 4 | `docs/HANDOFF.md` | 已知的 8 个坑、未决问题、交接检查清单 |

## 3. 工作规则

### 3.1 分支

| 分支 | 用途 | 提交到哪 |
| --- | --- | --- |
| `master` | 主线（离线，本地 LLM） | 新功能 / 修复 |
| `demo/deepseek-voice` | 演示（云端 LLM + 打包） | 只改 `demo/` 与相关文档 |

- 不要为了让 demo 能跑而改 `audio/` 或 `tts/` 的公共接口；接口要改，先在主线改并跑验收。
- 合并演示分支进主线是**禁止动作**，除非需求方明确同意。

### 3.2 提交

```
<type>(<scope>): <中文摘要> @ <ISO8601>
type ∈ feat / fix / docs / test / build / chore
scope ∈ tts / audio / demo / docs
```

- 一次提交只做一件事；正文写清"为什么"，不写"改了什么"（diff 已经说了）。
- 禁止 `git add -A` / `git add .`：仓库里有模型、密钥、构建产物，误收代价很大。
- 提交前必须 `git status` 确认没有 `models/`、`.env`、`VoxDeskVoice/`、`*.wav` 混进来。

### 3.3 验证

| 改动 | 必须跑 |
| --- | --- |
| `tts/` | `cd tts && uv run pytest -q`（13 个）+ `uv run python scripts/accept_s1.py --engine piper` |
| `audio/` | `cd audio && uv run pytest -q`（15 个）+ `uv run python scripts/accept_s3.py` |
| `demo/` | `cd demo && uv run python scripts/voice_chat.py --file ..\audio\out\corpus\01.wav --mock` |
| 打包相关 | `cd demo && .\build.ps1`，再双击 `..\VoxDeskVoice\VoxDeskVoice.exe` 验一次 |

没有实测数字的改动**不算完成**；性能相关的改动要在提交信息里写"改前/改后"。

## 4. 文档同步顺序

1. 改代码；
2. 改对应切片 `README.md`（若有接口/用法变化）；
3. 改 `docs/STATUS.md` 的数字或状态；
4. 若结构/接口变了，改 `docs/ARCHITECTURE.md`；
5. 若踩到新坑或解决旧坑，改 `docs/HANDOFF.md`；
6. 提交。

## 5. 禁止事项

| 禁止 | 原因 |
| --- | --- |
| 提交模型权重（`*.onnx`、`models/`） | 单文件 157.8MB 超 GitHub 限制；`.gitignore` 已挡 |
| 提交 `demo/.env` 或任何密钥 | 会泄露；`.gitignore` 已挡，别用 `-f` 绕过 |
| 提交 `VoxDeskVoice/`、`build/`、`*.wav`、`*.mp4` | 构建/运行产物，体积大 |
| 改 `audio/`/`tts/` 的公共接口只为适配 demo | 会让切片失去独立性 |
| 用 `python` 直接跑（PATH 上没有） | 一律 `uv run` |
| 在 `tts` 里写播放逻辑 | 违反"引擎不播放"不变式 |

## 6. 环境

- Windows 11 + PowerShell（5.1 与 7 都要能跑）。
- 脚本文件若含中文，**必须存 UTF-8 with BOM**（PS 5.1 否则乱码并可能吞行）。
- `uv` 管依赖；每个切片独立虚拟环境；`demo` 通过 path 依赖引用 `audio` / `tts`。
- 模型下载：`cd demo && uv run python scripts\fetch_models.py`（hf-mirror 优先）。

## 7. 交接要求

任何一次"阶段性完成"的提交，必须能让下一个人只读三个文件就接手：

1. `docs/STATUS.md` 的状态表是新的；
2. `docs/HANDOFF.md` 的坑表包含这次踩到的坑；
3. `docs/ARCHITECTURE.md` 的接口与不变式仍然成立。

做不到就别提交。
