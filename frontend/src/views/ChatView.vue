<template>
  <div :class="['chat-view', { 'is-sidebar-collapsed': sidebarCollapsed }]">
    <div class="ambient ambient-rose" />
    <div class="ambient ambient-apricot" />

    <Transition name="panel-overlay">
      <button
        v-if="sidebarOpen"
        class="mobile-overlay"
        type="button"
        aria-label="关闭历史侧栏"
        @click="sidebarOpen = false"
      />
    </Transition>

    <aside :class="['panel-wrap left-panel', { 'is-open': sidebarOpen, 'is-collapsed': sidebarCollapsed }]">
        <ConversationSidebar
          :active-id="activeConversationId"
          :collapsed="sidebarCollapsed"
          :conversations="historyConversations"
          :is-authenticated="isAuthenticated"
          :user-profile="userProfile"
          @edit-profile="openProfileDialog"
          @manage-memory="openProfileDialog"
          @new-chat="handleNewChat"
          @open-auth="openAuthDialog"
          @sign-out="signOut"
          @switch-chat="handleSwitchConversation"
          @toggle-collapse="toggleSidebarCollapse"
        />
    </aside>

    <section class="stage-panel">
      <div class="stage-toolbar">
        <button class="mobile-toggle focus-ring" type="button" @click="sidebarOpen = true">
          心动回忆
        </button>
      </div>

      <div class="chat-shell">
        <div class="chat-content-wrap">
          <MessageList
            :conversation="activeConversation"
            :is-empty="isEmptyConversation"
            :should-show-advisor="shouldShowAdvisor"
            :submitting="submitting"
            :user-avatar-url="userProfile.avatarUrl"
            @advisor-question="submitMessage"
          />
        </div>

        <div class="chat-composer-wrap">
          <ComposerBar
            :active-mode="activeConversation.mode"
            :draft="activeConversation.draft"
            :input-disabled="isComposerLocked"
            :mode-options="modeOptions"
            :streaming="isStreamActive"
            :submitting="submitting"
            @change-mode="changeMode"
            @stop="stopStreaming"
            @submit="submitMessage"
            @update:draft="updateDraft"
          />
        </div>
      </div>
    </section>

    <Transition name="auth-panel">
      <div v-if="authDialogOpen" class="auth-overlay" role="dialog" aria-modal="true">
        <div class="auth-modal">
          <button class="auth-close" type="button" aria-label="关闭登录弹窗" @click="closeAuthDialog">
            ×
          </button>
          <div class="auth-copy">
            <span class="auth-kicker">继续聊天</span>
            <h2>{{ authMode === 'login' ? '登录后继续发送' : '创建账号继续发送' }}</h2>
            <p>未登录试用次数已用完，登录后当前消息会自动继续发送。</p>
          </div>
          <div class="auth-tabs" aria-label="登录方式">
            <button
              :class="['auth-tab', { 'is-active': authMode === 'login' }]"
              type="button"
              @click="authMode = 'login'"
            >
              登录
            </button>
            <button
              :class="['auth-tab', { 'is-active': authMode === 'register' }]"
              type="button"
              @click="authMode = 'register'"
            >
              注册
            </button>
          </div>
          <div class="auth-form">
            <label class="auth-field">
              <span>账号</span>
              <input v-model="authForm.loginName" type="text" autocomplete="username" />
            </label>
            <label v-if="authMode === 'register'" class="auth-field">
              <span>昵称</span>
              <input v-model="authForm.nickname" type="text" autocomplete="nickname" />
            </label>
            <label class="auth-field">
              <span>密码</span>
              <input
                v-model="authForm.password"
                type="password"
                autocomplete="current-password"
                @keydown.enter="submitAuth"
              />
            </label>
            <a-button
              class="auth-submit"
              type="primary"
              :loading="authSubmitting"
              @click="submitAuth"
            >
              {{ authMode === 'login' ? '登录并继续' : '注册并继续' }}
            </a-button>
          </div>
        </div>
      </div>
    </Transition>

    <Transition name="auth-panel">
      <div v-if="profileDialogOpen" class="auth-overlay" role="dialog" aria-modal="true">
        <div class="auth-modal profile-modal">
          <button class="auth-close" type="button" aria-label="关闭资料弹窗" @click="closeProfileDialog">
            ×
          </button>
          <div class="auth-copy">
            <span class="auth-kicker">个人资料</span>
            <h2>让 AI Love 认出你</h2>
            <p>修改昵称和头像后，侧栏与聊天气泡会立即使用新的资料。</p>
          </div>

          <div class="profile-avatar-editor">
            <div class="profile-avatar-preview">
              <img v-if="userProfile.avatarUrl" :src="userProfile.avatarUrl" alt="" />
              <span v-else>{{ userProfile.name.slice(0, 1) }}</span>
            </div>
            <label class="avatar-upload-button">
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp,image/gif"
                :disabled="avatarUploading"
                @change="handleAvatarChange"
              />
              {{ avatarUploading ? '上传中...' : '上传头像' }}
            </label>
          </div>

          <div class="auth-form">
            <label class="auth-field">
              <span>昵称</span>
              <input
                v-model="profileForm.nickname"
                type="text"
                autocomplete="nickname"
                @keydown.enter="submitProfile"
              />
            </label>
            <a-button
              class="auth-submit"
              type="primary"
              :loading="profileSubmitting"
              @click="submitProfile"
            >
              保存资料
            </a-button>
          </div>

          <section class="memory-panel" aria-label="长期记忆">
            <div class="memory-panel-head">
              <div>
                <span class="auth-kicker">长期记忆</span>
                <h3>记住你的偏好</h3>
              </div>
              <label :class="['memory-switch', { 'is-on': memorySettings.memory_enabled }]">
                <input
                  type="checkbox"
                  :checked="memorySettings.memory_enabled"
                  :disabled="memorySettingsLoading || memorySettingsSaving"
                  @change="handleMemoryToggle"
                />
                <span />
              </label>
            </div>
            <p class="memory-note">默认关闭；开启后只保存偏好、称呼和沟通风格，敏感信息会跳过。</p>

            <div class="memory-list">
              <div v-if="memoryItemsLoading" class="memory-empty">加载中...</div>
              <div v-else-if="memoryItems.length === 0" class="memory-empty">
                {{ memorySettings.memory_enabled ? '还没有长期记忆' : '长期记忆已关闭' }}
              </div>
              <template v-else>
                <article v-for="item in memoryItems" :key="item.id" class="memory-item">
                  <div class="memory-item-head">
                    <span>{{ memoryTypeLabel(item.memory_type) }}</span>
                    <button type="button" @click="removeMemoryItem(item.id)">删除</button>
                  </div>
                  <p>{{ item.content }}</p>
                  <small>{{ formatMemoryTime(item.updated_at || item.last_seen_at || item.created_at) }}</small>
                </article>
              </template>
            </div>

            <button
              class="memory-clear-button focus-ring"
              type="button"
              :disabled="memoryItems.length === 0 || memoryClearing"
              @click="confirmClearMemoryItems"
            >
              {{ memoryClearing ? '清空中...' : `清空全部记忆${memoryTotal ? `（${memoryTotal}）` : ''}` }}
            </button>
          </section>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import ComposerBar from '@/components/chat/ComposerBar.vue'
