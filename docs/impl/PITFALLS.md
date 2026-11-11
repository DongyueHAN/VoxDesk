# 技术上的坑（PITFALLS）

> 只收**已经踩过或确定会踩**的坑。每条写：现象 → 原因 → 对策 → 来源。
> 来源 "原框架" 表示在 `D:\VoxDesk` 已踩过并解决；"Web" 是本仓库新增的。

## 1. 音频与模型

| # | 现象 | 原因 | 对策 | 来源 |
| --- | --- | --- | --- | --- |
| 1 | VAD 对所有帧都输出 ≈0.00x，像模型坏了 | Silero VAD v5 的 ONNX 需要 **64 点上下文**，直接喂 512 点会失效 | 输入 = `concat(上一帧尾部 64 点, 当前 512 点)` = 576 点 | 原框架 |
| 2 | ASR 最后一个字被吞（"第三句很短"→"第三"） | 流式模型没有尾静音，最后一块没被 flush | 尾部补 **500ms 静音**再送模型（CER 31%→24%） | 原框架 |
| 3 | 采样率/声道不对时识别结果乱码或空 | 模型只接受 **16k 单声道** | 进 ASR 前统一 `resample → 16k mono float32` | 原框架 |
| 4 | 首次合成慢到 2.5s | `PiperEngine.warmup()` 没覆盖音素化/声码器的懒加载 | 启动时**真合成一次**（本仓库已加 `_warm.wav`） | Web |
| 5 | 两个标签页同时请求时合成崩/串音 | Piper 引擎实例**不是线程安全的** | `_engine_lock` 串行化 `synth()`（已加） | Web |
| 6 | 换了机器跑不起来 | `server.py` 用 `sys.path` 指向 `D:\VoxDesk\...` | 用环境变量 `VOXDESK_HOME` 覆盖；或将 `tts`/`audio` 改为正式依赖 | Web |
| 7 | `ModuleNotFoundError: voxdesk_tts` | 复用了 demo 的 venv，但路径变了 | 必须用 `D:\VoxDesk\demo\.venv\Scripts\python.exe` 启动 | Web |

## 2. 浏览器

| # | 现象 | 原因 | 对策 | 来源 |
| --- | --- | --- | --- | --- |
| 8 | `getUserMedia` 报 `NotAllowedError` 或 undefined | 浏览器要求**安全上下文**：`https://` 或 `localhost` | 用 `http://127.0.0.1` 访问；局域网访问需自签 https | Web（预判） |
| 9 | 采集到的音频无法直接给 ASR | `MediaRecorder` 产出的是 **webm/opus**，本机没有 ffmpeg 解码 | 用 **WebAudio** 取裸 PCM（`AudioWorklet` 或 `ScriptProcessor`），在 JS 里重采样到 16k、转 Int16 再发 | Web（预判） |
| 10 | `AudioContext` 的 `sampleRate` 是 48000 而不是 16000 | 浏览器跟随系统/声卡 | 在 JS 里做线性插值降采样，或 `OfflineAudioContext(1, n, 16000)` 重采样 | Web（预判） |
| 11 | 音频不自动播放 | 浏览器自动播放策略要求**用户手势**触发 | 播放调用放在点击/回车的事件处理里（当前实现满足） | Web |
| 12 | 页面发消息后没声音但接口 200 | `audio` 字段为 null（回复为空）或 wav 404 | 前端兜底：`reply` 为空时不播；服务端确保 wav 写完再返回 | Web |

## 3. 服务端与环境

| # | 现象 | 原因 | 对策 | 来源 |
| --- | --- | --- | --- | --- |
| 13 | 请求偶发 500 / 连接被重置 | 单线程 `HTTPServer` + 长 LLM 请求 | 用 `ThreadingHTTPServer`（已用），长请求不阻塞其它请求 | Web |
| 14 | PowerShell 里脚本中文变乱码、变量为空 | PS 5.1 按 ANSI 解码 UTF-8 无 BOM 的 `.ps1` | `.ps1` 存 **UTF-8 with BOM**；`start.ps1` 目前纯 ASCII，安全 | 原框架 |
| 15 | 控制台输出中文乱码 | Windows 控制台默认 GBK | Python 侧 `enable_utf8()`；或 `chcp 65001` | 原框架 |
| 16 | `OSError: [WinError 10048] 端口被占用` | 上一个进程没退干净 | `--port 9000` 换端口；或 `Get-NetTCPConnection -LocalPort 8800` 杀掉 | Web |
| 17 | `502：没有 API key` | 没读到 `.env` | 在 `D:\VoxDesk-Web\.env` 或 `D:\VoxDesk\demo\.env` 写 `DEEPSEEK_API_KEY=` | Web |
| 18 | 启动时报 `wave.Error: # channels not specified` | 预热合成用了标点（"。"），Piper 产出空音频，写 WAV 时没有声道信息 | 预热用**有实际发音的短句**（如"你好"），不要用标点 | Web |

