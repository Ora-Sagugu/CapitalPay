import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createRouter, createWebHistory } from 'vue-router'
import ElementPlus from 'element-plus'

import { i18n } from '@/i18n'
import { useAuthStore } from '@/store/auth'
import DefaultLayout from '../DefaultLayout.vue'

vi.mock('@/api/auth', () => ({
  loginByPassword: vi.fn(),
  loginByEmail: vi.fn(),
  loginBySms: vi.fn(),
  registerByPhone: vi.fn(),
  registerByEmail: vi.fn(),
  getProfile: vi.fn().mockResolvedValue({
    onboarding_status: 'approved',
    portal_role: 'agent',
    email: 'GraceNyambura@gmail.com',
    real_name: 'Grace Nyambura'
  })
}))

function mountAgentLayout() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.token = 'token'
  auth.user = {
    onboarding_status: 'approved',
    portal_role: 'agent',
    email: 'GraceNyambura@gmail.com',
    real_name: 'Grace Nyambura'
  }
  const router = createRouter({
    history: createWebHistory(),
    routes: [
      {
        path: '/',
        component: DefaultLayout,
        children: [
          { path: 'agent', name: 'agent-overview', component: { template: '<div>overview</div>' } },
          { path: 'agent/account', name: 'agent-account', component: { template: '<div>account</div>' } },
          { path: 'bank', name: 'bank', component: { template: '<div>bank</div>' } },
          { path: 'wallet', name: 'wallet', component: { template: '<div>wallet</div>' } },
          { path: 'cards', name: 'cards', component: { template: '<div>cards</div>' } }
        ]
      }
    ]
  })
  router.push('/agent')
  return mount(DefaultLayout, {
    global: {
      plugins: [pinia, i18n, ElementPlus, router],
      stubs: {
        RouterView: true
      }
    }
  })
}

describe('agent navigation', () => {
  beforeEach(() => {
    localStorage.clear()
    i18n.global.locale.value = 'en-US'
  })

  it('hides Bank and Wallet for approved agents', async () => {
    const wrapper = mountAgentLayout()
    await wrapper.vm.$router.isReady()
    const text = wrapper.text()
    expect(text).toContain('Account')
    expect(text).toContain('Merchant')
    expect(text).toContain('Customers')
    expect(text).not.toContain('KYC')
    expect(text).not.toContain('Earnings')
    expect(text).not.toContain('Transfers')
    expect(text).not.toContain('Bank')
    expect(text).not.toContain('Wallet')
    expect(text).not.toContain('Cards')
    expect(wrapper.find('.el-menu-item[index="/bank"]').exists()).toBe(false)
    expect(wrapper.find('.el-menu-item[index="/wallet"]').exists()).toBe(false)
    expect(wrapper.find('.el-menu-item[index="/merchant"]').exists()).toBe(false)
    const customerItem = wrapper.findAll('.el-menu-item').find((node) => node.text().includes('Customers'))
    expect(customerItem).toBeTruthy()
    expect(wrapper.find('.el-menu-item[index="/agent/kyc"]').exists()).toBe(false)
    expect(wrapper.find('.el-menu-item[index="/agent/earnings"]').exists()).toBe(false)
    expect(wrapper.find('.el-menu-item[index="/agent/transfers"]').exists()).toBe(false)
  })
})