import ConversationSidebar from '@/components/chat/ConversationSidebar.vue'
import MessageList from '@/components/chat/MessageList.vue'
import { useChatWorkbench } from '@/composables/useChatWorkbench'
import type { ChatMode } from '@/types/chat'

const route = useRoute()
const router = useRouter()

const getRouteSessionId = () => {
  const raw = route.query.session_id
  return Array.isArray(raw) ? String(raw[0] ?? '').trim() : String(raw ?? '').trim()
}

const {
  activeConversation,
  activeConversationId,
  authDialogOpen,
  authForm,
  authMode,
  authSubmitting,
  avatarUploading,
  changeMode,
  clearAllMemoryItems,
  closeAuthDialog,
  closeProfileDialog,
  historyConversations,
  initialize,
  isAuthenticated,
  isComposerLocked,
  isEmptyConversation,
  isStreamActive,
  memoryClearing,
  memoryItems,
  memoryItemsLoading,
  memorySettings,
  memorySettingsLoading,
  memorySettingsSaving,
  memoryTotal,
  openAuthDialog,
  openProfileDialog,
  profileDialogOpen,
  profileForm,
  profileSubmitting,
  removeMemoryItem,
  selectConversation,
  setMemoryEnabled,
  signOut,
  shouldShowAdvisor,
  startNewChat,
  submitAuth,
  submitProfile,
  submitting,
  submitMessage,
  stopStreaming,
  switchConversation,
  updateDraft,
  uploadProfileAvatar,
  userProfile,
} = useChatWorkbench({
  initialSessionId: getRouteSessionId(),
})

