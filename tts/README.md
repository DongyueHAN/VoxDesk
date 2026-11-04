# tts · 第一个切片

> **S0 已跑通**（2026-11-04）：机器能念中文，且能合成到 WAV 落盘。
> **S1 已跑通**（2026-11-04）：分句 + 缓存 + 队列 + 打断，四项验收全过。
> **S2 已跑通**（2026-11-05）：加 `PiperEngine`，**`service.py` 一行未改**。

| 项 | 值 |
| --- | --- |
| 冲刺 | S0 出声 → S1 可交付 → **S2 换引擎**（见文档仓 `docs/12-process.md`） |
| 引擎 | **Piper（`piper1-gpl` 1.8.0，ONNX）** 上线；SAPI 保留作对照 |
| 解释器 | Python 3.11.17（uv 管理，落在 `D:\uv-python\`） |
| 依赖 | `pywin32==312`、`piper-tts==1.8.0`、`onnxruntime==1.31.1`；开发 `pytest==9.2.0` |
| 模型 | `models/zh_CN-huayan-medium.onnx`（60 MB，22.05 kHz），gitignore 不提交 |
| 测试 | 13 个单测（切句 + 队列/缓存），`uv run pytest -q` |

---

## 已实现的 C4 图

**这张图的第一条规则：图里出现 = 代码里存在。** 计划中但没写的东西不进图，只进 §3.4 的表。
S2 完成后，`PiperEngine` 从 §3.4 的表里消失、出现在下面两张图里——这就是"图随代码长"。

### 3.1 `CTX-07` · 上下文（已实现）

它跟谁打交道。**没有网络节点、没有云端**，因为现在真的没有。

```mermaid
%% diagram: CTX-07 TTS 切片上下文（已实现） | updated: 2026-11-05
flowchart LR
    CALL["调用方<br/>scripts/say.py · accept_s1.py"]
    TTS["TTS 切片<br/>voxdesk_tts · Python 3.11"]
    SAPI["Windows SAPI 5<br/>SpVoice / SpFileStream（COM）"]
    WINMM["Windows 音频<br/>winsound.PlaySound（winmm）"]
    SPK(["扬声器"])
    DISK[("本地磁盘<br/>cache/ · out/ · models/")]

    CALL -->|"speak() / stop()"| TTS
    TTS -->|"合成请求（COM，仅 SAPI）"| SAPI
    SAPI -->|"WAV · PCM 22.05kHz"| DISK
    TTS -->|"读取 WAV"| DISK
    TTS -->|"异步播放 / purge"| WINMM
    WINMM --> SPK
```

**读法**：两个 Windows 子系统分工明确——**SAPI 只负责合成**（写 WAV），**winmm 只负责播放**。
把它们画成一条线是错的，这也是 S1 打断能做成的前提：播放受我们自己的线程控制。

> **为什么 L1 里没有 Piper**：Piper 是**进程内库**（onnxruntime 推理），不是外部系统。
> C4 的上下文图只画"进程之外的依赖"，Piper 出现在下一层的容器图里。

### 3.2 `C4-07` · 运行容器（已实现）

进程与线程边界。整个切片是**一个 `python.exe` 进程**，没有服务、没有端口。

```mermaid
%% diagram: C4-07 TTS 切片容器（已实现） | updated: 2026-11-05
flowchart TB
    subgraph PROC["python.exe · 单进程 · .venv"]
        CLI["CLI 线程<br/>say.py / accept_s1.py"]
        SVC["TTSService<br/>队列 · 换代 · 缓存键"]
        SYN["tts-synth 线程"]
        PLAY["tts-play 线程"]
        ORT["onnxruntime<br/>（进程内推理）"]
    end
    subgraph OS["Windows 本机子系统"]
        SAPI["SAPI 5（COM）"]
        WINMM["winmm"]
    end
    CACHE[("cache/*.wav")]
    SPK(["扬声器"])

    CLI -->|"speak() 立刻返回"| SVC
    SVC -->|"投递分段"| SYN
    SYN -->|"SapiEngine"| SAPI
    SYN -->|"PiperEngine"| ORT
    SAPI -->|"写文件"| CACHE
    ORT -->|"写文件"| CACHE
    SYN -->|"WAV 路径"| PLAY
    PLAY -->|"WavPlayer.play"| WINMM
    WINMM --> SPK
    SVC -.->|"stop()：换代 + 清空 + purge"| PLAY
