# tts · 第一个切片

> **S0 已跑通**（2026-11-04）：机器能念出中文，且能合成到 WAV 落盘。

| 项 | 值 |
| --- | --- |
| 冲刺 | S0 · 环境与出声（`docs/12-process.md`） |
| 引擎 | Windows SAPI 5（`pywin32`） |
| 解释器 | Python 3.11.17（uv 管理，落在 `D:\uv-python\`） |
| 依赖 | `pywin32==312` |
| 实测 | 3 个音色；22.05 kHz / 16 bit / 单声道；5.8 s 音频合成 0.05 s（RTF 0.009） |

## 怎么跑

```powershell
cd D:\VoxDesk\tts
uv sync                                   # 装依赖（首次）

uv run python scripts/probe_voices.py     # 1. 有什么音色
uv run python scripts/speak_once.py --voice "Huihui"   # 2. 出声
uv run python scripts/to_wav.py --play    # 3. 合成到 out/s0_hello.wav 并回放
```

期望输出：

```
共 3 个音色：
  1. Microsoft Huihui Desktop - Chinese (Simplified)  [zh-CN · Female · Adult]
  2. Microsoft Zira Desktop - English (United States)  [en-US · Female · Adult]
  3. Microsoft David Desktop - English (United States)  [en-US · Male · Adult]

✓ 播完，用时 4.95s
```

## 结构

```
tts/
├─ pyproject.toml            # requires-python ==3.11.*，依赖 pywin32
├─ src/voxdesk_tts/
│  ├─ sapi.py                # 三个函数：list_voices / speak / synth_to_wav
│  └─ console.py             # 控制台 UTF-8（Windows 默认 cp936，中文会乱码）
├─ scripts/
│  ├─ probe_voices.py        # 列音色（--zh / --json）
│  ├─ speak_once.py          # 同步朗读，返回耗时
│  └─ to_wav.py              # 合成到 WAV，报告时长/采样率/RTF（--play 回放）
└─ out/                      # 合成产物，已 gitignore
```

**刻意没做的事**：没有 `TTSEngine` 协议、没有缓存、没有队列、没有 splitter。
那些是 S1/S2 的事（`docs/09-tts-module.md` §4、§7）。在没有第二个引擎之前就抽接口，
等于猜。

## 两个踩过的坑

1. **`Win32 exception occurred releasing IUnknown`**
   SAPI 是 COM，`SpVoice` 必须在 `CoUninitialize()` 之前释放。如果让它活到进程退出，
   解释器会在关闭时打印这行异常。解法：把所有 COM 引用关在 `_collect` / `_speak` /
   `_synth` 的栈帧里，函数一返回就随帧销毁。

2. **中文乱码**
   Python 在 Windows 上默认按 cp936 输出，PowerShell 按 UTF-8 解码 → 乱码。
   解法：`voxdesk_tts.console.enable_utf8()`，脚本入口调一次。

## 已知限制

| 限制 | 影响 | 何时解决 |
| --- | --- | --- |
| 中文只有 `Huihui Desktop` 一个音色 | 听感机械、无法换性别 | S2 换 Piper（`zh_CN-huayan`） |
| Kangkang / Yaoyao 在 `Speech_OneCore`，SAPI 5 看不见 | 拿不到男声 | 装 SAPI 5 语音包，或不管 |
| SAPI 只有 22.05 kHz | 音质上限低 | S2 |
| 没有分句/缓存/打断 | 长文本要等整句合成 | S1 |

## 下一步（S1）

分句 + 缓存 + 队列 + `stop()`，验收见 `docs/09-tts-module.md` §8 六条。
