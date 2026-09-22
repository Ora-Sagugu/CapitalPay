import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { i18n } from '@/i18n'
import FundTransfers from '../FundTransfers.vue'
import { confirmTransfer, getPendingTransfers, getPayoutBanks } from '@/api/orders'

vi.mock('@/api/orders', () => ({
  getPendingTransfers: vi.fn(),
  confirmTransfer: vi.fn(),
  getPayoutBanks: vi.fn()
}))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({
    hasPermission: (code) => code === 'feature:fund_transfers'
  })
}))

const passthrough = { template: '<div><slot /></div>' }
const stubs = {
  PageHeader: passthrough,
  KpiCards: passthrough,
  StatusPill: { props: ['value'], template: '<span>{{ value }}</span>' },
  EmptyState: { props: ['message'], template: '<div class="empty">{{ message }}</div>' },
  'el-select': passthrough,
  'el-option': passthrough,
  'el-input': passthrough,
  'el-button': { template: '<button v-bind="$attrs"><slot /></button>' },
  'el-table': { props: ['data'], template: '<div class="table"><slot /></div>' },
  'el-table-column': { template: '<div></div>' },
  'el-pagination': passthrough,
  'el-dialog': { template: '<div class="dialog"><slot /><slot name="footer" /></div>' },
  'el-checkbox-group': passthrough,
  'el-checkbox': passthrough,
  'el-empty': passthrough,
  'el-tag': passthrough
}

function mountPage() {
  return mount(FundTransfers, { global: { plugins: [i18n], stubs } })
}

describe('ops banking transfers queue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    i18n.global.locale.value = 'en-US'
    getPendingTransfers.mockResolvedValue({
      results: [
        {
          order_no: 'RMT_READY',
          status: 'PAY_RECEIVED',
          agent_payout_request_status: 'none',
          from_currency: 'USD',
          to_currency: 'CNY',
          amount: '100.00'
        }
      ],
      count: 1
    })
    getPayoutBanks.mockResolvedValue({
      amount: '100.00',
      currency: 'USD',
      recommended_bank_code: 'CHEAP',
      recommended_bank_codes: ['CHEAP', 'MID'],
      recommended_split: [
        { bank_code: 'CHEAP', amount: '20.00' },
        { bank_code: 'MID', amount: '80.00' }
      ],
      results: [
        {
          bank_code: 'CHEAP',
          bank_name: 'Cheap Bank',
          sufficient: false,
          partial: true,
          bank_fee_ok: true,
          selectable: true,
          recommended: true,
          balance: '20.00',
          usable_amount: '20.00',
          computed_fee: '0.10'
        },
        {
          bank_code: 'MID',
          bank_name: 'Mid Bank',
          sufficient: true,
          bank_fee_ok: true,
          selectable: true,
          recommended: true,
          balance: '500.00',
          computed_fee: '0.20'
        }
      ]
    })
    confirmTransfer.mockResolvedValue({ status: 'PENDING_SETTLE' })
  })

  it('loads only remittance orders awaiting Confirm transfer', async () => {
    const wrapper = mountPage()
    await flushPromises()
    expect(getPendingTransfers).toHaveBeenCalled()
    expect(wrapper.vm.canConfirmTransfer({
      status: 'PAY_RECEIVED',
      agent_payout_request_status: 'none'
    })).toBe(true)
    expect(wrapper.vm.canConfirmTransfer({
      status: 'PAY_RECEIVED',
      agent_payout_request_status: 'pending'
    })).toBe(false)
    expect(wrapper.vm.rows.map((row) => row.order_no)).toEqual(['RMT_READY'])
  })

  it('drops the instruction after Confirm transfer', async () => {
    getPendingTransfers
      .mockResolvedValueOnce({
        results: [{ order_no: 'RMT_READY', status: 'PAY_RECEIVED', agent_payout_request_status: 'none' }],
        count: 1
      })
      .mockResolvedValueOnce({ results: [], count: 0 })
    const wrapper = mountPage()
    await flushPromises()
    wrapper.vm.payoutOrderNo = 'RMT_READY'
    wrapper.vm.payoutBanks = [
      { bank_code: 'MID', balance: '500.00', sufficient: true, selectable: true }
    ]
    wrapper.vm.payoutMeta.amount = '100.00'
    wrapper.vm.payoutBankCodes = ['MID']
    await wrapper.vm.submitPayout()
    await flushPromises()
    expect(confirmTransfer).toHaveBeenCalledWith('RMT_READY', { bank_code: 'MID' })
    expect(wrapper.vm.rows).toEqual([])
    expect(wrapper.vm.total).toBe(0)
  })

  it('confirms a leftover split across two banks', async () => {
    const wrapper = mountPage()
    await flushPromises()
    wrapper.vm.payoutOrderNo = 'RMT_READY'
    wrapper.vm.payoutBanks = [
      { bank_code: 'CHEAP', balance: '20.00', sufficient: false, selectable: true },
      { bank_code: 'MID', balance: '500.00', sufficient: true, selectable: true }
    ]
    wrapper.vm.payoutMeta.amount = '100.00'
    wrapper.vm.payoutBankCodes = ['CHEAP', 'MID']
    await wrapper.vm.submitPayout()
    await flushPromises()
    expect(confirmTransfer).toHaveBeenCalledWith('RMT_READY', { bank_codes: ['CHEAP', 'MID'] })
  })
})