```

**读法**：三个线程各司其职——CLI 只投递，`tts-synth` 只合成，`tts-play` 只播放。
`stop()` 不阻塞等待，它改代号（generation）让队列里的旧任务自然作废。
**新引擎没有新增进程、没有新增端口**：`onnxruntime` 就在 `tts-synth` 线程里跑。

### 3.3 `C3-07` · 代码组件（已实现）

模块与类，以及那个可替换点——现在它下面挂了**两个**实现。

```mermaid
%% diagram: C3-07 TTS 切片组件（已实现） | updated: 2026-11-05
flowchart LR
    subgraph PURE["纯函数 · 可单测"]
        SPL["splitter.split<br/>句末断 → 合并短句 → 超长硬切"]
    end
    subgraph SERVICE["service.py（S2 未改动）"]
        SVC["TTSService"]
        Q1["合成队列"]
        Q2["播放队列"]
        GEN["换代计数<br/>_gen + 1"]
        KEY["缓存键<br/>sha1(engine.signature + text)"]
    end
    subgraph ADAPTER["适配层 · 可替换点"]
        ENG{{"TTSEngine 协议<br/>voices() · synth()"}}
        SAPI_E["SapiEngine<br/>pywin32 COM"]
        PIPE_E["PiperEngine<br/>onnxruntime · 60MB"]
        PLY["WavPlayer"]
    end

    SPL -->|"list[str]"| SVC
    SVC --> GEN
    SVC --> KEY
    SVC --> Q1
    Q1 -->|"text + wav 路径"| SAPI_E
    Q1 -->|"text + wav 路径"| PIPE_E
    SAPI_E --> Q2
    PIPE_E --> Q2
    Q2 --> PLY
    ENG -.->|"被实现"| SAPI_E
    ENG -.->|"被实现"| PIPE_E
```

**读法**：六边形是 `TTSEngine` 协议，下面挂两个实心节点——这就是 S2 的全部意义。
`Q1` 到两个引擎的箭头是**同一个队列**：引擎换了，队列、缓存、播放、打断全都不用动。

### 3.4 未实现（刻意不画）

| 计划 | 属于 | 会出现在图里的条件 |
| --- | --- | --- |
| 流式合成 `synth_chunks()` | M6 | 接 CosyVoice 时才需要（`docs/09` §3.3） |
| 与 `CMP-02` 会话网关的对接 | M2 | 上层打通后，`TTSService.speak()` 变成 `IF-05` 的一个实现 |
| 缓存淘汰策略 | M2 之后 | 缓存目录真的涨到影响磁盘时 |
| GPU 推理（`use_cuda=True`） | 待定 | 装 `onnxruntime-gpu` 并实测**确实更快**之后 |

> 这张表是"想法的坟场"：想加功能先写在这里，等真写完了再挪进图。

---

## 实测

### S2 引擎对比（同一段文本、同一套 `TTSService`）

| 引擎 | 模型加载 | 合成耗时 | 音频时长 | 实时因子 | 首音（冷） | 打断 | 二次播放 | 体积 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **SAPI** | — | 0.08 s | 9.12 s | 0.009 | 103 ms | 13.5 ms | 1 命中 / 0 合成 | 0（系统自带） |
| **Piper** | 2.23 s | 0.157 s | 6.06 s | **0.026** | 169 ms | 16.8 ms | 1 命中 / 0 合成 | **60 MB** |

两点值得记：

- **同一段中文，Piper 只要 6.06 s，SAPI 要 9.12 s**——SAPI 的默认语速明显偏慢
- **模型加载 2.23 s 是一次性成本**：`make_engine(..., warmup=True)` 在服务启动时加载，
  不把它算进"首音"；否则第一句话会是 2.4 s

### 验收（`scripts/accept_s1.py`，两个引擎各跑一遍）

| 项 | SAPI | Piper |
| --- | --- | --- |
| B-1 分句 | 445 字 → 10 段，最长 46 | 同左（纯函数，与引擎无关） |
| B-2 首音 | 91 ms | **56 ms** |
| B-3 打断 | 38.8 ms | **12.2 ms** |
| B-4 缓存 | 二轮合成 0 段 | 同左 |

### 离线（`C-1`）

把 `HTTP_PROXY / HTTPS_PROXY / ALL_PROXY` 全部指向一个死端口（`127.0.0.1:1`）后合成：

```
offline synth ok  0.099s  audio 2.62s
```

模型在本地、推理在本地、播放走 winmm——**没有任何一处需要网络**。

## 怎么跑

```powershell
cd D:\VoxDesk\tts
uv sync

