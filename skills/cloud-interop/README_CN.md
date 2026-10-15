# Cloud Interop / 云端互通技能说明

这个技能把“本机双帐号、不同平台、HPC/台式机/Muse、Kaggle、Google Drive”等互通方式统一成一套可复用流程。

核心原则：**账号凭据只留在拥有该账号的本机，不写入仓库，不发到聊天里。** 仓库里只放脚本、说明、非敏感状态报告和需要转运的产物。

## 1. Google Drive 打通方式

推荐用 `rclone`：

1. 在 Windows 本机安装/更新 `rclone`。
2. 用浏览器 OAuth 登录对应 Google 账号并授权 Drive。
3. rclone token 存在本机 `%APPDATA%\rclone\rclone.conf`，不进入 git。
4. Arena / watcher 后续只通过远端名访问，例如 `gdrive_main:` 或 `gdrive_jzthjyz:`。

本机 PowerShell 示例：

```powershell
.\skills\cloud-interop\scripts\setup-gdrive-rclone.ps1 -RemoteName gdrive_jzthjyz -AccountEmail your@gmail.com -Scope drive
.\skills\cloud-interop\scripts\interop-health.ps1 -GDriveRemote gdrive_jzthjyz -ProbeWrite
```

你需要做的只有：当浏览器弹出 Google 登录/授权时，选择目标 Gmail 账号并确认授权。不要把密码、验证码、OAuth token 发给我。

### Drive 权限范围选择

| Scope | 用途 | 说明 |
|---|---|---|
| `drive` | 完整 Drive 读写 | 最省事，适合把 Drive 当作跨机器文件总线 |
| `drive.readonly` | 只读 | 只从 Drive 取文件，不写回 |
| `drive.file` | 仅访问由本应用创建/打开的文件 | 权限最小，但跨已有文件夹可能不方便 |

如果要写入已有共享文件夹，请告诉我目标文件夹名或 folder id；如果只想读某个文件夹，也可以限定 root folder。

## 2. Kaggle 打通方式

推荐保留 Kaggle 官方凭据文件：

```text
%USERPROFILE%\.kaggle\kaggle.json
```

`kaggle.json` 不能提交。健康检查只报告“存在/可用”，不会打印 key。

常用用途：

- 从 Kaggle dataset 拉数据到本机/HPC。
- 把本机或 Drive 的结果上传成私有 Kaggle dataset。
- 让 Notebook 与 GitHub 分支产物互通。

## 3. 本机双帐号/多平台命名规范

建议每个平台用清晰 remote/profile 名：

| 类型 | 命名例子 | 凭据位置 |
|---|---|---|
| GitHub | `origin` + `arena/...` 分支 | `gh`/GCM 本机凭据 |
| Google Drive 个人号 | `gdrive_main` | `%APPDATA%\rclone\rclone.conf` |
| Google Drive 第二账号 | `gdrive_jzthjyz` | 同上，本机 rclone 管理多个 remote |
| Kaggle | `kaggle_default` | `%USERPROFILE%\.kaggle\kaggle.json` |
| Muse | `muse_git_poll` | Muse 机器自己的 git 凭据 |
| HPC/台式机 | `tailscale` / `ssh` | 本机 SSH/Tailscale 凭据 |

## 4. HPC / 台式机 / Muse 互通

- Laptop/Windows：用 `git-sync` watcher 跑真实本机任务。
- Desktop/HPC：优先 Tailscale/SSH/已有 VPN 路线；状态写到 `results/status/`。
- Muse：按用户纠正，Muse 是 outbound-only，不要求 laptop 主动连入 Muse。Muse 任务走 GitHub 分支 request/status/artifact，或以后加 Google Drive 邮箱式目录。

Muse 已有路径：

- 协议：`results/muse/REQUEST_PROTOCOL.md`
- Poller：`code/muse/muse_poll_once.sh`
- 产物目录：`sources/muse/`
- 状态目录：`results/muse/`

## 5. 需要用户提供/确认什么

Google Drive 真正打通时，我只需要这些非密码信息：

1. 要授权的 Google 账号是哪一个。
2. 权限范围：完整读写、只读，还是最小权限。
3. 是否要绑定到某个 Drive 文件夹或共享盘。
4. 本机能否打开浏览器完成一次 OAuth 授权。
5. 是否允许写一个很小的 `Arena/interop/` 探针文件来证明读写。

我不需要、也不会索要：Google 密码、短信验证码、2FA、OAuth token、cookie、Kaggle key、SSH 私钥。


## 6. 本次实测结果（2026-10-03）

`gdrive_jzthjyz:` 已在 Windows 笔记本通过 rclone OAuth 打通，账号提示为 `jzthjyz@gmail.com`，权限范围为 `drive`。

实测报告：

- `results/cloud_interop/GDRIVE_SETUP_R249.md`
- `results/cloud_interop/INTEROP_HEALTH.md`

通过标记：

```text
GDRIVE_RCLONE_READY=True
GDRIVE_PROBE_WRITE_OK=True
gdrive_about_ok=True
gdrive_probe_write=True path=gdrive_jzthjyz:Arena/interop/probe-20261003-203544.txt
```

注意：rclone 报告提示 shared Google Drive client_id 会在 2026 年停用；短期可用，长期建议以后为本账号创建自有 Google OAuth client_id。
