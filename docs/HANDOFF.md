# 交接说明（给下一个 agent / 接手的人）

> 目标：读完本文 + `STATUS.md`，能在 10 分钟内继续干活，不踩已知的坑。

## 1. 五分钟上手顺序

1. 根 `README.md` —— 项目是什么、现在能做什么。
2. 本文 §2「当前状态」—— 一句话结论。
3. `docs/STATUS.md` —— 已实现/未实现、下一步。
4. `docs/ARCHITECTURE.md` —— 代码结构、接口、不变式。
5. 需要"为什么"时，去文档仓看 `docs/03-architecture.md` 与 `docs/adr/`。

## 2. 当前状态（一句话）

`tts` 与 `audio` 两个切片已验收（播报 / 断句 / 听写都能单独跑）；
`demo` 分支把三者串成一轮对话并用云端 LLM 跑通、可打包；
**主线缺的是本地 LLM（S5）与端到端串联（S7）**。

## 3. 环境与复现

| 项 | 值 |
| --- | --- |
| 系统 | Windows 11 x64 |
| Python | 3.11（`uv` 自动安装，PATH 上没有 python 也正常） |
| 依赖管理 | 每个切片独立 `uv sync`；`demo` 用 path 依赖引用 `audio` / `tts` |
| 模型 | `audio/models/`（VAD + ASR）、`tts/models/`（Piper），**不进 git** |
| 密钥 | `demo/.env` 里的 `DEEPSEEK_API_KEY`，**不进 git** |

最小验证：

```powershell
cd audio; uv run pytest -q          # 15 passed
cd ..\tts; uv run pytest -q         # 13 passed
cd ..\audio; uv run python scripts\accept_s3.py
cd ..\tts;   uv run python scripts\accept_s1.py --engine piper
```

## 4. 已知的坑（都踩过，别再踩）

| # | 坑 | 现象 | 正确做法 |
| --- | --- | --- | --- |
| 1 | **Silero VAD 需要 64 点上下文** | 所有帧概率 ≈0.00x，像模型坏了 | 输入 = `concat(上一帧尾部 64 点, 当前 512 点)` = 576 点 |
| 2 | **ASR 尾字被吞** | "第三句很短" 只识别出 "第三" | 尾部补 500ms 静音再喂模型（CER 31%→24%） |
| 3 | **SAPI 同步播放打不断** | `SND_PURGE` 后声音仍在放（实测 4.55s/4.40s） | 用 `SND_ASYNC` + 10ms 轮询 + 同线程 purge |
| 4 | **缓存键不能用 `hash()`** | 重启后缓存全失效 | `sha1(engine.signature() + text)` |
| 5 | **模型进了 git** | 仓库 1GB、push 失败 | `.gitignore` 有 `models/`；误加用 `git rm -r --cached` |
| 6 | **打包漏收 soundcard** | exe 里 `import soundcard` 崩 | `--collect-all soundcard`（它带 `.py.h` 数据文件） |
| 7 | **build.ps1 在 PS 5.1 乱码** | 中文变乱码、`$dist` 为空 | 脚本存 **UTF-8 with BOM** |
| 8 | **loopback 自激** | 它把自己的播报当输入 | 演示用 `--no-tts`，或输出接耳机 |

## 5. 许可与上游

- 本仓库 **GPL-3.0**：`tts/` 链接 `piper-tts`（GPL-3.0），分发打包产物即衍生作品。
- 上游：piper1-gpl（GPL-3.0）、sherpa-onnx（Apache-2.0）、silero-vad（MIT）、onnxruntime（MIT）、
  sounddevice / PortAudio（MIT）、soundcard（BSD-3）、keyboard（MIT）、pywin32（PSF）、PyInstaller（GPL-2.0 + 例外）。
- 模型：Paraformer 权重按上游模型页（Apache-2.0，商用前复核）；Piper 中文音色许可**逐个声明**，商用前需自查。

## 6. 未决问题（需要人拍板）

| # | 问题 | 现状 | 建议 |
| --- | --- | --- | --- |
| 1 | 主线 LLM 用 Ollama 还是 llama.cpp | 文档写 Ollama + Qwen3-4B | 先 Ollama（OpenAI 兼容，换引擎成本低） |
| 2 | 唤醒词是否必做 | 从 M1 挪到 M2，可能再滑 | 先用 PTT 交付，KWS 作为增强 |
| 3 | 是否把 `demo` 合进主线 | 现在不合并 | 主线接上 Ollama 后，把 `demo/app.py` 的编排上提 |
| 4 | 演示视频是否入库 | 已提交 33MB `demo_ruler.mp4` | 建议移出仓库或用 LFS |

## 7. 交接检查清单

接手后先确认这几条，任何一条不成立就说明环境或代码已漂移：

- [ ] `audio` 与 `tts` 的 `uv run pytest -q` 全绿（15 + 13）
- [ ] `accept_s3.py` 打印切错 0 / 50
- [ ] `accept_s1.py --engine piper` 首音 < 300ms
- [ ] `demo` 能跑 `demo_one.py`（需要 `.env` 里的 key），打印首 token
- [ ] `git status` 干净；`models/`、`.env` 未被跟踪
