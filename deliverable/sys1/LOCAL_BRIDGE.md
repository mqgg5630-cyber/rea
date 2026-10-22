# 与本机打通：现状、重建、以及"只留结果"的本地布局

"本机"指用户 Windows 机器上的 **git-sync 值守任务**（`watch.ps1`），不是沙箱里的任何
目录。链路只有 git：agent 推分支 → 值守拉取 → 在本机执行 `code/tasks/tN_*.ps1` →
把回执推回来。沙箱无法直接在你的机器上执行命令；唯一能执行的是那个计划任务。

---

## 1. 已经证明了什么（第 1 轮）

`E:\0github\git-sync\rea-1bfdc2ed` 这个目录**现在已经不存在**（你删掉了旧克隆），但它
当时留下的回执还在仓库里：

```text
results/link/LINK_PROBE.md
LINK_PROBE_ROUND=1
host=LAPTOP-R77M5D6M
os=Microsoft Windows 11 专业版 (build 26200)
repo_path=E:\0github\git-sync\rea-1bfdc2ed
watcher_task=git-sync-watch-rea-1bfdc2ed state=Running mode=powershell loop
LINK_PROBE_OK=True
```

即：**拉取 → 在真机执行 → 推回** 三段都成功；机器名、PowerShell 版本、仓库路径、
值守任务状态都是真机事实。第 1 轮整体判 `failed` 只因第二个任务
`t2_computer_use_smoke.ps1` 在这台机器上找不到 UIA 文本框（`CU_UIA_TYPE_OK=False`）——
和链路、和 laya 都无关。该标准已在本轮主动退役。

第 2 轮（`round=2`）已经排好队，就等新的本地克隆出现。

---

## 2. 新的本地布局：`.git-sync` + `results`

以后你的机器上**不保留项目源码**：

```text
E:\0github\
├─ .git-sync\                     # 控制区：sparse + blobless 克隆，只落盘运行所需
│  ├─ rea-94caee25\               #   根脚本 + code\ + skills\ + results\ + deliverable\
│  └─ <project>-<branch>\
├─ results\                       # 唯一给你看的东西（hub mirror 出来的）
│  ├─ rea-94caee25\
│  └─ <project>-<branch>\
└─ hub.ps1 -> 在控制区里，用 `.\hub.ps1` 调用
```

* 克隆参数：`--filter=blob:none --sparse`，sparse 只保留
  `results deliverable code skills`（根目录脚本总是保留）。
  这个仓库在 GitHub 上 374 MB，实测 blobless+sparse 克隆后落盘 **13 MB / 1.4 秒**
  （`src/`、`website/`、`tests/` 不下载），并且在这个克隆里 `selfcheck.py` 仍是 21/21。
