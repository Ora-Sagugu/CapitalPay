<template>
  <div>
    <h1 class="ptitle">{{ $t('remittance.title') }}</h1>
    <p class="psub">{{ $t('remittance.subtitle') }}</p>
    <el-alert
      v-if="auth.onboardingStatus !== 'approved'"
      type="warning"
      :closable="false"
      style="margin-bottom: 16px"
    >
      {{ $t('remittance.needKyc') }}
      <el-button link type="primary" @click="$router.push('/onboarding')">{{ $t('remittance.goOnboarding') }}</el-button>
    </el-alert>
    <el-alert
      v-else-if="!customersLoading && !customers.length"
      type="warning"
      :closable="false"
      style="margin-bottom: 16px"
    >
      {{ $t('remittance.noCustomers') }}
      <el-button link type="primary" @click="$router.push('/customers')">{{ $t('remittance.goCustomers') }}</el-button>
    </el-alert>
    <el-alert
      v-else-if="!customersLoading && eligibilityBanner"
      type="warning"
      :closable="false"
      style="margin-bottom: 16px"
    >
      {{ eligibilityBanner }}
    </el-alert>
    <el-row :gutter="16">
      <el-col :span="16">
        <div class="page-card">
          <el-form :model="form" label-width="110px" :disabled="!formEnabled" class="remittance-form">
            <div class="section-title">{{ $t('remittance.selectCustomer') }}</div>
            <el-form-item :label="$t('remittance.selectCustomer')" required>
              <el-select
                v-model="form.customer_id"
                filterable
                clearable
                style="width: 100%"
                :placeholder="$t('remittance.selectCustomerPh')"
                :loading="customersLoading"
                data-testid="customer-select"
                @change="onCustomerChange"
              >
                <el-option
                  v-for="c in customers"
                  :key="c.id"
                  :label="`${c.customer_name || c.legal_name} (${c.customer_no})`"
                  :value="c.id"
                  :disabled="!c.remittance_eligibility?.eligible"
                />
              </el-select>
            </el-form-item>
            <el-alert
              v-if="selectedIneligibleMessage"
              type="warning"
              :closable="false"
              style="margin-bottom: 16px"
              :title="selectedIneligibleMessage"
            />
            <div class="section-title">{{ $t('remittance.fundingTitle') }}</div>
            <el-form-item :label="$t('remittance.fundingMethod')" required>
              <el-radio-group v-model="form.pay_method" class="funding-group" data-testid="funding-method">
                <el-radio
                  v-for="option in fundingOptions"
                  :key="option.value"
                  :value="option.value"
                  border
                  class="funding-option"
                >
                  {{ option.label }}
                </el-radio>
              </el-radio-group>
            </el-form-item>
            <el-alert
              type="info"
              :closable="false"
              show-icon
              class="funding-alert"
              :title="$t('remittance.fundingRecordHint')"
            />
            <div class="section-title">{{ $t('remittance.info') }}</div>
            <el-row :gutter="12">
              <el-col :span="12">
                <el-form-item :label="$t('remittance.fromCcy')" required>
                  <el-select v-model="form.from_currency" style="width: 100%" @change="onFinancialInput">
                    <el-option label="US Dollar (USD)" value="USD" /><el-option label="Chinese Yuan (CNY)" value="CNY" />
                    <el-option label="Euro (EUR)" value="EUR" /><el-option label="Hong Kong Dollar (HKD)" value="HKD" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item :label="$t('remittance.toCcy')" required>
                  <el-select v-model="form.to_currency" style="width: 100%" @change="onFinancialInput">
                    <el-option label="Chinese Yuan (CNY)" value="CNY" /><el-option label="US Dollar (USD)" value="USD" />
                    <el-option label="Euro (EUR)" value="EUR" /><el-option label="Hong Kong Dollar (HKD)" value="HKD" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item :label="$t('remittance.amount')" required>
              <el-input v-model="form.amount" :placeholder="$t('remittance.amountPh')" @input="invalidateQuote" @blur="preview" />
            </el-form-item>
            <el-form-item :label="$t('remittance.feeBearing')">
              <el-select v-model="form.fee_bearing" style="width: 100%" @change="onFinancialInput">
                <el-option :label="$t('remittance.feeBearingOur')" value="OUR" />
                <el-option :label="$t('remittance.feeBearingBen')" value="BEN" />
                <el-option :label="$t('remittance.feeBearingSha')" value="SHA" />
              </el-select>
            </el-form-item>
            <div class="section-title">{{ $t('remittance.beneficiaryInfo') }}</div>
            <el-form-item :label="$t('remittance.beneficiaryName')" required>
              <el-input v-model="form.beneficiary_name" @input="onBeneficiaryInput" @blur="runSanctionCheck" />
            </el-form-item>
            <el-form-item :label="$t('remittance.beneficiaryAccount')" required><el-input v-model="form.beneficiary_account" /></el-form-item>
            <el-form-item :label="$t('remittance.beneficiaryBank')" required><el-input v-model="form.beneficiary_bank" /></el-form-item>
            <el-form-item label="SWIFT"><el-input v-model="form.beneficiary_swift" /></el-form-item>
            <el-form-item :label="$t('remittance.beneficiaryAddress')">
              <el-input v-model="form.beneficiary_address" @input="onBeneficiaryInput" @blur="runSanctionCheck" />
            </el-form-item>
            <el-alert
              v-if="sanctionWarning"
              class="sanction-alert"
              type="warning"
              :closable="false"
              show-icon
              :title="$t('remittance.sanctionWarningTitle')"
              :description="sanctionWarning"
            />
            <div v-else-if="sanctionChecking" class="sanction-checking">{{ $t('remittance.sanctionChecking') }}</div>
            <el-form-item :label="$t('remittance.purpose')">
              <el-select v-model="form.remittance_purpose" style="width: 100%" clearable>
                <el-option
                  v-for="item in remittancePurposes"
                  :key="item"
                  :label="item"
                  :value="item"
                />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="submitting" :disabled="!fee?.quote_id" @click="submit">{{ $t('remittance.submitReview') }}</el-button>
            </el-form-item>
          </el-form>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="page-card">
          <div class="section-title">{{ $t('remittance.feeDetails') }}</div>
          <div v-if="!fee">{{ quoteLoading ? $t('remittance.quoting') : $t('remittance.quoteHint') }}</div>
          <div v-else>
            <p>{{ $t('remittance.totalFee') }}：{{ money(fee.total_fee) }} {{ fee.fee_currency }}</p>
            <p>{{ $t('remittance.senderTotal') }}：{{ money(fee.sender_total) }} {{ fee.from_currency }}</p>
            <p>{{ $t('remittance.settleAmount') }}：{{ money(fee.settle_amount) }} {{ fee.to_currency }}</p>
          </div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { ENABLE_CARDS } from '@/config/features'
