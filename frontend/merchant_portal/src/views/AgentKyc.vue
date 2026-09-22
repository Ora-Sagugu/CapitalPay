<template>
  <div>
    <template v-if="!embedded">
      <h1 class="ptitle">{{ $t('agent.kycTitle') }}</h1>
      <p class="psub">{{ $t('agent.kycSub') }}</p>
    </template>

    <el-alert
      v-if="!embedded && auth.onboardingStatus !== 'approved'"
      :title="$t('agent.needOnboarding')"
      type="warning"
      :closable="false"
      show-icon
      style="margin-bottom: 16px"
    />

    <div class="page-card">
      <div class="section-bar">
        <h2 v-if="embedded" class="section-heading">{{ $t('agent.merchantPendingTitle') }}</h2>
        <el-button :disabled="auth.onboardingStatus !== 'approved'" :loading="loading" @click="reload">
          {{ $t('common.refresh') }}
        </el-button>
      </div>
      <p v-if="embedded" class="section-hint">{{ $t('agent.merchantPendingSub') }}</p>
      <el-table v-if="rows.length || loading" :data="rows" v-loading="loading">
        <el-table-column :label="$t('agent.merchantsName')" min-width="200">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">{{ merchantName(row) }}</el-button>
          </template>
        </el-table-column>
        <el-table-column :label="$t('agent.kycEmail')" min-width="220">
          <template #default="{ row }">{{ dash(row.email) }}</template>
        </el-table-column>
        <el-table-column width="180" align="right">
          <template #default="{ row }">
            <el-button
              v-if="row.agent_review_status === 'pending'"
              link
              type="success"
              @click="reviewApplication(row, 'approve')"
            >{{ $t('agent.kycApprove') }}</el-button>
            <el-button
              v-if="row.agent_review_status === 'pending'"
              link
              type="danger"
              @click="reviewApplication(row, 'reject')"
            >{{ $t('agent.kycReject') }}</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !rows.length" :description="$t('agent.merchantPendingEmpty')" />
      <el-pagination
        v-if="total > pageSize"
        class="toolbar"
        background
        layout="total, prev, pager, next"
        :total="total"
        :page-size="pageSize"
        :current-page="page"
        @current-change="onPage"
      />
    </div>

    <el-drawer v-model="detailVisible" :title="detailTitle" size="640px">
      <div v-loading="detailLoading">
        <el-descriptions :title="$t('onboarding.profileTitle')" :column="1" border>
          <el-descriptions-item :label="$t('agent.kycUsername')">{{ dash(detailUser?.username) }}</el-descriptions-item>
          <el-descriptions-item :label="$t('profile.email')">{{ dash(detailUser?.email) }}</el-descriptions-item>
          <el-descriptions-item :label="$t('onboarding.legalName')">{{ dash(basic.legal_name) }}</el-descriptions-item>
          <el-descriptions-item :label="$t('onboarding.idType')">{{ idTypeLabel(basic.id_type) }}</el-descriptions-item>
          <el-descriptions-item :label="$t('onboarding.idNumber')">{{ dash(basic.id_number) }}</el-descriptions-item>
          <el-descriptions-item :label="$t('onboarding.nationality')">{{ dash(basic.nationality) }}</el-descriptions-item>
          <el-descriptions-item :label="$t('onboarding.phone')">{{ dash(basic.contact_phone) }}</el-descriptions-item>
          <el-descriptions-item :label="$t('onboarding.address')">{{ dash(basic.address) }}</el-descriptions-item>
          <el-descriptions-item :label="$t('onboarding.tradingMarket')">{{ dash(marketLabel(basic.trading_market)) }}</el-descriptions-item>
          <el-descriptions-item :label="$t('onboarding.trn')">{{ dash(basic.trn) }}</el-descriptions-item>
          <el-descriptions-item :label="$t('onboarding.agentCode')">{{ dash(basic.agent_code) }}</el-descriptions-item>
        </el-descriptions>
        <el-descriptions :title="$t('onboarding.docsTitle')" :column="1" border style="margin-top: 16px">
          <el-descriptions-item :label="$t('onboarding.governmentId')">
            <DocFile :path="images.government_id_image || images.id_front_image" />
          </el-descriptions-item>
          <el-descriptions-item :label="$t('onboarding.proofOfAddress')">
            <DocFile :path="images.proof_of_address_image || images.id_back_image" />
          </el-descriptions-item>
          <el-descriptions-item :label="$t('onboarding.trnCertificate')">
            <DocFile :path="images.trn_certificate_image || images.license_image" />
          </el-descriptions-item>
        </el-descriptions>
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">{{ $t('common.cancel') }}</el-button>
        <el-button
          v-if="detailUser?.agent_review_status === 'pending'"
          type="danger"
          @click="reviewApplication(detailUser, 'reject')"
        >{{ $t('agent.kycReject') }}</el-button>
        <el-button
          v-if="detailUser?.agent_review_status === 'pending'"
          type="primary"
          @click="reviewApplication(detailUser, 'approve')"
        >{{ $t('agent.kycApprove') }}</el-button>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, defineComponent, h, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox, ElImage } from 'element-plus'
