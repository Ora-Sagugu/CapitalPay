import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  defaultHomePath,
  defaultLoginRouteName,
  getPortalMode,
  isAgentApp,
  otherPortalUrl
} from './portal'

describe('portal mode', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it('defaults to merchant and the merchant home path', () => {
    vi.stubEnv('VITE_PORTAL_MODE', '')
    vi.stubEnv('VITE_OTHER_PORTAL_URL', '')
    expect(getPortalMode()).toBe('merchant')
    expect(isAgentApp()).toBe(false)
    expect(defaultHomePath()).toBe('/overview')
    expect(defaultLoginRouteName()).toBe('login')
    expect(otherPortalUrl()).toBe('')
  })

  it('treats agent mode as a dedicated portal on its own port', () => {
    vi.stubEnv('VITE_PORTAL_MODE', 'agent')
    vi.stubEnv('VITE_OTHER_PORTAL_URL', 'http://localhost:1027/login')
    expect(getPortalMode()).toBe('agent')
    expect(isAgentApp()).toBe(true)
    expect(defaultHomePath()).toBe('/agent')
    expect(defaultLoginRouteName()).toBe('login')
    expect(otherPortalUrl()).toBe('http://localhost:1027/login')
  })
})
