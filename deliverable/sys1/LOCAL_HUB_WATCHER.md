# One local self-polling hub

`hub-watch.ps1` replaces one scheduled watcher per checkout with one machine-user task, `git-sync-hub`. Install it once from the sparse checkout:

```powershell
.\hub-watch.ps1 -Install
.\hub-watch.ps1 -Status
```

The task starts at the current Windows user's logon and runs one serialized loop. Each tick discovers remote `arena/*` branches for the already registered project remotes, creates sparse, blobless checkouts for new branches under `E:\0github\.git-sync`, then runs each checkout's existing `watch.ps1` once. The sparse paths are `results`, `deliverable`, `code`, and `skills`; project source trees are not materialized. Results and deliverables are mirrored to `E:\0github\results\<checkout-name>` by PowerShell. Polling, branch discovery, and result mirroring do not require Python.

The first checkout for a project is the seed that supplies its remote URL. To onboard another project, add one sparse seed checkout (no source tree and no per-project scheduled task):

```powershell
.\hub-watch.ps1 -AddUrl https://github.com/OWNER/REPO.git -Branch arena/SESSION-REPO
```

The hub will discover all its `arena/*` branches thereafter. A new Arena conversation branch for an already registered remote is discovered automatically on a later tick. No per-branch watcher registration is needed.

The one-time `-Install` migration pauses and removes existing `git-sync-watch-*` scheduled tasks, then registers only `git-sync-hub`. Useful commands:

```powershell
.\hub-watch.ps1 -Once       # run one serialized cycle now
.\hub-watch.ps1 -Status
.\hub-watch.ps1 -Remove
```

Logs are kept outside the repository at `%LOCALAPPDATA%\git-sync\hub\hub-watch.log`. This is logon-start, not pre-logon boot execution. It continues unattended after the user logs in, while the machine is awake and network/GitHub credentials are available.
