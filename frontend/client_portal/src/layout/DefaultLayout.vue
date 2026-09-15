<template>
  <el-container class="tech-layout">
    <el-aside :width="collapsed ? '72px' : '232px'" class="tech-aside">
      <div class="logo">{{ collapsed ? 'C' : 'CapitalPay' }}</div>
      <el-menu
        :default-active="activeMenu"
        :collapse="collapsed"
        :collapse-transition="false"
        router
        class="tech-menu"
      >
        <el-menu-item v-if="can('feature:dashboard')" index="/dashboard">
          <el-icon><Odometer /></el-icon><span>{{ $t('menu.dashboard') }}</span>
        </el-menu-item>

        <el-menu-item v-if="can('feature:reports')" index="/reports">
          <el-icon><DataAnalysis /></el-icon><span>{{ $t('menu.reports') }}</span>
        </el-menu-item>

        <el-menu-item v-if="can('feature:wallet')" index="/wallet">
          <el-icon><Wallet /></el-icon><span>{{ $t('menu.wallet') }}</span>
        </el-menu-item>

        <el-sub-menu v-if="canAny(['feature:merchants','feature:virtual_accounts','feature:deposits'])" index="customer">
          <template #title><el-icon><User /></el-icon><span>{{ $t('menu.customer') }}</span></template>
          <el-menu-item v-if="can('feature:merchants')" index="/merchants">{{ $t('menu.merchants') }}</el-menu-item>
          <el-menu-item v-if="can('feature:virtual_accounts')" index="/virtual-accounts">{{ $t('menu.virtualAccounts') }}</el-menu-item>
          <el-menu-item v-if="can('feature:deposits')" index="/deposits">{{ $t('menu.deposits') }}</el-menu-item>
        </el-sub-menu>

        <el-sub-menu v-if="canAny(['feature:fund_trace','feature:orders','feature:pre_orders','feature:refunds','feature:exchange_rates','feature:remittance_fees'])" index="remittance">
          <template #title><el-icon><Promotion /></el-icon><span>{{ $t('menu.remittance') }}</span></template>
          <el-menu-item v-if="can('feature:fund_trace')" index="/fund-trace">{{ $t('menu.fundTrace') }}</el-menu-item>
          <el-menu-item v-if="can('feature:orders')" index="/orders">{{ $t('menu.orders') }}</el-menu-item>
          <el-menu-item v-if="can('feature:pre_orders')" index="/pre-orders">{{ $t('menu.preOrders') }}</el-menu-item>
          <el-menu-item v-if="can('feature:refunds')" index="/refunds">{{ $t('menu.refunds') }}</el-menu-item>
          <el-menu-item v-if="can('feature:exchange_rates')" index="/exchange-rates">{{ $t('menu.exchange') }}</el-menu-item>
          <el-menu-item v-if="can('feature:remittance_fees')" index="/remittance-fees">{{ $t('menu.remittanceFees') }}</el-menu-item>
        </el-sub-menu>

        <el-sub-menu v-if="canAny(['feature:agents','feature:agent_fees','feature:disbursements'])" index="agent">
          <template #title><el-icon><Briefcase /></el-icon><span>{{ $t('menu.agent') }}</span></template>
          <el-menu-item v-if="can('feature:agents')" index="/agents">{{ $t('menu.agents') }}</el-menu-item>
          <el-menu-item v-if="can('feature:agent_fees')" index="/agent-fees">{{ $t('menu.agentFees') }}</el-menu-item>
          <el-menu-item v-if="can('feature:disbursements')" index="/disbursements">{{ $t('menu.disbursements') }}</el-menu-item>
        </el-sub-menu>

        <el-sub-menu v-if="canAny(['feature:banks','feature:accounts','feature:params','feature:bank_notifications','feature:reconciliation','feature:fund_transfers','feature:adjustments'])" index="bank">
          <template #title><el-icon><OfficeBuilding /></el-icon><span>{{ $t('menu.bank') }}</span></template>
          <el-menu-item v-if="can('feature:banks')" index="/banks">{{ $t('menu.banks') }}</el-menu-item>
          <el-menu-item v-if="can('feature:accounts')" index="/accounts">{{ $t('menu.accounts') }}</el-menu-item>
          <el-menu-item v-if="can('feature:params')" index="/params">{{ $t('menu.params') }}</el-menu-item>
          <el-menu-item v-if="can('feature:bank_notifications')" index="/bank-notifications">{{ $t('menu.bankNotifications') }}</el-menu-item>
          <el-menu-item v-if="can('feature:reconciliation')" index="/reconciliation">{{ $t('menu.reconciliation') }}</el-menu-item>
          <el-menu-item v-if="can('feature:fund_transfers')" index="/fund-transfers">{{ $t('menu.fundTransfers') }}</el-menu-item>
          <el-menu-item v-if="can('feature:adjustments')" index="/adjustments">{{ $t('menu.adjustments') }}</el-menu-item>
        </el-sub-menu>

        <el-sub-menu v-if="canAny(['feature:sanctions','feature:scans','feature:risk_rating'])" index="sanction">
          <template #title><el-icon><Warning /></el-icon><span>{{ $t('menu.sanction') }}</span></template>
          <el-menu-item v-if="can('feature:sanctions')" index="/sanctions">{{ $t('menu.sanctions') }}</el-menu-item>
          <el-menu-item v-if="can('feature:scans')" index="/scans">{{ $t('menu.scans') }}</el-menu-item>
          <el-menu-item v-if="can('feature:risk_rating')" index="/risk-rating">{{ $t('menu.riskRating') }}</el-menu-item>
        </el-sub-menu>

        <el-sub-menu v-if="canAny(['feature:roles','feature:users'])" index="system">
          <template #title><el-icon><Setting /></el-icon><span>{{ $t('menu.system') }}</span></template>
          <el-menu-item v-if="can('feature:roles')" index="/roles">{{ $t('menu.roles') }}</el-menu-item>
          <el-menu-item v-if="can('feature:users')" index="/users">{{ $t('menu.users') }}</el-menu-item>
        </el-sub-menu>
      </el-menu>

      <div v-if="!collapsed" class="aside-user">
        <el-avatar :size="28" class="aside-avatar">{{ avatarLetter }}</el-avatar>
        <div>
          <div class="aside-name">{{ auth.user?.username || 'admin' }}</div>
          <div class="aside-role">{{ roleLabel }}</div>
        </div>
      </div>
    </el-aside>

    <el-container>
      <el-header class="tech-header">
        <div class="header-left">
          <el-icon class="hamburger" @click="collapsed = !collapsed"><Fold v-if="!collapsed" /><Expand v-else /></el-icon>
          <span class="welcome">{{ $t('common.welcome') }}</span>
        </div>
        <div class="header-right">
          <el-icon class="bell"><ChatDotSquare /></el-icon>
          <el-dropdown @command="onCommand">
            <span class="user">
              <el-avatar :size="24" class="aside-avatar">{{ avatarLetter }}</el-avatar>
              {{ auth.user?.username || auth.displayName }}
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">{{ $t('common.logout') }}</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      <el-main class="tech-main">
        <router-view />
      </el-main>
    </el-container>
    <ChatFab />
  </el-container>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/store/auth'