# SAPI（对照）
uv run python scripts/speak_once.py --voice "Huihui"

# Piper（上线引擎）
uv run python scripts/say.py --engine piper --text "第一句。第二句。第三句。" --stats

# 长文本 + 中途打断
uv run python scripts/say.py --engine piper --file note.txt --stop-after 1.5

# 验收（两个引擎各跑一遍）
uv run python scripts/accept_s1.py --engine sapi
uv run python scripts/accept_s1.py --engine piper

# A/B 基准（出上面那张表）
uv run python scripts/bench_engines.py

# 单测（不出声）
uv run pytest -q
```

## 结构

```
tts/
├─ src/voxdesk_tts/
│  ├─ splitter.py   切句：句末断 → 合并短句 → 超长硬切（纯函数，最好测）
│  ├─ engine.py     TTSEngine 协议 + SapiEngine + PiperEngine + make_engine()
│  ├─ player.py     WavPlayer：异步播放 + 10ms 轮询取消
│  ├─ service.py    队列 + 缓存 + 换代（generation）+ 统计（S2 未改动）
│  ├─ sapi.py       COM 封装（枚举 / 朗读 / 合成）
│  └─ console.py    UTF-8 控制台
├─ scripts/         probe_voices / speak_once / to_wav / say / accept_s1 / bench_engines
├─ tests/           test_splitter.py（9 个）+ test_service.py（4 个）
├─ models/          Piper 模型（gitignore，需手动下载）
├─ cache/           合成缓存（gitignore）
└─ out/             临时产物（gitignore）
```

## 四个设计选择（都不是随手写的）

### 1. 换代（generation）而不是"取消任务"

每次 `speak()` 把 `_gen + 1`，队列里的旧任务带着旧代号。播放线程看到代号不匹配就丢弃。
好处：`stop()` 不需要真去取消一个正在合成的任务（SAPI 没有取消接口），结果自然作废。

### 2. 合成线程与播放线程分开

播放第一段的同时，第二段已经在合成。所以句与句之间没有"合成 - 播放 - 合成"的空档。

### 3. 打断用"异步播放 + 轮询"，不是"同步播放 + SND_PURGE"

文档 `09` §7 的骨架写的是同步播放 + 另线程 `SND_PURGE`。**实测这条路走不通**：

```
同步播放，0.5s 时从另一线程 SND_PURGE
→ PlaySound 阻塞时长 4.55s（音频全长 4.40s），压根没停
```

原因：`SND_PURGE` 只停**调用线程自己**的发声。所以改成异步播放 + 10ms 轮询取消标志，
在**同一个线程**里 purge，实测静音延迟 12–39ms。

### 4. 缓存键里必须带 `engine.signature`

SAPI 与 Piper 的签名不同（`sapi|...` vs `piper|zh_CN-huayan-medium|...`），
所以换引擎后**不会读到旧引擎的音频**。这不是巧合，是 S1 就写死的规则。

## 两个踩过的坑

1. **`Win32 exception occurred releasing IUnknown`**：SAPI 是 COM，`SpVoice` 必须在 `CoUninitialize()` 之前释放。解法：把所有 COM 引用关进 `_collect` / `_speak` / `_synth` 的栈帧。
2. **中文乱码**：Python 默认 cp936 输出、PowerShell 按 UTF-8 解码。解法：`enable_utf8()`。

## 已知限制

| 限制 | 影响 | 何时解决 |
| --- | --- | --- |
| Piper `zh_CN-huayan` 只有一个女声 | 无男声、无法换音色 | 找其他 voice 或接 CosyVoice（M6） |
| 没有流式合成接口 | 单段最长 50 字，仍要等这一段合成完 | M6 接 CosyVoice 前 |
| `stop()` 后不保留"已播到哪" | 只能重播整段 | M2 接对话时不重要（一句话级别） |
| Piper 是 GPL-3.0 | 开源分发需评估 | 换 CosyVoice（Apache-2.0）或 MeloTTS（MIT） |

## 下一步（S3 = M1 端侧前端）

`sounddevice` 回调 → 队列 → Silero VAD 端点；RNNoise 带 bypass；PTT 热键。
TTS 这边挂着的只有一件事：**M6 用 CosyVoice 取代 Piper**（设计见文档仓 `docs/09`）。
