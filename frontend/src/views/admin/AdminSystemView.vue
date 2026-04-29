<template>
  <div class="admin-page">
    <section class="admin-card">
      <div class="admin-card-header">
        <h2>系统状态</h2>
        <button class="admin-button secondary" type="button" @click="load">刷新</button>
      </div>
      <div class="admin-card-body">
        <p>{{ health?.summary || '暂无健康检查摘要' }}</p>
      </div>
      <div class="admin-table-wrap">
        <table class="admin-table">
          <thead>
            <tr>
              <th>依赖</th>
              <th>状态</th>
              <th>端点</th>
              <th>详情</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in health?.dependencies ?? []" :key="item.name">
              <td>{{ item.name }}</td>
              <td><span :class="['status-pill', item.status]">{{ item.status }}</span></td>
              <td>{{ item.endpoint }}</td>
              <td class="text-cell">{{ item.detail }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="admin-card">
      <div class="admin-card-header"><h2>配置摘要</h2></div>
      <div class="admin-card-body json-cell">{{ JSON.stringify(config, null, 2) }}</div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { fetchSystemConfig, fetchSystemHealth } from '@/api/admin'

const health = ref<{ summary: string; dependencies: Array<Record<string, string>> } | null>(null)
const config = ref<Record<string, unknown>>({})

const load = async () => {
  const [healthResult, configResult] = await Promise.all([fetchSystemHealth(), fetchSystemConfig()])
  health.value = healthResult
  config.value = configResult
}

onMounted(() => {
  void load()
})
</script>