const sidebarOpen = ref(false)
const sidebarCollapsed = ref(false)

const modeOptions: Array<{ label: string; value: ChatMode }> = [
  { label: '陪伴模式', value: 'companion' },
  { label: '恋爱建议', value: 'advice' },
  { label: '语气复刻', value: 'style_clone' },
  { label: '情绪安抚', value: 'soothing' },
]

const handleNewChat = () => {
  if (getRouteSessionId()) {
    clearRouteSession()
  } else {
    startNewChat()
  }
  sidebarOpen.value = false
}

const handleSwitchConversation = (id: string) => {
  if (switchConversation(id)) {
    syncRouteSession(id)
  }
  sidebarOpen.value = false
}

const syncRouteSession = (sessionId: string) => {
  if (!sessionId || getRouteSessionId() === sessionId) {
    return
  }
  void router.replace({
    path: '/chat',
    query: {
      ...route.query,
      session_id: sessionId,
    },
  })
}

const clearRouteSession = () => {
  if (!getRouteSessionId()) {
    return
  }
  const { session_id: _sessionId, ...query } = route.query
  void router.replace({
    path: '/chat',
    query,
  })
}

watch(
  () => route.query.session_id,
  () => {
    const sessionId = getRouteSessionId()
    if (!sessionId) {
      startNewChat()
      return
    }
    if (sessionId === activeConversationId.value) {
      return
    }
    if (!selectConversation(sessionId)) {
      clearRouteSession()
    }
  },
)

const toggleSidebarCollapse = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

const handleAvatarChange = (event: Event) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) {
    void uploadProfileAvatar(file)
  }
  input.value = ''
}

const handleMemoryToggle = (event: Event) => {
  const input = event.target as HTMLInputElement
  void setMemoryEnabled(input.checked)
}

const confirmClearMemoryItems = () => {
  if (window.confirm('确定清空全部长期记忆吗？')) {
    void clearAllMemoryItems()
  }
}

const memoryTypeLabel = (type: string) => {
  if (type === 'preference') {
    return '偏好'
  }
  if (type === 'profile_summary') {
    return '画像'
  }
  return '事件'
}

