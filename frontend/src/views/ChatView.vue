<template>
  <div :class="['chat-view', { 'is-sidebar-collapsed': sidebarCollapsed }]">
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
          历史记录
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
import { computed, onMounted, ref } from 'vue'

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
const isMobileSidebarVisible = computed(() => sidebarOpen.value)

const modeOptions: Array<{ label: string; value: ChatMode }> = [
  { label: '陪伴', value: 'companion' },
  { label: '建议', value: 'advice' },
  { label: '复刻', value: 'style_clone' },
  { label: '安抚', value: 'soothing' },
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
}

.chat-view.is-sidebar-collapsed {
  grid-template-columns: 56px minmax(0, 1fr);
}

.panel-wrap,
.stage-panel {
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
}

.stage-toolbar {
  display: none;
}

.chat-shell {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  min-height: 0;
  border-top: 1px solid var(--chat-line);
  border-left: 1px solid var(--chat-line);
  background: linear-gradient(180deg, rgba(15, 18, 24, 0.98), rgba(10, 12, 18, 0.98));
  overflow: hidden;
}

.chat-content-wrap {
  display: flex;
  flex: 1 1 auto;
  min-height: 0;
}

.chat-composer-wrap {
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
  padding: 0 12px;
  border: 1px solid var(--chat-line);
  background: rgba(255, 255, 255, 0.03);
  color: var(--chat-text-primary);
  font-size: 12px;
  font-weight: 600;
}

.mobile-overlay {
  position: fixed;
  inset: 0;
  z-index: 19;
  border: none;
  background: rgba(4, 8, 15, 0.48);
  backdrop-filter: blur(3px);
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
    padding: 0 0 10px;
  }

  .mobile-toggle {
    display: inline-flex;
    align-items: center;
  }

  .chat-shell {
    border-left: 1px solid var(--chat-line);
  }
}

@media (min-width: 961px) {
  .mobile-toggle {
    display: none;
  }
}
</style>