import { ElMessageBox, ElMessage } from 'element-plus'
import ChatFab from '@/components/ChatFab.vue'
import { ROLE_NAME } from '@/utils/format'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { t } = useI18n()
const collapsed = ref(false)

const activeMenu = computed(() => {
  if (route.path.startsWith('/agent-fees')) return '/agent-fees'
  return route.path
})
const avatarLetter = computed(() => (auth.user?.username || 'A').slice(0, 1).toUpperCase())
const roleLabel = computed(() => {
  const roles = auth.roles || []
  const code = roles[0]?.code || roles[0] || 'super_admin'
  return ROLE_NAME[code] || code
})

function can(code) {
  return auth.hasPageAccess(code)
}
function canAny(codes) {
  return codes.some((c) => auth.hasPageAccess(c))
}

async function onCommand(cmd) {
  if (cmd === 'logout') {
    try {
      await ElMessageBox.confirm(t('common.logoutConfirm'), t('common.hint'), { type: 'warning' })
    } catch {
      return
    }
    await auth.logout()
    ElMessage.success(t('common.loggedOut'))
    router.replace({ name: 'login' })
  }
}

onMounted(() => {
  auth.fetchMe()
})
</script>

<style scoped>
.tech-layout { height: 100vh; }
.tech-aside {
  background: linear-gradient(180deg, var(--tech-aside-from, #e07030) 0%, var(--tech-aside-mid, #f5a060) 55%, var(--tech-aside-to, #f7b878) 100%);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: width 0.2s;
}
.logo {
  height: 56px;
  line-height: 56px;
  text-align: center;
  color: #fff;
  font-size: 20px;
  font-weight: 700;
  letter-spacing: 0.5px;
  flex-shrink: 0;
}
.tech-menu {
  border-right: none;
  background: transparent;
  flex: 1;
  overflow-y: auto;
  --el-menu-bg-color: transparent;
  --el-menu-hover-bg-color: rgba(255, 255, 255, 0.18);
  --el-menu-text-color: rgba(255, 255, 255, 0.92);
  --el-menu-active-color: #fff;
  --el-menu-item-height: 44px;
}
.tech-menu :deep(.el-menu-item.is-active) {
  background: rgba(255, 255, 255, 0.28) !important;
  border-radius: 8px;
  margin: 0 8px;
}
.tech-menu :deep(.el-sub-menu__title),
.tech-menu :deep(.el-menu-item) {
  color: #fff;
}
.tech-menu :deep(.el-sub-menu .el-menu) {
  background: transparent !important;
}
.aside-user {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px 16px;
  color: #fff;
  flex-shrink: 0;
}
.aside-avatar { background: #fff; color: #e07030; font-weight: 700; }
.aside-name { font-size: 13px; font-weight: 600; }
.aside-role { font-size: 11px; opacity: 0.85; }
.tech-header {
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
  border-bottom: 1px solid #f0ece6;
  padding: 0 20px;
}
.header-left, .header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.hamburger { cursor: pointer; font-size: 18px; }
.welcome { color: #666; font-size: 14px; }
.bell { font-size: 18px; color: #666; }
.user { cursor: pointer; display: inline-flex; align-items: center; gap: 6px; }
.tech-main {
  background: var(--tech-page);
  padding: 20px 24px 40px;
  overflow: auto;
}
</style>
