# Accio Work 桌面端 · 复刻架构说明书（REA 阶段 1–2 证据版）

> 生成：2026-10-15 · 来源：`rea` 仓库 `arena/84877cdd-rea` 分支，阿里 Accio Work `E:\AccioWork` 只读分析（轮次 2/12/13）
> 证据等级标注：**【证实】** 直接来自文件/代码；**【推断】** 依据证据合理外推；**【未知】** 需要后续阶段。

---

## 0. 分析对象身份

| 项 | 值 | 等级 |
|---|---|---|
| 包名/版本 | `@phoenix/desktop@0.34.4`（workspace：app / agent-runtime / llm / sdk / ui / common / core-types / security-guard） | 【证实】`extract/package.json` |
| 产品 | Accio Work Desktop（www.accio.com / www.accio-ai.com），发行证书 “ALIBABA (CHINA) NETWORK TECHNOLOGY CO.,LTD.”（杭州） | 【证实】`app-update.yml` publisherName |
| 运行时 | Electron；打包 electron-vite；`bun@1.3.14` 作包管理器 | 【证实】 |
| 安装包 | `AccioWork-setup.exe`（install-channel.json）；更新 `provider: generic`，频道 `beta-win`，地址 `work-download.accio-ai.com/package/` | 【证实】 |
| `app.asar` | 121,683,226 B · SHA-256 `115DFC0F…78D382` · 1689 文件 | 【证实】sha256 于 LAPTOP-R77M5D6M rounds 9–13 |

---

## 1. 进程与窗口模型【证实】

- 主进程 `out/main/index.js`（1.57 MB），渲染壳 `out/renderer/assets/index-*.js + app-store-*.js`。
- **双 WebContentsView 浏览器预览**：`browser-preview:toolbar-ready/open/close…` + `browser-preview:*` IPC；toolbar 与 content 两个 `WebContentsView`，preload 分别为 `browser/toolbar`、`browser/content`。
- **IAB（in-app browser）标签化子窗口**：`iab:open/switch/close/navigate/go-back/go-forward/reload/set-bounds/set-visible/set-owner/list-all`，事件 `iab:show-requested / iab:tabs-changed`，配 `iab-guard-extension`（chrome 扩展 guard.js+manifest，导航守卫）。
- **Agent Island（悬浮层）**：`agent-island:publish-snapshot / sync-availability / get-display-options / focus-target / perform-action / renderer-ready` + push 通道 `agent-island:action`。
- 窗口控制面 `window:*`（bounds/move-by/size/fullscreen/always-on-top/auth-layout-mode），多窗：`about / help-center / support-chat`（prewarm 预热机制）。
- **安全默认**：所有新建窗口 `contextIsolation:!0, sandbox:!0, nodeIntegration:!1`；`setWindowOpenHandler` 白名单校验 + `will-navigate` 拦截 + `did-create-window` 递归套同一策略。【证实】`webpreferences` 上下文
- 语音：`speech:warmup` + `app:*microphone*` 三个 IPC（状态/申请/跳系统设置）。
- 自定义协议：`aw-market:`、`skill-app:`（skills 应用市场与技能深链）。

## 2. IPC 表面（主进程 130+ 通道，按域分类）【证实】

启动/磁盘：`startup:get-disk-space-status, startup:open-storage-settings, startup:quit-for-disk-space, startup:graphics-*`（崩溃风暴熔断 `graphics-crash-storm`）；更新：`app:update-install-data, app:update-available/progress/downloaded`；认证：`auth:status-changed/login-failed/login-timeout/recovery-changed, app:get-access-token, app:set-ali1688-sgcookie`；通知：`notify:task-complete, notify:badge-*`；文件：`app:export-html-to-pdf, app:capture-main-window, dialog:select-*`；工作区：`workspace:watch-start/stop`；调试：`dev:toggle-debug-panel, dev:open-mcp-debug-panel, dev:mcp-app-debug-event(s), dev:open-connector-debug-panel, dev:open-plugin-docs-panel, dev:trigger-crash-debug-action, dev:quit-app-for-cold-start`；灰度：`unify-gray:get-snapshot/refresh/push-snapshot`；画布：`canvas:set-design-paste-active, canvas:native-image-paste`；`open-in-cowork`（协同入口）、`open-markdown-file(:ready)`、`my-apps-assets:*`、`slot-iframe-cache:*`（插件 iframe 槽缓存）、`vm:select-folder / simulator:*`（沙盒模拟器窗）。

## 3. 网关与 Agent Runtime（`gateway-worker.js` 12.6 MB）【证实】

**进程定位**：独立 worker，承载 LLM 网关 + 工具编排 + 本地记忆。环境键：`ACCIO_GATEWAY_URL / GATEWAY_BASE_URL / GATEWAY_PORT / PHOENIX_SECURITY_GUARD_APPKEY / EMBEDDING_BASE_URL / EMBEDDING_MODEL / HAPPYHORSE_* / COMPOSIO_API_KEY / CDP_USER_DATA_DIR`。

