# Computer Use / Windows MCP Skill

## Trigger

Use this skill when the user asks for "computer use", Windows MCP, GUI automation, Antigravity/browser control, Office/WPS COM automation, desktop/HPC assisted GUI tasks, or cross-platform coordination with the laptop watcher.

## Current empirically tested laptop baseline

Fresh laptop smoke was run through git-sync on `LAPTOP-R77M5D6M` in round 253.

Evidence files:

- `results/computer_use/COMPUTER_USE_LAPTOP_R249.md`
- `results/computer_use/COMPUTER_USE_LAPTOP_R249.json`
- `results/cloud_interop/GDRIVE_SETUP_R249.md`
- `results/cloud_interop/INTEROP_HEALTH.md`

Known-good markers:

- `COMPUTER_USE_LAPTOP_OK=True`
- `WCU_UIA_INVOKE_OK=True`
- `GDRIVE_SETUP_OK=True`
- `gdrive_probe_write=True`

## Tested modules and roles

| Module / surface | Role | Laptop status |
|---|---|---|
| `windows-computer-use` | Windows UIA backend; find/activate/invoke controls | Present and tested: WinForms button found and invoked; marker file written |
| `Windows-MCP` | Windows MCP project candidate | Present on E-drive lab path; included in capability inventory |
| `pywinauto-mcp` | pywinauto MCP project candidate | Present on E-drive lab path; included in capability inventory |
| Antigravity | Local IDE/agent surface and terminal/GUI endpoint | Executable detected; prior CDP/terminal tests kept in `results/mcp_agv_lab/` |
| WPS Office COM | Document/deck automation via COM | `KWPS.Application`, `KET.Application`, and `KWPP.Application` instantiated successfully |
| Google Drive `gdrive_jzthjyz:` | Cross-machine/cloud mailbox for non-secret artifacts | rclone OAuth completed; probe file written under `Arena/interop/` |
| Tailscale peers | Laptop/Desktop/Muse coordination | Health report sees laptop, desktop, and Muse peers; Muse remains outbound-only |

## Operating rules

1. Use git-sync watcher for tasks that must run on the user's Windows laptop.
2. Do not run destructive GUI automation without an explicit user-approved task.
3. Do not capture or commit screenshots unless the user asks and approves the privacy risk.
4. Do not commit tokens, cookies, OAuth refresh tokens, `rclone.conf`, `kaggle.json`, SSH keys, or MCP secrets.
5. Redact account IDs, long tokens, GUID-like IDs, and private paths in reports when possible.
6. For Muse, do not require inbound laptop-to-Muse access; use GitHub request/status/artifacts or Google Drive mailbox style exchange.

## Preferred smoke test

The minimal safe laptop proof is a local WinForms test window:

1. Start a small local form with a button.
2. Use `windows-computer-use` UIA backend to activate the window.
3. Find the `Write Marker` button.
4. Invoke it via UIA/fallback click.
5. Verify the marker file exists.

This proves the backend can control a real Windows UI without touching the user's personal apps.

## Coordination with cloud interop

Use `skills/cloud-interop/` when a computer-use workflow needs a cloud mailbox:

- Google Drive remote: `gdrive_jzthjyz:`
- Probe path pattern: `gdrive_jzthjyz:Arena/interop/probe-YYYYMMDD-HHMMSS.txt`
- Local health report: `results/cloud_interop/INTEROP_HEALTH.md`

## Follow-up extensions

- Add a Windows-MCP server-level JSON-RPC smoke after the exact server command is chosen.
- Add pywinauto-mcp stdio smoke when the project dependency environment is pinned.
- Add desktop-side fallback smoke once the desktop E-drive lab path and archive extraction are confirmed healthy.
- Add Kaggle dataset/notebook interop after local Kaggle CLI credentials are configured.
