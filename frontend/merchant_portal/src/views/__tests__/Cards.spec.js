import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import ElementPlus from 'element-plus'

import { i18n } from '@/i18n'
import { canonicalType, canonicalRefundKind, CARD_EVENT_TYPE, CARD_FAMILY, CARD_REFUND_KIND, eventDirection, normalizeCardEvent } from '@/data/cardPlatform'
import {
  exhibitionCardInstruments,
  exhibitionCards,
  exhibitionCardTxns
} from '@/data/exhibitionFunding'
import { useFundingStore } from '@/store/funding'
import Cards from '../Cards.vue'

function mountPage() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return mount(Cards, {
    attachTo: document.body,
    global: { plugins: [pinia, i18n, ElementPlus] }
  })
}

describe('customer cards funding page', () => {
  beforeEach(() => {
    i18n.global.locale.value = 'en-US'
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('maps unknown provider types without dropping the raw label', () => {
    expect(canonicalType('payment_captured')).toBe(CARD_EVENT_TYPE.CAPTURED)
    expect(canonicalType('charge.dispute.created')).toBe(CARD_EVENT_TYPE.FIRST_CHARGEBACK)
    expect(canonicalType('CHARGEBACK_OPENED')).toBe(CARD_EVENT_TYPE.FIRST_CHARGEBACK)
    expect(canonicalType('SECOND_CHARGEBACK')).toBe(CARD_EVENT_TYPE.SECOND_CHARGEBACK)
    expect(canonicalType('pre_arbitration')).toBe(CARD_EVENT_TYPE.SECOND_CHARGEBACK)
    expect(canonicalType('second.presentment')).toBe(CARD_EVENT_TYPE.REPRESENTMENT)
    expect(canonicalType('first.presentment')).toBe(CARD_EVENT_TYPE.PRESENTMENT)
    expect(canonicalType('arbitration.opened')).toBe(CARD_EVENT_TYPE.ARBITRATION)
    expect(canonicalType('weird.psp.event')).toBe(CARD_EVENT_TYPE.UNKNOWN)
  })

  it('distinguishes money-only refunds from refunds with goods return', () => {
    expect(canonicalRefundKind({ refund_kind: 'money_only' }, CARD_FAMILY.REFUND)).toBe(CARD_REFUND_KIND.MONEY_ONLY)
    expect(canonicalRefundKind({ goods_return: true }, CARD_FAMILY.REFUND)).toBe(CARD_REFUND_KIND.WITH_GOODS)
    expect(canonicalRefundKind({ refund_kind: 'with_return' }, CARD_FAMILY.REFUND)).toBe(CARD_REFUND_KIND.WITH_GOODS)
    expect(canonicalRefundKind({}, CARD_FAMILY.REFUND)).toBe(CARD_REFUND_KIND.MONEY_ONLY)
    expect(canonicalRefundKind({ refund_kind: 'WITH_GOODS' }, CARD_FAMILY.CHECKOUT)).toBeNull()
    expect(normalizeCardEvent({ type: 'REFUND_SUCCEEDED', refund_kind: 'WITH_GOODS' }).refund_kind).toBe(
      CARD_REFUND_KIND.WITH_GOODS
    )
  })

  it('shows an empty record view until the card platform syncs', () => {
    const wrapper = mountPage()
    expect(wrapper.text()).toContain('Card-platform balances and events')
    expect(wrapper.text()).toContain('not initiated here')
    expect(wrapper.get('[data-testid="cards-empty"]').text()).toContain('No card balances have been recorded yet')
    expect(wrapper.get('[data-testid="card-tx-empty"]').text()).toContain('No card activity yet')
    expect(wrapper.find('[data-testid="card-kpis"]').exists()).toBe(false)
  })

  it('does not offer acquiring actions', () => {
    const wrapper = mountPage()
    const buttonText = wrapper.findAll('button').map((node) => node.text()).join(' | ')
    expect(buttonText).not.toMatch(/Capture|Represent|Accept chargeback|Authorize/)
    expect(wrapper.find('form').exists()).toBe(false)
  })

  it('renders checkout, refund and chargeback events with balance buckets', async () => {
    const wrapper = mountPage()
    const funding = useFundingStore()
    funding.cards = exhibitionCards()
    funding.cardTxns = exhibitionCardTxns()
    funding.cardInstruments = exhibitionCardInstruments()
    await flushPromises()
    await nextTick()

    const balances = wrapper.get('[data-testid="card-balances"]').text()
    expect(balances).toContain('Available')
    expect(balances).toContain('Dispute hold')
    expect(balances).toContain('9,400.00')

    const kpis = wrapper.get('[data-testid="card-kpis"]').text()
    expect(kpis).toContain('Open checkouts')
    expect(kpis).toContain('Refunds in progress')
    expect(kpis).toContain('Open chargebacks')

    const body = wrapper.get('[data-testid="card-events"]').text()
    expect(body).toContain('Checkout')
    expect(body).toContain('Refund · Money only')
    expect(body).toContain('Refund · Money + goods return')
    expect(body).toContain('Chargeback')
    expect(body).toContain('Captured')
    expect(body).toContain('PAY-LILY-CHK-001')
    expect(wrapper.text()).toContain('Visa ••4242')
    expect(body).not.toContain('Funding')
    expect(body).not.toContain('Other')
    expect(body).not.toContain('Fee')
    expect(body).not.toContain('Transfer out')
    expect(body).not.toContain('Top up')
    expect(body).not.toContain('Freeze')

    const buttonText = wrapper.findAll('button').map((node) => node.text()).join(' | ')
    expect(buttonText).not.toMatch(/Capture|Represent|Accept chargeback/)
  })

  it('filters the activity table by event family', async () => {
    const wrapper = mountPage()
    const funding = useFundingStore()
    funding.cards = exhibitionCards()
    funding.cardTxns = exhibitionCardTxns()
    await flushPromises()
    await nextTick()

    wrapper.vm.txFilter = 'CHARGEBACK'
    await nextTick()
    const body = wrapper.get('[data-testid="card-events"]').text()
    expect(body).toContain('1st Chargeback')
    expect(body).toContain('Presentment')
    expect(body).toContain('2nd Chargeback')
    expect(body).toContain('Arbitration')
    expect(body).not.toContain('Captured')

    wrapper.vm.txFilter = 'REFUND'
    await nextTick()
    const refunds = wrapper.get('[data-testid="card-events"]').text()
    expect(refunds).toContain('Refund · Money only')
    expect(refunds).toContain('Refund · Money + goods return')
    expect(refunds).toContain('Refund succeeded')
    expect(refunds).toContain('Refund pending')
    expect(refunds).not.toContain('1st Chargeback')
  })

  it('opens the chargeback timeline from an event row', async () => {
    const wrapper = mountPage()
    const funding = useFundingStore()
    funding.cards = exhibitionCards()
    funding.cardTxns = exhibitionCardTxns()
    await flushPromises()
    await nextTick()

    await wrapper.find('tbody tr').trigger('click')
    await nextTick()
    expect(document.body.textContent).toContain('Chargeback timeline')
  })

  it('shows chargeback timeline only up to the clicked step', async () => {
    const wrapper = mountPage()
    const funding = useFundingStore()
    funding.cards = exhibitionCards()
    funding.cardTxns = exhibitionCardTxns()
    await flushPromises()
    await nextTick()

    wrapper.vm.activePaymentId = 'PAY-LILY-CHK-003'
    wrapper.vm.drawerOpen = true
    await nextTick()
    expect(document.body.querySelector('[data-testid="payment-flow"]')).toBeNull()
    expect(document.body.textContent).toContain('No chargeback cycle events for this payment')

    wrapper.vm.activePaymentId = 'PAY-LILY-CHK-004'
    await nextTick()
    expect(document.body.querySelector('[data-testid="payment-flow"]')).toBeNull()

    wrapper.vm.activePaymentId = 'PAY-LILY-CHK-002'
    wrapper.vm.activeDisputeId = 'DSP-LILY-002'
    wrapper.vm.activeUntilType = 'FIRST_CHARGEBACK'
    await nextTick()
    const cycle1 = document.body.querySelector('[data-testid="payment-flow"]')?.textContent || ''
    expect(cycle1).toContain('Presentment')
    expect(cycle1).toContain('1st Chargeback')
    expect(cycle1).toContain('Stopped at this step')
    expect(cycle1).not.toContain('Checkout created')
    expect(cycle1).not.toContain('Authorized')
    expect(cycle1).not.toContain('Captured')
    expect(cycle1).not.toContain('Refund')
    expect(cycle1).not.toContain('Representment')
    expect(cycle1).not.toContain('Arbitration')

    wrapper.vm.activePaymentId = 'PAY-LILY-CHK-005'
    wrapper.vm.activeDisputeId = 'DSP-LILY-005'
    wrapper.vm.activeUntilType = 'FIRST_CHARGEBACK'
    await nextTick()
    const early = document.body.querySelector('[data-testid="payment-flow"]')?.textContent || ''
    expect(early).toContain('Presentment')
    expect(early).toContain('1st Chargeback')
    expect(early).toContain('Stopped at this step')
    expect(early).not.toContain('Representment')
    expect(early).not.toContain('2nd Chargeback')
    expect(early).not.toContain('Arbitration')

    wrapper.vm.activeUntilType = 'ARBITRATION'
    await nextTick()
    const full = document.body.querySelector('[data-testid="payment-flow"]')?.textContent || ''
    expect(full).toContain('Presentment')
    expect(full).toContain('1st Chargeback')
    expect(full).toContain('Representment')
    expect(full).toContain('2nd Chargeback')
    expect(full).toContain('Arbitration')
    expect(full).not.toContain('Checkout created')
    expect(full).not.toContain('Authorized')
    expect(wrapper.findAll('button').map((node) => node.text()).join(' | ')).not.toMatch(/Represent|Accept chargeback/)
  })

  it('loads two checkout, refund and chargeback money signs for Miaa Grey', async () => {
    const wrapper = mountPage()
    const funding = useFundingStore()
    const miaa = { email: 'miaagrey@gmail.com', username: 'MiaaGrey' }
    expect(funding.ensureExhibitionFunding(miaa)).toBe(true)
    await flushPromises()
    await nextTick()

    expect(wrapper.get('[data-testid="card-balances"]').text()).toContain('6,680.00')
    expect(wrapper.text()).toContain('Visa ••4242')
    expect(wrapper.text()).toContain('Mastercard ••5555')

    const all = wrapper.get('[data-testid="card-events"]').text()
    expect(all).toContain('Checkout')
    expect(all).toContain('Refund · Money only')
    expect(all).toContain('Refund · Money + goods return')
    expect(all).toContain('Chargeback')
    expect(all).toContain('PAY-MIAA-CHK-001')
    expect(all).toContain('PAY-MIAA-CHK-004')

    wrapper.vm.txFilter = 'CHECKOUT'
    await nextTick()
    expect(wrapper.findAll('[data-testid="card-events"] tbody tr')).toHaveLength(2)

    wrapper.vm.txFilter = 'REFUND'
    await nextTick()
    expect(wrapper.findAll('[data-testid="card-events"] tbody tr')).toHaveLength(2)

    wrapper.vm.txFilter = 'CHARGEBACK'
    await nextTick()
    const chargebacks = wrapper.get('[data-testid="card-events"]').text()
    expect(chargebacks).toContain('Request for information')
    expect(chargebacks).toContain('Presentment')
    expect(chargebacks).toContain('1st Chargeback')
    expect(chargebacks).toContain('Representment')
    expect(chargebacks).toContain('2nd Chargeback')
    expect(chargebacks).toContain('Arbitration')
    expect(chargebacks).not.toContain('Chargeback won')
    expect(chargebacks).not.toContain('Chargeback lost')
    expect(chargebacks).not.toContain('Chargeback reversed')
    expect(chargebacks).not.toContain('Captured')
    expect(chargebacks).not.toContain('Refund succeeded')

    const events = funding.cardEvents.filter((row) => row.family === 'CHARGEBACK')
    const byType = Object.fromEntries(events.map((row) => [row.id, row]))
    expect(eventDirection(byType['CEV-MIAA-009'])).toBe('CREDIT')
    expect(eventDirection(byType['CEV-MIAA-010'])).toBe('CREDIT')
    expect(eventDirection(byType['CEV-MIAA-006'])).toBe('DEBIT')
    expect(eventDirection(byType['CEV-MIAA-011'])).toBe('DEBIT')
    expect(['CREDIT', 'DEBIT']).toContain(eventDirection(byType['CEV-MIAA-012']))
    expect(['CREDIT', 'DEBIT']).toContain(eventDirection(byType['CEV-MIAA-017']))
  })
})
