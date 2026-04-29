<template>
  <aside :class="['conversation-sidebar', { 'is-collapsed': collapsed }]">
    <template v-if="collapsed">
      <button
        class="rail-icon-button focus-ring"
        type="button"
        aria-label="展开侧边栏"
        @click="$emit('toggle-collapse')"
      >
        <MenuUnfoldOutlined />
      </button>
    </template>

    <template v-else>
    <div class="sidebar-head">
      <div class="brand-block">
        <img class="brand-logo" src="/i-love-new-york.svg" alt="" />
        <div>
          <p class="sidebar-label">AI Love</p>
          <h2>心动回忆</h2>
        </div>
      </div>

      <button
        class="collapse-icon-button focus-ring"
        type="button"
        aria-label="收起侧边栏"
        @click="$emit('toggle-collapse')"
      >
        <MenuFoldOutlined />
      </button>
    </div>

    <button class="new-chat-button focus-ring" type="button" @click="$emit('new-chat')">
      <PlusOutlined />
      开启新的心事
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
        <strong>还没有留下心动回忆</strong>
        <span>发出第一条消息后，这里会保存你们聊过的重要片段。</span>
      </div>
    </div>

    <div class="sidebar-user">
      <template v-if="isAuthenticated">
        <div class="profile-card">
          <button class="profile-entry focus-ring" type="button" @click="$emit('edit-profile')">
            <span class="profile-avatar">
              <img v-if="userProfile.avatarUrl" :src="userProfile.avatarUrl" alt="" />
              <UserOutlined v-else />
            </span>
            <span class="profile-text">
              <strong>{{ userProfile.name }}</strong>
              <small>编辑个人资料</small>
            </span>
            <EditOutlined />
          </button>
          <button class="memory-entry focus-ring" type="button" @click="$emit('manage-memory')">
            <DatabaseOutlined />
            <span>长期记忆</span>
          </button>
          <button class="logout-button focus-ring" type="button" @click="$emit('sign-out')">
            退出登录
          </button>
        </div>
      </template>

      <template v-else>
        <div class="auth-entry">
          <span>登录后保存你的对话和头像</span>
          <div class="auth-actions">
            <button class="auth-mini-button focus-ring" type="button" @click="$emit('open-auth', 'login')">
              登录
            </button>
            <button class="auth-mini-button is-primary focus-ring" type="button" @click="$emit('open-auth', 'register')">
              注册
            </button>
          </div>
        </div>
      </template>
    </div>
    </template>
  </aside>
</template>

<script setup lang="ts">
import {
  DatabaseOutlined,
  EditOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  PlusOutlined,
  UserOutlined,
} from '@ant-design/icons-vue'

import type { ConversationItem } from '@/composables/useChatWorkbench'

defineProps<{
  conversations: ConversationItem[]
  activeId: string
  collapsed: boolean
  isAuthenticated: boolean
  userProfile: {
    name: string
    avatarUrl: string
  }
}>()

defineEmits<{
  (event: 'new-chat'): void
  (event: 'switch-chat', id: string): void
  (event: 'toggle-collapse'): void
  (event: 'open-auth', mode: 'login' | 'register'): void
  (event: 'edit-profile'): void
  (event: 'manage-memory'): void
  (event: 'sign-out'): void
}>()
</script>

<style scoped>
.conversation-sidebar {
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr) auto;
  gap: 14px;
  min-width: 0;
  min-height: 0;
  height: 100%;
  padding: 18px;
  border-right: 1px solid rgba(255, 255, 255, 0.54);
  background:
    linear-gradient(180deg, rgba(255, 250, 247, 0.9), rgba(255, 238, 232, 0.86)),
    radial-gradient(circle at 30% 0%, rgba(248, 223, 229, 0.88), transparent 46%);
  box-shadow: inset -1px 0 0 rgba(157, 83, 100, 0.08);
  backdrop-filter: blur(16px);
}

.conversation-sidebar.is-collapsed {
  grid-template-rows: 1fr;
  align-items: start;
  justify-items: stretch;
  padding: 12px 8px;
}

.rail-icon-button,
.collapse-icon-button {
  display: inline-grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border: 1px solid var(--chat-line);
  border-radius: 13px;
  background: rgba(255, 250, 247, 0.78);
  color: var(--chat-accent-strong);
  font-size: 18px;
  cursor: pointer;
  transition:
    border-color var(--transition-base),
    background var(--transition-base),
    transform var(--transition-base);
}