import { useAuthStore } from '@/store/auth'
import { applyRemittance, feePreview, getCustomers, sanctionCheck } from '@/api/payments'
import { money, REMITTANCE_PURPOSES } from '@/utils/format'

const FUNDING_METHODS = {
  WIRE_TRANSFER: 'WIRE_TRANSFER',
  WALLET: 'WALLET',
  CARD: 'CARD'
}

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const { t, te } = useI18n()

const customers = ref([])
const customersLoading = ref(false)
const remittancePurposes = REMITTANCE_PURPOSES
const fee = ref(null)
const submitting = ref(false)
const quoteLoading = ref(false)
const sanctionWarning = ref('')
const sanctionChecking = ref(false)
const form = reactive({
  customer_id: '',
  pay_method: FUNDING_METHODS.WIRE_TRANSFER,
  from_currency: 'USD', to_currency: 'USD', amount: '', fee_bearing: 'OUR',
  beneficiary_name: '', beneficiary_account: '', beneficiary_bank: '', beneficiary_swift: '',
  beneficiary_address: '', remittance_purpose: ''
})

const fundingOptions = computed(() => {
  const options = [
    { value: FUNDING_METHODS.WIRE_TRANSFER, label: t('remittance.fundingBank') },
    { value: FUNDING_METHODS.WALLET, label: t('remittance.fundingWallet') }
  ]
  if (ENABLE_CARDS) {
    options.push({ value: FUNDING_METHODS.CARD, label: t('remittance.fundingCard') })
  }
  return options
})
const allowedFundingMethods = computed(() => fundingOptions.value.map((o) => o.value))

