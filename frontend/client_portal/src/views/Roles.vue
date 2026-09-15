<template>
  <div>
    <PageHeader title="Roles" subtitle-key="pages.roles.subtitle" />
    <el-row :gutter="12" class="role-grid">
      <el-col v-for="card in roles" :key="card.code" :xs="24" :sm="12" :md="6">
        <button
          type="button"
          class="role-card"
          :class="{ active: selectedCode === card.code, locked: card.locked }"
          @click="selectedCode = card.code"
        >
          <div class="role-top">
            <span class="role-name">{{ card.name }}</span>
            <el-tag size="small" :type="card.locked ? 'danger' : 'warning'" effect="plain">
              {{ $t('pages.roles.functions', { n: card.capability_count || 0 }) }}
            </el-tag>
          </div>
          <p>{{ card.description }}</p>
        </button>
      </el-col>
    </el-row>

    <div class="page-card">
      <div class="toolbar">
        <span class="hint">{{ selectedRole?.locked ? $t('pages.roles.lockedHint') : $t('pages.roles.hint') }}</span>
        <el-button @click="load">{{ $t('pages.roles.refresh') }}</el-button>
      </div>
      <div v-loading="loading">
        <div v-for="group in groups" :key="group.group || 'root'" class="fn-group">
          <div class="fn-group-head">
            <div v-if="group.group_name" class="fn-group-title">{{ group.group_name }}</div>
            <div v-else class="fn-group-title">{{ $t('menu.dashboard') }}</div>
            <div v-if="selectedRole && !selectedRole.locked" class="fn-group-actions">
              <el-button link type="primary" @click="setGroup(group, true)">{{ $t('pages.roles.selectAll') }}</el-button>
              <el-button link @click="setGroup(group, false)">{{ $t('pages.roles.clearAll') }}</el-button>
            </div>
          </div>
          <div v-for="cap in group.capabilities" :key="cap.code" class="fn-row">
            <el-checkbox
              :model-value="isChecked(cap.code)"
              :disabled="!selectedRole || selectedRole.locked || saving"
              @change="(checked) => toggle(cap, checked)"
            >
              <span class="fn-name">{{ cap.name }}</span>
            </el-checkbox>
            <span class="fn-path">{{ cap.path }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import { getFunctions, setRoleCapabilities } from '@/api/rbac'

const { t } = useI18n()
const roles = ref([])
const groups = ref([])
const loading = ref(false)
const saving = ref(false)
const selectedCode = ref('super_admin')

const selectedRole = computed(() => roles.value.find((r) => r.code === selectedCode.value) || null)
const selectedCodes = computed(() => new Set(selectedRole.value?.capability_codes || []))

function isChecked(code) {
  if (selectedRole.value?.locked) return true
  return selectedCodes.value.has(code)
}

async function load() {
  loading.value = true
  try {
    const data = await getFunctions()
    roles.value = data.roles || []
    groups.value = data.groups || []
    if (!roles.value.some((r) => r.code === selectedCode.value)) {
      selectedCode.value = roles.value[0]?.code || 'super_admin'
    }
  } finally {
    loading.value = false
  }
}

async function persist(nextCodes, message) {
  const role = selectedRole.value
  if (!role || role.locked || !role.id) return
  saving.value = true
  const previous = [...(role.capability_codes || [])]
  role.capability_codes = nextCodes
  role.capability_count = nextCodes.length
  try {
    const data = await setRoleCapabilities(role.id, { capability_codes: nextCodes })
    role.capability_codes = data.capability_codes || nextCodes
    role.capability_count = role.capability_codes.length
    if (message) ElMessage.success(message)
  } catch (err) {
    role.capability_codes = previous
    role.capability_count = previous.length
    throw err
  } finally {
    saving.value = false
  }
}

async function toggle(cap, checked) {
  const role = selectedRole.value
  if (!role || role.locked) return
  const current = new Set(role.capability_codes || [])
  if (checked) current.add(cap.code)
  else current.delete(cap.code)
  const next = [...current]
  await persist(next, t(checked ? 'pages.roles.saved' : 'pages.roles.removed', {
    role: role.name,
    name: cap.name
  }))
}

async function setGroup(group, enabled) {
  const role = selectedRole.value
  if (!role || role.locked) return
  const groupCodes = (group.capabilities || []).map((c) => c.code)
  const kept = (role.capability_codes || []).filter((code) => !groupCodes.includes(code))
  const next = enabled ? [...kept, ...groupCodes] : kept
  await persist(next, t('pages.roles.groupUpdated', {
    role: role.name,
    group: group.group_name || t('menu.dashboard')
  }))
}

onMounted(load)
</script>

<style scoped>
.role-grid { margin-bottom: 14px; }
.role-card {
  display: block;
  width: 100%;
  text-align: left;
  background: #fff;
  border: 1px solid transparent;
  border-radius: 10px;
  padding: 14px 16px;
  margin-bottom: 12px;
  min-height: 96px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.04);
  cursor: pointer;
}
.role-card.active {
  border-color: var(--tech-orange);
  box-shadow: 0 0 0 1px var(--tech-orange);
}
.role-top { display: flex; justify-content: space-between; align-items: center; }
.role-name { font-weight: 700; }
.role-card p { margin: 8px 0 0; color: #8c8c8c; font-size: 12px; line-height: 1.5; }
.hint { color: #8c8c8c; font-size: 13px; }
.fn-group { margin-bottom: 18px; }
.fn-group-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 8px 0 6px;
}
.fn-group-title {
  font-weight: 700;
  font-size: 13px;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.fn-group-actions { display: flex; gap: 4px; }
.fn-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}
.fn-name { font-weight: 600; }
.fn-path { color: #999; font-size: 12px; }
</style>
