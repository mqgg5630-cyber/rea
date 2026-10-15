# Computer Use / Windows MCP 技能说明

这个技能覆盖你提醒的那部分：computer use、Windows MCP、pywinauto-mcp、Antigravity/browser 控制、WPS/Office COM、以及和本机 watcher、台式机、HPC、Muse、Google Drive 的配合。

## 已在笔记本实测通过

实测机器：`LAPTOP-R77M5D6M`  
实测轮次：round 253  
报告：

- `results/computer_use/COMPUTER_USE_LAPTOP_R249.md`
- `results/computer_use/COMPUTER_USE_LAPTOP_R249.json`
- `results/cloud_interop/GDRIVE_SETUP_R249.md`
- `results/cloud_interop/INTEROP_HEALTH.md`

通过标记：

```text
COMPUTER_USE_LAPTOP_OK=True
WCU_UIA_INVOKE_OK=True
GDRIVE_SETUP_OK=True
gdrive_probe_write=True
```

## 当前可用模块

| 模块 | 用途 | 实测状态 |
|---|---|---|
| `windows-computer-use` | Windows UIA 找窗口、找控件、点击/Invoke | 已实测：WinForms 测试按钮被找到并触发，marker 文件写入成功 |
| `Windows-MCP` | Windows MCP 候选项目 | E 盘 lab 路径存在，纳入能力清单 |
| `pywinauto-mcp` | pywinauto MCP 候选项目 | E 盘 lab 路径存在，纳入能力清单 |
| Antigravity | IDE/agent 界面、terminal/GUI 入口 | 可检测；历史 CDP/terminal 证明在 `results/mcp_agv_lab/` |
| WPS Office COM | 文档、表格、PPT 自动化 | Writer/Sheet/Presentation COM 都能实例化 |
| Google Drive `gdrive_jzthjyz:` | 跨设备文件邮箱 | OAuth 已完成，`Arena/interop/` probe 已写入 |
| Tailscale | laptop/desktop/Muse 互通状态 | health 报告能看到 laptop、desktop、Muse；Muse 仍按 outbound-only 处理 |

## 安全规则

1. 需要动真实 Windows GUI 的任务，优先走 git-sync watcher 在本机执行。
2. 先用安全 smoke test 验证能力，不直接操作用户重要软件。
3. 不经允许不截图、不录屏、不上传窗口内容。
4. 不提交 `rclone.conf`、Kaggle key、OAuth token、cookie、SSH 私钥、MCP 密钥。
5. Muse 不要求入站连接；走 GitHub request/status/artifact 或 Google Drive 邮箱式目录。

## 标准 smoke test

最小安全证明是本地 WinForms 测试窗：

1. 开一个只含测试按钮的小窗。
2. 用 `windows-computer-use` UIA backend 激活窗口。
3. 查找 `Write Marker` 按钮。
4. Invoke 按钮。
5. 检查 marker 文件写入。

这次已经通过，说明 laptop 侧 computer-use 的基础 UIA 控制链路是通的。

## 下一步可补

- 选定 `Windows-MCP` 的实际 server 启动命令后，加 stdio JSON-RPC 级 smoke。
- 为 `pywinauto-mcp` 固定依赖环境后，加 stdio smoke。
- 台式机侧等 E 盘 lab/解压状态稳定后，补 desktop fallback smoke。
- Kaggle CLI 凭据配置好后，补 Kaggle dataset/notebook 和 Drive/GitHub 的互通。
