<template>
  <el-container class="tech-layout">
    <el-aside width="220px" class="tech-aside">
      <div class="logo">CapitalPay</div>
      <el-menu :default-active="activeMenu" router class="tech-menu">
        <el-menu-item index="/onboarding"><el-icon><Document /></el-icon><span>{{ $t('menu.onboarding') }}</span></el-menu-item>
        <template v-if="auth.isAgent">
          <el-menu-item index="/agent"><el-icon><OfficeBuilding /></el-icon><span>{{ $t('menu.agentOverview') }}</span></el-menu-item>
          <el-menu-item index="/agent/kyc"><el-icon><Stamp /></el-icon><span>{{ $t('menu.agentKyc') }}</span></el-menu-item>
          <el-menu-item index="/agent/orders"><el-icon><Tickets /></el-icon><span>{{ $t('menu.agentOrders') }}</span></el-menu-item>
          <el-menu-item index="/agent/remittance"><el-icon><Promotion /></el-icon><span>{{ $t('menu.agentRemittance') }}</span></el-menu-item>
          <el-menu-item index="/agent/customers"><el-icon><User /></el-icon><span>{{ $t('menu.agentCustomers') }}</span></el-menu-item>
          <el-menu-item index="/agent/account"><el-icon><CreditCard /></el-icon><span>{{ $t('menu.agentAccount') }}</span></el-menu-item>
          <el-menu-item index="/agent/earnings"><el-icon><Coin /></el-icon><span>{{ $t('menu.agentEarnings') }}</span></el-menu-item>
        </template>
        <template v-else>
          <el-menu-item index="/remittance"><el-icon><Promotion /></el-icon><span>{{ $t('menu.remittance') }}</span></el-menu-item>
          <el-menu-item index="/orders"><el-icon><Tickets /></el-icon><span>{{ $t('menu.orders') }}</span></el-menu-item>
          <el-menu-item index="/accounts"><el-icon><Wallet /></el-icon><span>{{ $t('menu.accounts') }}</span></el-menu-item>
          <el-menu-item index="/wallet"><el-icon><Money /></el-icon><span>{{ $t('menu.wallet') }}</span></el-menu-item>
        </template>
      </el-menu>
      <div class="aside-user">
        <el-avatar :size="28" class="avatar">{{ (auth.displayName || 'C').slice(0, 1) }}</el-avatar>
        <div>
          <div class="aside-name">{{ auth.displayName }}</div>
          <div class="aside-role">{{ auth.isAgent ? $t('common.agent') : $t('common.customer') }}</div>
        </div>
      </div>
    </el-aside>
    <el-container>
      <el-header class="tech-header">
        <span class="welcome">{{ $t('common.welcome') }}</span>
        <el-dropdown @command="onCommand">
          <span class="user">{{ auth.displayName }} <el-icon><ArrowDown /></el-icon></span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout">{{ $t('common.logout') }}</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>
      <el-main class="tech-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/store/auth'
import { ElMessageBox, ElMessage } from 'element-plus'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { t } = useI18n()
const activeMenu = computed(() => route.path)

onMounted(async () => {
  await auth.fetchProfile()
})

async function onCommand(cmd) {
  if (cmd === 'logout') {
    await ElMessageBox.confirm(t('common.logoutConfirm'), t('common.hint'), { type: 'warning' })
    const loginName = auth.loginRouteName()
    auth.logout()
    ElMessage.success(t('common.loggedOut'))
    router.replace({ name: loginName })
  }
}
</script>

<style scoped>
.tech-layout { height: 100vh; }
.tech-aside {
  background: linear-gradient(180deg, var(--tech-aside-from, #e07030) 0%, var(--tech-aside-mid, #f5a060) 55%, var(--tech-aside-to, #f7b878) 100%);
  display: flex;
  flex-direction: column;
}
.logo {
  height: 56px; line-height: 56px; text-align: center;
  color: #fff; font-size: 20px; font-weight: 700;
}
.tech-menu {
  border-right: none; background: transparent; flex: 1;
  --el-menu-bg-color: transparent;
  --el-menu-hover-bg-color: rgba(255,255,255,0.18);
  --el-menu-text-color: #fff;
  --el-menu-active-color: #fff;
}
.tech-menu :deep(.el-menu-item.is-active) {
  background: rgba(255,255,255,0.28) !important;
  border-radius: 8px; margin: 0 8px;
}
.aside-user { display: flex; gap: 8px; align-items: center; padding: 12px 16px 16px; color: #fff; }
.avatar { background: #fff; color: #e07030; font-weight: 700; }
.aside-name { font-size: 13px; font-weight: 600; }
.aside-role { font-size: 11px; opacity: 0.85; }
.tech-header {
  background: #fff; display: flex; align-items: center; justify-content: space-between;
  height: 56px; border-bottom: 1px solid #f0ece6; padding: 0 20px;
}
.welcome { color: #666; }
.user { cursor: pointer; display: inline-flex; align-items: center; gap: 4px; margin-left: auto; }
.tech-main { background: var(--tech-page); padding: 20px 24px; overflow: auto; }
</style>