## 4. 声纹可视化（w0.3）

| # | 现象 | 原因 | 对策 | 来源 |
| --- | --- | --- | --- | --- |
| 19 | 所有音色出来几乎一个颜色 | `np.log` 得到的是**自然对数**，却按 dB 用 `10**(rel/10)` 转能量；35dB 动态被压成 6 倍，频带权重趋平 | 用 `exp(rel_nat)`，或先 ×10/ln10 转成 dB 再算 | Web |
| 20 | 第一次 `/api/chat` 的 `timbre_ms` 约 190ms，之后 3–28ms | 首次 `analyze_wav` 要导入 `voxdesk_audio`（连带 sherpa）并建 mel 滤波器 | 启动时用 `_warm.wav` 跑一次 `timbre.warmup()` | Web |
| 21 | 安静麦克风 / 手机录进来波形几乎空白 | 固定增益按桌面麦克风电平写死，设备间电平差 10 倍 | 用缓慢衰减的峰值做自适应增益（≤24），再 `pow(x, .72)` 提亮 | Web |
| 22 | 1024 段希尔伯特曲线逐段 `stroke()` 掉帧 | 每帧 1024 次 stroke + 颜色/线宽切换 | 按振幅分 11 桶，每桶一个 `Path2D`；整体限 30fps | Web |
| 23 | 曲线发糊、位置偏 | 只设 `canvas.width` 没乘 DPR，也没 `setTransform` | `width = cssW*dpr`，`ctx.setTransform(dpr,0,0,dpr,0,0)` | Web |
| 24 | 录音时扬声器啸叫 | 麦克风直接连到 `destination` | 经 `gain=0` 的节点进 destination，Analyser 只旁路分析 | Web |
| 25 | 重播后进度/状态被上一次播放清掉 | 旧 `BufferSource.onended` 异步触发 | 回调里 `if (state.ttsSource !== src) return;` | Web |
| 26 | Chrome headless `--screenshot` 遇到播放/iframe 不退出 | 媒体管线 + 动态页面让截图模式一直等 | 用 CDP `Page.captureScreenshot`；页面加 `?mute=1` 只画不播 | Web（验证用） |
| 27 | `POST /api/timbre` 偶发 500（buffer size 不是 2 的倍数） | `np.frombuffer(int16)` 要求字节数是 2 的倍数 | 服务端截掉奇数尾字节；前端保证 16k int16 | Web |
| 28 | 想直接复用 CosyVoice 的 192D 音色嵌入但跑不起来 | 仓库没有 `campplus.onnx`（约 27MB），硬约束不复制模型 | 先复刻 80D log-mel 统计；把 `_descriptor()` 换成嵌入投影即可，接口不变 | Web |

## 5. 希尔伯特阶数扩展 + 伪残影（w0.4）

| # | 现象 | 原因 | 对策 | 来源 |
| --- | --- | --- | --- | --- |
| 29 | 固定 order 5 / 1024 点做不出"随时长扩展" | 点数和画布边长都写死了 | order + `4^k` 动态化，包络按当前点数重采样；边长 `2^(order-max)` | Web |
| 30 | 麦克风只画当前 `AnalyserNode` 一帧，阶数没有"录音时长"含义 | 每帧只取 2048 个时域样本，不是整段历史 | 累积 5ms 一格 RMS（200Hz、20s、4000 点），再按 `4^k` 重采样 | Web |
| 31 | 残影在 headless/低帧率下拖尾好几秒，正常 30fps 又是另一个速度 | 衰减用"每帧固定 alpha"，和帧率绑定 | 用真实 `dt` 做 `1-exp(-dt/τ)`，τ=0.30s | Web |
| 32 | 待机/静态曲线越来越白，最后烧成一团 | 残影层用 `lighter`，静态高亮每帧叠加 | 残影层改 `source-over`，只在合成回主画布时 `lighter`；高密度阶数降低辉光 | Web |
| 33 | 点"录音"时画面从整屏突然反向缩成小点 | 待机用上限阶数，录音从下限起始 | `startMic` 里直接 `sideShown=sideTarget()` 并 `clearGlow()`，不做反向过渡 | Web |
| 34 | 4096 点逐段 `stroke()` + 每帧建路径掉帧 | 每帧 4096 段 × 颜色/线宽切换 | 振幅分 11 桶、每桶一个 `Path2D`、30fps；上限 6，更高阶需降采样/WebGL | Web |
| 35 | 阶数看起来"卡住"或与录音秒数不同步 | 用 rAF 帧数计时，被后台/headless 节流 | 阶数只看音频包络块数（`envLen/HISTORY_HZ`），不看帧数 | Web |
| 36 | 想直接用 3Blue1Brown 的 Manim 做拖尾 | Manim 是 Python + OpenGL + 渲染管线，不符合单文件无构建 | 只借 `TracedPath(dissipating_time)` / `LaggedStart(lag_ratio)` 思路，Canvas 实现 | Web（调研） |