import { useAuthStore } from '@/store/auth'
import { getAgentKycList, getAgentKycDetail, reviewAgentKyc } from '@/api/agent'
import { extractErrorMessage } from '@/api/error'

defineProps({
  embedded: { type: Boolean, default: false }
})
const emit = defineEmits(['reviewed'])

const MARKET_LABELS = {
  ZM: 'Zambia',
  TZ: 'Tanzania',
  NG: 'Nigeria',
  RW: 'Rwanda',
  UG: 'Uganda',
  ZA: 'South Africa',
  MZ: 'Mozambique',
  EU: 'European Union',
  US: 'United States',
  PH: 'Philippines',
  JM: 'Jamaica (Caribbean)',
  OTHER: "My country isn't listed"
}

const { t } = useI18n()
const auth = useAuthStore()
const rows = ref([])
const stats = ref({})
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const detailVisible = ref(false)
const detailLoading = ref(false)
const detailUser = ref(null)
const basic = reactive({
  legal_name: '', id_type: '', id_number: '', contact_phone: '',
  nationality: '', address: '', trading_market: '', trn: '', agent_code: ''
})
const images = reactive({
  license_image: '',
  id_front_image: '',
  id_back_image: '',
  government_id_image: '',
  proof_of_address_image: '',
  trn_certificate_image: ''
})

const DocFile = defineComponent({
  name: 'DocFile',
  props: { path: { type: String, default: '' } },
  setup(props) {
    return () => {
      if (!props.path) return h('span', '—')
      const url = mediaUrl(props.path)
      const name = String(props.path).split('/').pop() || props.path
      if (/\.(png|jpe?g|gif|webp|bmp)$/i.test(props.path)) {
        return h('div', { class: 'doc-preview' }, [
          h(ElImage, {
            src: url,
            previewSrcList: [url],
            fit: 'contain',
            class: 'doc-thumb',
            previewTeleported: true
          }),
          h('a', { href: url, target: '_blank', rel: 'noopener' }, name)
        ])
      }
      return h('a', { href: url, target: '_blank', rel: 'noopener' }, name)
    }
  }
})

const detailTitle = computed(() => {
  const name = merchantName(detailUser.value)
  return name && name !== '—' ? name : t('agent.merchantPendingTitle')
})

function dash(value) {
  return value || '—'
}

function merchantName(row) {
  return dash(row?.legal_person || row?.username)
}

