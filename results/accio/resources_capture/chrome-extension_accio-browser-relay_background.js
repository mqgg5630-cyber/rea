/**
 * Accio Browser Relay — MV3 Service Worker entry point.
 *
 * Thin orchestration layer: wires up relay, tabs, and CDP modules,
 * then registers Chrome event listeners.
 *
 * CDP channel            → lib/cdp/            (WebSocket relay, tab management, CDP dispatch)
 * Content Script channel → lib/content_script/  (DOM interaction via chrome.scripting)
 */

import {
  TabManager,
  createDispatcher,
  createTabCommandScheduler,
  initRelay,
  trySendToRelay,
  isRelayConnected,
  isRelayEnabled,
  isReconnecting,
  getRelayConnectionSnapshot,
  toggle,
  connectAndAttach,
  reconnectNow,
  bootstrapRelayConnection,
  initFromStorage,
  setRelayEnabled,
  getLogBuffer,
  ensureKeepAliveAlarm,
  handleConnectionAlarm,
  hasPendingReconnectAlarm,
} from './lib/cdp/index.js'
import { SETTINGS_KEYS, getSetting } from './lib/constants.js'
import { awaitWithDeadline } from './lib/cdp/commands/deadline.js'
import { createLogger, setDebug } from './lib/logger.js'
import { initExternalBridge } from './lib/external/bridge.js'
import { initDownloadTracker } from './lib/downloads/tracker.js'
import { registerTabDiscoveryListeners } from './lib/cdp/tabs/discovery-listeners.js'
import {
  clearAgentClaimFaviconCache,
  isAgentClaimFavicon,
} from './lib/page-tab-indicator.js'

setDebug(true)

const log = createLogger('bg')
const ACCIO_PAGE_URLS = [
  'https://www.accio.com/*',
  'https://pre-www.accio.com/*',
  'https://local.accio.com/*',
  // aimode 内嵌在 alibaba.com 宿主页中，宿主域名不可枚举，故用通配兜底。
  // 内嵌场景下宿主 tab 是用户已打开的页面，扩展更新时必须补注入 content script，
  // 否则页面拿不到 extensionId、无法建立 external 连接。通配覆盖原
  // aimode.alibaba.com / pre-aimode / local.aimode 三条精确 host（已并入通配）。
  'https://*.alibaba.com/*',
]

// ── Wire modules together ──

const context = createBackgroundContext()

initializeRelay(context)

// ── External bridge (App layer via chrome.runtime.connect) ──
initializeExternalBridge(context)

// ── Chrome event listeners ──

registerTabLifecycleListeners(context)

// Reconcile persisted state whenever Chrome creates a new MV3 worker instance.
void bootstrapRelayConnection()

registerAlarmListeners(context)
registerRuntimeLifecycleListeners()
registerRuntimeMessageListeners(context)

// ── Helpers ──

function createBackgroundContext() {
  const scheduler = createTabCommandScheduler()
  const mgr = new TabManager(trySendToRelay, scheduler)
  const handleCdp = createDispatcher(mgr, scheduler)
  const tabsReady = (async () => {
    const restored = await mgr.loadTabs()
    if (!restored) return false
    try {
      await mgr.reconcileTabs()
      return true
    } catch (e) {
      log.warn('reconcileTabs failed:', e)
      return false
    }
  })()

  // 下载追踪：SW 顶层同步注册（MV3 事件唤醒约束）；事件仅供 relay server 消费。
  // deny-by-default —— 只有 relay arm 了归属窗口才上报，见 lib/downloads/tracker.js。
  const { resyncDownloads } = initDownloadTracker(trySendToRelay)
  const tabsReadyBarrier = { current: tabsReady }

  return { mgr, handleCdp, tabsReady, tabsReadyBarrier, resyncDownloads }
}

