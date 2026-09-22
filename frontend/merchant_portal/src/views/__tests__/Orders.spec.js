import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ElMessage, ElMessageBox } from 'element-plus'
import ElementPlus from 'element-plus'

import { i18n } from '@/i18n'
import { useAuthStore } from '@/store/auth'
import Orders from '../Orders.vue'
import { applyRefund, getPaymentHistory, getRemittances } from '@/api/payments'

vi.mock('@/api/payments', () => ({
  getRemittances: vi.fn(),
  getPaymentHistory: vi.fn(),
  getOrderDetail: vi.fn(),
  applyRefund: vi.fn()
}))

vi.mock('@/api/auth', () => ({
  loginByPassword: vi.fn(),
  loginByEmail: vi.fn(),
  loginBySms: vi.fn(),
  registerByPhone: vi.fn(),
  registerByEmail: vi.fn(),
  getProfile: vi.fn()
}))

vi.mock('element-plus', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    ElMessageBox: {
      ...actual.ElMessageBox,
      prompt: vi.fn()
    },
    ElMessage: {
      ...actual.ElMessage,
      success: vi.fn(),
      warning: vi.fn(),
      error: vi.fn()
    }
  }
})

const refundableOrder = {
  order_no: 'RMT_REFUND_OK',
  prn_code: 'PRN001',
  amount: '100.00',
  from_currency: 'USD',
  to_currency: 'CNY',
  status: 'PAY_RECEIVED',
  created_at: '2026-03-20T10:00:00Z'
}

function mountPage() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.token = 'token'
  auth.user = { onboarding_status: 'approved', portal_role: 'merchant' }
  return mount(Orders, {
    global: { plugins: [pinia, i18n, ElementPlus] }
  })
}

describe('merchant orders refund', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    i18n.global.locale.value = 'en-US'
    getRemittances.mockResolvedValue({ results: [refundableOrder], count: 1 })
    getPaymentHistory.mockResolvedValue({ items: [], total: 0 })
    applyRefund.mockResolvedValue({ refund_no: 'R_001', status: 'PENDING_REVIEW', refund_amount: '100.00' })
    ElMessageBox.prompt.mockResolvedValue({ value: 'Goods returned' })
  })

  it('shows a refund action for refundable orders', async () => {
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.text()).toContain('Refund')
    expect(wrapper.find('[data-testid="refund-btn"]').exists()).toBe(true)
  })

  it('submits a refund request with order amount and reason', async () => {
    getRemittances
      .mockResolvedValueOnce({ results: [refundableOrder], count: 1 })
      .mockResolvedValueOnce({
        results: [{ ...refundableOrder, status: 'REFUNDING' }],
        count: 1
      })
    const wrapper = mountPage()
    await flushPromises()
    await wrapper.get('[data-testid="refund-btn"]').trigger('click')
    await flushPromises()
    expect(ElMessageBox.prompt).toHaveBeenCalled()
    expect(applyRefund).toHaveBeenCalledWith({
      order_no: 'RMT_REFUND_OK',
      refund_amount: '100.00',
      reason: 'Goods returned'
    })
    expect(ElMessage.success).toHaveBeenCalled()
    expect(getRemittances).toHaveBeenCalledTimes(2)
  })

  it('hides refund for closed orders', async () => {
    getRemittances.mockResolvedValue({
      results: [{ ...refundableOrder, status: 'CLOSED' }],
      count: 1
    })
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.find('[data-testid="refund-btn"]').exists()).toBe(false)
  })

  it('does not call applyRefund when the prompt is cancelled', async () => {
    ElMessageBox.prompt.mockRejectedValue('cancel')
    const wrapper = mountPage()
    await flushPromises()
    await wrapper.get('[data-testid="refund-btn"]').trigger('click')
    await flushPromises()
    expect(applyRefund).not.toHaveBeenCalled()
  })
})