const eligibleCustomers = computed(() =>
  customers.value.filter((c) => c.remittance_eligibility?.eligible)
)

const selectedCustomer = computed(() =>
  customers.value.find((c) => c.id === form.customer_id) || null
)

const formEnabled = computed(() => auth.onboardingStatus === 'approved')

const canSubmit = computed(() =>
  formEnabled.value && !!selectedCustomer.value?.remittance_eligibility?.eligible
)

function blockerMessage(blocker) {
  if (!blocker) return ''
  const key = `remittance.blockers.${blocker.code}`
  return te(key) ? t(key) : (blocker.message || '')
}

const eligibilityBanner = computed(() => {
  if (eligibleCustomers.value.length) return ''
  const merchantBlocker = auth.remittanceEligibility?.blockers?.[0]
  if (auth.remittanceEligibility?.eligible === false) {
    return blockerMessage(merchantBlocker) || t('remittance.notEligible')
  }
  const customerBlocker = customers.value[0]?.remittance_eligibility?.blockers?.[0]
  return blockerMessage(customerBlocker) || t('remittance.noEligibleCustomers')
})

const selectedIneligibleMessage = computed(() => {
  const customer = selectedCustomer.value
  if (!customer || customer.remittance_eligibility?.eligible) return ''
  return blockerMessage(customer.remittance_eligibility?.blockers?.[0])
    || t('remittance.customerIneligible')
})

let quoteRequest = 0
let idempotencyKey = ''
let sanctionTimer = null
let sanctionRequest = 0

function clearSanctionWarning() {
  sanctionWarning.value = ''
  sanctionChecking.value = false
}

function onBeneficiaryInput() {
  if (sanctionTimer) clearTimeout(sanctionTimer)
  if (!form.beneficiary_name?.trim() && !form.beneficiary_address?.trim()) {
    clearSanctionWarning()
    return
  }
  sanctionTimer = setTimeout(runSanctionCheck, 500)
}

async function runSanctionCheck() {
  const name = form.beneficiary_name?.trim() || ''
  const address = form.beneficiary_address?.trim() || ''
  if (!name && !address) {
    clearSanctionWarning()
    return
  }
  const requestNo = ++sanctionRequest
  sanctionChecking.value = true
  try {
    const result = await sanctionCheck({
      beneficiary_name: name,
      beneficiary_address: address
    })
    if (requestNo !== sanctionRequest) return
    sanctionWarning.value = result.total_hits > 0 ? (result.warning_message || '') : ''
  } catch {
    if (requestNo === sanctionRequest) sanctionWarning.value = ''
  } finally {
    if (requestNo === sanctionRequest) sanctionChecking.value = false
  }
}

function invalidateQuote() {
  quoteRequest += 1
  quoteLoading.value = false
  fee.value = null
  idempotencyKey = ''
}

function onCustomerChange() {
  invalidateQuote()
  const customer = selectedCustomer.value
  if (customer) {
    if (!form.beneficiary_name && customer.account_name) form.beneficiary_name = customer.account_name
    if (!form.beneficiary_bank && customer.bank_name) form.beneficiary_bank = customer.bank_name
    if (!form.beneficiary_account && customer.bank_account) form.beneficiary_account = customer.bank_account
    if (!form.beneficiary_swift && customer.swift_code) form.beneficiary_swift = customer.swift_code
  }
  preview()
}

function onFinancialInput() {
  invalidateQuote()
  preview()
}

