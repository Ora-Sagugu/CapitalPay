import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ElMessage, ElMessageBox } from 'element-plus'
import ElementPlus from 'element-plus'

import { i18n } from '@/i18n'
import { useAuthStore } from '@/store/auth'
import Customers from '../Customers.vue'
import { deleteCustomer, getCustomers } from '@/api/payments'

const { push } = vi.hoisted(() => ({ push: vi.fn() }))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push })
}))

vi.mock('@/api/payments', () => ({
  getCustomers: vi.fn(),
  createCustomer: vi.fn(),
  updateCustomer: vi.fn(),
  deleteCustomer: vi.fn()
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
      confirm: vi.fn()
    },
    ElMessage: {
      ...actual.ElMessage,
      success: vi.fn(),
      warning: vi.fn(),
      error: vi.fn()
    }
  }
})

const customer = {
  id: 'c-1',
  customer_no: 'AC001',
  legal_name: 'Buyer Co',
  contact_email: 'buyer@example.com',
  kyc_status: 'approved',
  remittance_eligibility: { eligible: true, blockers: [] }
}

function mountPage() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.token = 'token'
  auth.user = { onboarding_status: 'approved', portal_role: 'merchant' }
  return mount(Customers, {
    global: { plugins: [pinia, i18n, ElementPlus] }
  })
}

describe('merchant customers', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    i18n.global.locale.value = 'en-US'
    getCustomers.mockResolvedValue({ items: [customer] })
    deleteCustomer.mockResolvedValue()
    ElMessageBox.confirm.mockResolvedValue('confirm')
  })

  it('lists customers with remit and delete actions', async () => {
    const wrapper = mountPage()
    await flushPromises()
    expect(getCustomers).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('Buyer Co')
    expect(wrapper.text()).toContain('Remit')
    expect(wrapper.text()).toContain('Delete')
  })

  it('opens remittance with the selected customer', async () => {
    const wrapper = mountPage()
    await flushPromises()
    await wrapper.get('[data-testid="remit-btn"]').trigger('click')
    expect(push).toHaveBeenCalledWith({ name: 'remittance', query: { customer_id: 'c-1' } })
  })

  it('deletes a customer after confirmation', async () => {
    getCustomers
      .mockResolvedValueOnce({ items: [customer] })
      .mockResolvedValueOnce({ items: [] })
    const wrapper = mountPage()
    await flushPromises()
    await wrapper.get('[data-testid="delete-btn"]').trigger('click')
    await flushPromises()
    expect(ElMessageBox.confirm).toHaveBeenCalled()
    expect(deleteCustomer).toHaveBeenCalledWith('c-1')
    expect(ElMessage.success).toHaveBeenCalled()
    expect(getCustomers).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).not.toContain('Buyer Co')
  })

  it('does not delete when confirmation is cancelled', async () => {
    ElMessageBox.confirm.mockRejectedValue('cancel')
    const wrapper = mountPage()
    await flushPromises()
    await wrapper.get('[data-testid="delete-btn"]').trigger('click')
    await flushPromises()
    expect(deleteCustomer).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Buyer Co')
  })
})
