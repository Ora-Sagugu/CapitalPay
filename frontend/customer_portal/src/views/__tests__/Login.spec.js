import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { i18n } from '@/i18n'
import Login from '../Login.vue'

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

function mountLogin() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/login', name: 'login', component: Login, meta: { public: true } }]
  })
  return mount(Login, {
    global: {
      plugins: [createPinia(), i18n, router],
      stubs
    }
  })
}

describe('Login portal switch', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it('links Customer login to the Agent port', () => {
    vi.stubEnv('VITE_PORTAL_MODE', 'customer')
    vi.stubEnv('VITE_OTHER_PORTAL_URL', 'http://localhost:1026/login')
    setActivePinia(createPinia())
    const wrapper = mountLogin()
    expect(wrapper.get('a.switch-link').attributes('href')).toBe('http://localhost:1026/login')
  })

  it('uses Agent copy when the dedicated Agent portal is running', () => {
    vi.stubEnv('VITE_PORTAL_MODE', 'agent')
    vi.stubEnv('VITE_OTHER_PORTAL_URL', 'http://localhost:1027/login')
    setActivePinia(createPinia())
    const wrapper = mountLogin()
    expect(wrapper.text()).toContain('Agent portal')
    expect(wrapper.get('a.switch-link').attributes('href')).toBe('http://localhost:1027/login')
  })
})
