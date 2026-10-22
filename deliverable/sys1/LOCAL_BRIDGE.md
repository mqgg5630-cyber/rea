# 与本机打通：现状与第 2 轮

"本机"指用户 Windows 机器上的 **git-sync 值守任务**（`watch.ps1`），不是沙箱里的任何
目录。链路只有 git：agent 推分支 → 值守拉取 → 在本机执行 `code/tasks/tN_*.ps1` →
把回执推回来。沙箱无法直接在你的机器上执行命令；唯一能执行的是这个计划任务。

---

## 第 1 轮：链路已证明，唯一失败项是 UIA

回执 `results/link/LINK_PROBE.md`（由本机执行后推回）：

```text
LINK_PROBE_ROUND=1
host=LAPTOP-R77M5D6M
os=Microsoft Windows 11 专业版 (build 26200)
powershell=5.1.26100.8875
repo_path=E:\0github\git-sync\rea-1bfdc2ed
config_branch=arena/1bfdc2ed-rea
head_branch=arena/1bfdc2ed-rea branch_matches_config=True
watcher_task=git-sync-watch-rea-1bfdc2ed state=Running mode=powershell loop
LINK_PROBE_OK=True
```

即：**拉取 → 执行 → 推回** 三段都成功，机器、PowerShell 版本、仓库路径、值守任务状态
都是真机事实。`results/status/check_r1_20261015-103335.txt` 里还能看到每个任务的
起止与退出码。

失败的是同一轮的第二个任务：

```text
results/computer_use/CU_SMOKE.md
CU_WINDOW_FOUND=True
CU_UIA_TYPE_OK=False
CU_DETAIL=text box not found via UIA
COMPUTER_USE_SMOKE_OK=False
```

这不是链路问题，是 Windows 11 (26200) 上 UIA 找不到文本框（可能被安全桌面/焦点/
控件虚拟化挡住）。第 1 轮的成功标准因此整体判 `failed`。

**结论：与本机的“管道”是通的；第 1 轮只是被一个与本次任务无关的 UI 测试拖红了。
sys1 不需要任何 UI。**

---

## 第 2 轮：让 sys1 在你的机器上跑一遍

新增 `code/tasks/t3_sys1_selfcheck.ps1`（ASCII-only，只用 `Write-Output`），在真机上：

1. 找到 Python（依次尝试 `python`、`py -3`、`python3`）；
2. `python code/sys1/selfcheck.py --local` → 21 项离线检查（解码一致、路由、HTTP、
   MCP、socket 阻断、延迟）；
3. `python -m sys1 decide --agent-logits …` → **agent 的分数在本机解码**，
   期望 `billing` / `0.9042`；
4. `python code/sys1/demo_agent.py` → 6 个多语言案例；
5. 写 `results/sys1/local/SYS1_LOCAL.md`，带 `SYS1_LOCAL_OK=True/False`。

成功标准（`results/status/success_criteria.json`）要求该文件同时含：

```text
SYS1_ROUND=2
SYS1_AGENT_CHOICE=billing
SYS1_HTTP_OK=True
SYS1_MCP_OK=True
SYS1_LOCAL_OK=True
```

以及 `deliverable/sys1/` 三份文档、`results/sys1/EVAL.md`、`SELFCHECK.md` 存在。

> 第 1 轮的 computer-use 标准已**主动退役**：它需要 UIA 注入文本，而这台机器的
> 安全策略不允许；本轮要证明的是决策引擎，不是 UI 自动化。`LINK_PROBE.md` 仍然保留
> 作为链路证据。

---

## 你只需要两条命令

配置里的分支已改成本会话的 `arena/94caee25-rea`；旧 clone 上执行：

```powershell
cd E:\0github\git-sync\rea-1bfdc2ed
.\sync.ps1 -Branch arena/94caee25-rea
.\watch.ps1 -Status
```

* `sync.ps1` 会 fetch、切分支、`pull --ff-only`（本地有改动会先 stash）；
* `watch.ps1` 每轮会自动拉取 `results/status/handshake.json`，看到 `round=2` 就执行
  `code/local_check.ps1` → 其 section 4 运行 `code/tasks/t3_sys1_selfcheck.ps1`；
* 跑完自动 commit + push 回执，agent 侧用 `agent-wait.sh` / `agent-criteria.sh` 读取。

如果值守任务不在运行：

```powershell
.\watch.ps1 -Register
```

（任务名固定为 `git-sync-watch-<仓库名>`，同一个 clone 不需要重建。）

---

## agent 侧如何收尾

```bash
bash skills/git-sync/scripts/agent-handsfree.sh \
  --sync "feat(sys1): agent-as-decision-engine + laya/Jev reverse engineering" \
  --request "verify: round 2 - run sys1 selfcheck + agent-logit decision on the local machine" \
  --timeout auto
```

它会： sync → 请求（round+1）→ 轮询值守 → 跑成功标准 → 全过则 `--accept`。
`exit 3` 表示值守没有回传（机器关机/任务未注册），不是代码失败。

---

## 验收时看什么

| 文件 | 含义 |
|---|---|
| `results/sys1/local/SYS1_LOCAL.md` | 真机上的 Python 版本、git head、21/21、`billing` 决策、HTTP/MCP 结果 |
| `results/sys1/local/SELFCHECK.json` | 同一份自检的机器可读回执（含 host/platform/延迟） |
| `results/status/check_r2_*.txt` | 值守捕获的完整 stdout 与每步退出码 |
| `results/status/handshake.json` | `round`、`arena_state`、`local_state`、`host` |

若 `SYS1_LOCAL_OK=False`，先看 `SYS1_LOCAL.md` 里失败的那一行：常见原因是机器上没有
Python（`PYTHON=missing`）或 `code/check_all.sh` 的 gate 在 Windows 的 bash 上没通过。
