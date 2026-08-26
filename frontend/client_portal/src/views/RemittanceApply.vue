<template>
  <el-card class="page-card" shadow="never">
    <template #header><span class="card-title">汇款申请</span></template>
    <el-form :model="form" label-width="120px" style="max-width: 720px">
      <el-form-item label="汇款方(商户)" required>
        <el-select v-model="form.merchant" filterable remote :remote-method="searchMerchants" placeholder="选择商户" style="width: 100%" @change="onMerchantChange">
          <el-option v-for="m in merchants" :key="m.merchant_no" :label="`${m.merchant_no} — ${m.merchant_name}`" :value="m.merchant_no" />
        </el-select>
      </el-form-item>
      <el-row :gutter="12">
        <el-col :span="12">
          <el-form-item label="源币种" required>
            <el-select v-model="form.from_currency" style="width: 100%" @change="previewFee">
              <el-option v-for="c in currencies" :key="c" :label="c" :value="c" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="目标币种" required>
            <el-select v-model="form.to_currency" style="width: 100%" @change="previewFee">
              <el-option v-for="c in currencies" :key="c" :label="c" :value="c" />
            </el-select>
          </el-form-item>
        </el-col>
      </el-row>
      <el-form-item label="金额" required>
        <el-input v-model="form.amount" placeholder="汇款金额" @blur="previewFee" />
      </el-form-item>
      <el-form-item label="费用承担">
        <el-select v-model="form.fee_bearing" style="width: 100%">
          <el-option label="OUR" value="OUR" />
          <el-option label="BEN" value="BEN" />
          <el-option label="SHA" value="SHA" />
        </el-select>
      </el-form-item>
      <el-form-item label="收款人姓名" required>
        <el-input v-model="form.beneficiary_name" />
      </el-form-item>
      <el-form-item label="收款银行" required>
        <el-input v-model="form.beneficiary_bank" />
      </el-form-item>
      <el-form-item label="收款账号" required>
        <el-input v-model="form.beneficiary_account" />
      </el-form-item>
      <el-form-item label="SWIFT">
        <el-input v-model="form.beneficiary_swift" placeholder="选填" />
      </el-form-item>
      <el-form-item label="收款人地址">
        <el-input v-model="form.beneficiary_address" type="textarea" placeholder="选填" />
      </el-form-item>
      <el-form-item label="用途">
        <el-input v-model="form.remittance_purpose" placeholder="选填" />
      </el-form-item>
      <el-form-item label="合同路径">
        <el-input v-model="form.contract_file" placeholder="选填，已上传合同路径" />
      </el-form-item>

      <el-alert v-if="feeInfo" type="info" :closable="false" style="margin-bottom: 16px">
        <div>手续费公式：{{ feeInfo.fee_formula }}</div>
        <div>手续费合计：{{ feeInfo.total_fee }} · 结算金额：{{ feeInfo.settle_amount }}</div>
        <div v-if="feeInfo.exchange_rate">汇率：{{ feeInfo.exchange_rate }}（{{ feeInfo.rate_source }}）</div>
      </el-alert>
      <el-alert v-if="sanctionMsg" :type="sanctionClear ? 'success' : 'warning'" :closable="false" style="margin-bottom: 16px">
        {{ sanctionMsg }}
      </el-alert>

      <el-form-item>
        <el-button @click="runSanctionCheck" :loading="checking">制裁预检</el-button>
        <el-button type="primary" :loading="submitting" @click="onSubmit">提交审核</el-button>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getMerchants } from '@/api/merchants'
import { applyRemittance, feePreview, sanctionCheck } from '@/api/orders'

const router = useRouter()
const currencies = ['USD', 'EUR', 'GBP', 'CNY', 'JPY', 'HKD']
const merchants = ref([])
const feeInfo = ref(null)
const sanctionMsg = ref('')
const sanctionClear = ref(true)
const checking = ref(false)
const submitting = ref(false)

const form = reactive({
  merchant: '',
  from_currency: 'USD',
  to_currency: 'CNY',
  amount: '',
  fee_bearing: 'OUR',
  beneficiary_name: '',
  beneficiary_bank: '',
  beneficiary_account: '',
  beneficiary_swift: '',
  beneficiary_address: '',
  remittance_purpose: '',
  contract_file: '',
  pay_method: 'WIRE_TRANSFER'
})

async function searchMerchants(q) {
  const data = await getMerchants({ search: q || undefined, page_size: 50 })
  merchants.value = data.results || []
}
function onMerchantChange() {
  previewFee()
}
async function previewFee() {
  if (!form.merchant || !form.amount) return
  try {
    feeInfo.value = await feePreview({
      merchant: form.merchant,
      amount: form.amount,
      from_currency: form.from_currency,
      to_currency: form.to_currency
    })
  } catch (e) {
    feeInfo.value = null
  }
}
async function runSanctionCheck() {
  if (!form.beneficiary_name && !form.beneficiary_address) {
    ElMessage.warning('请填写收款人姓名或地址')
    return
  }
  checking.value = true
  try {
    const res = await sanctionCheck({
      beneficiary_name: form.beneficiary_name,
      beneficiary_address: form.beneficiary_address
    })
    sanctionClear.value = !!res.is_clear
    sanctionMsg.value = res.is_clear
      ? '制裁预检通过'
      : (res.warning_message || '存在制裁命中风险，请确认后再提交')
  } finally {
    checking.value = false
  }
}
async function onSubmit() {
  if (!form.merchant || !form.amount || !form.beneficiary_name || !form.beneficiary_bank || !form.beneficiary_account) {
    ElMessage.warning('请填写必填项')
    return
  }
  await runSanctionCheck()
  if (!sanctionClear.value) {
    try {
      await ElMessageBox.confirm('制裁预检未完全通过，确认仍要提交？', '风险确认', { type: 'warning' })
    } catch {
      return
    }
  }
  submitting.value = true
  try {
    const order = await applyRemittance({ ...form })
    ElMessage.success(`已提交，订单号 ${order.order_no}`)
    router.push({ name: 'orders' })
  } finally {
    submitting.value = false
  }
}

searchMerchants('')
</script>

<style scoped>
.card-title { font-weight: 600; }
</style>
