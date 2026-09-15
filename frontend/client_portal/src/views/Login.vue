<template>
  <div class="login-wrap">
    <div class="login-card">
      <div class="brand"><span class="capital">Capital</span><span class="pay">Pay</span></div>
      <div class="hello">{{ $t('login.hello') }}</div>
      <el-form :model="form" @submit.prevent="onSubmit">
        <el-form-item>
          <el-input v-model="form.account" :placeholder="$t('login.account')" size="large" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.password" type="password" :placeholder="$t('login.password')" size="large" show-password />
        </el-form-item>
        <el-button type="primary" size="large" :loading="loading" class="login-btn" @click="onSubmit">{{ $t('login.submit') }}</el-button>
      </el-form>
      <div class="hint">{{ $t('login.hint') }}</div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/store/auth'
import { ElMessage, ElMessageBox } from 'element-plus'
import { OPS_FUNCTIONS, canAccessPath, firstAllowedPath } from '@/config/functions'

const { t } = useI18n()
const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const form = reactive({ account: '', password: '' })
const loading = ref(false)

async function onSubmit() {
  if (!form.account || !form.password) {
    ElMessage.warning(t('login.required'))
    return
  }
  loading.value = true
  try {
    const data = await auth.login(form.account, form.password)
    ElMessage.success(t('login.success'))
    const warnings = data?.license_warnings || []
    if (warnings.length) {
      const text = warnings.map((w) => {
        if (typeof w === 'string') return w
        return `${w.merchant_name || w.merchant_no || ''} — the business licence expires on ${w.license_expiry_date || w.expiry || ''} (${w.days_to_expiry ?? w.days ?? '?'} days remaining)`
      }).join('\n')
      await ElMessageBox.alert(text, t('login.licenseTitle'), { type: 'warning', confirmButtonText: t('login.licenseOk') })
    }
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : ''
    const fn = OPS_FUNCTIONS.find((item) => redirect === item.path || redirect.startsWith(`${item.path}/`))
    if (redirect && fn && canAccessPath(data.user, fn.code)) {
      router.replace(redirect)
    } else {
      router.replace(firstAllowedPath(data.user))
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f9f7f2;
}
.login-card {
  width: 380px;
  background: #fff;
  border-radius: 12px;
  padding: 36px 32px 28px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.06);
  text-align: center;
}
.brand { font-size: 28px; font-weight: 800; margin-bottom: 6px; }
.capital { color: #f08040; }
.pay { color: #2c2c2c; }
.hello { color: #9aa0a6; margin-bottom: 24px; font-size: 14px; }
.login-btn { width: 100%; border-radius: 8px; height: 42px; }
.hint { margin-top: 18px; color: #c0c4cc; font-size: 12px; }
</style>
