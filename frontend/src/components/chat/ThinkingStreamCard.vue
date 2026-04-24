<template>
  <div :class="['thinking-card', { 'is-done': status === 'done' }]">
    <div class="thinking-head">
      <div class="thinking-head__meta">
        <span class="thinking-pulse" />
        <strong>{{ status === 'done' ? '已思考' : '思考中' }}</strong>
      </div>

      <button
        v-if="chunks.length > 0"
        class="thinking-toggle focus-ring"
        type="button"
        @click="expanded = !expanded"
      >
        {{ expanded ? '收起' : '查看' }}
      </button>
    </div>

    <div class="thinking-body">
      <template v-if="expanded && chunks.length > 0">
        <TransitionGroup name="thinking-line" tag="div" class="thinking-lines">
          <span v-for="chunk in chunks" :key="chunk.id">{{ chunk.content }}</span>
        </TransitionGroup>
      </template>
      <template v-else>
        <span>{{ summaryText }}</span>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type { ThinkingChunk, ThinkingStatus } from '@/types/chat'

const props = defineProps<{
  status: ThinkingStatus
  chunks: ThinkingChunk[]
}>()

const expanded = ref(true)

const summaryText = computed(() => {
  if (props.chunks.length === 0) {
    return props.status === 'done' ? '思考完成' : '正在整理思路'
  }
  if (props.status === 'done') {
    return `已完成思考，共 ${props.chunks.length} 条`
  }
  return props.chunks[props.chunks.length - 1]?.content ?? '正在整理思路'
})

watch(
  () => props.status,
  (nextStatus) => {
    expanded.value = nextStatus !== 'done'
  },
  { immediate: true },
)
</script>

<style scoped>
.thinking-card {
  display: inline-grid;
  gap: 6px;
  width: min(100%, 560px);
  padding: 10px 12px;
  border: 1px solid rgba(123, 162, 255, 0.16);
  background: rgba(34, 40, 50, 0.7);
  color: var(--chat-text-muted);
}

.thinking-head {
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 12px;
}

.thinking-head__meta {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.thinking-toggle {
  min-height: 24px;
  padding: 0 8px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.03);
  color: var(--chat-text-muted);
  font-size: 11px;
  cursor: pointer;
}

.thinking-pulse {
  width: 8px;
  height: 8px;
  background: var(--chat-accent);
  animation: pulse 1.2s ease-in-out infinite;
}

.thinking-card.is-done .thinking-pulse {
  background: var(--chat-success);
  animation: none;
}

.thinking-body {
  font-size: 12px;
  line-height: 1.7;
  white-space: pre-wrap;
}

.thinking-lines {
  display: grid;
  gap: 3px;
}

.thinking-line-enter-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.thinking-line-enter-from {
  opacity: 0;
  transform: translateY(4px);
}

@keyframes pulse {
  0%,
  100% {
    opacity: 0.36;
    transform: scale(0.82);
  }

  50% {
    opacity: 1;
    transform: scale(1);
  }
}
</style>
