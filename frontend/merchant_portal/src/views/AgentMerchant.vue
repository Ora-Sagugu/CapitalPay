<template>
  <div>
    <h1 class="ptitle">{{ $t('agent.merchantPageTitle') }}</h1>
    <p class="psub">{{ $t('agent.merchantPageSub') }}</p>

    <el-alert
      v-if="auth.onboardingStatus !== 'approved'"
      :title="$t('agent.needOnboarding')"
      type="warning"
      :closable="false"
      show-icon
      style="margin-bottom: 16px"
    />

    <AgentKyc embedded @reviewed="loadMerchants" />

    <div class="page-card merchants-card">
      <div class="section-bar">
        <h2 class="section-heading">{{ $t('agent.merchantAgreedTitle') }}</h2>
        <el-button :disabled="!canLoad" :loading="merchantsLoading" @click="loadMerchants">
          {{ $t('common.refresh') }}
        </el-button>
      </div>
      <p class="section-hint">{{ $t('agent.merchantAgreedSub') }}</p>
      <el-table v-if="merchants.length" :data="merchants" v-loading="merchantsLoading">
        <el-table-column prop="merchant_name" :label="$t('agent.merchantsName')" min-width="200" />
        <el-table-column :label="$t('agent.merchantCustomerCount')" width="140" align="right">
          <template #default="{ row }">{{ row.customer_count ?? 0 }}</template>
        </el-table-column>
        <el-table-column :label="$t('agent.kycEmail')" min-width="220">
          <template #default="{ row }">{{ dash(row.contact_email) }}</template>
        </el-table-column>
      </el-table>
      <el-empty
        v-else-if="!merchantsLoading && canLoad"
        :description="$t('agent.merchantAgreedEmpty')"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'

import { getAgentMerchants } from '@/api/agent'
import { extractErrorMessage } from '@/api/error'
import { useAuthStore } from '@/store/auth'
import AgentKyc from './AgentKyc.vue'

const { t } = useI18n()
const auth = useAuthStore()
const merchantsLoading = ref(false)
const merchants = ref([])

const canLoad = computed(() => auth.onboardingStatus === 'approved')

function dash(value) {
  return value || '—'
}

async function loadMerchants() {
  // #region agent log
  fetch('http://127.0.0.1:7400/ingest/4ebbb499-0df2-4dae-83ef-65d3a7131853',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'ce1e79'},body:JSON.stringify({sessionId:'ce1e79',runId:'post-fix',hypothesisId:'C',location:'AgentMerchant.vue:loadMerchants:entry',message:'loadMerchants called',data:{canLoad:canLoad.value,onboardingStatus:auth.onboardingStatus,portalRole:auth.user?.portal_role||''},timestamp:Date.now()})}).catch(()=>{});
  // #endregion
  if (!canLoad.value) {
    merchants.value = []
    return
  }
  merchantsLoading.value = true
  try {
    const data = await getAgentMerchants()
    const items = data.items || data.results || []
    merchants.value = items
    // #region agent log
    fetch('http://127.0.0.1:7400/ingest/4ebbb499-0df2-4dae-83ef-65d3a7131853',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'ce1e79'},body:JSON.stringify({sessionId:'ce1e79',runId:'post-fix',hypothesisId:'A',location:'AgentMerchant.vue:loadMerchants:ok',message:'merchants loaded',data:{keys:data&&typeof data==='object'?Object.keys(data):[],total:data?.total,itemCount:items.length,names:items.slice(0,5).map((r)=>r.merchant_name||'')},timestamp:Date.now()})}).catch(()=>{});
    // #endregion
  } catch (err) {
    merchants.value = []
    const payload = err?.response?.data
    const msg = extractErrorMessage(payload, t('agent.merchantAgreedLoadFailed'))
    // #region agent log
    fetch('http://127.0.0.1:7400/ingest/4ebbb499-0df2-4dae-83ef-65d3a7131853',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'ce1e79'},body:JSON.stringify({sessionId:'ce1e79',runId:'post-fix',hypothesisId:'A',location:'AgentMerchant.vue:loadMerchants:err',message:'merchants load failed',data:{status:err?.response?.status||0,code:payload?.code||'',apiMessage:payload?.message||'',toast:msg,url:err?.config?.url||''},timestamp:Date.now()})}).catch(()=>{});
    // #endregion
    ElMessage.error(msg)
  } finally {
    merchantsLoading.value = false
  }
}

onMounted(loadMerchants)
</script>

<style scoped>
.ptitle { margin: 0 0 4px; font-size: 22px; }
.psub { margin: 0 0 16px; color: #8c8c8c; font-size: 13px; }
.merchants-card {
  background: #fff;
  padding: 16px;
  border-radius: 8px;
  margin-top: 16px;
}
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
</style>
