import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ListingsView from '../../frontend/src/views/ListingsView.vue'
import { useAuthStore } from '../../frontend/src/stores/auth'

const getMock = vi.fn()
const postMock = vi.fn()
const putMock = vi.fn()

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
    auth.token = 'token' as any
    auth.user = {
      id: 'admin-id',
      username: 'admin',
      role: 'admin',
      canary_enabled: false,
    } as any

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
