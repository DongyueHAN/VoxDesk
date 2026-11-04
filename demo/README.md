# demo · 语音 → ASR → DeepSeek → TTS（临时）

> ⚠️ **这个目录只在分支 `demo/deepseek-voice` 上存在。**
> 主线（`master`）的 S5 接的是**本地 Ollama + Qwen3-4B**，与 `docs/13-M2process.md` 一致。
> 本 demo 只是为了先看到"能对话"的体感，用的是云 API（DeepSeek），**不并入主线**。

## 它拼了什么

```
麦克风 → [audio] VAD/录音 → StreamingASR（S4，39ms 首字）
      → DeepSeekChat（本分支新增，SSE 流式，量首 token）
      → [tts] TTSService + Piper（S1/S2，RTF 0.026）
```

三个件都是主线上已有的实现，这里只加了一个 **LLM 适配器**和一个**串联脚本**。

## 跑起来

```powershell
cd D:\VoxDesk\demo
uv sync

# 0) 先不花钱验证链路（固定回复，不调 API）
uv run python scripts/voice_chat.py --file ..\audio\out\corpus\01.wav --mock

# 1) 设 key（只读环境变量，不写进仓库）
$env:DEEPSEEK_API_KEY = "sk-..."

# 2) 固定录 4 秒
uv run python scripts/voice_chat.py --seconds 4

# 3) 按住 f2 说话，松开即回答（默认）
uv run python scripts/voice_chat.py
```

## 实测（本机，mock 模式）

| 环节 | 数值 | 说明 |
| --- | --- | --- |
| ASR | 869ms（首次，含模型加载）/ 约 330ms（后续） | 5.13s 音频 |
| TTS | 7530ms | 这是**播放时长**，不是合成耗时（合成 RTF 0.026） |
| API 可达性 | `HTTP 401`（假 key） | 域名通、鉴权生效；真 key 待你配 |

> 真调 API 的数字（首 token / 总耗时）要等你配 key 后跑一次才知道——脚本会打印 `首token XXms`。

## 与主线的差异（这是分支存在的理由）

| 项 | 主线 S5 | 本 demo |
| --- | --- | --- |
| LLM | Ollama + Qwen3-4B（本地、离线） | DeepSeek API（云端、需网络） |
| 首 token 目标 | ≤ 1.2s（CPU） | 不设目标，先看体感 |
| 隐私 | 音频不出本机 | 只有**文本**出本机（音频仍本地转写） |
| 依赖 | Ollama 常驻 | 一个 HTTP 客户端（标准库实现） |

## 已知限制

| 限制 | 影响 | 备注 |
| --- | --- | --- |
| 按住才开麦（开麦 ~50ms） | 第一个字可能被削 | demo 够用；主线用常开麦 + VAD |
| 没走 VAD 分段 | 一次说的全交给 ASR | `--seconds` 模式尤其明显 |
| 单轮 + 6 条历史 | 多轮会忘 | 够演示 |
| `--mock` 回复是固定模板 | 只能验链路 | 真链路要 key |

## 主线怎么继续

```powershell
git checkout master     # 回到主线（demo 目录会消失，git 里还在）
```

主线 S5 的验收（`docs/13-M2process.md`）：首 token ≤ 1.2s、10 条指令工具调用合法 ≥ 8 条。
