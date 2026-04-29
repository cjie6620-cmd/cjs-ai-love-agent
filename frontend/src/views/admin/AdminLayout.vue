<template>
  <div class="admin-shell">
    <aside class="admin-sidebar">
      <RouterLink class="admin-brand" to="/admin/dashboard">
        <span class="brand-mark">AL</span>
        <strong>Agent Admin</strong>
      </RouterLink>
      <nav class="admin-nav" aria-label="管理员导航">
        <RouterLink v-for="item in menu" :key="item.path" :to="item.path">
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>
    </aside>

    <section class="admin-main">
      <header class="admin-header">
        <div>
          <span class="eyebrow">Enterprise Console</span>
          <h1>{{ currentTitle }}</h1>
        </div>
        <div class="admin-identity">
          <span>{{ adminName }}</span>
          <small>{{ tenantId }}</small>
          <button type="button" @click="handleLogout">退出</button>
        </div>
      </header>
      <RouterView />
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { fetchAdminMe } from '@/api/admin'
import { logout } from '@/api/auth'

const route = useRoute()
const router = useRouter()

const adminName = ref('管理员')
const tenantId = ref('default')

const menu = [
  { label: '仪表盘', path: '/admin/dashboard' },
  { label: '用户管理', path: '/admin/users' },
  { label: '角色权限', path: '/admin/roles' },
  { label: '知识库管理', path: '/admin/knowledge/documents' },
  { label: '索引任务', path: '/admin/knowledge/jobs' },
  { label: '审计日志', path: '/admin/audit' },
  { label: '安全事件', path: '/admin/safety' },
  { label: '系统状态', path: '/admin/system' },
]

const currentTitle = computed(() => {
  const matched = menu.find((item) => route.path.startsWith(item.path))
  return matched?.label ?? '管理员后台'
})

const handleLogout = async () => {
  await logout()
  await router.replace('/chat')
}

onMounted(async () => {
  const result = await fetchAdminMe()
  adminName.value = result.user.nickname || result.user.login_name
  tenantId.value = result.user.tenant_id
})
</script>

<style scoped>
.admin-shell {
  display: grid;
  grid-template-columns: 248px minmax(0, 1fr);
  width: 100%;
  min-height: 100dvh;
  background: #eef1f4;
  color: #17202a;
  font-family: "PingFang SC", "Microsoft YaHei", sans-serif;
}

.admin-sidebar {
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding: 22px 16px;
  background: #141a21;
  color: #f6f8fb;
}

.admin-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px;
}

.brand-mark {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: #d3f36b;
  color: #111820;
  font-weight: 800;
}

.admin-nav {
  display: grid;
  gap: 6px;
}

.admin-nav a {
  padding: 11px 12px;
  border-radius: 8px;
  color: rgba(246, 248, 251, 0.72);
  font-size: 14px;
}

.admin-nav a.router-link-active,
.admin-nav a:hover {
  background: rgba(211, 243, 107, 0.12);
  color: #ffffff;
}

.admin-main {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  min-width: 0;
  padding: 22px;
  overflow: auto;
}

.admin-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.eyebrow {
  color: #5f6f7f;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}

h1 {
  margin: 4px 0 0;
  font-size: 24px;
  letter-spacing: 0;
}

.admin-identity {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border: 1px solid #d7dde3;
  border-radius: 8px;
  background: #ffffff;
}

.admin-identity small {
  color: #687684;
}

.admin-identity button {
  border: 0;
  border-radius: 6px;
  padding: 6px 10px;
  background: #17202a;
  color: #ffffff;
  cursor: pointer;
}

@media (max-width: 860px) {
  .admin-shell {
    grid-template-columns: 1fr;
  }

  .admin-sidebar {
    position: static;
  }
}
</style>
