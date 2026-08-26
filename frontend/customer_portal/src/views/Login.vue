<template>
  <div class="login-wrap">
    <el-card class="login-card">
      <h2>Techtanium 客户门户</h2>

      <el-tabs v-model="mode" class="login-tabs">
        <el-tab-pane label="登录" name="login" />
        <el-tab-pane label="注册" name="register" />
      </el-tabs>

      <el-radio-group v-model="accountType" style="margin-bottom: 16px">
        <el-radio-button value="phone">手机号</el-radio-button>
        <el-radio-button value="email">邮箱</el-radio-button>
      </el-radio-group>

      <el-form :model="form" label-width="0" @submit.prevent="onSubmit">
        <template v-if="accountType === 'phone'">
          <el-form-item>
            <el-input v-model="form.phone" placeholder="手机号" size="large">
              <template #prefix><el-icon><Iphone /></el-icon></template>
            </el-input>
          </el-form-item>
        </template>
        <template v-else>
          <el-form-item v-if="mode === 'register'">
            <el-input v-model="form.username" placeholder="用户名" size="large">
              <template #prefix><el-icon><User /></el-icon></template>
            </el-input>
          </el-form-item>
          <el-form-item>
            <el-input v-model="form.email" placeholder="邮箱" size="large">
              <template #prefix><el-icon><Message /></el-icon></template>
            </el-input>
          </el-form-item>
        </template>

        <el-form-item v-if="!useSmsLogin">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码"
            size="large"
            show-password
          >
            <template #prefix><el-icon><Lock /></el-icon></template>
          </el-input>
        </el-form-item>

        <template v-if="accountType === 'phone' && (useSmsLogin || mode === 'register')">
          <el-form-item>
            <div style="display: flex; gap: 8px; width: 100%">
              <el-input v-model="form.sms_code" placeholder="短信验证码" size="large" />
              <el-button
                size="large"
                :disabled="smsCountdown > 0"
                :loading="sendingSms"
                @click="sendSms"
              >
                {{ smsCountdown > 0 ? `${smsCountdown}s` : '获取验证码' }}
              </el-button>
            </div>
          </el-form-item>
        </template>

        <el-form-item v-if="accountType === 'phone' && mode === 'login'">
          <el-checkbox v-model="useSmsLogin">使用短信验证码登录</el-checkbox>
        </el-form-item>

        <el-form-item v-if="mode === 'register' && accountType === 'phone'">
          <el-input v-model="form.nickname" placeholder="昵称（可选）" size="large" />
        </el-form-item>

        <el-button type="primary" size="large" :loading="loading" style="width: 100%" @click="onSubmit">
          {{ mode === 'login' ? '登录' : '注册' }}
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/store/auth'
import { sendSmsCode } from '@/api/auth'
import { ElMessage } from 'element-plus'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const mode = ref('login')
const accountType = ref('phone')
const useSmsLogin = ref(false)
const loading = ref(false)
const sendingSms = ref(false)
const smsCountdown = ref(0)

const form = reactive({
  phone: '',
  email: '',
  username: '',
  password: '',
  sms_code: '',
  nickname: ''
})

let smsTimer = null

watch(accountType, () => {
  useSmsLogin.value = false
})

watch(mode, () => {
  useSmsLogin.value = false
})

async function sendSms() {
  if (!form.phone) {
    ElMessage.warning('请输入手机号')
    return
  }
  sendingSms.value = true
  try {
    const scene = mode.value === 'register' ? 'REGISTER' : useSmsLogin.value ? 'LOGIN' : 'REGISTER'
    await sendSmsCode({ phone: form.phone, scene })
    ElMessage.success('验证码已发送')
    smsCountdown.value = 60
    smsTimer = setInterval(() => {
      smsCountdown.value -= 1
      if (smsCountdown.value <= 0) clearInterval(smsTimer)
    }, 1000)
  } finally {
    sendingSms.value = false
  }
}

async function onSubmit() {
  loading.value = true
  try {
    if (mode.value === 'login') {
      if (accountType.value === 'phone') {
        if (useSmsLogin.value) {
          if (!form.phone || !form.sms_code) {
            ElMessage.warning('请输入手机号和验证码')
            return
          }
          await auth.loginByPhoneSms(form.phone, form.sms_code)
        } else {
          if (!form.phone || !form.password) {
            ElMessage.warning('请输入手机号和密码')
            return
          }
          await auth.loginByPhonePassword(form.phone, form.password)
        }
      } else {
        if (!form.email || !form.password) {
          ElMessage.warning('请输入邮箱和密码')
          return
        }
        await auth.loginByEmailPassword(form.email, form.password)
      }
    } else {
      if (accountType.value === 'phone') {
        if (!form.phone || !form.password) {
          ElMessage.warning('请输入手机号和密码')
          return
        }
        await auth.registerPhone({
          phone: form.phone,
          password: form.password,
          sms_code: form.sms_code || undefined,
          nickname: form.nickname || undefined
        })
      } else {
        if (!form.username || !form.email || !form.password) {
          ElMessage.warning('请填写用户名、邮箱和密码')
          return
        }
        await auth.registerEmail({
          username: form.username,
          email: form.email,
          password: form.password
        })
      }
    }
    ElMessage.success(mode.value === 'login' ? '登录成功' : '注册成功')
    const redirect = route.query.redirect || '/orders'
    router.replace(redirect)
  } finally {
    loading.value = false
  }
}
</script>
