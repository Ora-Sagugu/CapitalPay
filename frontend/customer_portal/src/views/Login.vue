<template>
  <div class="login-wrap">
    <div class="login-card">
      <div class="brand"><span class="capital">Capital</span><span class="pay">Pay</span></div>
      <div class="hello">{{ heading }}</div>
      <el-tabs v-model="mode" class="tabs">
        <el-tab-pane :label="$t('login.tabLogin')" name="login" />
        <el-tab-pane :label="$t('login.tabRegister')" name="register" />
      </el-tabs>
      <el-radio-group v-model="accountType" style="margin-bottom: 16px">
        <el-radio-button value="phone">{{ $t('login.phone') }}</el-radio-button>
        <el-radio-button value="email">{{ $t('login.email') }}</el-radio-button>
      </el-radio-group>
      <el-form :model="form" @submit.prevent="onSubmit">
        <el-form-item v-if="accountType === 'phone'">
          <el-input v-model="form.phone" :placeholder="$t('login.phone')" size="large" />
        </el-form-item>
        <template v-else>
          <el-form-item>
            <el-input v-model="form.email" :placeholder="$t('login.accountPh')" size="large" />
          </el-form-item>
        </template>
        <el-form-item v-if="!useSmsLogin">
          <el-input v-model="form.password" type="password" :placeholder="$t('login.password')" size="large" show-password />
        </el-form-item>
        <el-form-item v-if="accountType === 'phone' && (useSmsLogin || mode === 'register')">
          <div style="display:flex;gap:8px;width:100%">
            <el-input v-model="form.sms_code" :placeholder="$t('login.sms')" size="large" />
            <el-button size="large" :disabled="smsCountdown > 0" :loading="sendingSms" @click="sendSms">
              {{ smsCountdown > 0 ? `${smsCountdown}s` : $t('login.getCode') }}
            </el-button>
          </div>
        </el-form-item>
        <el-form-item v-if="accountType === 'phone' && mode === 'login'">
          <el-checkbox v-model="useSmsLogin">{{ $t('login.smsLogin') }}</el-checkbox>
        </el-form-item>
        <el-button type="primary" size="large" :loading="loading" class="login-btn" @click="onSubmit">
          {{ mode === 'login' ? $t('login.submit') : $t('login.register') }}
        </el-button>
      </el-form>
      <a v-if="switchHref" class="switch-link" :href="switchHref">{{ switchLabel }}</a>
      <div class="hint">{{ hint }}</div>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { getPortalMode, otherPortalUrl } from '@/config/portal'
import { useAuthStore } from '@/store/auth'
import { sendSmsCode } from '@/api/auth'
import { ElMessage } from 'element-plus'

const { t } = useI18n()
const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const mode = ref('login')
const accountType = ref('email')
const useSmsLogin = ref(false)
const loading = ref(false)
const sendingSms = ref(false)
const smsCountdown = ref(0)
const form = reactive({ phone: '', email: '', username: '', password: '', sms_code: '', nickname: '' })

const portalRole = computed(() => (
  route.meta.portalRole === 'agent' || getPortalMode() === 'agent' ? 'agent' : 'customer'
))
const isAgentPortal = computed(() => portalRole.value === 'agent')
const switchHref = computed(() => otherPortalUrl())
const heading = computed(() => {
  if (mode.value === 'login') {
    return isAgentPortal.value ? t('login.helloAgent') : t('login.hello')
  }
  return isAgentPortal.value ? t('login.createAgent') : t('login.create')
})
const hint = computed(() => (isAgentPortal.value ? t('login.hintAgent') : t('login.hint')))
const switchLabel = computed(() => (
  isAgentPortal.value ? t('login.switchCustomer') : t('login.switchAgent')
))

async function sendSms() {
  if (!form.phone) { ElMessage.warning('Enter the mobile number.'); return }
  sendingSms.value = true
  try {
    await sendSmsCode({ phone: form.phone, scene: mode.value === 'register' ? 'register' : 'login' })
    ElMessage.success('The verification code has been sent.')
    smsCountdown.value = 60
    const timer = setInterval(() => { smsCountdown.value -= 1; if (smsCountdown.value <= 0) clearInterval(timer) }, 1000)
  } finally { sendingSms.value = false }
}

async function onSubmit() {
  loading.value = true
  try {
    const role = portalRole.value
    if (mode.value === 'register') {
      if (accountType.value === 'phone') {
        await auth.registerPhone({
          phone: form.phone,
          password: form.password,
          sms_code: form.sms_code,
          nickname: form.nickname,
          portal_role: role
        })
      } else {
        const email = (form.email || '').trim()
        if (!email.toLowerCase().endsWith('@gmail.com')) {
          ElMessage.warning('Only @gmail.com email addresses are allowed.')
          return
        }
        await auth.registerEmail({
          email,
          username: email.split('@')[0],
          password: form.password,
          portal_role: role
        })
      }
      ElMessage.success(role === 'agent' ? 'Agent account created.' : 'Customer account created.')
    } else if (accountType.value === 'phone' && useSmsLogin.value) {
      await auth.loginByPhoneSms(form.phone, form.sms_code, role)
    } else if (accountType.value === 'phone') {
      await auth.loginByPhonePassword(form.phone, form.password, role)
    } else {
      const email = (form.email || '').trim()
      if (!email.toLowerCase().endsWith('@gmail.com')) {
        ElMessage.warning('Only @gmail.com email addresses are allowed.')
        return
      }
      await auth.loginByEmailPassword(email, form.password, role)
    }
    if (mode.value !== 'register') {
      ElMessage.success('Authentication successful.')
    }
    router.replace(auth.homeRoute(route.query.redirect))
  } finally { loading.value = false }
}
</script>

<style scoped>
.login-wrap { min-height: 100vh; display: flex; align-items: center; justify-content: center; background: #f9f7f2; }
.login-card {
  width: 400px; background: #fff; border-radius: 12px; padding: 32px 28px 24px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.06); text-align: center;
}
.brand { font-size: 28px; font-weight: 800; }
.capital { color: #f08040; }
.pay { color: #2c2c2c; }
.hello { color: #9aa0a6; margin: 6px 0 12px; }
.login-btn { width: 100%; }
.switch-link { display: inline-block; margin-top: 16px; color: #f08040; font-size: 13px; }
.hint { margin-top: 12px; color: #c0c4cc; font-size: 12px; }
</style>
