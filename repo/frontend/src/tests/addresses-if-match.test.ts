import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import AddressesView from '@/views/AddressesView.vue'

const { getMock, putMock, postMock, deleteMock } = vi.hoisted(() => ({
  getMock: vi.fn(),
  putMock: vi.fn(),
  postMock: vi.fn(),
  deleteMock: vi.fn(),
}))

vi.mock('@/services/api', () => ({
  default: {
    get: getMock,
    put: putMock,
    post: postMock,
    delete: deleteMock,
  },
}))

describe('addresses optimistic locking', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getMock.mockReset()
    putMock.mockReset()
    postMock.mockReset()
    deleteMock.mockReset()
  })

  it('sends If-Match header when updating address', async () => {
    getMock.mockResolvedValueOnce({
      data: [{
        id: 'addr-1',
        version: 3,
        address_type: 'shipping',
        line1: '123 Main',
        line2: '',
        city: 'Springfield',
        state: 'CA',
        zip_code: '90210',
      }],
    })
    putMock.mockResolvedValueOnce({ data: {} })
    getMock.mockResolvedValueOnce({ data: [] })

    const wrapper = mount(AddressesView)
    await flushPromises()

    await wrapper.find('.btn-secondary').trigger('click')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(putMock).toHaveBeenCalledTimes(1)
    const [, , config] = putMock.mock.calls[0]
    expect(config.headers['If-Match']).toBe('3')
  })
})
