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
        @new-chat="handleNewChat"
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
            :mode-options="modeOptions"
            :submitting="submitting"
            @change-mode="changeMode"
            @submit="submitMessage"
            @update:draft="updateDraft"
          />
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import ComposerBar from '@/components/chat/ComposerBar.vue'
import ConversationSidebar from '@/components/chat/ConversationSidebar.vue'
import MessageList from '@/components/chat/MessageList.vue'
import { useChatWorkbench } from '@/composables/useChatWorkbench'
import type { ChatMode } from '@/types/chat'

const {
  activeConversation,
  activeConversationId,
  changeMode,
  historyConversations,
  initialize,
  isEmptyConversation,
  shouldShowAdvisor,
  startNewChat,
  submitting,
  submitMessage,
  switchConversation,
  updateDraft,
  userProfile,
} = useChatWorkbench()

const sidebarOpen = ref(false)
const sidebarCollapsed = ref(false)

const modeOptions: Array<{ label: string; value: ChatMode }> = [
  { label: '陪伴模式', value: 'companion' },
  { label: '恋爱建议', value: 'advice' },
  { label: '语气复刻', value: 'style_clone' },
  { label: '情绪安抚', value: 'soothing' },
]

const handleNewChat = () => {
  startNewChat()
  sidebarOpen.value = false
}

const handleSwitchConversation = (id: string) => {
  switchConversation(id)
  sidebarOpen.value = false
}

const toggleSidebarCollapse = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

onMounted(() => {
  void initialize()
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