**MCP 工具表（16 个）**：
`list, notify_user, browser_act, browser_rpa_login, browser_rpa_run, browser_rpa_get_spec, store_auth_gateway, discover_store_accounts, skill, present_files, dashboard_report, competitor_report, competitor_monitor_list, weekly_report, mcp_call, bash`
→ 复刻要点：工具=「RPA 浏览器 4 + 店铺授权 2 + 报表 4 + 技能/文件/通知/bash/转发」的电商运营代理面。

**LLM 防线**：`LLMGuard` — 隔离“重复输出”的 assistant 消息（quarantine）、工具调用合法性校验（缺 name/id 的 malformed tool_call 计数并告警）、流式输出 stable-prefix 截断（`stablePrefixEnd`）、token 估算链（systemPromptEstimatedTokens/historyEstimatedTokens/currentTurnEstimatedTokens/cachedInputTokens）。

**SubAgent 编排**：`subTaskRunner` + `agent_start` 事件流（label/title/prompt/phaseTitle/phaseIndex/tools/maxRounds(默认10)/model/systemPrompt/skills），技能范式 `newton-skill-workflow-v1`，子代理快照 systemPrompt 懒分层回读与 UT 事件埋点（`utEventId:"19999"`，slotFields surface/pluginId/errorCode）。

**本地记忆/持久化（better-sqlite3 + sqlite-vec, WAL）**：
- `messages`（含 recall_count/last_recall_at/source/ingress_type/start_line/end_line 迁移列）
- `vec0` 虚拟表做 embedding 召回（embeddingFn.dimensions，Electron 模式加载 `app.asar.unpacked/sqlite-vec` 扩展）
- `upload_queue`（信封队列）、`video_submission_tombstones(+aliases)`、SessionIndexStore 磁盘水位 3% 阈值
- HTTP 网关域：`phoenix-gw(.alibaba.com)/pre-phoenix-gw(-{sg,us,de}.alibaba-inc.com)/gateway.1688.com/aipro.alibaba.com/www.accio{-ai}.com/pre-www.*`，阿里云 SLS 双日志端（cn-hangzhou.phoenix-gateway-china、us-east-1.phoenix-server-logstore）【证实】

## 4. 工作流/调度内核（`workflow-worker.js` 798 KB）【证实】

独立 worker + 规矩的 schema 迁移表：`schema_version, context_messages(+agent_seq索引), agent_metadata, summaries, checkpoints, notes(+workspace_module索引), task_items(+workspace_status索引), task_checkpoints, schedule(+enabled/channel_agent/next_trigger索引), schedule_execution`。
⇒ 等价于内嵌一个轻量化 Temporal：可恢复 checkpoint + 总结压缩 + 定时调度 + 频道化多 agent。`NEWTON_WF_CALLTOOL_CONCURRENCY` 控制工具并发，`PHOENIX_LOCAL_AGENT` 区分本地代理模式。

## 5. 电商 RPA 子系统【证实】

