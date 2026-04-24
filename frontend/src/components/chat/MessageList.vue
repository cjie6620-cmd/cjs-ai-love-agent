<template>
  <section ref="messageListRef" class="message-list">
    <div v-if="isEmpty" class="welcome-panel">
      <p class="welcome-kicker">AI Love</p>
      <h2>把你现在最想说的话发出来</h2>
      <p>这里不会显示预设提示词，直接说你的处境、感受或想问的问题就可以。</p>
    </div>

    <TransitionGroup v-else name="message-in" tag="div" class="message-list-inner">
      <MessageBubble
        v-for="item in conversation.messages"
        :key="item.id"
        :message="item"
        :show-advisor="shouldShowAdvisor(item)"
        :submitting="submitting"
        :user-avatar-url="userAvatarUrl"
        @advisor-question="$emit('advisor-question', $event)"
      />
    </TransitionGroup>
  </section>
</template>

<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'

import MessageBubble from '@/components/chat/MessageBubble.vue'
import type { ConversationItem, MessageItem } from '@/composables/useChatWorkbench'

const props = defineProps<{
  conversation: ConversationItem
  isEmpty: boolean
  shouldShowAdvisor: (message: MessageItem) => boolean
  submitting: boolean
  userAvatarUrl: string
}>()

defineEmits<{
  (event: 'advisor-question', question: string): void
}>()

const messageListRef = ref<HTMLElement | null>(null)

const scrollToBottom = () => {
  nextTick(() => {
    const el = messageListRef.value
    if (el) {
      el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
    }
  })
}

const getLastMessage = () => props.conversation.messages[props.conversation.messages.length - 1]

watch(
  () => [
    props.conversation.id,
    props.conversation.messages.length,
    getLastMessage()?.content,
    getLastMessage()?.streamState?.thinkingChunks.length,
  ],
  scrollToBottom,
)
</script>

<style scoped>
.message-list {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  min-height: 0;
  padding: 18px 24px 12px;
  overflow: auto;
}

.message-list-inner {
  display: flex;
  flex-direction: column;
  gap: 24px;
  min-height: 100%;
  width: 100%;
  max-width: 920px;
  margin: 0 auto;
}

.welcome-panel {
  display: grid;
  flex: 1;
  place-items: center;
  align-content: center;
  min-height: 100%;
  max-width: 560px;
  margin: 0 auto;
  padding: 32px 0;
  text-align: center;
}

.welcome-kicker {
  margin: 0 0 10px;
  color: var(--chat-accent);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

h2 {
  margin: 0;
  color: var(--chat-text-primary);
  font-size: clamp(30px, 4vw, 38px);
  line-height: 1.18;
  letter-spacing: -0.03em;
}

.welcome-panel > p:last-child {
  max-width: 520px;
  margin: 14px 0 0;
  color: var(--chat-text-muted);
  font-size: 14px;
  line-height: 1.85;
}

.message-in-enter-active {
  transition: opacity 0.22s ease, transform 0.22s ease;
}

.message-in-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

@media (max-width: 760px) {
  .message-list {
    padding: 16px 14px 12px;
  }

  h2 {
    font-size: 28px;
  }
}
</style>
