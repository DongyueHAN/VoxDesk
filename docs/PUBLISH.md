# 发布到 GitHub：基于 `demo/deepseek-voice` 的新分支

> 目标仓库：https://github.com/DongyueHAN/VoxDesk
> 基线：远端 `demo/deepseek-voice`，即本机 `D:\VoxDesk` 的 HEAD `7e77b2e`
> 新分支：`web/w0.6`

## 目录说明

为了让新分支真正从 `demo/deepseek-voice` 长出来，发布内容放在一个**独立克隆**里，
不修改 `D:\VoxDesk`：

```text
D:\VoxDesk-Web\out\publish\VoxDesk
```

这个目录是 `out/` 下的临时发布 checkout（gitignore），特点是：

- 父提交 = `7e77b2e`（demo 分支 HEAD），可直接向 demo 分支开 PR；
- 保留 demo 分支原有的 `demo/`、`LICENSE`、`demo.mp4`、`audio/`、`tts/` 测试与文档；
- 叠加 Web 应用：`server.py`、`voice_app.py`、`static/app.*`、`start.ps1` 等；
- `audio/`、`tts/` 使用 demo 分支的版本，不重复造一份；
- 模型、`data/`、`out/`、`.env` 不入库；
- 本地分支已创建：`web/w0.6`。

> 源仓库 `D:\VoxDesk-Web` 仍是开发仓库；它的 `master` 不直接推送到 GitHub。
> 上传完成后，发布 checkout 可以保留或删除。

## 一、推送（只差这一步）

本机凭据 helper 是 `manager`。进入发布 checkout：

```powershell
cd D:\VoxDesk-Web\out\publish\VoxDesk
git status --short          # 应为干净
git log --oneline -3        # 第一条是 w0.6 提交，第二条是 7e77b2e
git push -u origin web/w0.6
```

第一次 push 会弹 GitHub 登录/凭据窗口；按提示登录 `DongyueHAN` 账号即可。
不要把 Personal Access Token 直接写进 remote URL。

如果 remote 不对：

```powershell
git remote set-url origin https://github.com/DongyueHAN/VoxDesk.git
```

如果推送后提示分支已存在（本机查询时不存在），换一个名字：

```powershell
git push -u origin web/w0.6-20261106
```

不要用 `--force` 推已有分支。

## 二、认证备选（HTTPS 无弹窗时）

```powershell
git config --global credential.helper manager
git push -u origin web/w0.6
```

或 SSH：

```powershell
ssh-keygen -t ed25519 -C "your-email@example.com"
Get-Content $env:USERPROFILE\.ssh\id_ed25519.pub
# 把公钥加到 GitHub → Settings → SSH and GPG keys
ssh -T git@github.com
cd D:\VoxDesk-Web\out\publish\VoxDesk
git remote set-url origin git@github.com:DongyueHAN/VoxDesk.git
git push -u origin web/w0.6
```

## 三、验证

推送成功后打开：

```text
https://github.com/DongyueHAN/VoxDesk/tree/web/w0.6
```

确认：

1. 分支基于 `demo/deepseek-voice`（提交历史里能看到 `7e77b2e`）；
2. 根目录有 `server.py`、`voice_app.py`、`static/app.html`、`start.ps1`；
3. 有 `demo/`、`audio/`、`tts/`（从 demo 分支保留）；
4. 没有 `audio/models`、`tts/models`、`data/`、`.env`；
5. 页面可读 [README.md](../README.md)。

可以开 PR：`web/w0.6` → `demo/deepseek-voice`。
因为分支基于 demo，PR 的 diff 只包含 Web 应用与文档改动。

## 四、在新机器上运行分支

```powershell
git clone --branch web/w0.6 https://github.com/DongyueHAN/VoxDesk.git
cd VoxDesk
# 模型不在 git 里；把模型放回：
#   audio/models/...
#   tts/models/zh_CN-huayan-medium.onnx
# 或从本机复制（约 289MB）
# 依赖：本机已有 D:\VoxDesk\demo\.venv，或按 requirements.txt 建 .venv
.\start.ps1
```

## 五、注意事项

- 当前 `D:\VoxDesk` 工作区有未提交的文档修改；发布分支只基于它的 **HEAD**，
  不包含那些本地改动。
- 如果远端 demo 分支之后又更新，先 `git fetch origin`、`git rebase origin/demo/deepseek-voice`
  再 push；不要强推。
- 如果想要完全独立的 Web 快照分支（不带 demo 历史），那是另一种方案，不适合 PR；
  当前不采用。
