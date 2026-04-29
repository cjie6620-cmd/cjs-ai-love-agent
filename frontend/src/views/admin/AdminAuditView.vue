<template>
  <div class="admin-page">
    <section class="admin-card">
      <div class="admin-card-header">
        <h2>审计日志</h2>
        <button class="admin-button secondary" type="button" @click="load">刷新</button>
      </div>
      <div class="admin-table-wrap">
        <table class="admin-table">
          <thead>
            <tr>
              <th>操作人</th>
              <th>动作</th>
              <th>资源</th>
              <th>IP</th>
              <th>时间</th>
              <th>详情</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="event in events" :key="event.id">
              <td>{{ event.actor_user_id || '-' }}</td>
              <td>{{ event.action }}</td>
              <td>{{ event.resource_type }} / {{ event.resource_id || '-' }}</td>
              <td>{{ event.ip || '-' }}</td>
              <td>{{ event.created_at || '-' }}</td>
              <td class="json-cell">{{ JSON.stringify(event.detail_json) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { fetchAuditEvents } from '@/api/admin'
import type { AuditEvent } from '@/types/admin'

const events = ref<AuditEvent[]>([])

const load = async () => {
  events.value = await fetchAuditEvents()
}

onMounted(() => {
  void load()
})
</script>
