import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ListingsView from '@/views/ListingsView.vue'
import { useAuthStore } from '@/stores/auth'

const { getMock, postMock, putMock } = vi.hoisted(() => ({
  getMock: vi.fn(),
  postMock: vi.fn(),
  putMock: vi.fn(),
}))

vi.mock('@/services/api', () => ({
  default: {
    get: getMock,
    post: postMock,
    put: putMock,
  },
}))

describe('listings bulk status API', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getMock.mockReset()
    postMock.mockReset()
    putMock.mockReset()
  })

  it('uses bulk-status endpoint for bulk publish', async () => {
    const auth = useAuthStore()
    sessionStorage.setItem('harborview_token', 'token')
    sessionStorage.setItem('harborview_user', JSON.stringify({
      id: 'admin-id',
      username: 'admin',
      role: 'admin',
      canary_enabled: false,
    }))
    auth.loadFromStorage()

    getMock.mockResolvedValue({
      data: {
        items: [
          { id: 'l1', title: 'A', category: 'garage_sale', status: 'draft', version: 1, media: [] },
          { id: 'l2', title: 'B', category: 'garage_sale', status: 'draft', version: 1, media: [] },
        ],
      },
    })
    postMock.mockResolvedValue({ data: { updated: 2, failed: 0, results: [] } })

    const wrapper = mount(ListingsView)
    await flushPromises()

    const checks = wrapper.findAll('input[type="checkbox"]')
    await checks[0].setValue(true)
    await checks[1].setValue(true)
    await wrapper.find('.btn-promote').trigger('click')
    await flushPromises()

    expect(postMock).toHaveBeenCalledWith('/listings/bulk-status', {
      listing_ids: ['l1', 'l2'],
      status: 'published',
    })
  })
})
