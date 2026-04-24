<template>
  <aside :class="['conversation-sidebar', { 'is-collapsed': collapsed }]">
    <template v-if="collapsed">
      <button class="rail-toggle focus-ring" type="button" @click="$emit('toggle-collapse')">
        展开
      </button>
    </template>

    <template v-else>
    <div class="sidebar-head">
      <div class="brand-block">
        <img class="brand-logo" src="/i-love-new-york.svg" alt="" />
        <div>
          <p class="sidebar-label">AI Love</p>
          <h2>对话历史</h2>
        </div>
      </div>

      <button class="collapse-button focus-ring" type="button" @click="$emit('toggle-collapse')">
        收起
      </button>
    </div>

    <button class="new-chat-button focus-ring" type="button" @click="$emit('new-chat')">
      <PlusOutlined />
      新对话
    </button>

    <div class="session-list">
      <button
        v-for="item in conversations"
        :key="item.id"
        :class="['session-item', { 'is-active': item.id === activeId }]"
        type="button"
        @click="$emit('switch-chat', item.id)"
      >
        <span class="session-title">{{ item.title }}</span>
        <span class="session-preview">{{ item.preview }}</span>
      </button>

      <div v-if="conversations.length === 0" class="empty-history">
        <strong>还没有历史消息</strong>
        <span>发出第一条消息后，这里会保存你的会话记录。</span>
      </div>
    </div>
    </template>
  </aside>
</template>

<script setup lang="ts">
import { PlusOutlined } from '@ant-design/icons-vue'

import type { ConversationItem } from '@/composables/useChatWorkbench'

defineProps<{
  conversations: ConversationItem[]
  activeId: string
  collapsed: boolean
}>()

defineEmits<{
  (event: 'new-chat'): void
  (event: 'switch-chat', id: string): void
  (event: 'toggle-collapse'): void
}>()
</script>

<style scoped>
.conversation-sidebar {
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr);
  gap: 14px;
  min-width: 0;
  min-height: 0;
  height: 100%;
  padding: 16px;
  border-right: 1px solid var(--chat-line);
  background: rgba(10, 13, 18, 0.98);
}

.conversation-sidebar.is-collapsed {
  grid-template-rows: 1fr;
  align-items: start;
  justify-items: stretch;
  padding: 12px 8px;
}

.rail-toggle {
  width: 100%;
  min-height: 34px;
  padding: 0 6px;
  border: 1px solid var(--chat-line);
  background: rgba(255, 255, 255, 0.03);
  color: var(--chat-text-primary);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  writing-mode: vertical-rl;
  text-orientation: mixed;
}

.sidebar-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.brand-block {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.brand-logo {
  width: 30px;
  height: 30px;
  object-fit: contain;
  filter: grayscale(1) brightness(1.45);
}

.sidebar-label {
  margin: 0 0 4px;
  color: var(--chat-accent);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

h2 {
  margin: 0;
  color: var(--chat-text-primary);
  font-size: 18px;
  font-weight: 700;
}

.collapse-button,
.new-chat-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 38px;
  border: 1px solid var(--chat-line);
  background: rgba(255, 255, 255, 0.03);
  color: var(--chat-text-primary);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition:
    border-color var(--transition-base),
    background var(--transition-base);
}

.collapse-button {
  min-width: 64px;
  padding: 0 10px;
}

.new-chat-button {
  width: 100%;
}

.collapse-button:hover,
.new-chat-button:hover {
  border-color: rgba(123, 162, 255, 0.34);
  background: rgba(123, 162, 255, 0.08);
}

.session-list {
  display: grid;
  align-content: start;
  gap: 4px;
  min-height: 0;
  overflow: auto;
}

.session-item {
  display: grid;
  gap: 4px;
  width: 100%;
  padding: 12px 10px;
  border: 1px solid transparent;
  background: transparent;
  text-align: left;
  cursor: pointer;
  transition:
    border-color var(--transition-base),
    background var(--transition-base);
}

.session-item:hover,
.session-item.is-active {
  border-color: rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
}

.session-title,
.session-preview {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-title {
  color: var(--chat-text-primary);
  font-size: 14px;
  font-weight: 600;
}

.session-preview {
  color: var(--chat-text-muted);
  font-size: 12px;
}

.empty-history {
  display: grid;
  gap: 6px;
  padding: 18px 0;
  color: var(--chat-text-muted);
  font-size: 13px;
  line-height: 1.7;
}

.empty-history strong {
  color: var(--chat-text-primary);
}
</style>
