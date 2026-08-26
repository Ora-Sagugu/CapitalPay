<template>
  <div class="page-card">
    <el-alert
      v-if="statusInfo.onboarding_status"
      :title="statusLabel"
      :type="statusType"
      :description="statusDescription"
      show-icon
      style="margin-bottom: 16px"
    />

    <el-steps :active="step" finish-status="success" align-center style="margin-bottom: 24px">
      <el-step title="基本信息" />
      <el-step title="财务信息" />
      <el-step title="证件资料" />
    </el-steps>

    <el-form v-if="step === 0" :model="basic" label-width="120px" style="max-width: 640px">
      <el-form-item label="法定名称" required>
        <el-input v-model="basic.legal_name" />
      </el-form-item>
      <el-form-item label="证件类型" required>
        <el-select v-model="basic.id_type" style="width: 100%">
          <el-option label="身份证" value="ID_CARD" />
          <el-option label="护照" value="PASSPORT" />
          <el-option label="营业执照" value="BUSINESS_LICENSE" />
        </el-select>
      </el-form-item>
      <el-form-item label="证件号码" required>
        <el-input v-model="basic.id_number" />
      </el-form-item>
      <el-form-item label="联系电话" required>
        <el-input v-model="basic.contact_phone" />
      </el-form-item>
      <el-form-item label="国籍">
        <el-input v-model="basic.nationality" />
      </el-form-item>
      <el-form-item label="地址">
        <el-input v-model="basic.address" type="textarea" :rows="2" />
      </el-form-item>
      <el-form-item label="代理编码">
        <el-input v-model="basic.agent_code" />
      </el-form-item>
      <el-form-item label="执照到期日">
        <el-date-picker
          v-model="basic.license_expiry_date"
          type="date"
          value-format="YYYY-MM-DD"
          style="width: 100%"
        />
      </el-form-item>
    </el-form>

    <el-form v-else-if="step === 1" :model="finance" label-width="120px" style="max-width: 640px">
      <el-form-item label="开户银行" required>
        <el-input v-model="finance.bank_name" />
      </el-form-item>
      <el-form-item label="支行名称">
        <el-input v-model="finance.branch_name" />
      </el-form-item>
      <el-form-item label="银行账号" required>
        <el-input v-model="finance.bank_account" />
      </el-form-item>
    </el-form>

    <el-form v-else :model="images" label-width="120px" style="max-width: 640px">
      <el-form-item label="营业执照/执照" required>
        <el-input v-model="images.license_image" placeholder="图片 URL 或 base64" />
      </el-form-item>
      <el-form-item label="证件正面" required>
        <el-input v-model="images.id_front_image" placeholder="图片 URL 或 base64" />
      </el-form-item>
      <el-form-item label="证件反面" required>
        <el-input v-model="images.id_back_image" placeholder="图片 URL 或 base64" />
      </el-form-item>
      <el-alert
        title="提示"
        type="info"
        description="当前版本使用文本 URL 提交证件图片；生产环境可接入文件上传服务。"
        :closable="false"
        style="margin-bottom: 16px"
      />
    </el-form>

    <div style="margin-top: 24px; display: flex; gap: 12px">
      <el-button v-if="step > 0" @click="step -= 1">上一步</el-button>
      <el-button v-if="step < 2" type="primary" @click="nextStep">下一步</el-button>
      <el-button
        v-if="step === 2"
        type="primary"
        :loading="submitting"
        :disabled="statusInfo.onboarding_status === 'pending' || statusInfo.onboarding_status === 'approved'"
        @click="submit"
      >
        提交审核
      </el-button>
      <el-button @click="loadStatus">刷新状态</el-button>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { getOnboardingStatus, submitOnboarding } from '@/api/onboarding'
import { useAuthStore } from '@/store/auth'
import { ElMessage } from 'element-plus'

const auth = useAuthStore()
const step = ref(0)
const submitting = ref(false)
const statusInfo = reactive({
  onboarding_status: 'none',
  submitted_at: null,
  reviewed_at: null,
  reviewer: '',
  remark: '',
  data: null
})