function mediaUrl(path) {
  if (!path) return ''
  if (/^https?:\/\//.test(path) || path.startsWith('/') || path.startsWith('data:')) return path
  return `/media/${path}`
}

function marketLabel(code) {
  return MARKET_LABELS[code] || code || ''
}

function idTypeLabel(code) {
  if (!code) return '—'
  const key = `onboarding.idTypes.${code}`
  const label = t(key)
  return label === key ? code : label
}

async function load() {
  if (auth.onboardingStatus !== 'approved') {
    rows.value = []
    stats.value = {}
    total.value = 0
    return
  }
  loading.value = true
  try {
    const data = await getAgentKycList({
      page: page.value,
      page_size: pageSize,
      stage: 'needs_review'
    })
    rows.value = data.items || data.results || []
    total.value = data.total || data.count || 0
    stats.value = data.stats || {}
    // #region agent log
    fetch('http://127.0.0.1:7400/ingest/4ebbb499-0df2-4dae-83ef-65d3a7131853',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'ce1e79'},body:JSON.stringify({sessionId:'ce1e79',runId:'post-fix',hypothesisId:'D',location:'AgentKyc.vue:load:ok',message:'kyc list loaded',data:{itemCount:(data.items||data.results||[]).length,total:data.total||data.count||0},timestamp:Date.now()})}).catch(()=>{});
    // #endregion
  } catch (err) {
    rows.value = []
    total.value = 0
    stats.value = {}
    const payload = err?.response?.data
    const msg = extractErrorMessage(payload, t('agent.merchantPendingEmpty'))
    // #region agent log
    fetch('http://127.0.0.1:7400/ingest/4ebbb499-0df2-4dae-83ef-65d3a7131853',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'ce1e79'},body:JSON.stringify({sessionId:'ce1e79',runId:'post-fix',hypothesisId:'D',location:'AgentKyc.vue:load:err',message:'kyc list failed',data:{status:err?.response?.status||0,code:payload?.code||'',apiMessage:payload?.message||'',toast:msg,url:err?.config?.url||''},timestamp:Date.now()})}).catch(()=>{});
    // #endregion
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

function reload() {
  page.value = 1
  load()
}

function onPage(p) {
  page.value = p
  load()
}

async function openDetail(row) {
  detailUser.value = row
  detailVisible.value = true
  detailLoading.value = true
  Object.assign(basic, {
    legal_name: '', id_type: '', id_number: '', contact_phone: '',
    nationality: '', address: '', trading_market: '', trn: '', agent_code: ''
  })
  Object.assign(images, {
    license_image: '',
    id_front_image: '',
    id_back_image: '',
    government_id_image: '',
    proof_of_address_image: '',
    trn_certificate_image: ''
  })
  try {
    const data = await getAgentKycDetail(row.id)
    const payload = data?.data || {}
    Object.assign(basic, payload.basic || {})
    Object.assign(images, payload.images || {})
  } finally {
    detailLoading.value = false
  }
}

async function reviewApplication(row, action) {
  let remark = ''
  if (action === 'reject') {
    const { value } = await ElMessageBox.prompt(
      t('agent.kycRejectPrompt'),
      t('agent.kycRejectTitle'),
      { inputPattern: /.+/, inputErrorMessage: t('agent.kycRejectRequired') }
    )
    remark = value
  }
  await reviewAgentKyc(row.id, { action, remark })
  ElMessage.success(action === 'approve' ? t('agent.kycApprovedMsg') : t('agent.kycRejectedMsg'))
  rows.value = rows.value.filter((item) => item.id !== row.id)
  total.value = Math.max(0, total.value - 1)
  stats.value = {
    ...stats.value,
    pending_profile: Math.max(0, (stats.value.pending_profile || 1) - 1),
    approved: (stats.value.approved || 0) + (action === 'approve' ? 1 : 0),
    rejected: (stats.value.rejected || 0) + (action === 'reject' ? 1 : 0)
  }
  if (detailUser.value?.id === row.id) detailVisible.value = false
  emit('reviewed', { action, id: row.id })
}

onMounted(load)
</script>

<style scoped>
.ptitle { margin: 0 0 4px; font-size: 22px; }
.psub { margin: 0 0 16px; color: #8c8c8c; font-size: 13px; }
.section-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 4px;
}
.section-heading { margin: 0; font-size: 16px; font-weight: 600; }
.section-hint {
  margin: 0 0 12px;
  color: #8c8c8c;
  font-size: 13px;
}
.doc-preview { display: flex; flex-direction: column; align-items: flex-start; gap: 8px; }
.doc-thumb {
  max-width: 100%;
  max-height: 160px;
  cursor: pointer;
  border: 1px solid #ebeef5;
  border-radius: 4px;
}
</style>
