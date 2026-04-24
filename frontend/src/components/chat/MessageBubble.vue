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
        <div v-if="message.content" class="message-text">{{ message.content }}</div>
        <div v-else class="typing-line">
          <span />
          <span />
          <span />
        </div>

        <div v-if="showAdvisor" class="advisor-panel">
          <p>继续追问</p>
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
  gap: 14px;
}

.message-row.is-user {
  flex-direction: row-reverse;
}

.message-avatar {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
  color: var(--chat-text-muted);
  flex-shrink: 0;
}

.assistant-mark {
  width: 18px;
  height: 18px;
  object-fit: contain;
  filter: grayscale(1) brightness(1.45);
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
  max-width: min(78%, 760px);
}

.is-user .message-stack {
  justify-items: end;
}

.message-block {
  min-width: 0;
  padding: 16px 18px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  box-shadow: 0 14px 28px rgba(0, 0, 0, 0.18);
}

.block-assistant {
  background: rgba(25, 29, 37, 0.94);
  color: var(--chat-text-primary);
}

.block-user {
  background: linear-gradient(180deg, rgba(43, 82, 188, 0.92), rgba(35, 66, 153, 0.94));
  color: #f8fbff;
}

.message-text {
  font-size: 14px;
  line-height: 1.9;
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
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.advisor-panel p {
  margin: 0;
  color: var(--chat-text-muted);
  font-size: 12px;
  font-weight: 600;
}

.advisor-questions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.advisor-question-chip {
  padding: 8px 12px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.03);
  color: var(--chat-text-primary);
  font-size: 12px;
  line-height: 1.5;
  cursor: pointer;
  transition:
    border-color var(--transition-base),
    background var(--transition-base),
    transform var(--transition-base);
}

.advisor-question-chip:hover:enabled {
  border-color: rgba(123, 162, 255, 0.38);
  background: rgba(123, 162, 255, 0.09);
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