const formatMemoryTime = (value?: string | null) => {
  if (!value) {
    return '暂无更新时间'
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return '暂无更新时间'
  }
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

onMounted(async () => {
  const requestedSessionId = getRouteSessionId()
  await initialize()
  if (requestedSessionId && requestedSessionId !== activeConversationId.value) {
    clearRouteSession()
  }
})
</script>

<style scoped>
.chat-view {
  position: relative;
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 0;
  height: 100%;
  min-height: 0;
  background:
    radial-gradient(circle at 22% 18%, rgba(248, 190, 199, 0.38), transparent 28%),
    radial-gradient(circle at 86% 8%, rgba(242, 177, 120, 0.24), transparent 26%),
    linear-gradient(135deg, #fff7f2 0%, #ffeef1 45%, #fffaf7 100%);
  color: var(--chat-text-primary);
  overflow: hidden;
}

.ambient {
  position: absolute;
  z-index: 0;
  border-radius: 999px;
  filter: blur(4px);
  pointer-events: none;
}

.ambient-rose {
  right: 12%;
  top: 9%;
  width: 180px;
  height: 180px;
  background: radial-gradient(circle, rgba(200, 95, 120, 0.18), transparent 68%);
  animation: floatGlow 8s ease-in-out infinite;
}

.ambient-apricot {
  left: 32%;
  bottom: 6%;
  width: 240px;
  height: 240px;
  background: radial-gradient(circle, rgba(242, 177, 120, 0.16), transparent 70%);
  animation: floatGlow 10s ease-in-out infinite reverse;
}

.chat-view.is-sidebar-collapsed {
  grid-template-columns: 56px minmax(0, 1fr);
}

.panel-wrap,
.stage-panel {
  position: relative;
  z-index: 1;
  min-width: 0;
  min-height: 0;
  height: 100%;
}

.left-panel {
  transition:
    width 0.24s ease,
    min-width 0.24s ease,
    opacity 0.18s ease,
    transform 0.24s ease;
}

.left-panel.is-collapsed {
  width: 56px;
  min-width: 56px;
  opacity: 1;
  overflow: hidden;
}

.stage-panel {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  min-height: 0;
  align-self: stretch;
  padding: 0;
}

.stage-toolbar {
  display: none;
}

.chat-shell {
  position: relative;
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  min-height: 0;
  border: 0;
  border-radius: 0;
  background:
    linear-gradient(180deg, rgba(255, 250, 247, 0.9), rgba(255, 241, 238, 0.82)),
    radial-gradient(circle at 50% 0%, rgba(255, 255, 255, 0.9), transparent 34%);
  box-shadow: 0 24px 70px rgba(125, 72, 84, 0.14);
  overflow: hidden;
  backdrop-filter: blur(18px);
}

.chat-shell::before {
  position: absolute;
  inset: 0;
  background-image:
    radial-gradient(circle at 16px 16px, rgba(200, 95, 120, 0.08) 1px, transparent 1px),
    linear-gradient(110deg, rgba(255, 255, 255, 0.52), transparent 34%);
  background-size: 34px 34px, auto;
  content: "";
  pointer-events: none;
}

.chat-content-wrap {
  position: relative;
  z-index: 1;
  display: flex;
  flex: 1 1 auto;
  min-height: 0;
}

.chat-composer-wrap {
  position: relative;
  z-index: 1;
  display: flex;
  flex-shrink: 0;
  min-height: 0;
}

.chat-content-wrap :deep(.message-list) {
  flex: 1 1 auto;
  min-height: 0;
}

.chat-composer-wrap :deep(.composer-bar) {
  flex: 1 1 auto;
  margin: 0;
}

.mobile-toggle {
  min-height: 34px;
  padding: 0 14px;
  border: 1px solid var(--chat-line);
  border-radius: 999px;
  background: rgba(255, 250, 247, 0.78);
  color: var(--chat-text-primary);
  font-size: 12px;
  font-weight: 700;
  box-shadow: var(--shadow-panel);
}

.mobile-overlay {
  position: fixed;
  inset: 0;
  z-index: 19;
  border: none;
  background: rgba(75, 41, 50, 0.22);
  backdrop-filter: blur(8px);
}

.auth-overlay {
  position: fixed;
  inset: 0;
  z-index: 40;
  display: grid;
  place-items: center;
  padding: 18px;
  background: rgba(75, 41, 50, 0.28);
  backdrop-filter: blur(12px);
}

.auth-modal {
  position: relative;
  width: min(92vw, 420px);
  padding: 24px;
  border: 1px solid rgba(255, 255, 255, 0.78);
  border-radius: 24px;
  background:
    linear-gradient(160deg, rgba(255, 250, 247, 0.96), rgba(255, 239, 235, 0.94)),
    radial-gradient(circle at 18% 0%, rgba(200, 95, 120, 0.16), transparent 28%);
  box-shadow: 0 28px 70px rgba(75, 41, 50, 0.28);
}

.auth-close {
  position: absolute;
  top: 14px;
  right: 14px;
  width: 32px;
  height: 32px;
  border: 1px solid rgba(157, 83, 100, 0.12);
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.62);
  color: var(--chat-text-muted);
  cursor: pointer;
}

.auth-copy {
  display: grid;
  gap: 8px;
  padding-right: 28px;
}

.auth-kicker {
  color: var(--chat-accent-strong);
  font-size: 12px;
  font-weight: 900;
}

.auth-copy h2 {
  margin: 0;
  color: var(--chat-text-primary);
  font-size: 24px;
  line-height: 1.2;
}

.auth-copy p {
  margin: 0;
  color: var(--chat-text-muted);
  font-size: 14px;
  line-height: 1.7;
}

.auth-tabs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin: 20px 0 16px;
}

