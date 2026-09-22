import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ElMessage } from 'element-plus'

import { i18n } from '@/i18n'
import Login from '../Login.vue'
import { registerByEmail } from '@/api/auth'

vi.mock('@/api/auth', () => ({
  sendSmsCode: vi.fn(),
  loginByPassword: vi.fn(),
  loginByEmail: vi.fn(),
  loginBySms: vi.fn(),
  registerByPhone: vi.fn(),
  registerByEmail: vi.fn(),
  getProfile: vi.fn()
}))

const passthrough = { template: '<div><slot /></div>' }
const stubs = {
  'el-tabs': passthrough,
  'el-tab-pane': passthrough,
  'el-radio-group': passthrough,
  'el-radio-button': passthrough,
  'el-form': { template: '<form><slot /></form>' },
  'el-form-item': passthrough,
  'el-input': passthrough,
  'el-button': { template: '<button><slot /></button>' },
  'el-checkbox': passthrough
}

function setupState(wrapper) {
  return wrapper.vm.$.setupState
}

function mountLogin() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/login', name: 'login', component: Login, meta: { public: true } },
      { path: '/onboarding', name: 'onboarding', component: { template: '<div />' } },
      { path: '/profile', name: 'profile', component: { template: '<div />' } },
      { path: '/accounts', name: 'accounts', component: { template: '<div />' } },
      { path: '/agent', name: 'agent-overview', component: { template: '<div />' } }
    ]
  })
  const wrapper = mount(Login, {
    global: {
      plugins: [createPinia(), i18n, router],
      stubs
    }
  })
  return { wrapper, router }
}

describe('Login portal switch', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.restoreAllMocks()
  })

  it('links Merchant login to the Agent port', () => {
    vi.stubEnv('VITE_PORTAL_MODE', 'merchant')
    vi.stubEnv('VITE_OTHER_PORTAL_URL', 'http://localhost:1026/login')
    setActivePinia(createPinia())
    const { wrapper } = mountLogin()
    expect(wrapper.get('a.switch-link').attributes('href')).toBe('http://localhost:1026/login')
  })

  it('uses Agent copy when the dedicated Agent portal is running', () => {
    vi.stubEnv('VITE_PORTAL_MODE', 'agent')
    vi.stubEnv('VITE_OTHER_PORTAL_URL', 'http://localhost:1027/login')
    setActivePinia(createPinia())
    const { wrapper } = mountLogin()
    expect(wrapper.text()).toContain('Agent portal')
    expect(wrapper.get('a.switch-link').attributes('href')).toBe('http://localhost:1027/login')
  })
})

describe('Login register', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.restoreAllMocks()
  })

  it('registers a merchant without a created-account toast and goes to onboarding', async () => {
    setActivePinia(createPinia())
    registerByEmail.mockResolvedValue({
      token: 't',
      user: { portal_role: 'merchant', onboarding_status: 'none', email: 'merchant@example.com' }
    })
    const success = vi.spyOn(ElMessage, 'success').mockImplementation(() => {})
    const { wrapper, router } = mountLogin()
    await router.push('/login')
    const replace = vi.spyOn(router, 'replace')
    const state = setupState(wrapper)
    state.mode = 'register'
    state.form.email = 'merchant@example.com'
    state.form.password = 'Pass@123'
    await state.onSubmit()
    await flushPromises()
    const messages = success.mock.calls.map((args) => args[0])
    expect(messages).not.toContain('Merchant account created.')
    expect(messages).not.toContain('Agent account created.')
    expect(replace).toHaveBeenCalledWith({ name: 'onboarding' })
  })

  it('registers an agent without a created-account toast and goes to onboarding', async () => {
    vi.stubEnv('VITE_PORTAL_MODE', 'agent')
    setActivePinia(createPinia())
    registerByEmail.mockResolvedValue({
      token: 't',
      user: { portal_role: 'agent', onboarding_status: 'none', email: 'agent@example.com' }
    })
    const success = vi.spyOn(ElMessage, 'success').mockImplementation(() => {})
    const { wrapper, router } = mountLogin()
    await router.push('/login')
    const replace = vi.spyOn(router, 'replace')
    const state = setupState(wrapper)
    state.mode = 'register'
    state.form.email = 'agent@example.com'
    state.form.password = 'Pass@123'
    await state.onSubmit()
    await flushPromises()
    const messages = success.mock.calls.map((args) => args[0])
    expect(messages).not.toContain('Agent account created.')
    expect(messages).not.toContain('Merchant account created.')
    expect(replace).toHaveBeenCalledWith({ name: 'onboarding' })
  })
})
