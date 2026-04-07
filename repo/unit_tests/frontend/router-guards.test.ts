import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import router from '../../frontend/src/router'
import { useAuthStore } from '../../frontend/src/stores/auth'

describe('router role guards', () => {
  beforeEach(async () => {
    setActivePinia(createPinia())
    sessionStorage.clear()
    localStorage.clear()
    await router.push('/login')
  })

  it('redirects unauthenticated users to login', async () => {
    await router.push('/billing')
    expect(router.currentRoute.value.path).toBe('/login')
  })

  it('blocks resident access to admin route', async () => {
    const auth = useAuthStore()
    sessionStorage.setItem('harborview_token', 'token')
    sessionStorage.setItem('harborview_user', JSON.stringify({
      id: 'resident-id',
      username: 'resident1',
      role: 'resident',
      canary_enabled: false,
    }))
    auth.loadFromStorage()

    await router.push('/admin/users')
    expect(router.currentRoute.value.path).toBe('/')
  })
})
