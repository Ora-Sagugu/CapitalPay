<template>
  <el-tag :type="tagType" round effect="light" size="small">{{ text }}</el-tag>
</template>

<script setup>
import { computed } from 'vue'
import { ORDER_STATUS, ORDER_STATUS_TYPE, KYC_STATUS, RISK_LEVEL, MERCHANT_STATUS, AGENT_STATUS, DEPOSIT_STATUS, ONBOARDING_STATUS, BANK_NOTIFICATION_STATUS, statusLabel } from '@/utils/format'

const props = defineProps({
  value: { type: [String, Boolean, Number], default: '' },
  kind: { type: String, default: 'order' }
})

const maps = {
  order: ORDER_STATUS,
  kyc: KYC_STATUS,
  risk: RISK_LEVEL,
  merchant: MERCHANT_STATUS,
  agent: AGENT_STATUS,
  deposit: DEPOSIT_STATUS,
  onboarding: ONBOARDING_STATUS,
  bankNotification: BANK_NOTIFICATION_STATUS
}

const types = {
  order: ORDER_STATUS_TYPE,
  kyc: { PENDING: 'warning', APPROVED: 'success', REJECTED: 'danger', WARNING: 'warning', DRAFT: 'info' },
  risk: { LOW: 'success', MEDIUM: 'warning', HIGH: 'danger', BLOCKED: 'danger' },
  merchant: { ACTIVE: 'success', SUSPENDED: 'warning', CLOSED: 'info', PENDING: 'warning' },
  agent: { ACTIVE: 'success', SUSPENDED: 'warning', CLOSED: 'info' },
  deposit: { PENDING: 'warning', APPROVED: 'success', REJECTED: 'danger' },
  onboarding: { none: 'info', pending: 'warning', under_review: 'warning', approved: 'success', rejected: 'danger' },
  bankNotification: { RECEIVED: 'info', MATCHED: 'success', MISMATCH: 'warning', UNMATCHED: 'info' }
}

const text = computed(() => {
  if (typeof props.value === 'boolean') return props.value ? 'Enabled' : 'Disabled'
  return statusLabel(maps[props.kind] || {}, props.value)
})
const tagType = computed(() => {
  if (typeof props.value === 'boolean') return props.value ? 'success' : 'info'
  return (types[props.kind] || {})[props.value] || 'info'
})
</script>
