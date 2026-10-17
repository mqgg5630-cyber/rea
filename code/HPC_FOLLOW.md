# hpc_follow.ps1 — Windows 一次安装、长期值守（只要结果版）

解决的问题：以前每开一轮对话就要在 Windows 机器上重装一遍值守、整仓同步，
占空间又费事。现在的模型是：

- **只装一次**：计划任务每分钟自己醒，自己 `fetch`、自己切到有请求的分支、
  自己跑 `code/tasks/r<N>.sh`、把结果推回同一分支。关掉对话、再开新会话，
  同一条安装照样接活，不需要重装。
- **只同步结果**：每轮只浅拉被服务的单个分支（`--depth 1 --filter=blob:none`），
  复用 `%LOCALAPPDATA%\hpc_follow\repo` 这一个工作区；提交时只 `add results/`，
  任务写到 `results/` 以外的东西会被丢弃。不同步所有仓库、不拉全部历史。
- **驱动自动 accept**：回执写回 `results/status/handshake.json`
  （`local_state=passed/failed`），Arena 侧驱动轮询到就按原有规则 accept，
  与现有 `skills/git-sync` 握手协议完全兼容。
- **`-Prefer` 语义**：指定分支有未应答轮次时只服务它；答完后自动回退到
  发现规则——在 `arena/*` 里挑 tip 提交时间最新且有未应答轮次的分支。

## 一次性安装（在 Windows 机器上，仓库任意一个检出里执行一次）

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\code\hpc_follow.ps1 -Install -Repo https://github.com/<owner>/<repo>.git -Prefer arena/84877cdd-rea
```

安装器会先做一次「无人值守探活」：关掉一切交互提示去 `git ls-remote`。

- 探活通过 → 注册计划任务 `hpc_follow_tick`（每分钟 + 登录时），并立刻踢一轮。
- 探活失败 → **不注册假活的计划任务**（这是以前踩过的坑：任务在、但无人值守
  环境里 git 鉴权过不去，每分钟静默失败）。它会改为从当前交互 shell 启动
  常驻循环（继承你当前能用的凭据），并告诉你修复路径：让 git 能非交互工作
  （Git Credential Manager 存好 token，或用无口令部署密钥），再跑一次
  `-Install`，计划任务即接管。Windows OpenSSH agent 是系统服务，计划任务
  同用户可达，`-Status` 会如实报告它的状态，但不靠猜。

## 日常使用

```powershell
.\code\hpc_follow.ps1 -Status     # 看真实状态：会现场重新探活，不只看注册项在不在
.\code\hpc_follow.ps1 -Tick       # 手工跑一轮（计划任务调的也是这个）
.\code\hpc_follow.ps1 -Uninstall  # 摘计划任务 + 停常驻循环（状态目录保留）
```

改服务偏好不用重装，改配置即可（或重跑一次带新 `-Prefer` 的 `-Install`，幂等）：

- 配置：`%LOCALAPPDATA%\hpc_follow\config.json`（`repo` / `prefer` / `timeout_min` / `branch_glob`）
- 状态与日志：`%LOCALAPPDATA%\hpc_follow\state.json`、`follow.log`
- 每轮产物（推回分支的只有这些）：`results/status/check_r<N>_<stamp>.log`、
  `results/status/hpc_r<N>.json`、更新后的 `results/status/handshake.json`

## 轮次协议（给 Arena 侧驱动）

请求一轮 = 向目标分支提交两样东西（和仓库现有协议一致）：

1. `results/status/handshake.json`：`round=N`、`arena_state="awaiting_check"`、`local_state="pending"`
2. `code/tasks/r<N>.sh`：要在 Windows 上跑的脚本（经 Git Bash 执行，
   环境变量 `HPC_ROUND` / `HPC_BRANCH` 可用；产物必须写到 `results/` 下才会被回传）

值守端答完自动提交 `local: auto: check round N ...` 并推送，驱动轮询到
`local_state` 后按 `results/status/success_criteria.json` 自动 accept。

## 已知边界（不糊弄）

- 本脚本在本仓库的沙箱里只过了静态门（`code/check_all.sh`：ASCII、
  `$var:` 扫描、括号配平）；沙箱没有 PowerShell，解析级检查是 SKIP。
  **第一次在 Windows 上跑时先执行 `-Status` 和一次手工 `-Tick` 验证**，
  有报错把 `follow.log` 贴回来。
- 计划任务以当前用户身份运行；机器重启后靠「登录时」触发 + 每分钟重复，
  不登录则不跑（需要免登录运行请改用常驻循环或自行以服务方式注册）。
- 单轮默认超时 120 分钟（`timeout_min`），期间锁文件保证不重叠跑。