.auth-tab {
  height: 38px;
  border: 1px solid rgba(157, 83, 100, 0.12);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.56);
  color: var(--chat-text-muted);
  font-weight: 800;
  cursor: pointer;
}

.auth-tab.is-active {
  border-color: rgba(200, 95, 120, 0.36);
  background: rgba(248, 223, 229, 0.92);
  color: var(--chat-accent-strong);
}

.auth-form {
  display: grid;
  gap: 13px;
}

.auth-field {
  display: grid;
  gap: 7px;
  color: var(--chat-text-muted);
  font-size: 12px;
  font-weight: 800;
}

.auth-field input {
  width: 100%;
  height: 42px;
  padding: 0 13px;
  border: 1px solid rgba(157, 83, 100, 0.12);
  border-radius: 14px;
  outline: none;
  background: rgba(255, 255, 255, 0.72);
  color: var(--chat-text-primary);
  font-size: 14px;
}

.auth-field input:focus {
  border-color: rgba(200, 95, 120, 0.42);
  box-shadow: 0 0 0 3px rgba(200, 95, 120, 0.1);
}

.auth-submit.auth-submit {
  height: 42px;
  margin-top: 4px;
  font-weight: 900;
}

.profile-modal {
  width: min(94vw, 560px);
  max-height: min(92vh, 760px);
  overflow: auto;
}

.profile-avatar-editor {
  display: flex;
  align-items: center;
  gap: 14px;
  margin: 20px 0 16px;
  padding: 14px;
  border: 1px solid rgba(157, 83, 100, 0.12);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.48);
}

.profile-avatar-preview {
  display: grid;
  place-items: center;
  width: 66px;
  height: 66px;
  border: 1px solid rgba(255, 255, 255, 0.72);
  border-radius: 24px;
  background: linear-gradient(145deg, #fff4dc, #f5bfd0);
  color: var(--chat-accent-strong);
  font-size: 24px;
  font-weight: 900;
  overflow: hidden;
  box-shadow: 0 16px 30px rgba(164, 61, 88, 0.14);
}

.profile-avatar-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.avatar-upload-button {
  display: inline-grid;
  place-items: center;
  min-width: 108px;
  height: 38px;
  border: 1px solid rgba(200, 95, 120, 0.22);
  border-radius: 999px;
  background: rgba(248, 223, 229, 0.72);
  color: var(--chat-accent-strong);
  font-size: 13px;
  font-weight: 900;
  cursor: pointer;
}

.avatar-upload-button input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}

.memory-panel {
  display: grid;
  gap: 12px;
  margin-top: 18px;
  padding-top: 18px;
  border-top: 1px solid rgba(157, 83, 100, 0.12);
}

.memory-panel-head,
.memory-item-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.memory-panel-head h3 {
  margin: 4px 0 0;
  color: var(--chat-text-primary);
  font-size: 17px;
  line-height: 1.25;
}

.memory-note {
  margin: 0;
  color: var(--chat-text-muted);
  font-size: 13px;
  line-height: 1.7;
}