const basic = reactive({
  legal_name: '',
  id_type: 'ID_CARD',
  id_number: '',
  contact_phone: '',
  nationality: '',
  address: '',
  agent_code: '',
  license_expiry_date: null
})

const finance = reactive({
  bank_name: '',
  branch_name: '',
  bank_account: ''
})

const images = reactive({
  license_image: '',
  id_front_image: '',
  id_back_image: ''
})

const statusLabel = computed(() => {
  const map = {
    none: '尚未提交资料',
    pending: '资料审核中',
    approved: '资料已通过',
    rejected: '资料已驳回'
  }
  return map[statusInfo.onboarding_status] || statusInfo.onboarding_status
})

const statusType = computed(() => {
  const map = { none: 'info', pending: 'warning', approved: 'success', rejected: 'error' }
  return map[statusInfo.onboarding_status] || 'info'
})

const statusDescription = computed(() => {
  const parts = []
  if (statusInfo.submitted_at) parts.push(`提交时间：${formatTime(statusInfo.submitted_at)}`)
  if (statusInfo.reviewed_at) parts.push(`审核时间：${formatTime(statusInfo.reviewed_at)}`)
  if (statusInfo.reviewer) parts.push(`审核人：${statusInfo.reviewer}`)
  if (statusInfo.remark) parts.push(`备注：${statusInfo.remark}`)
  return parts.join(' · ') || '请完成三步资料填写并提交审核。'
})

function formatTime(value) {
  if (!value) return ''
  return new Date(value).toLocaleString()
}

function fillFromData(data) {
  if (!data) return
  const b = data.basic || {}
  const f = data.finance || {}
  const i = data.images || {}
  Object.assign(basic, {
    legal_name: b.legal_name || '',
    id_type: b.id_type || 'ID_CARD',
    id_number: b.id_number || '',
    contact_phone: b.contact_phone || '',
    nationality: b.nationality || '',
    address: b.address || '',
    agent_code: b.agent_code || '',
    license_expiry_date: b.license_expiry_date || null
  })
  Object.assign(finance, {
    bank_name: f.bank_name || '',
    branch_name: f.branch_name || '',
    bank_account: f.bank_account || ''
  })
  Object.assign(images, {
    license_image: i.license_image || '',
    id_front_image: i.id_front_image || '',
    id_back_image: i.id_back_image || ''
  })
}

async function loadStatus() {
  const res = await getOnboardingStatus()
  Object.assign(statusInfo, {
    onboarding_status: res.onboarding_status,
    submitted_at: res.submitted_at,
    reviewed_at: res.reviewed_at,
    reviewer: res.reviewer,
    remark: res.remark,
    data: res.data
  })
  fillFromData(res.data)
  if (auth.user) {
    auth.user.onboarding_status = res.onboarding_status
    localStorage.setItem('user', JSON.stringify(auth.user))
  }
}

function validateStep() {
  if (step.value === 0) {
    if (!basic.legal_name || !basic.id_type || !basic.id_number || !basic.contact_phone) {
      ElMessage.warning('请填写基本信息必填项')
      return false
    }
  } else if (step.value === 1) {
    if (!finance.bank_name || !finance.bank_account) {
      ElMessage.warning('请填写银行名称和账号')
      return false
    }
  } else if (!images.license_image || !images.id_front_image || !images.id_back_image) {
    ElMessage.warning('请填写全部证件图片地址')
    return false
  }
  return true
}

function nextStep() {
  if (!validateStep()) return
  step.value += 1
}

async function submit() {
  if (!validateStep()) return
  submitting.value = true
  try {
    await submitOnboarding({
      basic: { ...basic },
      finance: { ...finance },
      images: { ...images }
    })
    ElMessage.success('资料已提交，等待审核')
    await loadStatus()
  } finally {
    submitting.value = false
  }
}

onMounted(loadStatus)
</script>
