# VoxDesk · 代码仓库

> 语音助手 VoxDesk 的实现代码。**架构与文档在另一个仓库**（`D:\Obsidian\Geist\Project\full-deplux dialogue system`），这里只放能跑的东西。

| 项 | 值 |
| --- | --- |
| 当前冲刺 | **S0 · 环境与出声**（见 docs/12-process.md） |
| 代码位置 | `tts/`（第一个切片） |
| 语言 | Python 3.11（uv 管理） |
| 平台 | Windows 11（SAPI 起步，S2 换 Piper） |

## 为什么单独一个仓库

文档仓要求"原型阶段以图交付、不写实现代码"（`REQ-C-001`）。代码一旦进去，那条约束就形同虚设。所以：

- **文档仓**：做什么、为什么这么做、决策与取舍
- **本仓库**：怎么做的、能跑吗

两边用 ADR 号与文档小节号互相指路，不做 git submodule。

## 目录

```
VoxDesk/
└─ tts/            第一个可交付切片（TTS）
   ├─ src/voxdesk_tts/
   ├─ scripts/     可直接跑的验证脚本
   └─ out/         合成产物（不入库）
```

## 起步

```powershell
cd D:\VoxDesk\tts
uv sync
uv run python scripts/probe_voices.py --zh
uv run python scripts/speak_once.py --text "你好，我是 VoxDesk。"
```
