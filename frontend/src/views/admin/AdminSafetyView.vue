<template>
  <div class="admin-page">
    <section class="admin-card">
      <div class="admin-card-header">
        <h2>安全事件</h2>
        <button class="admin-button secondary" type="button" @click="load">刷新</button>
      </div>
      <div class="admin-table-wrap">
        <table class="admin-table">
          <thead>
            <tr>
              <th>用户</th>
              <th>等级</th>
              <th>类型</th>
              <th>动作</th>
              <th>输入快照</th>
              <th>时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="event in events" :key="event.id">
              <td>{{ event.user_id }}</td>
              <td>{{ event.risk_level }}</td>
              <td>{{ event.risk_type }}</td>
              <td>{{ event.action }}</td>
              <td class="text-cell">{{ event.input_snapshot }}</td>
              <td>{{ event.created_at || '-' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { fetchSafetyEvents } from '@/api/admin'
import type { SafetyEvent } from '@/types/admin'

const events = ref<SafetyEvent[]>([])

const load = async () => {
  events.value = await fetchSafetyEvents()
}

onMounted(() => {
  void load()
})
</script>
