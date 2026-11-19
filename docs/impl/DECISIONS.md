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
| ADR-0009 | 知识库：JSON 索引 + CJK 双字 + BM25 | Accepted（内核） | 零新依赖；召回待实测 |

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

## ADR-0009：知识库用 JSON 索引 + CJK 双字 + BM25

> 注意：本文件是**实现区** ADR 序列（0001–0009），与规范区
> `docs/system/docs/adr/ADR-0001~0011` 是两套独立编号，只是都叫 `ADR-000x`。

**背景**：`CMP-12` 知识接入要落地，组件级契约是 `IF-07 Search(query, k) -> Chunk[]`
（带来源路径与行号）。可选路线：SQLite FTS5、纯 JSON 索引、向量检索。
约束条件：本仓库只用标准库（ADR-0001）、本机没有 `rg` 二进制、语料是中文 Markdown。

**决策**：

1. **索引格式**：单个 `data/kb/index.json`；每篇文档记 `path/mtime/size/sha1/chunks`，
   每个 chunk 是 `[start_line, end_line, text]`；写入仍走 `tmp + os.replace`（同 ADR-0004）。
2. **分词**：不引入 jieba 或分词模型。拉丁词按 `[a-z0-9_]{2,}`；中文按**双字切分**（bigram），
   单字查询保留原字。
3. **打分**：BM25（`k1=1.2`、`b=0.75`），并加**覆盖率门槛**：命中词数必须
   ≥ `max(1, ceil(0.4 × 查询词数))`。
4. **切块**：按空行切段，再合并到 480 字上限，同时记录行号区间。
5. **增量**：`mtime+size` 未变直接复用；变了再比 `sha1`；真的变了才重新切块。
6. **路径边界**：语料根 = `VOXDESK_KB_DIR` 环境变量，缺省为本仓 `docs/`；
   只收 `.md`/`.txt`；跳过 `.obsidian`、`.trash`、隐藏目录、超 2MB 文件；
   符号链接解析后必须仍在根内。
7. **不依赖 `rg`**：纯 Python 扫描，`rg` 将来可作为快路径叠加。

**为什么不用别的**：

| 方案 | 否决理由 |
| --- | --- |
| SQLite FTS5 | `unicode61` 对中文几乎无效（整句被当成一个 token）；改 `trigram` 要另调参数，收益不明 |
| jieba / 分词模型 | 新增依赖与词典，违背"只用标准库"；对检索召回提升有限 |
| 向量检索（bge-m3 + sqlite-vec） | 要建 embedding、处理增删改；规范区 `ADR-0009` 已定"先全文、后混合" |
| 直接调 `rg` 子进程 | 本机没有 `rg`；且拿不到稳定的行号区间与可比较的分数 |

**后果**：

- **正面**：零新依赖；索引是 JSON，可读可 diff；行号直接可用于引用（`REQ-F-088`）；
  检索不到返回空列表，由上层明说"没记过"（`REQ-F-089`）。
- **负面**：全量重建受磁盘 I/O 支配（1 万篇冷缓存约 111s，热缓存约 6.5s）；
  每次增量都重写整份索引，单篇改动约 0.9–2.4s（见 `STATUS.md` §5）。
- **负面**：双字切分对同义改写不敏感，`Recall@5 ≥ 80%`（`REQ-F-087`）**尚未验收**。
- **风险**：索引不会自动感知语料变化，需要 `POST /api/kb/reindex`（P2）或启动时检查。

**状态**：Accepted；内核已落（`kb.py` + `tests/test_kb.py`），HTTP 与对话接入见 P2/P3。

---

## ADR 模板

```markdown
## ADR-XXXX：标题

**背景**：
**决策**：
**后果**：
**状态**：Proposed / Accepted / Superseded by ADR-YYYY
```
