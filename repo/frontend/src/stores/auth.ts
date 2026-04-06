import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/services/api'
import { useOfflineStore } from '@/stores/offline'

interface AuthUser {
  id: string
  username: string
  role: string
  canary_enabled: boolean
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('harborview_token'))
  const refreshToken = ref<string | null>(localStorage.getItem('harborview_refresh'))
  const user = ref<AuthUser | null>(JSON.parse(localStorage.getItem('harborview_user') || 'null'))
  const isAuthenticated = computed(() => !!token.value)

  async function login(username: string, password: string): Promise<void> {
    const resp = await api.post('/auth/login', { username, password })
    token.value = resp.data.access_token
    refreshToken.value = resp.data.refresh_token
    user.value = resp.data.user
    localStorage.setItem('harborview_token', resp.data.access_token)
    localStorage.setItem('harborview_refresh', resp.data.refresh_token)
    localStorage.setItem('harborview_user', JSON.stringify(resp.data.user))
    // Initialize offline encryption
    const offlineStore = useOfflineStore()
    await offlineStore.setupEncryption(password)
    // Store derived key (not raw password) in sessionStorage for reload recovery
    const { getExportedKey } = await import('@/services/offlineCache')
    const derivedKey = await getExportedKey()
    if (derivedKey) {
      sessionStorage.setItem('harborview_offline_dk', derivedKey)
    }
  }

  function logout() {
    token.value = null
    refreshToken.value = null
    user.value = null
    localStorage.removeItem('harborview_token')
    localStorage.removeItem('harborview_refresh')
    localStorage.removeItem('harborview_user')
    sessionStorage.removeItem('harborview_offline_dk')
    const offlineStore = useOfflineStore()
    offlineStore.teardownEncryption()
    offlineStore.clearAll()
  }

  function loadFromStorage() {
    token.value = localStorage.getItem('harborview_token')
    refreshToken.value = localStorage.getItem('harborview_refresh')
    const stored = localStorage.getItem('harborview_user')
    user.value = stored ? JSON.parse(stored) : null
    // Restore offline encryption from derived key (not raw password)
    const derivedKey = sessionStorage.getItem('harborview_offline_dk')
    if (derivedKey && token.value) {
      import('@/services/offlineCache').then(({ importKey }) => importKey(derivedKey))
    }
  }

  function hasRole(...roles: string[]): boolean {
    return !!user.value && roles.includes(user.value.role)
  }

  return { token, refreshToken, user, isAuthenticated, login, logout, loadFromStorage, hasRole }
})
