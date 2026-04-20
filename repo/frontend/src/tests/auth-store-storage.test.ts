import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'

const {
  apiPostMock,
  setupEncryptionMock,
  teardownEncryptionMock,
  clearAllMock,
} = vi.hoisted(() => ({
  apiPostMock: vi.fn(),
  setupEncryptionMock: vi.fn(),
  teardownEncryptionMock: vi.fn(),
  clearAllMock: vi.fn(),
}))

vi.mock('@/services/api', () => ({
  default: {
    post: apiPostMock,
  },
}))

vi.mock('@/stores/offline', () => ({
  useOfflineStore: () => ({
    setupEncryption: setupEncryptionMock,
    teardownEncryption: teardownEncryptionMock,
    clearAll: clearAllMock,
  }),
}))

describe('auth store storage and role helpers', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    sessionStorage.clear()
    localStorage.clear()
    apiPostMock.mockReset()
    setupEncryptionMock.mockReset()
    teardownEncryptionMock.mockReset()
    clearAllMock.mockReset()
  })

  it('loadFromStorage migrates local auth data into sessionStorage', () => {
    const storedUser = {
      id: 'u-1',
      username: 'resident1',
      role: 'resident',
      canary_enabled: false,
    }
    localStorage.setItem('harborview_token', 'token-123')
    localStorage.setItem('harborview_refresh', 'refresh-456')
    localStorage.setItem('harborview_user', JSON.stringify(storedUser))

    const auth = useAuthStore()
    auth.loadFromStorage()

    expect(auth.token).toBe('token-123')
    expect(auth.refreshToken).toBe('refresh-456')
    expect(auth.user?.username).toBe('resident1')
    expect(sessionStorage.getItem('harborview_token')).toBe('token-123')
    expect(sessionStorage.getItem('harborview_refresh')).toBe('refresh-456')
    expect(sessionStorage.getItem('harborview_user')).toBe(JSON.stringify(storedUser))
    expect(localStorage.getItem('harborview_token')).toBeNull()
    expect(localStorage.getItem('harborview_refresh')).toBeNull()
    expect(localStorage.getItem('harborview_user')).toBeNull()
  })

  it('hasRole reflects current authenticated user role', () => {
    const auth = useAuthStore()
    auth.user = {
      id: 'u-2',
      username: 'admin',
      role: 'admin',
      canary_enabled: true,
    }

    expect(auth.hasRole('admin', 'resident')).toBe(true)
    expect(auth.hasRole('resident', 'accounting_clerk')).toBe(false)
  })
})
