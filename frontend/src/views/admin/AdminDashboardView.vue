<template>
  <div class="admin-page">
    <section class="admin-grid">
      <div v-for="item in metricItems" :key="item.label" class="metric-card">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </div>
    </section>

    <section class="admin-card">
      <div class="admin-card-header">
        <h2>最近索引任务</h2>
        <button class="admin-button secondary" type="button" @click="load">刷新</button>
      </div>
      <div class="admin-table-wrap">
        <table class="admin-table">
          <thead>
            <tr>
              <th>类型</th>
              <th>状态</th>
              <th>文件</th>
              <th>进度</th>
              <th>错误</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="job in dashboard?.recent_jobs ?? []" :key="job.id">
              <td>{{ job.job_type }}</td>
              <td><span :class="['status-pill', job.status]">{{ job.status }}</span></td>
              <td>{{ job.filename || '-' }}</td>
              <td>{{ job.progress }}%</td>
              <td class="text-cell">{{ job.error_message || '-' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="admin-card">
      <div class="admin-card-header">
        <h2>最近安全事件</h2>
      </div>
      <div class="admin-table-wrap">
        <table class="admin-table">
          <thead>
            <tr>
              <th>等级</th>
              <th>类型</th>
              <th>动作</th>
              <th>输入快照</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="event in dashboard?.recent_safety_events ?? []" :key="event.id">
              <td>{{ event.risk_level }}</td>
              <td>{{ event.risk_type }}</td>
              <td>{{ event.action }}</td>
              <td class="text-cell">{{ event.input_snapshot }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { fetchAdminDashboard } from '@/api/admin'
import type { AdminDashboard } from '@/types/admin'

const dashboard = ref<AdminDashboard | null>(null)

const metricItems = computed(() => [
  { label: '用户数', value: dashboard.value?.metrics.users ?? 0 },
  { label: '知识文档', value: dashboard.value?.metrics.knowledge_documents ?? 0 },
  { label: '运行任务', value: dashboard.value?.metrics.running_jobs ?? 0 },
  { label: '失败任务', value: dashboard.value?.metrics.failed_jobs ?? 0 },
  { label: '会话数', value: dashboard.value?.metrics.conversations ?? 0 },
])

const load = async () => {
  dashboard.value = await fetchAdminDashboard()
}

onMounted(() => {
  void load()
})
</script>
