# 架构决策记录（DECISIONS / ADR）

> 目的：记录“为什么这样做”，避免下次对话把已讨论过的取舍重新推翻。
> 新决策追加到表尾；不要直接改历史结论，写“Superseded by ADR-xxxx”。

## 决策索引

| ID | 决策 | 状态 | 影响 |
| --- | --- | --- | --- |
| ADR-0001 | 浏览器 UI + Python 标准库单进程 | Accepted | 部署简单；并发/鉴权是代价 |
| ADR-0002 | 本地 ASR/TTS + 云端 LLM | Accepted | 隐私/成本/延迟分层 |
| ADR-0003 | `deepseek-flash` + 函数工具，而不是内置 web_search | Accepted | 需要 Search/Fetch API + 工具循环 |
| ADR-0004 | 本地 JSON 存储 + 30/100/1MB | Accepted | 有界状态；无数据库/迁移 |
| ADR-0005 | F2 按住、F3 切换；VAD 不接主链路 | Accepted | 输入可控；不是自动监听 |
| ADR-0006 | 陪伴语气用 DeepSeek 分类，不引入 Qwen0.8B | Accepted | 少一个本地模型；多一次 API 调用 |
| ADR-0007 | 像素表情提取白色像素、主题色点阵 | Accepted | 视觉统一；依赖 Canvas 提取 |
| ADR-0008 | 当前单用户、无鉴权 | Accepted（demo） | 不能直接公网暴露 |

---

## ADR-0001：浏览器 UI + Python 标准库单进程

**背景**：需要快速做可演示的本地语音应用，避免前端构建/后端框架成本。

**决策**：`http.server.ThreadingHTTPServer` + 原生 HTML/CSS/JS；一个进程同时服务页面和 API。

**后果**：

- 部署简单、调试直接；
- 无异步框架，靠锁处理 ASR/TTS/store；
- 多用户/高并发需要迁移到 ASGI/反向代理；
- 没有内建鉴权、限流、CSRF。

**状态**：Accepted；生产化时重新评估。

## ADR-0002：本地 ASR/TTS + 云端 LLM

**背景**：音频隐私、TTS 成本、LLM 质量三者需要平衡。

**决策**：

- ASR：Paraformer（sherpa-onnx，本地）；
- VAD：Silero VAD 已放置，未接主链路；
- TTS：Piper（本地）；
- LLM：DeepSeek `deepseek-flash`（云端，非开源权重）。

**后果**：

- 音频和模型留在本地；只有文本/query 出网；
- 模型约 289MB，换机需准备；
- 首字/冷启动受本地模型影响；
- LLM 依赖网络和 API key。

**状态**：Accepted。

## ADR-0003：`deepseek-flash` + 函数工具

**背景**：`deepseek-v4.1` 不是合法 ID；内置 Responses `web_search` 仅 v4-pro 支持。

**决策**：使用 `deepseek-flash`（V4.1-Flash-1017）Chat Completions，函数工具：

- `web_search` → `/v1/tools/search`
- `web_fetch` → `/v1/tools/fetch`（加 cache-bust）
- 工具循环最多 3 轮。

**后果**：

- 时间/新闻等实时信息可核验并带来源；
- 多一次模型/工具往返，时钟问题约 18s；
- 需要处理工具参数错误、空结果、来源去重。

**状态**：Accepted。

## ADR-0004：本地 JSON + 30/100/1MB

**背景**：不引入数据库，但需要防止本地状态无限增长/静默丢数据。

**决策**：

- `data/chats/<uuid>.json`、`data/archive/<uuid>.json`；
- 30 活跃 / 100 归档 / 单会话 1MB；
- 活跃满 409、单会话满 413、归档满 FIFO；
- 活跃永不自动删除；
- `tmp + os.replace` 原子写。

**后果**：

- 行为可预测、易备份；
- 无全文检索/并发写扩展；
- 1MB 满后需要归档/新开；
- 未来若上数据库需要迁移脚本。

**状态**：Accepted。

## ADR-0005：手动热键，不接自动 VAD

**背景**：自动 VAD 在浏览器/桌面音频上误切风险高，演示需要可控。

**决策**：

- F2 按住麦克风；F3 按下开始/再按停止桌面音频；
- ASR 加 500ms 尾静音；
- Silero VAD 保留为可选模块，**不接主链路**。

**后果**：

- 输入边界清晰、演示可控；
- 不是“随时监听”的语音助手；
- 后续接 VAD 需要处理打断、噪声、端点误判。

**状态**：Accepted；P3 重新评估。

## ADR-0006：陪伴语气用 DeepSeek 分类

**背景**：表情需要随回答语气变化；候选是 DeepSeek API 或本地 Qwen0.8B。

**决策**：

- 仅陪伴模式，在回答生成后调用一次极短分类（`positive/neutral/negative`，`max_tokens=8`）；
- 失败按 `neutral`；
- 不引入 Qwen0.8B 运行时/权重。

**后果**：

- 少一个本地模型和显存/内存占用；
- 每次陪伴回答多约 0.7–0.9s 和少量 token；
- 分类只判断助手回复，不判断用户情绪；
- 若离线/成本敏感，可切换 Qwen 或规则分类（需新 ADR）。

**状态**：Accepted。

## ADR-0007：像素表情提取白色像素 + 主题色

**背景**：素材是白/透明 PNG；需要与页面按钮/主题色一致，而不是白图。

**决策**：

- Canvas 读取 PNG；
- 只保留近白像素（alpha>48，RGB>180）；
- 按 4× 点阵、1px 间隙重绘；
- 颜色取 CSS `--accent`（与发送按钮一致）；
- 作为 `.main` 背景层，陪伴模式显示。

**后果**：

- 视觉统一、可随主题换色；
- 依赖 Canvas 像素读取，素材需同源；
- 黑色描边被丢弃，只保留白色形状；
- 大量像素时有绘制成本（当前 ~1.2 万点，可接受）。

**状态**：Accepted。

## ADR-0008：当前单用户、无鉴权

**背景**：本地演示优先，未做账号体系。

**决策**：只监听 `127.0.0.1`，不做登录/权限/CSRF。

**后果**：

- 本机可用；
- 不能直接暴露局域网/公网；
- 生产化前必须加认证、HTTPS、限流、审计。

**状态**：Accepted（demo 限制）；生产化前必须 supersede。

---

## ADR 模板

```markdown
## ADR-XXXX：标题

**背景**：
**决策**：
**后果**：
**状态**：Proposed / Accepted / Superseded by ADR-YYYY
```
