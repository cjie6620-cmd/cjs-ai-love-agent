<template>
  <section class="chat-header">
    <div class="chat-header__main">
      <p class="chat-header__meta">
        <span :class="['status-dot', { 'is-online': serviceReady }]" />
        {{ serviceReady ? '系统在线' : '服务待连接' }}
      </p>
      <h1 class="chat-header__title">{{ conversationTitle }}</h1>
      <p class="chat-header__subtitle">{{ activeModeLabel }}模式</p>
    </div>

    <button class="chat-header__action focus-ring" type="button" @click="$emit('new-chat')">
      新对话
    </button>
  </section>
</template>

<script setup lang="ts">
defineProps<{
  activeModeLabel: string
  conversationTitle: string
  serviceReady: boolean
}>()

defineEmits<{
  (event: 'new-chat'): void
}>()
</script>

<style scoped>
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 24px 18px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(17, 20, 27, 0.9);
}

.chat-header__main {
  min-width: 0;
}

.chat-header__meta {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 8px;
  color: var(--chat-text-muted);
  font-size: 12px;
  font-weight: 600;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: rgba(137, 148, 168, 0.7);
}

.status-dot.is-online {
  background: var(--chat-success);
  box-shadow: 0 0 0 6px rgba(92, 180, 122, 0.12);
}

.chat-header__title {
  margin: 0;
  color: var(--chat-text-primary);
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.chat-header__subtitle {
  margin: 6px 0 0;
  color: var(--chat-text-muted);
  font-size: 13px;
}

.chat-header__action {
  min-width: 92px;
  height: 38px;
  padding: 0 16px;
  border: 1px solid var(--chat-line);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.03);
  color: var(--chat-text-primary);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition:
    border-color var(--transition-base),
    background var(--transition-base),
    transform var(--transition-base);
}

.chat-header__action:hover {
  border-color: rgba(123, 162, 255, 0.42);
  background: rgba(123, 162, 255, 0.08);
  transform: translateY(-1px);
}

@media (max-width: 760px) {
  .chat-header {
    align-items: flex-start;
    flex-direction: column;
    padding: 16px 16px 14px;
  }

  .chat-header__action {
    width: 100%;
  }

  .chat-header__title {
    font-size: 20px;
  }
}
</style>
