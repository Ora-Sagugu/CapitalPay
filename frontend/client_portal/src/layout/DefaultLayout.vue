<template>
  <el-container class="layout">
    <el-aside width="220px">
      <div class="logo">Techtanium</div>
      <el-menu :default-active="activeMenu" router background-color="#001529" text-color="rgba(255,255,255,0.75)" active-text-color="#fff">
        <el-menu-item v-if="can('report:dashboard')" index="/dashboard">
          <el-icon><DataLine /></el-icon><span>仪表盘</span>
        </el-menu-item>

        <el-sub-menu v-if="canAny(['payment:view','payment:create','refund:view'])" index="remittance">
          <template #title><el-icon><List /></el-icon><span>汇款服务</span></template>
          <el-menu-item v-if="can('payment:create')" index="/remittance-apply">汇款申请</el-menu-item>
          <el-menu-item v-if="can('payment:view')" index="/orders">汇款管理</el-menu-item>
          <el-menu-item v-if="can('payment:view')" index="/pre-settlement">预清算管理</el-menu-item>
          <el-menu-item v-if="can('payment:view')" index="/fund-trace">资金追踪</el-menu-item>
          <el-menu-item v-if="can('refund:view')" index="/refunds">退款查询</el-menu-item>
          <el-menu-item v-if="can('payment:view')" index="/exchange-rates">汇率管理</el-menu-item>
        </el-sub-menu>

        <el-sub-menu v-if="canAny(['merchant:view','merchant:approve'])" index="customer">
          <template #title><el-icon><Shop /></el-icon><span>客户</span></template>
          <el-menu-item index="/merchants">客户管理</el-menu-item>
          <el-menu-item index="/deposits">入账管理</el-menu-item>
          <el-menu-item index="/virtual-accounts">账户管理</el-menu-item>
          <el-menu-item index="/user-portal">终端用户</el-menu-item>
        </el-sub-menu>

        <el-sub-menu v-if="can('merchant:view')" index="agent">
          <template #title><el-icon><Shop /></el-icon><span>代理服务</span></template>
          <el-menu-item index="/agents">代理尽调</el-menu-item>
          <el-menu-item index="/agent-extras">代理分润配置</el-menu-item>
        </el-sub-menu>

        <el-sub-menu v-if="canAny(['account:view','settlement:view','reconciliation:view'])" index="account">
          <template #title><el-icon><Wallet /></el-icon><span>账户与资金</span></template>
          <el-menu-item v-if="can('account:view')" index="/fund-transfers">资金调拨</el-menu-item>
          <el-menu-item v-if="can('account:view')" index="/account-extras">Nostro / 其他</el-menu-item>
          <el-menu-item v-if="can('settlement:view')" index="/settlement">结算分润</el-menu-item>
          <el-menu-item v-if="can('reconciliation:view')" index="/reconciliation">对账管理</el-menu-item>
          <el-menu-item v-if="can('settlement:manage')" index="/adjustments">调账管理</el-menu-item>
        </el-sub-menu>

        <el-sub-menu v-if="canAny(['system:view','payment:view'])" index="risk">
          <template #title><el-icon><Stamp /></el-icon><span>合规与银行</span></template>
          <el-menu-item index="/compliance">制裁名单扫描</el-menu-item>
          <el-menu-item index="/channels">银行通道</el-menu-item>
          <el-menu-item index="/params">参数配置</el-menu-item>
        </el-sub-menu>

        <el-menu-item v-if="can('report:view')" index="/reports">
          <el-icon><Document /></el-icon><span>报表服务</span>
        </el-menu-item>

        <el-menu-item v-if="canAny(['system:user','system:role','system:audit'])" index="/system-users">
          <el-icon><Lock /></el-icon><span>系统设置</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header>
        <span class="title">{{ currentTitle }}</span>
        <el-dropdown @command="onCommand">
          <span class="user">
            {{ auth.displayName }}
            <el-icon><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/store/auth'
import { ElMessageBox, ElMessage } from 'element-plus'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const activeMenu = computed(() => route.path)
const currentTitle = computed(() => route.meta.title || '运营后台')

function can(code) {
  return auth.hasPermission(code)
}
function canAny(codes) {
  return codes.some((c) => auth.hasPermission(c))
}

async function onCommand(cmd) {
  if (cmd === 'logout') {
    try {
      await ElMessageBox.confirm('确认退出登录？', '提示', { type: 'warning' })
    } catch (e) {
      return
    }
    await auth.logout()
    ElMessage.success('已退出登录')
    router.replace({ name: 'login' })
  }
}

onMounted(() => {
  auth.fetchMe()
})
</script>

<style scoped>
.layout { height: 100vh; }
.logo {
  height: 56px;
  line-height: 56px;
  text-align: center;
  color: #fff;
  font-size: 18px;
  font-weight: 700;
  background: #000c17;
}
.el-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid #f0f0f0;
}
.title { font-size: 16px; font-weight: 600; }
.user { cursor: pointer; display: inline-flex; align-items: center; gap: 4px; }
.el-aside { overflow-y: auto; }
</style>