function initializeRelay({ mgr, handleCdp, tabsReady, tabsReadyBarrier, resyncDownloads }) {
  initRelay({
    async onMessage(msg, commandContext) {
      const readiness = tabsReadyBarrier.current
      const transportGeneration = getRelayConnectionSnapshot().transportGeneration
      if (commandContext) {
        await awaitWithDeadline(commandContext, 'background.tabsReady', () => readiness)
      } else {
        await readiness
      }
      const relay = getRelayConnectionSnapshot()
      if (
        !relay.connected ||
        relay.transportGeneration !== transportGeneration ||
        readiness !== tabsReadyBarrier.current
      ) {
        throw new Error('Relay connection changed while waiting for tab resync')
      }
      return handleCdp(msg, commandContext)
    },
    async onShutdown(reason) {
      log.info('onShutdown callback:', reason)
      if (reason === 'connectionLost') {
        log.info('onShutdown: connectionLost — preserving tab/debugger state for reconnect')
        mgr.stopSessionIndicators()
        return
      }
      let dissolveGroup = false
      if (reason === 'disabled') {
        const shouldClose = await getSetting(SETTINGS_KEYS.CLOSE_GROUP_ON_DISABLE)
        log.info('onShutdown: closeGroupOnDisable setting =', shouldClose)
        if (shouldClose) {
          log.info('onShutdown: dissolving agent tab group per user setting')
          dissolveGroup = true
        }
      }
      await mgr.shutdown({ dissolveGroup })
      log.info('onShutdown: done, dissolveGroup =', dissolveGroup)
    },
    onConnected() {
      log.info('onConnected callback: discovering tabs (lazy attach)')
      const epoch = mgr.beginTabsResync()
      const transportGeneration = getRelayConnectionSnapshot().transportGeneration
      const resync = (async () => {
        const tabsStateReady = await tabsReady
        const isCurrent = () => {
          const relay = getRelayConnectionSnapshot()
          return (
            relay.connected &&
            relay.transportGeneration === transportGeneration &&
            mgr.isTabsResyncCurrent(epoch)
          )
        }
        if (!isCurrent()) return
        mgr.startSessionIndicators()
        if (!(await mgr.discoverAll(isCurrent))) return
        if (tabsStateReady) mgr.resyncAttachedTabs({ epoch, authoritative: true })
        void resyncDownloads()
      })()
      tabsReadyBarrier.current = resync.catch((error) => {
        log.warn('onConnected tab resync failed:', error)
      })
      return tabsReadyBarrier.current
    },
    installDebuggerListeners() {
      chrome.debugger.onEvent.addListener((source, method, params) => {
        mgr.onDebuggerEvent(source, method, params)
      })
      chrome.debugger.onDetach.addListener((source, reason) => {
        log.info('chrome.debugger.onDetach:', source.tabId, reason)
        void mgr
          .onDebuggerDetach(source, reason)
          .catch((error) => log.warn('chrome.debugger.onDetach handling failed:', error))
      })
    },
  })
}

function initializeExternalBridge({ mgr, handleCdp, tabsReadyBarrier }) {
  initExternalBridge(mgr, handleCdp, async () => {
    while (true) {
      const readiness = tabsReadyBarrier.current
      await readiness
      if (readiness === tabsReadyBarrier.current) return
    }
  })
}

async function handleToggle() {
  log.info('handleToggle: begin')
  await toggle()
  log.info('handleToggle: done')
}

function registerTabLifecycleListeners({ mgr, tabsReady }) {
  chrome.tabs.onActivated.addListener(() => {
    if (isRelayConnected() || isReconnecting()) return
    void (async () => {
      if (!(await isRelayEnabled()) || isRelayConnected() || isReconnecting()) return
      void connectAndAttach()
    })()
  })

  registerTabDiscoveryListeners(chrome.tabs, mgr, isRelayConnected, {
    schedule: (task) => void tabsReady.then(task),
    onUpdated: (tabId, changeInfo) => {
      const pageChanged = changeInfo.url !== undefined
      const faviconChanged =
        changeInfo.favIconUrl !== undefined && !isAgentClaimFavicon(changeInfo.favIconUrl)
      if (pageChanged || faviconChanged) clearAgentClaimFaviconCache(tabId)
      return pageChanged || changeInfo.status === 'complete' || faviconChanged
    },
  })

  chrome.webNavigation.onCreatedNavigationTarget.addListener((details) => {
    void tabsReady.then(() => {
      if (!mgr.has(details.sourceTabId)) return
      mgr.recordNavigationTarget(details.tabId, details.sourceTabId)
    })
  })

  chrome.tabs.onRemoved.addListener((tabId) => {
    clearAgentClaimFaviconCache(tabId)
    void tabsReady.then(() => {
      mgr.removeNavigationTarget(tabId)
      if (!mgr.has(tabId)) return
      // Chrome fires this for the relay's own removes too; the manager's
      // relay-requested mark overrides 'external' in that case, so only a close
      // nobody here asked for reaches the relay as external.
      void mgr.close(tabId, 'tab-closed', { closedBy: 'external' })
    })
  })
}