async function preview() {
  const numericAmount = Number(form.amount)
  if (!canSubmit.value || !form.customer_id || !Number.isFinite(numericAmount) || numericAmount <= 0) {
    invalidateQuote()
    return
  }
  const requestNo = ++quoteRequest
  fee.value = null
  quoteLoading.value = true
  try {
    const quote = await feePreview({
      customer_id: form.customer_id,
      amount: form.amount,
      from_currency: form.from_currency,
      to_currency: form.to_currency,
      fee_bearing: form.fee_bearing
    })
    if (requestNo === quoteRequest) {
      fee.value = quote
    }
  } catch {
    if (requestNo === quoteRequest) fee.value = null
  } finally {
    if (requestNo === quoteRequest) quoteLoading.value = false
  }
}

function validateForm() {
  if (!form.customer_id) {
    ElMessage.warning(t('remittance.customerRequired'))
    return false
  }
  if (!allowedFundingMethods.value.includes(form.pay_method)) {
    ElMessage.warning(t('remittance.fundingRequired'))
    return false
  }
  if (!form.amount || !Number.isFinite(Number(form.amount)) || Number(form.amount) <= 0) {
    ElMessage.warning('Enter a valid remittance amount.')
    return false
  }
  if (!form.beneficiary_name?.trim()) {
    ElMessage.warning('Enter the beneficiary name.')
    return false
  }
  if (!form.beneficiary_account?.trim()) {
    ElMessage.warning('Enter the beneficiary account number.')
    return false
  }
  if (!form.beneficiary_bank?.trim()) {
    ElMessage.warning('Enter the beneficiary bank.')
    return false
  }
  return true
}

async function submit() {
  if (submitting.value) return
  if (!canSubmit.value) {
    ElMessage.warning(selectedIneligibleMessage.value || t('remittance.customerIneligible'))
    return
  }
  if (!validateForm()) return
  if (!fee.value?.quote_id) {
    ElMessage.warning(t('remittance.quoteRequired'))
    return
  }
  if (new Date(fee.value.expires_at).getTime() <= Date.now()) {
    invalidateQuote()
    ElMessage.warning(t('remittance.quoteExpired'))
    return
  }
  submitting.value = true
  try {
    if (!idempotencyKey) {
      idempotencyKey = globalThis.crypto?.randomUUID?.()
        || `rmt-${Date.now()}-${Math.random().toString(16).slice(2)}`
    }
    await applyRemittance({
      customer_id: form.customer_id,
      quote_id: fee.value.quote_id,
      pay_method: form.pay_method,
      beneficiary_name: form.beneficiary_name.trim(),
      beneficiary_account: form.beneficiary_account.trim(),
      beneficiary_bank: form.beneficiary_bank.trim(),
      beneficiary_swift: form.beneficiary_swift.trim(),
      beneficiary_address: form.beneficiary_address.trim(),
      remittance_purpose: form.remittance_purpose.trim()
    }, idempotencyKey)
    ElMessage.success(t('remittance.submitted'))
    router.push('/orders')
  } finally { submitting.value = false }
}

async function loadCustomers() {
  if (auth.onboardingStatus !== 'approved') return
  customersLoading.value = true
  try {
    const data = await getCustomers()
    customers.value = data.items || data.results || []
    const preferred = String(route.query.customer_id || '')
    const eligible = customers.value.filter((c) => c.remittance_eligibility?.eligible)
    if (preferred && eligible.some((c) => c.id === preferred)) {
      form.customer_id = preferred
      onCustomerChange()
    } else if (!form.customer_id && eligible.length === 1) {
      form.customer_id = eligible[0].id
      onCustomerChange()
    }
  } finally {
    customersLoading.value = false
  }
}

onMounted(async () => {
  await auth.fetchProfile()
  await loadCustomers()
})
</script>

<style scoped>
.ptitle { margin: 0 0 4px; font-size: 22px; }
.psub { margin: 0 0 16px; color: #8c8c8c; font-size: 13px; }
.funding-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  width: 100%;
}
.funding-option {
  margin: 0 !important;
}
.funding-alert { margin: 0 0 16px; }
.sanction-alert { margin-bottom: 16px; }
.sanction-checking { margin-bottom: 12px; color: #8c8c8c; font-size: 13px; }
</style>
