# Skills installed on this branch (rea × git-sync bridge)

Source: [`mqgg5630-cyber/git-pull-arena` @ `arena/01a0ff69-git-pull-arena`](https://github.com/mqgg5630-cyber/git-pull-arena/tree/arena%2F01a0ff69-git-pull-arena)
— git-sync **v2.8.1**, installed with its own `agent-install.sh`, plus the two
agent-side fixes from the same v2.8.1 on `arena/01a10bfd-git-pull-arena`
(`git config --replace-all` for the fetch refspec; `agent-handsfree.sh`
fast-forwards before judging `success_criteria.json`).

> rea treats `/skills/` as generated output (`npm run docs:generate`). `.gitignore`
> on this branch keeps that rule and only un-ignores the four entries below, so
> the generated `skills/reverse-engineer-anything/` stays untracked.
> **Do not merge this branch into `main`**: rea's `verify-repository-skill` check
> requires a tracked tree without `skills/`, and `package.json#files` ships `skills/`.

| Path | What it is |
|---|---|
| `skills/git-sync/` | Arena branch ⇄ GitHub ⇄ Windows machine: watcher, silent push, receipts, hands-free loop |
| `skills/computer-use/` | Windows UIA / MCP / COM automation playbook + safety rules |
| `skills/cloud-interop/` | Multi-account slots: Google Drive (rclone OAuth), Kaggle, HPC/desktop, Muse |
| `skills/README.md` | this index |

## 需求 → 机制对照（你要的每一项落在哪）

| 需求 | 机制 | 位置 |
|---|---|---|
| 本地电脑**自动 pull** | 值守每轮 `auto_pull`（`hands_free=true`，默认每 2 分钟） | `watch.ps1` → `sync.ps1` |
| **执行代码** | `code/tasks/manifest.json` 把轮次映射到脚本，本机 `code/local_check.ps1` 第 4 节逐个运行（独立子进程，输出进回执，非 0 判失败） | `code/tasks/*.ps1` |
| **push 返回状态** | 每轮结论 + 日志推回分支：`results/status/handshake.json`、`results/status/check_rN_*.txt`；平时本机改动 `auto_push` 静默推送 | `push.ps1 -NoPrompt` |
| **轮询** | 本机：常驻 `watch.ps1 -Loop`（2 分钟）；助手：`agent-wait.sh` 自适应轮询，结论一到就返回 | `agent-wait.sh --timeout auto` |
| **切换账号 / 会话** | 每个 Arena 会话（换账号=新会话=新分支）一个新文件夹 + 一个值守；新值守注册时自动 park 其他会话；`.\watch.ps1 -Focus` 切回、`-RestoreParked` 全恢复、`-KeepOthers` 并行；GitHub 凭据 `.\auth.ps1 -Setup -Verify` / `-GhLogin`；云账号槽位见 `skills/cloud-interop` | `watch.ps1`、`auth.ps1` |
| **解放双手** | 助手一条命令：sync → request → 等本机结论 → 读 `success_criteria.json` → 全过自动 accept | `agent-handsfree.sh` |
| **computer use** | UIA 找窗/找控件/输入/点击；本仓库自带零依赖自检 `t2_computer_use_smoke.ps1`；外部后端（windows-computer-use / Windows-MCP / pywinauto-mcp）见技能文档 | `skills/computer-use/` |

## 助手每轮怎么用（Arena 侧）

```bash
# 0) 本机已经跑过 agent-handoff.sh 打印的那段 PowerShell（clone + bootstrap -Auto）
# 1) 新本机任务：写 code/tasks/tN_xxx.ps1（ASCII、Write-Output、产物放 results/）
#    并登记到 code/tasks/manifest.json 的下一轮；更新 results/status/success_criteria.json
# 2) 一条命令闭环：
bash skills/git-sync/scripts/agent-handsfree.sh \
     --sync "feat: <本轮改动>" --request "verify: <任务一句话>" --timeout auto
#    exit 0 = 本机过 + 标准过 + 已 accept；2 = 看 results/status/check_r*_*.txt 修完再跑；
#    3 = 本机值守不在线 -> 重新贴 agent-handoff.sh 的输出，不要假装成功
bash skills/git-sync/scripts/agent-check.sh --read   # 随时看最近一轮
```

## 本机常用（Windows PowerShell，在本仓库克隆目录里）

```powershell
.\doctor.ps1                 # 体检：branch / ahead-behind / watcher / heartbeat / auth / hands-free
.\watch.ps1 -Status          # 值守是否活着、上一轮结论
.\watch.ps1 -Focus           # 只让这个会话的值守运行（切回本会话）
.\watch.ps1 -RestoreParked   # 恢复被 park 的其他会话值守
.\auth.ps1 -Setup -Verify    # 免点击推送（换 GitHub 账号/令牌后重跑）
.\hardware.ps1 -Deep         # 上报本机 GPU/conda 环境给助手
```

## 安全默认值（继承自源仓库）

1. 不向用户索要密码、OAuth/API 令牌、cookie、2FA；凭据只留在本机（`gh`/GCM、rclone.conf、kaggle.json）。
2. `auto_push_exclude` 永不自动推送 `.env*`、`*.pem`、`*.key`、`*credentials*`、`*secret*`、`*token*`。
3. computer use 只在安全自检或用户明确批准的任务里操作 GUI；不截图、不记录其他窗口标题。
4. 「与本地打通」= 用户 Windows 上的 `watch.ps1` 计划任务；沙箱目录永远不算本机。
