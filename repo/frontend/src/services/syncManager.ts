import { ref, onMounted, onUnmounted } from 'vue'
import api from '@/services/api'
import { processRetryQueue, setConflictHandler, type ConflictEvent } from '@/services/retryQueue'
import { getQueueLength } from '@/services/offlineCache'

const PING_INTERVAL_MS = 15000

export function useSyncManager() {
  const isOnline = ref(navigator.onLine)
  const isSyncing = ref(false)
  const pendingCount = ref(0)
  const activeConflict = ref<ConflictEvent | null>(null)
  let pingTimer: ReturnType<typeof setInterval> | null = null

  // Register conflict handler
  setConflictHandler((event: ConflictEvent) => {
    activeConflict.value = event
  })

  async function checkHealth(): Promise<boolean> {
    try {
      await api.get('/health', { timeout: 5000 })
      return true
    } catch {
      return false
    }
  }

  async function updatePendingCount() {
    try {
      pendingCount.value = await getQueueLength()
    } catch {
      pendingCount.value = 0
    }
  }

  async function handleReconnect() {
    if (isSyncing.value) return
    isSyncing.value = true
    try {
      const result = await processRetryQueue()
      console.log(`[SyncManager] Replay result: ${result.processed} processed, ${result.failed} failed, conflicted=${result.conflicted}`)
    } finally {
      isSyncing.value = false
      await updatePendingCount()
    }
  }

  function onOnline() {
    const wasOffline = !isOnline.value
    isOnline.value = true
    if (wasOffline) handleReconnect()
  }

  function onOffline() {
    isOnline.value = false
  }

  async function periodicPing() {
    const healthy = await checkHealth()
    const wasOffline = !isOnline.value
    isOnline.value = healthy
    if (healthy && wasOffline) handleReconnect()
    await updatePendingCount()
  }

  function resolveConflict() {
    activeConflict.value = null
    // After resolution, continue processing the queue
    handleReconnect()
  }

  function start() {
    window.addEventListener('online', onOnline)
    window.addEventListener('offline', onOffline)
    pingTimer = setInterval(periodicPing, PING_INTERVAL_MS)
    updatePendingCount()
  }

  function stop() {
    window.removeEventListener('online', onOnline)
    window.removeEventListener('offline', onOffline)
    if (pingTimer) { clearInterval(pingTimer); pingTimer = null }
  }

  onMounted(start)
  onUnmounted(stop)

  return {
    isOnline,
    isSyncing,
    pendingCount,
    activeConflict,
    checkHealth,
    triggerSync: handleReconnect,
    resolveConflict,
  }
}
