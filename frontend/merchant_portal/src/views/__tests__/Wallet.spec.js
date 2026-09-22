import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it } from 'vitest'
import ElementPlus from 'element-plus'

import { i18n } from '@/i18n'
import Wallet from '../Wallet.vue'

function mountPage() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return mount(Wallet, {
    global: { plugins: [pinia, i18n, ElementPlus] }
  })
}

describe('customer wallet page', () => {
  beforeEach(() => {
    i18n.global.locale.value = 'en-US'
  })

  it('is a read-only record of the wallet system with no funding actions', () => {
    const wrapper = mountPage()
    expect(wrapper.text()).toContain('recorded from the wallet system')
    expect(wrapper.text()).toContain('not performed here')
    expect(wrapper.get('[data-testid="wallet-empty"]').text()).toContain('No wallet balances have been recorded yet')
    expect(wrapper.get('[data-testid="wallet-tx-empty"]').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('Reset demo')
    expect(wrapper.find('.actions-card').exists()).toBe(false)
    expect(wrapper.find('form').exists()).toBe(false)
  })
})
