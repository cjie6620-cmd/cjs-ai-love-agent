<template>
  <div class="admin-page">
    <section class="admin-card">
      <div class="admin-card-header">
        <h2>用户管理</h2>
        <div class="admin-toolbar">
          <input v-model="keyword" class="admin-input" placeholder="搜索账号或昵称" />
          <select v-model="status" class="admin-select">
            <option value="">全部状态</option>
            <option value="active">active</option>
            <option value="disabled">disabled</option>
          </select>
          <button class="admin-button" type="button" @click="load">查询</button>
        </div>
      </div>
      <div class="admin-table-wrap">
        <table class="admin-table">
          <thead>
            <tr>
              <th>账号</th>
              <th>昵称</th>
              <th>状态</th>
              <th>角色</th>
              <th>最后活跃</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in users" :key="user.id">
              <td>{{ user.login_name }}</td>
              <td>{{ user.nickname }}</td>
              <td><span :class="['status-pill', user.status]">{{ user.status }}</span></td>
              <td>{{ user.roles.join(', ') || '-' }}</td>
              <td>{{ user.last_active_at || '-' }}</td>
              <td>
                <div class="admin-actions">
                  <button class="admin-button secondary" type="button" @click="toggleStatus(user)">
                    {{ user.status === 'active' ? '禁用' : '启用' }}
                  </button>
                  <select class="admin-select" @change="assignFromEvent(user.id, $event)">
                    <option value="">分配角色</option>
                    <option v-for="role in roles" :key="role.id" :value="role.id">{{ role.name }}</option>
                  </select>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { assignAdminRole, fetchAdminRoles, fetchAdminUsers, updateAdminUser } from '@/api/admin'
import type { AdminRole, AdminUser } from '@/types/admin'

const users = ref<AdminUser[]>([])
const roles = ref<AdminRole[]>([])
const keyword = ref('')
const status = ref('')

const load = async () => {
  users.value = await fetchAdminUsers({ keyword: keyword.value, status: status.value })
  roles.value = await fetchAdminRoles()
}

const toggleStatus = async (user: AdminUser) => {
  await updateAdminUser(user.id, { status: user.status === 'active' ? 'disabled' : 'active' })
  await load()
}

const assign = async (userId: string, roleId: string) => {
  if (!roleId) {
    return
  }
  await assignAdminRole(userId, roleId)
  await load()
}

const assignFromEvent = async (userId: string, event: Event) => {
  await assign(userId, (event.target as HTMLSelectElement).value)
}

onMounted(() => {
  void load()
})
</script>
