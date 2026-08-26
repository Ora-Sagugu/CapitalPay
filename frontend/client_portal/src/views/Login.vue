<template>
  <div class="login-wrap">
    <el-card class="login-card">
      <h2>Techtanium 运营后台</h2>
      <el-form :model="form" @submit.prevent="onSubmit">
        <el-form-item>
          <el-input v-model="form.account" placeholder="账号 / 邮箱" size="large">
            <template #prefix><el-icon><User /></el-icon></template>
          </el-input>
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.password" type="password" placeholder="密码" size="large" show-password>
            <template #prefix><el-icon><Lock /></el-icon></template>
          </el-input>
        </el-form-item>
        <el-button type="primary" size="large" :loading="loading" style="width: 100%" @click="onSubmit">
          登录
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/store/auth'
import { ElMessage, ElMessageBox } from 'element-plus'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const form = reactive({ account: '', password: '' })
const loading = ref(false)

async function onSubmit() {
  if (!form.account || !form.password) {
    ElMessage.warning('请输入账号和密码')
    return
  }
  loading.value = true
  try {
    const data = await auth.login(form.account, form.password)
    ElMessage.success('登录成功')
    const warnings = data?.license_warnings || []
    if (warnings.length) {
      const text = warnings.map((w) => {
        if (typeof w === 'string') return w
        return `${w.merchant_name || w.merchant_no || ''} 执照将于 ${w.license_expiry_date || w.expiry || ''} 到期（剩余 ${w.days_to_expiry ?? w.days ?? '?'} 天）`
      }).join('\n')
      await ElMessageBox.alert(text, '营业执照到期提醒', { type: 'warning', confirmButtonText: '已知晓' })
    }
    const redirect = route.query.redirect || '/dashboard'
    router.replace(redirect)
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
  background: linear-gradient(135deg, #001529 0%, #003a8c 100%);
}
.login-card {
  width: 400px;
  padding: 12px 8px 24px;
}
.login-card h2 {
  text-align: center;
  margin-bottom: 24px;
}
</style>