function registerAlarmListeners({ mgr }) {
  chrome.alarms.onAlarm.addListener((alarm) => {
    // Let connection module handle reconnect / disconnect-notify alarms
    if (handleConnectionAlarm(alarm.name)) return

    // Let session indicators handle idle-check alarm
    if (mgr.handleIndicatorAlarm(alarm.name)) return

    if (alarm.name !== 'relayKeepAlive') return

    if (isRelayConnected()) {
      trySendToRelay({ method: 'ping' })
      return
    }
    // SW may have restarted — in-memory state is DISABLED but storage says enabled.
    // Keep-alive is only a watchdog: it runs on the same 30s period as the
    // reconnect alarm, so bypassing a pending one would just double up attempts.
    void (async () => {
      await initFromStorage()
      if (await isRelayEnabled()) {
        if (isReconnecting() || await hasPendingReconnectAlarm()) return
        log.info('alarm: relay enabled but disconnected, attempting reconnect')
        await reconnectNow()
      }
    })().catch((err) => {
      log.warn('alarm: relay keepAlive reconnect check failed:', err)
    })
  })
}

function registerRuntimeLifecycleListeners() {
  chrome.runtime.onStartup.addListener(() => {
    void (async () => {
      await initFromStorage()
      if (!(await isRelayEnabled())) return
      console.info('[accio-relay] browser started with relay enabled, attempting connection')
      await connectAndAttach()
    })()
  })

  chrome.runtime.onInstalled.addListener((details) => {
    void (async () => {
      if (details.reason === 'install') {
        await setRelayEnabled(true)
        void chrome.runtime.openOptionsPage()
      }
      // 安装/更新时向已打开的 accio 页面补注入新版 content script，
      // 不刷新页面，用户状态保留；新 CS 会通过 window._accioCSCleanup 清理旧实例的 listener。
      if (details.reason === 'install' || details.reason === 'update') {
        await injectContentScriptIntoAccioPages()
      }
      if (!(await isRelayEnabled())) {
        log.info('onInstalled:', details.reason, '— relay disabled, skip connection')
        return
      }
      await ensureKeepAliveAlarm()
      log.info('onInstalled:', details.reason, '— attempting connection')
      await connectAndAttach()
    })()
  })
}

function registerRuntimeMessageListeners({ mgr }) {
  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg?.type === 'getRelayStatus') {
      chrome.tabs.query({}, (tabs) => {
        const relay = getRelayConnectionSnapshot()
        sendResponse({
          state: relay.state,
          connected: relay.connected,
          active: relay.active,
          reconnecting: relay.reconnecting,
          transportOpen: relay.transportOpen,
          handshakeReady: relay.handshakeReady,
          tabCount: tabs.length,
          totalTabs: tabs.length,
          attachedTabs: mgr.size,
          agentTabs: mgr.agentTabCount,
          retainedTabs: mgr.retainedTabCount,
        })
      })
      return true
    }
    if (msg?.type === 'toggleRelay') {
      handleToggle()
        .then(() => {
          const relay = getRelayConnectionSnapshot()
          try { sendResponse({ state: relay.state }) } catch { /* channel closed */ }
        })
        .catch((e) => {
          log.error('handleToggle failed:', e)
          const relay = getRelayConnectionSnapshot()
          try { sendResponse({ state: relay.state, error: e?.message }) } catch { /* channel closed */ }
        })
      return true
    }
    if (msg?.type === 'getTabList') {
      sendResponse({ tabs: mgr.listTabSnapshots() })
      return false
    }
    if (msg?.type === 'openInstallGuide') {
      const lang = typeof msg.lang === 'string' && msg.lang ? msg.lang : 'en'
      const url = chrome.runtime.getURL(`pages/install-extension.html?lang=${encodeURIComponent(lang)}`)
      chrome.tabs.create({ url })
      sendResponse({ ok: true })
      return false
    }
    if (msg?.type === 'getLogs') {
      sendResponse({ logs: getLogBuffer(msg.limit || 100) })
      return false
    }
  })
}

async function injectContentScriptIntoAccioPages() {
  const tabs = await chrome.tabs.query({ url: ACCIO_PAGE_URLS })
  for (const tab of tabs) {
    if (!tab.id) continue
    // 先注入新 CS（清理旧孤儿 listener），再通知 web 侧自动 recheck
    chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ['content-script.js'],
    }).then(() => {
      chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: () => window.postMessage({ type: 'accio.extension.updated' }, window.location.origin),
      }).catch(() => {})
    }).catch(() => {})
  }
}
