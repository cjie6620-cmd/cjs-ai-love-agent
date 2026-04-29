<template>
  <div class="admin-page">
    <section class="admin-card">
      <div class="admin-card-header">
        <h2>角色权限</h2>
        <button class="admin-button secondary" type="button" @click="resetForm">新建角色</button>
      </div>
      <div class="admin-card-body">
        <div class="admin-toolbar">
          <input v-model="form.code" class="admin-input" placeholder="角色编码" />
          <input v-model="form.name" class="admin-input" placeholder="角色名称" />
          <input v-model="form.description" class="admin-input" placeholder="描述" />
          <button class="admin-button" type="button" @click="saveRole">保存角色</button>
        </div>
        <div class="permission-grid">
          <label v-for="permission in permissions" :key="permission.code" class="permission-item">
            <input v-model="form.permissions" type="checkbox" :value="permission.code" />
            <span>{{ permission.name }}</span>
            <small>{{ permission.code }}</small>
          </label>
        </div>
      </div>
    </section>

    <section class="admin-card">
      <div class="admin-card-header">
        <h2>角色列表</h2>
      </div>
      <div class="admin-table-wrap">
        <table class="admin-table">
          <thead>
            <tr>
              <th>编码</th>
              <th>名称</th>
              <th>系统角色</th>
              <th>权限</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="role in roles" :key="role.id">
              <td>{{ role.code }}</td>
              <td>{{ role.name }}</td>
              <td>{{ role.is_system ? '是' : '否' }}</td>
              <td class="text-cell">{{ role.permissions.join(', ') }}</td>
              <td><button class="admin-button secondary" type="button" @click="editRole(role)">编辑</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { fetchAdminPermissions, fetchAdminRoles, saveAdminRole } from '@/api/admin'
import type { AdminPermission, AdminRole } from '@/types/admin'

const roles = ref<AdminRole[]>([])
const permissions = ref<AdminPermission[]>([])
const editingRoleId = ref('')
const form = reactive({
  code: '',
  name: '',
  description: '',
  permissions: [] as string[],
})

const load = async () => {
  const [roleItems, permissionItems] = await Promise.all([fetchAdminRoles(), fetchAdminPermissions()])
  roles.value = roleItems
  permissions.value = permissionItems
}

const resetForm = () => {
  editingRoleId.value = ''
  form.code = ''
  form.name = ''
  form.description = ''
  form.permissions = []
}

const editRole = (role: AdminRole) => {
  editingRoleId.value = role.id
  form.code = role.code
  form.name = role.name
  form.description = role.description
  form.permissions = [...role.permissions]
}

const saveRole = async () => {
  await saveAdminRole(
    {
      code: form.code,
      name: form.name,
      description: form.description,
      permissions: form.permissions,
    },
    editingRoleId.value || undefined,
  )
  resetForm()
  await load()
}

onMounted(() => {
  void load()
})
</script>

<style scoped>
.permission-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 8px;
  margin-top: 14px;
}

.permission-item {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 4px 8px;
  align-items: center;
  padding: 10px;
  border: 1px solid #dfe5eb;
  border-radius: 8px;
}

.permission-item small {
  grid-column: 2;
  color: #667789;
}
</style>
