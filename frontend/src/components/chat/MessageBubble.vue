<template>
  <div :class="['message-row', message.role === 'user' ? 'is-user' : 'is-assistant']">
    <div class="message-avatar">
      <img
        v-if="message.role === 'user' && userAvatarUrl"
        :src="userAvatarUrl"
        alt=""
        class="avatar-image"
      />
      <UserOutlined v-else-if="message.role === 'user'" />
      <img v-else src="/i-love-new-york.svg" alt="" class="assistant-mark" />
    </div>

    <div class="message-stack">
      <ThinkingStreamCard
        v-if="message.role === 'assistant' && message.streamState?.thinkingStatus !== 'idle'"
        :chunks="message.streamState?.thinkingChunks ?? []"
        :status="message.streamState?.thinkingStatus ?? 'idle'"
      />

      <div :class="['message-block', message.role === 'user' ? 'block-user' : 'block-assistant']">
        <p v-if="message.role === 'assistant'" class="message-name">AI Love</p>
        <div v-if="message.content" class="message-text">{{ message.content }}</div>
        <div v-else class="typing-line">
          <span />
          <span />
          <span />
        </div>

        <div v-if="showAdvisor" class="advisor-panel">
          <p>可以继续聊聊</p>
          <div class="advisor-questions">
            <button
              v-for="question in message.advisor?.suggested_questions ?? []"
              :key="question"
              class="advisor-question-chip focus-ring"
              type="button"
              :disabled="submitting"
              @click="$emit('advisor-question', question)"
            >
              {{ question }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { UserOutlined } from '@ant-design/icons-vue'

import type { MessageItem } from '@/composables/useChatWorkbench'
import ThinkingStreamCard from '@/components/chat/ThinkingStreamCard.vue'

defineProps<{
  message: MessageItem
  showAdvisor: boolean
  submitting: boolean
  userAvatarUrl: string
}>()

defineEmits<{
  (event: 'advisor-question', question: string): void
}>()
</script>

<style scoped>
.message-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.message-row.is-user {
  flex-direction: row-reverse;
}

.message-avatar {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border: 1px solid rgba(255, 255, 255, 0.82);
  border-radius: 15px;
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.88), rgba(248, 223, 229, 0.72));
  color: var(--chat-text-muted);
  flex-shrink: 0;
  box-shadow: 0 10px 22px rgba(125, 72, 84, 0.12);
  overflow: hidden;
}

.is-user .message-avatar {
  background: linear-gradient(145deg, #fff4dc, #f5bfd0);
  color: var(--chat-accent-strong);
}

.assistant-mark {
  width: 18px;
  height: 18px;
  object-fit: contain;
  filter: sepia(0.18) saturate(1.35);
}

.avatar-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.message-stack {
  display: grid;
  justify-items: start;
  gap: 10px;
  max-width: min(78%, 740px);
}

.is-user .message-stack {
  justify-items: end;
}

.message-block {
  min-width: 0;
  padding: 15px 18px;
  border: 1px solid rgba(255, 255, 255, 0.76);
  border-radius: 22px;
  box-shadow: 0 16px 34px rgba(125, 72, 84, 0.1);
  backdrop-filter: blur(12px);
}

.block-assistant {
  border-top-left-radius: 8px;
  background: rgba(255, 255, 255, 0.76);
  color: var(--chat-text-primary);
}

.block-user {
  border-color: rgba(255, 255, 255, 0.7);
  border-top-right-radius: 8px;
  background: linear-gradient(135deg, rgba(200, 95, 120, 0.95), rgba(242, 177, 120, 0.92));
  color: #fffaf7;
  box-shadow: 0 18px 34px rgba(164, 61, 88, 0.16);
}

.message-name {
  margin: 0 0 6px;
  color: var(--chat-accent-strong);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.04em;
}

.message-text {
  font-size: 15px;
  line-height: 1.88;
  white-space: pre-wrap;
  word-break: break-word;
}

.typing-line {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  min-width: 48px;
  min-height: 24px;
}

.typing-line span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--chat-accent);
  animation: typing 1.2s ease-in-out infinite;
}

.typing-line span:nth-child(2) {
  animation-delay: 0.15s;
}

.typing-line span:nth-child(3) {
  animation-delay: 0.3s;
}

.advisor-panel {
  display: grid;
  gap: 10px;
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid rgba(157, 83, 100, 0.12);
}

.advisor-panel p {
  margin: 0;
  color: var(--chat-text-muted);
  font-size: 12px;
  font-weight: 700;
}

.advisor-questions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.advisor-question-chip {
  padding: 8px 12px;
  border: 1px solid rgba(200, 95, 120, 0.16);
  border-radius: 999px;
  background: rgba(255, 250, 247, 0.72);
  color: var(--chat-text-secondary);
  font-size: 12px;
  line-height: 1.5;
  cursor: pointer;
  transition:
    border-color var(--transition-base),
    background var(--transition-base),
    transform var(--transition-base);
}

.advisor-question-chip:hover:enabled {
  border-color: rgba(200, 95, 120, 0.32);
  background: rgba(248, 223, 229, 0.82);
  color: var(--chat-accent-strong);
  transform: translateY(-1px);
}

.advisor-question-chip:disabled {
  cursor: not-allowed;
  opacity: 0.54;
}

@keyframes typing {
  0%,
  100% {
    opacity: 0.35;
    transform: translateY(0);
  }

  50% {
    opacity: 0.9;
    transform: translateY(-4px);
  }
}

@media (max-width: 760px) {
  .message-stack {
    max-width: calc(100% - 46px);
  }

  .message-block {
    padding: 14px;
  }
}
</style>