* `hub.py mirror` 把每个克隆的 `results\` 与 `deliverable\` 复制到
  `E:\0github\results\<name>\`，源码不复制。
* 想更狠：`.\hub.ps1 trim --keep results` 后，连 `code\` 也会从工作区消失
  （仍可通过 `git sparse-checkout set` 按需取回）。

> 值守任务仍然**每个克隆一个**：git-sync 的锁、握手、凭据、自动推回都是按仓库设计的，
> 一个进程轮询所有仓库需要重写它的事务模型，会把已经验证过的链路变成没验证过的代码。
> `hub.ps1` 给的是**一个入口、一套策略、一张总表**：新增项目、注册值守、镜像结果、
> 清理失效任务都在这里。

---

## 3. 重建（复制粘贴即可）

在你刚才的 `E:\0github` 下：

```powershell
New-Item -ItemType Directory -Force E:\0github\.git-sync | Out-Null
git clone --filter=blob:none --sparse -b arena/94caee25-rea https://github.com/mqgg5630-cyber/rea.git E:\0github\.git-sync\rea-94caee25
cd E:\0github\.git-sync\rea-94caee25
git sparse-checkout set results deliverable code skills
.\bootstrap.ps1 -Auto
```

`bootstrap.ps1 -Auto` 会：放开 CurrentUser 执行策略、补 git 身份、切分支、首拉、
**静默推 auth**、注册值守任务 `git-sync-watch-rea-94caee25`。

然后清掉指向已删除目录的旧任务：

```powershell
Unregister-ScheduledTask -TaskName git-sync-watch-rea-1bfdc2ed -Confirm:$false -ErrorAction SilentlyContinue
.\hub.ps1 status
```

看到 `watcher = Ready/Running` 即可。值守下一轮（默认 2 分钟）会读到
`results/status/handshake.json` 的 `round=2`，执行
`code/tasks/t3_sys1_selfcheck.ps1`，把
`results/sys1/local/SYS1_LOCAL.md` 推回来。

---

## 4. 以后新增项目 / 分支（一条命令）

```powershell
cd E:\0github\.git-sync\rea-94caee25
.\hub.ps1 add https://github.com/you/other.git arena/some-branch
```

它做四件事：`--sparse --filter=blob:none` 克隆到 `.git-sync\<name>` → 只检出
`results/deliverable/code/skills` → 若仓库带 `bootstrap.ps1` 就 `-Auto`（鉴权 + 注册值守）
→ 打印结果。

常用：

```powershell
.\hub.ps1 status          # 所有克隆：分支、HEAD、脏文件、值守状态、sparse 路径
.\hub.ps1 mirror          # results\ + deliverable\ -> E:\0github\results\<name>\
.\hub.ps1 trim            # 只留 results/deliverable/code/skills
.\hub.ps1 trim --keep results          # 连 code/skills 也不留（下次检查前要再 set 回来）
.\hub.ps1 prune           # 删掉目录已不存在的值守任务
.\hub.ps1 register        # 给所有已有克隆重新注册值守
```

`hub.py` 是纯标准库 Python；`hub.ps1` 只负责找 `python` 并转发，所以逻辑可以在
非 Windows 上测试（本仓库的 `code/hub/` 已用真实 git 仓库做过 clone / status /
mirror / trim 的回归）。

---

## 5. 第 2 轮：让 sys1 在你的机器上跑一遍

`code/tasks/t3_sys1_selfcheck.ps1`（ASCII-only，`Write-Output`）在真机上：

1. 找 Python（`python` → `py -3` → `python3`）；
2. `python code/sys1/selfcheck.py --local` → 21 项离线检查（解码一致、路由、HTTP、
   MCP、socket 阻断、延迟）；
3. `python -m sys1 decide --agent-logits …` → **agent 的分数在本机解码**，期望
   `billing / 0.9042`；
4. `python code/sys1/demo_agent.py` → 6 个多语言案例；
5. 写 `results/sys1/local/SYS1_LOCAL.md`。

成功标准（`results/status/success_criteria.json`）要求该文件含：

```text
SYS1_TASK=sys1-round2
SYS1_CHECK_ROUND=<handshake round>
SYS1_AGENT_CHOICE=billing
SYS1_HTTP_OK=True
SYS1_MCP_OK=True
SYS1_LOCAL_OK=True
```

以及 `deliverable/sys1/` 三份文档、`results/sys1/EVAL.md`、`SELFCHECK.md` 存在。

---

## 6. 验收时看什么

| 文件 | 含义 |
|---|---|
| `E:\0github\results\rea-94caee25\sys1\local\SYS1_LOCAL.md` | 真机 Python 版本、git head、21/21、`billing` 决策、HTTP/MCP 结果 |
| 同目录 `local\SELFCHECK.json` | 机器可读回执（host/platform/延迟/每项检查） |
| 克隆内 `results/status/check_r2_*.txt` | 值守捕获的完整 stdout 与退出码 |
| `results/status/handshake.json` | `round`、`arena_state`、`local_state`、`host` |

若 `SYS1_LOCAL_OK=False`：先看 `SYS1_LOCAL.md` 中失败的那一行，最常见的是
`PYTHON=missing`（PATH 上没有 python）或 gate 在 Windows bash 上没通过。
