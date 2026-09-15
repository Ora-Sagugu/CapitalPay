<template>
  <div>
    <h1 class="ptitle">{{ $t('remittance.title') }}</h1>
    <p class="psub">{{ $t('remittance.subtitle') }}</p>
    <el-alert v-if="!auth.canRemit" type="warning" :closable="false" style="margin-bottom: 16px">
      {{ eligibilityMessage }}
      <el-button v-if="auth.onboardingStatus !== 'approved'" link type="primary" @click="$router.push('/onboarding')">{{ $t('remittance.goOnboarding') }}</el-button>
    </el-alert>
    <el-row :gutter="16">
      <el-col :span="16">
        <div class="page-card">
          <el-form :model="form" label-width="110px" :disabled="!auth.canRemit">
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
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/store/auth'
import { applyRemittance, feePreview, sanctionCheck } from '@/api/payments'
import { money, REMITTANCE_PURPOSES } from '@/utils/format'

const auth = useAuthStore()
const router = useRouter()
const { t, te } = useI18n()
const fee = ref(null)
const submitting = ref(false)
const quoteLoading = ref(false)
const sanctionWarning = ref('')
const sanctionChecking = ref(false)
const remittancePurposes = REMITTANCE_PURPOSES
const form = reactive({
  from_currency: 'USD', to_currency: 'USD', amount: '', fee_bearing: 'OUR',
  beneficiary_name: '', beneficiary_account: '', beneficiary_bank: '', beneficiary_swift: '',
  beneficiary_address: '', remittance_purpose: ''
})
const eligibilityMessage = computed(() => {
  const blocker = auth.remittanceEligibility?.blockers?.[0]
  if (!blocker) return t('remittance.notEligible')
  const key = `remittance.blockers.${blocker.code}`
  return te(key) ? t(key) : blocker.message
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
function onFinancialInput() {
  invalidateQuote()
  preview()
}
async function preview() {
  const numericAmount = Number(form.amount)
  if (!auth.canRemit || !Number.isFinite(numericAmount) || numericAmount <= 0) {
    invalidateQuote()
    return
  }
  const requestNo = ++quoteRequest
  fee.value = null
  quoteLoading.value = true
  // #region agent log
  fetch('http://127.0.0.1:7400/ingest/4ebbb499-0df2-4dae-83ef-65d3a7131853',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'cc4e4a'},body:JSON.stringify({sessionId:'cc4e4a',runId:'quote-check',hypothesisId:'H-A',location:'RemittanceApply.vue:preview',message:'customer quote request',data:{requestNo,amount:form.amount,from:form.from_currency,to:form.to_currency,fee_bearing:form.fee_bearing},timestamp:Date.now()})}).catch(()=>{});
  // #endregion
  try {
    const quote = await feePreview({
      amount: form.amount,
      from_currency: form.from_currency,
      to_currency: form.to_currency,
      fee_bearing: form.fee_bearing
    })
    if (requestNo === quoteRequest) {
      fee.value = quote
      // #region agent log
      fetch('http://127.0.0.1:7400/ingest/4ebbb499-0df2-4dae-83ef-65d3a7131853',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'cc4e4a'},body:JSON.stringify({sessionId:'cc4e4a',runId:'quote-check',hypothesisId:'H-C',location:'RemittanceApply.vue:preview:response',message:'customer quote applied to panel',data:{requestNo,fee_bearing:quote?.fee_bearing,total_fee:quote?.total_fee,sender_fee:quote?.sender_fee,beneficiary_fee:quote?.beneficiary_fee,sender_total:quote?.sender_total,settle_amount:quote?.settle_amount,exchange_rate:quote?.exchange_rate,from:quote?.from_currency,to:quote?.to_currency},timestamp:Date.now()})}).catch(()=>{});
      // #endregion
    }
  } catch (err) {
    // #region agent log
    fetch('http://127.0.0.1:7400/ingest/4ebbb499-0df2-4dae-83ef-65d3a7131853',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'cc4e4a'},body:JSON.stringify({sessionId:'cc4e4a',runId:'quote-check',hypothesisId:'H-A',location:'RemittanceApply.vue:preview:error',message:'customer quote failed',data:{requestNo,fee_bearing:form.fee_bearing,error:String(err?.message||err)},timestamp:Date.now()})}).catch(()=>{});
    // #endregion
  }
  finally {
    if (requestNo === quoteRequest) quoteLoading.value = false
  }
}
function validateForm() {
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
  if (!auth.canRemit) {
    ElMessage.warning(eligibilityMessage.value)
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
    const res = await applyRemittance({
      quote_id: fee.value.quote_id,
      beneficiary_name: form.beneficiary_name.trim(),
      beneficiary_account: form.beneficiary_account.trim(),
      beneficiary_bank: form.beneficiary_bank.trim(),
      beneficiary_swift: form.beneficiary_swift.trim(),
      beneficiary_address: form.beneficiary_address.trim(),
      remittance_purpose: form.remittance_purpose.trim()
    }, idempotencyKey)
    ElMessage.success(
      res?.status === 'PENDING_AGENT_REVIEW'
        ? t('remittance.submittedAgent')
        : t('remittance.submitted')
    )
    router.push('/orders')
  } finally { submitting.value = false }
}
onMounted(() => { auth.fetchProfile() })
</script>

<style scoped>
.ptitle { margin: 0 0 4px; font-size: 22px; }
.psub { margin: 0 0 16px; color: #8c8c8c; font-size: 13px; }
.sanction-alert { margin-bottom: 16px; }
.sanction-checking { margin-bottom: 12px; color: #8c8c8c; font-size: 13px; }
</style>