.rail-icon-button:hover,
.collapse-icon-button:hover {
  border-color: rgba(200, 95, 120, 0.34);
  background: rgba(248, 223, 229, 0.86);
  transform: translateY(-1px);
}

.rail-icon-button {
  width: 40px;
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
  filter: sepia(0.18) saturate(1.35);
}

.sidebar-label {
  margin: 0 0 4px;
  color: var(--chat-accent);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

h2 {
  margin: 0;
  color: var(--chat-text-primary);
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 700;
}

.new-chat-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 38px;
  border: 1px solid var(--chat-line);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.58);
  color: var(--chat-text-primary);
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
  transition:
    border-color var(--transition-base),
    background var(--transition-base);
}

.new-chat-button {
  width: 100%;
  background: linear-gradient(135deg, rgba(200, 95, 120, 0.94), rgba(242, 177, 120, 0.88));
  color: #fffaf7;
  box-shadow: 0 14px 28px rgba(164, 61, 88, 0.16);
}

.new-chat-button:hover {
  border-color: rgba(200, 95, 120, 0.34);
  background: rgba(248, 223, 229, 0.86);
  color: var(--chat-accent-strong);
}

.new-chat-button:hover {
  background: linear-gradient(135deg, rgba(164, 61, 88, 0.96), rgba(238, 167, 109, 0.92));
  color: #fffaf7;
}

.session-list {
  display: grid;
  align-content: start;
  gap: 8px;
  min-height: 0;
  overflow: auto;
}

.session-item {
  display: grid;
  gap: 4px;
  width: 100%;
  padding: 12px;
  border: 1px solid transparent;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.44);
  text-align: left;
  cursor: pointer;
  transition:
    border-color var(--transition-base),
    background var(--transition-base);
}

.session-item:hover,
.session-item.is-active {
  border-color: rgba(200, 95, 120, 0.18);
  background: rgba(255, 250, 247, 0.86);
  box-shadow: 0 12px 24px rgba(125, 72, 84, 0.08);
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
  font-weight: 800;
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

.sidebar-user {
  padding-top: 12px;
  border-top: 1px solid rgba(157, 83, 100, 0.12);
}

.profile-card {
  display: grid;
  gap: 10px;
}

.profile-entry {
  display: grid;
  grid-template-columns: 40px minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-height: 56px;
  padding: 8px;
  border: 1px solid rgba(157, 83, 100, 0.12);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.5);
  color: var(--chat-text-primary);
  cursor: pointer;
  text-align: left;
}

.profile-entry:hover {
  border-color: rgba(200, 95, 120, 0.28);
  background: rgba(255, 250, 247, 0.86);
}

.memory-entry,
.logout-button {
  width: 100%;
  min-height: 36px;
  border: 1px solid rgba(157, 83, 100, 0.14);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.64);
  color: var(--chat-text-secondary);
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
  transition:
    border-color var(--transition-base),
    background var(--transition-base),
    color var(--transition-base);
}

.memory-entry {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.memory-entry:hover,
.logout-button:hover {
  border-color: rgba(200, 95, 120, 0.24);
  background: rgba(255, 244, 241, 0.86);
  color: var(--chat-accent-strong);
}

.profile-avatar {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: 15px;
  background: linear-gradient(145deg, #fff4dc, #f5bfd0);
  color: var(--chat-accent-strong);
  overflow: hidden;
}

.profile-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.profile-text {
  display: grid;
  min-width: 0;
}

.profile-text strong,
.profile-text small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.profile-text strong {
  font-size: 14px;
}

.profile-text small,
.auth-entry span {
  color: var(--chat-text-muted);
  font-size: 12px;
}

.auth-entry {
  display: grid;
  gap: 10px;
  padding: 12px;
  border: 1px solid rgba(157, 83, 100, 0.12);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.46);
}

.auth-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.auth-mini-button {
  height: 34px;
  border: 1px solid rgba(157, 83, 100, 0.14);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.62);
  color: var(--chat-text-secondary);
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
}

.auth-mini-button.is-primary {
  border-color: transparent;
  background: linear-gradient(135deg, rgba(200, 95, 120, 0.94), rgba(242, 177, 120, 0.88));
  color: #fffaf7;
}
</style>