## 6. 语音对话合并（w0.5）

| # | 现象 | 原因 | 对策 | 来源 |
| --- | --- | --- | --- | --- |
| 37 | `ZoneInfo("Asia/Shanghai")` 在 Windows 抛 `tzdata` 缺失 | venv 没装 tzdata | 时间戳用 `timezone(timedelta(hours=8))`，不依赖系统时区库 | Web |
| 38 | `deepseek-v4.1` 返回 400 | API 合法 ID 是 `deepseek-flash` / `deepseek-v4-pro`；v4.1 对应 Flash 版本 | 默认 `deepseek-flash`，版本记录为 V4.1-Flash-1017 | Web |
| 39 | Responses 的 `web_search` 工具在 v4.1 不可用 | 内置 `web_search` 仅 `deepseek-v4-pro` 支持 | 改用 Chat Completions function tools，服务端执行官方 Search/Fetch API | Web |
| 40 | 时间问题搜出来的页面时间不一致/过期 | 搜索结果缓存、多个时区/页面，模型无法确认到分钟 | 搜索后再 `web_fetch` 权威实时页，并加 `_voxdesk_ts` 防缓存；仍无法确认就如实说 | Web |
| 41 | 浏览器里 F2/F3 离开页面就失效；F3 若写成 keyup 停止，按住时会反复开关 | 网页不能注册系统级全局热键；F3 是切换而非按住 | 明确“仅页面聚焦”；F2 按住、F3 keydown 切换；stopRecording 重置 keyHeld；系统级热键需原生壳 | Web |
| 42 | 桌面音频偶尔没声音，或停止画面后音频也断 | `getDisplayMedia` 音频是可选勾选；停止 video track 会终止共享会话 | 检查 audio track 并提示；保留 video track，停止录音时再全部关闭 | Web |
| 43 | 30 活跃/1MB/100 归档的边界不清 | 自动删活跃会造成数据丢失；文件无限增长 | 活跃满 409 提示；单会话 1MB 拒绝追加；只自动清理归档最旧 | Web |
| 44 | 工具循环空回复 / 模型反复调工具 | 模型只返回 tool_calls，或工具不断失败 | 最多 3 轮；最后一轮强制无工具；工具参数 JSON 校验；空文本转 502 | Web |
| 45 | TTS 把 Markdown、链接、`[1]` 念出来 | 回复是给屏幕看的 | `clean_for_tts()` 去代码块/链接/引用标记，限长 1200 字 | Web |
| 46 | 新 `/api/chat` 改了返回字段后 `/voice` 颜色不更新 | 旧页面读 `data.timbre` | `/api/chat` 在合成后继续返回 `timbre`，并预热 timbre 分析 | Web |

## 快速自检顺序

出现"没反应"时按这个顺序查，多数问题能定位：

1. 服务起来了吗？→ `GET /` 是否 200
2. key 读到了吗？→ 看启动日志与 502 报错
3. 回答为空？→ 看 `reply` 字段
4. 有 wav 但没声？→ 浏览器控制台、自动播放策略
5. 识别不对（接麦克风后）→ 采样率/声道/尾静音（§1 第 2、3 条）
6. 颜色不对 / 所有音色一个色？→ 检查 log-mel 权重（§4 #19），再确认是否加载了 campplus
7. 麦克风波形空白？→ 授权与自适应增益（§4 #21、§2 #8）
8. headless 截图卡住？→ 用 CDP 或页面的 `?mute=1`（§4 #26）
9. 阶数不随录音增长？→ 看规则控件与 `envLen`（§5 #35）
10. 语音没反应？→ `/api/asr` 长度/采样率与 F2 聚焦（§6 #41/#42）
11. 时间回答不对？→ 看是否真的 search+fetch、缓存 bust（§6 #40）
12. 会话保存失败？→ 30 条/1MB/100 归档限制（§6 #43）
10. 画面发白或残影不散？→ 残影层合成与时间衰减（§5 #31/#32）
11. 开始录音突然变小？→ 正常：从下限种子开始；调大下限（§5 #33）
