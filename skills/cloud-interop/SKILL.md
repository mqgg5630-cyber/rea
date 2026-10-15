# Cloud Interop Skill

## Trigger

Use this skill when the user asks to connect Google Drive, Kaggle, cloud notebooks, the local Windows laptop, desktop/HPC, Muse, or multiple platform accounts.

## Goals

- Provide a repeatable path for file exchange across GitHub, Google Drive, Kaggle, the laptop watcher, desktop/HPC, and Muse.
- Keep account secrets local to the machine that owns them.
- Produce non-secret health reports that the Arena agent can read through git-sync.

## Google Drive policy

Preferred method: install `rclone` on the Windows machine and configure a Drive remote with browser OAuth.

- Do ask the user to be present for the browser sign-in/consent step.
- Do not ask for the Google password, OAuth code, refresh token, or cookies in chat.
- Store rclone's token only in the user's local rclone config, normally `%APPDATA%\rclone\rclone.conf`.
- Use remote names such as `gdrive_main`, `gdrive_work`, or `gdrive_jzthjyz` rather than embedding full credentials in paths.
- After setup, verify with `rclone about <remote>:` and optionally write a small sentinel file under `Arena/interop/`.

Scripts:

```powershell
.\skills\cloud-interop\scripts\setup-gdrive-rclone.ps1 -RemoteName gdrive_main -AccountEmail your@gmail.com
.\skills\cloud-interop\scripts\interop-health.ps1 -GDriveRemote gdrive_main -ProbeWrite
```

## Kaggle policy

Preferred method: use Kaggle's official API credential locally.

- `kaggle.json` must stay in `%USERPROFILE%\.kaggle\kaggle.json` or another local-only `KAGGLE_CONFIG_DIR`.
- Never commit the Kaggle username/key pair.
- Health checks may report that Kaggle CLI and credential file are present, but must mask the username and never print the key.

## Machine and Muse policy

- Laptop/desktop/HPC tasks use the git-sync watcher where possible.
- Muse is outbound-only on Tailscale; do not require inbound laptop -> Muse connections.
- Muse tasks should use GitHub branch request/status/artifact directories or a user-approved cloud mailbox.

## Account slots

Maintain distinct names for distinct accounts and surfaces:

| Slot | Example name | Credential home | Repo-safe use |
|---|---|---|---|
| GitHub agent branch | `origin/arena/...` | `gh`/GCM local store | commits, status, artifacts |
| Google Drive personal | `gdrive_main` | local rclone config | large file mailbox, shared folders |
| Google Drive secondary | `gdrive_work` | local rclone config | separate mailbox/account |
| Kaggle | `kaggle_default` | local `kaggle.json` | datasets/notebooks via CLI/API |
| Muse | `muse_git_poll` | Muse's own git credential | outbound request polling |
| HPC/Desktop | `tailscale/ssh` | SSH keys/local auth | compute, remote staging |

## Health report

Run `interop-health.ps1` after any account or route change. It writes a non-secret report under `results/cloud_interop/` that can be pushed through git-sync.
