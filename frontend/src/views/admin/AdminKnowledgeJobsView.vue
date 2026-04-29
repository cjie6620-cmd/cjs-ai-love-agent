<template>
  <div class="admin-page">
    <section class="admin-card">
      <div class="admin-card-header">
        <h2>索引任务</h2>
        <div class="admin-toolbar">
          <select v-model="status" class="admin-select">
            <option value="">全部</option>
            <option value="pending">pending</option>
            <option value="running">running</option>
            <option value="succeeded">succeeded</option>
            <option value="failed">failed</option>
            <option value="canceled">canceled</option>
          </select>
          <button class="admin-button" type="button" @click="load">刷新</button>
        </div>
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
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="job in jobs" :key="job.id">
              <td>{{ job.job_type }}</td>
              <td><span :class="['status-pill', job.status]">{{ job.status }}</span></td>
              <td>{{ job.filename || '-' }}</td>
              <td>{{ job.progress }}%</td>
              <td class="text-cell">{{ job.error_message || '-' }}</td>
              <td>
                <div class="admin-actions">
                  <button class="admin-button secondary" type="button" @click="retry(job.id)">重试</button>
                  <button class="admin-button danger" type="button" @click="cancel(job.id)">取消</button>
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

import { cancelKnowledgeJob, fetchKnowledgeJobs, retryKnowledgeJob } from '@/api/admin'
import type { KnowledgeJob } from '@/types/admin'

const jobs = ref<KnowledgeJob[]>([])
const status = ref('')

const load = async () => {
  jobs.value = await fetchKnowledgeJobs({ status: status.value })
}

const retry = async (jobId: string) => {
  await retryKnowledgeJob(jobId)
  await load()
}

const cancel = async (jobId: string) => {
  await cancelKnowledgeJob(jobId)
  await load()
}

onMounted(() => {
  void load()
})
</script>