- **DSL**：`agentwork.rpa.atomic.v1`，动作面已见 `waitTimeout/readText/queryAll`（多 selector: css、nth、readMode、outputKey、onError continue；步骤级 retries/continueOnError/stepGapMs）。
- **五平台托管店登录/profile**：1688、抖店、京东、拼多多、淘宝，各两份：`{platform}-stable-identity.dsl.json`（身份探活）+ `{platform}-merchant-profile/store-profile/merchant-products.dsl.json`（画像/商品）。示例（taobao-store-profile）：读标题/body、`queryAll a[href*='.taobao.com'],a[href*='.tmall.com'] limit 120 → 官方链接表。
- **Profile Browser 分区**：`webPreferences.partition` 隔离 + `CDP_USER_DATA_DIR`；stealth 走 `patchright-core@1.60.0`（playwright-core@1.50 并列共存）。
- **Chrome 接力扩展（MV3）**：`Accio Browser Relay 0.2.7`——debugger/tabs/scripting/webNavigation/downloads 权限 + `<all_urls>` host；`background.js` 只做装配：CDP WebSocket relay（`lib/cdp/`）、TabManager、命令调度器、断线重连（alarms 保活）、agent 占领 favicon 标记（`isAgentClaimFavicon`）、external bridge（`externally_connectable` 限 www/pre-www/local.accio.com 与 *.alibaba.com）。
- **store-auth 状态机**：`store-auth:chrome-status/chrome-version-status/register-and-start/update-url/start/complete/cancel/remove`，加 `store-auth-gateway`/`discover_store_accounts` MCP 工具。
- **ecommerce-data API**：`list-stores / list-store-products / list-stores-with-data / inventory-products / query-competitors / cancel-query / list-sources / query-source / query`。

## 6. MCP 生态与 CLI【证实】

`resources/accio-mcp-cli/accio-mcp.mjs`（bun 打包 `accio-mcp.ts`，148 KB）：
- 命令：`server list|add|remove|test|auth|tools [name]`、`call [--server s] <tool> --arg …`、`search <keyword>`。
- 配置兼容 Claude Desktop `{"mcpServers":{...}}`；传输 stdio（type:local）/http；OAuth 走 `server auth`（拉起默认浏览器，detached+windowsHide）。
- `resolveGatewayOrigin()` 从桌面网关拿源地址 ⇒ 复刻时 CLI 与桌面网关解耦部署。

## 7. 外部工具链预装（remote-tools 0.7.1）【证实】

三平台同名预装包（darwin-arm64/darwin-x64/win32-x64），win 端 `pre-install-win-x64.zip` sha256 `c9f84def…0181`，内含 `node-v22.23.2 / PortableGit-2.44.0 / python-3.12.2 / lark-cli-1.0.0 / zip.exe`；下载双源 `work-download.accio.com`（国际）↔ `work-download.accio-ai.com`（国内 CN）。落地 `%LOCALAPPDATA%\Accio\pre-install[.<version>]`，完成标记 `pre-install-done`。

## 8. 安全/合规/可观测

- `@phoenix-common/security-guard`：阿里安全 SDK（`AliSafeProxy.dll / AliSafePath64.dll / NetCore.dll / SecurityGuardSDK64.dll / ThreatSieveSDK64.dll` + `security_guard.node`，`PHOENIX_SECURITY_GUARD_APPKEY`）。
- `password-vault:*`（available/list/get-storage-path/reveal-storage-file/create/update/remove）——本机密钥库。
- 前端监控：阿里 itrace 全家桶 + `@arms/rum-electron`，RUM 上报 `h-ut-acciowork.alibaba.com` / `ah7am0wjds-default-cn.rum.aliyuncs.com`。
- 诊断：`app:get-network-startup-diagnostics`、`install-monitor:ui`、`install-monitor-manifest.json`。

## 9. 复刻实施映射（组件 → 建议实现栈）

| Accio 组件 | 复刻对应 |
|---|---|
| Electron 主骨架（main + WebContentsView 预览 + IAB + agent-island） | Electron ≥ latest 稳定 + electron-vite；窗口策略照抄三方固化（sandbox/contextIsolation/deny-by-default） |
| 网关 worker + 16 工具面 | Node worker_threads/`utilityProcess` + @modelcontextprotocol/sdk；工具按 §3 同名实现 |
| LLMGuard + subTaskRunner + newton 技能范式 | 自研中间件层：消息隔离 + tool_call 校验 + stable-prefix 流式；SubAgent=事件溯源(phase/round/maxRounds) |
| 记忆 sqlite-vec + WAL schema | better-sqlite3 + sqlite-vec（照抄 messages/vec0/upload_queue 设计），`app.asar.unpacked` 放 .node |
| 工作流调度（9 表 + 索引） | 按 §4 DDL 复刻即可（表名/索引名已给全） |
| RPA DSL + 5 平台身份/画像 | JSON DSL 解释器：actions 起步实现 `waitTimeout/readText/queryAll/click/type/navigation/screenshot`；patchright 托管浏览器 + partition 持久化 |
| Chrome 接力扩展 | MV3：debugger+scripting+webNavigation+downloads+alarms；CDP WS relay server:9222 可配；externally_connectable 白名单 |
| accio-mcp CLI | 小型 Node CLI（commander），兼容 mcpServers JSON，stdio/http，OAuth loopback |
| 预装工具链 | 安装器内置 node/python/git/lark 离线包 + `remote-tools.json` 版本钉住 + sha256 校验 |
| 更新 | electron-updater generic provider + 频道文件（install-channel.json） |
| 灰度/埋点 | unify-gray 快照推拉 + 自有埋点（勿上报至阿里端点） |
| 品牌/证书/密钥 | **不复刻**：阿里证书、PHOENIX appKey、accio.com 域名、网关凭证——全部替换为自有资产（合规边界） |

## 10. 已知未知（下一阶段候选）

【未知】gateway-worker 的 HTTP route 全表与鉴权握手；`skill` 工具的技能加载规约；IAB toolbar 的 UI 组件树；weekly/competitor 报表的产出格式；`bash` 工具的沙盒策略。→ 可由 stage-3 任务继续（按需开 `t6+`）。

---

*附：本说明全部事实可溯源到 `results/accio/`（ASAR_TREE.md / asar_index.json / SYMBOL_SCAN.md / extract/ / resources_capture/）与 `results/link`、`results/computer_use` 的本机回执。*
