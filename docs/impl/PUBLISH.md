# 发布与 GitHub Desktop 流程（PUBLISH）

> 当前仓库：`D:\VoxDesk`
> 当前分支：`web/w0.6`
> 远端：`https://github.com/DongyueHAN/VoxDesk.git`

## 1. 日常推送（GitHub Desktop）

1. GitHub Desktop 打开 `D:\VoxDesk`；
2. 确认当前分支是 `web/w0.6`（或你的 feature 分支）；
3. 先 **Pull origin**，再改代码；
4. 提交前检查 `Changes` 只包含预期文件；
5. Commit → Push origin。

命令行等价：

```powershell
cd D:\VoxDesk
git status --short
git pull --ff-only
git add <files>
git commit -m "feat: ..."
git push
```

禁止：

- 把 `.env`、模型、`data/`、`out/`、`defense/`、`*.wav` 加进提交；
- 直接 `git push --force` 覆盖远端；
- 直接把无关历史 merge 进 `web/w0.6`。

## 2. 分支策略

```text
web/w0.6       集成分支 / 当前默认开发分支
  ├─ feat/xxx  新功能
  ├─ fix/xxx   Bug 修复
  └─ docs/xxx  文档
```

- 一个分支只做一件事；
- 通过 PR 合并到 `web/w0.6`；
- demo/deepseek-voice 作为历史基线保留，不作为当前开发主线；
- 不把 `D:\VoxDesk-Web` 的独立历史强行 merge 进来；需要时先确认策略。

## 3. 发布前验证

```powershell
cd D:\VoxDesk
.\start.ps1

& 'D:\VoxDesk\demo\.venv\Scripts\python.exe' -m py_compile `
  server.py voice_app.py llm.py search.py store.py prompts.py paths.py
node --check static\app.js

Invoke-RestMethod http://127.0.0.1:8800/api/health | ConvertTo-Json
Invoke-WebRequest http://127.0.0.1:8800/ -UseBasicParsing | Select-Object StatusCode
```

发布前至少确认：

- `/api/health` 返回 200，ASR/TTS/api_key 正常；
- 文字对话、F2 语音、TTS、陪伴模式表情、归档/刷新持久化通过；
- 无密钥/模型/数据进入 Git；
- CHANGELOG/文档已更新。

## 4. 打 tag / release

```powershell
git tag -a w0.6.x -m "w0.6.x: ..."
git push origin w0.6.x
```

- tag 只打在验证通过的提交；
- GitHub Release 说明写：新增、修复、破坏性变更、已知问题；
- 需要源码 ZIP 时用 GitHub 的 `Code → Download ZIP`，或在干净目录打包；
- **源码 ZIP 不含模型**；模型/venv 需另外准备。

## 5. 新机器运行源码包

```powershell
git clone --branch web/w0.6 https://github.com/DongyueHAN/VoxDesk.git
cd VoxDesk

# 1) Python 3.11 环境
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 2) 放模型（约 289MB，不在 Git）
# audio/models/...
# tts/models/zh_CN-huayan-medium.onnx

# 3) API key
# 在根目录建 .env：DEEPSEEK_API_KEY=sk-...

.\start.ps1
```

如果本机已有 `D:\VoxDesk\demo\.venv`，`start.ps1` 会回退使用它；换机必须按
`requirements.txt` 安装。

## 6. 历史说明

早期为了让 `web/w0.6` 从 `demo/deepseek-voice` 长出来，曾使用
`D:\VoxDesk-Web\out\publish\VoxDesk` 临时发布 checkout。该目录只属于历史流程，
**现在不再作为发布源**。

当前发布源就是 `D:\VoxDesk` 本身；不要在 `out/publish` 和主仓库之间手工同步。

## 7. 出问题时的回滚

1. 回退到上一个 tag/commit；
2. 保留失败版本的日志与错误；
3. 如果模型/依赖升级导致回滚，恢复上一版模型哈希与 requirements；
4. 重新跑 DEVELOPING 的最低回归清单；
5. 在 DECISIONS/PITFALLS 记录原因，避免重复。
