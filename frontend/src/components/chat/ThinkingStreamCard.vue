<template>
  <div :class="['thinking-card', { 'is-done': status === 'done' }]">
    <div class="thinking-head">
      <div class="thinking-head__meta">
        <span class="thinking-pulse" />
        <strong>{{ status === 'done' ? '已整理好思路' : '正在温柔思考' }}</strong>
      </div>

      <button
        v-if="chunks.length > 0"
        class="thinking-toggle focus-ring"
        type="button"
        @click="expanded = !expanded"
      >
        {{ expanded ? '收起' : '查看细节' }}
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
    return props.status === 'done' ? '已经整理好啦' : '正在接住你的情绪线索'
  }
  if (props.status === 'done') {
    return `已经整理好 ${props.chunks.length} 条思路`
  }
  return props.chunks[props.chunks.length - 1]?.content ?? '正在接住你的情绪线索'
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
  position: relative;
  display: inline-grid;
  gap: 9px;
  width: min(100%, 520px);
  padding: 14px 16px;
  border: 1px solid rgba(255, 255, 255, 0.78);
  border-radius: 18px;
  background:
    linear-gradient(135deg, rgba(255, 250, 247, 0.86), rgba(248, 223, 229, 0.72)),
    radial-gradient(circle at 14% 0%, rgba(242, 177, 120, 0.2), transparent 42%);
  color: var(--chat-text-secondary);
  box-shadow: 0 18px 38px rgba(125, 72, 84, 0.12);
  overflow: hidden;
  backdrop-filter: blur(16px);
}

.thinking-card::before {
  position: absolute;
  inset: 0 auto 0 0;
  width: 4px;
  background: linear-gradient(180deg, var(--chat-accent), var(--chat-warm));
  content: "";
}

.thinking-head {
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: 13px;
}

.thinking-head__meta {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  min-width: 0;
}

.thinking-head__meta strong {
  color: var(--chat-accent-strong);
  font-weight: 800;
}

.thinking-toggle {
  min-height: 28px;
  padding: 0 12px;
  border: 1px solid rgba(200, 95, 120, 0.14);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.62);
  color: var(--chat-text-muted);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  transition:
    border-color var(--transition-base),
    color var(--transition-base),
    transform var(--transition-base);
}

.thinking-toggle:hover {
  border-color: rgba(200, 95, 120, 0.32);
  color: var(--chat-accent-strong);
  transform: translateY(-1px);
}

.thinking-pulse {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--chat-accent);
  box-shadow: 0 0 0 6px rgba(200, 95, 120, 0.1);
  animation: pulse 1.2s ease-in-out infinite;
}

.thinking-card.is-done .thinking-pulse {
  background: var(--chat-success);
  box-shadow: 0 0 0 6px rgba(120, 147, 126, 0.12);
  animation: none;
}

.thinking-body {
  padding-left: 18px;
  color: var(--chat-text-muted);
  font-size: 13px;
  line-height: 1.78;
  white-space: pre-wrap;
}

.thinking-lines {
  display: grid;
  gap: 5px;
}

.thinking-lines span {
  position: relative;
  padding-left: 14px;
}

.thinking-lines span::before {
  position: absolute;
  left: 0;
  top: 0.78em;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: rgba(200, 95, 120, 0.42);
  content: "";
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
    opacity: 0.48;
    transform: scale(0.82);
  }

  50% {
    opacity: 1;
    transform: scale(1.08);
  }
}
</style>