.memory-switch {
  position: relative;
  flex: 0 0 auto;
  width: 48px;
  height: 28px;
  cursor: pointer;
}

.memory-switch input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}

.memory-switch span {
  position: absolute;
  inset: 0;
  border: 1px solid rgba(157, 83, 100, 0.16);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.72);
  transition: background var(--transition-base), border-color var(--transition-base);
}

.memory-switch span::after {
  position: absolute;
  top: 3px;
  left: 3px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #fffaf7;
  box-shadow: 0 4px 12px rgba(75, 41, 50, 0.18);
  transition: transform var(--transition-base);
  content: "";
}

.memory-switch.is-on span {
  border-color: rgba(200, 95, 120, 0.34);
  background: rgba(200, 95, 120, 0.88);
}

.memory-switch.is-on span::after {
  transform: translateX(20px);
}

.memory-list {
  display: grid;
  gap: 10px;
  max-height: 220px;
  overflow: auto;
}

.memory-empty,
.memory-item {
  border: 1px solid rgba(157, 83, 100, 0.12);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.52);
}

.memory-empty {
  padding: 14px;
  color: var(--chat-text-muted);
  font-size: 13px;
  text-align: center;
}

.memory-item {
  display: grid;
  gap: 7px;
  padding: 12px;
}

.memory-item-head span {
  color: var(--chat-accent-strong);
  font-size: 12px;
  font-weight: 900;
}

.memory-item-head button {
  border: 0;
  background: transparent;
  color: var(--chat-text-muted);
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
}

.memory-item p {
  margin: 0;
  color: var(--chat-text-primary);
  font-size: 13px;
  line-height: 1.65;
}

.memory-item small {
  color: var(--chat-text-muted);
  font-size: 11px;
}

.memory-clear-button {
  min-height: 38px;
  border: 1px solid rgba(157, 83, 100, 0.14);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.64);
  color: var(--chat-text-secondary);
  font-size: 12px;
  font-weight: 900;
  cursor: pointer;
}

.memory-clear-button:disabled {
  cursor: not-allowed;
  opacity: 0.54;
}

.auth-panel-enter-active,
.auth-panel-leave-active {
  transition: opacity 0.2s ease;
}

.auth-panel-enter-active .auth-modal,
.auth-panel-leave-active .auth-modal {
  transition: transform 0.2s ease;
}

.auth-panel-enter-from,
.auth-panel-leave-to {
  opacity: 0;
}

.auth-panel-enter-from .auth-modal,
.auth-panel-leave-to .auth-modal {
  transform: translateY(12px) scale(0.98);
}

.panel-overlay-enter-active,
.panel-overlay-leave-active {
  transition: opacity 0.18s ease;
}

.panel-overlay-enter-from,
.panel-overlay-leave-to {
  opacity: 0;
}

@media (max-width: 960px) {
  .chat-view {
    grid-template-columns: 1fr;
  }

  .panel-wrap {
    position: fixed;
    top: 84px;
    bottom: 12px;
    left: 12px;
    z-index: 20;
    width: min(82vw, 320px);
    transform: translateX(-110%);
    transition: transform 0.24s ease;
    opacity: 1;
  }

  .panel-wrap.is-open {
    transform: translateX(0);
  }

  .left-panel.is-collapsed {
    width: min(82vw, 320px);
    min-width: min(82vw, 320px);
  }

  .stage-toolbar {
    display: flex;
    justify-content: flex-start;
    padding: 0 0 12px;
  }

  .mobile-toggle {
    display: inline-flex;
    align-items: center;
  }

  .chat-shell {
    border-radius: 0;
  }

  .stage-panel {
    padding: 0;
  }
}

@media (min-width: 961px) {
  .mobile-toggle {
    display: none;
  }
}

@keyframes floatGlow {
  0%,
  100% {
    opacity: 0.72;
    transform: translate3d(0, 0, 0) scale(1);
  }

  50% {
    opacity: 1;
    transform: translate3d(0, -14px, 0) scale(1.04);
  }
}
</style>
