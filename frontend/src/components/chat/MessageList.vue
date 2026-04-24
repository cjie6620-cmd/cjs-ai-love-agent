<template>
  <section ref="messageListRef" class="message-list">
    <div v-if="isEmpty" class="welcome-panel">
      <div class="welcome-orbit">
        <span>❤</span>
      </div>
      <p class="welcome-kicker">AI Love · 温柔在线</p>
      <h2>把心里话慢慢说给我听</h2>
      <p>不用组织得很完美，说出你的处境、感受或想问的问题，我会陪你一起理清。</p>
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
  padding: 28px 32px 18px;
  overflow: auto;
}

.message-list-inner {
  display: flex;
  flex-direction: column;
  gap: 22px;
  min-height: 100%;
  width: 100%;
  max-width: 900px;
  margin: 0 auto;
}

.welcome-panel {
  display: grid;
  flex: 1;
  place-items: center;
  align-content: center;
  min-height: 100%;
  max-width: 620px;
  margin: 0 auto;
  padding: 42px 0;
  text-align: center;
}

.welcome-orbit {
  display: grid;
  place-items: center;
  width: 78px;
  height: 78px;
  margin: 0 auto 18px;
  border: 1px solid rgba(255, 255, 255, 0.86);
  border-radius: 28px;
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.92), rgba(248, 223, 229, 0.72)),
    radial-gradient(circle at 28% 22%, rgba(242, 177, 120, 0.26), transparent 52%);
  box-shadow: 0 20px 42px rgba(164, 61, 88, 0.16);
}

.welcome-orbit span {
  color: var(--chat-accent);
  font-size: 30px;
  filter: drop-shadow(0 8px 14px rgba(164, 61, 88, 0.22));
  animation: heartBeat 2.6s ease-in-out infinite;
}

.welcome-kicker {
  margin: 0 0 10px;
  color: var(--chat-accent);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.12em;
}

h2 {
  margin: 0;
  color: var(--chat-text-primary);
  font-family: var(--font-display);
  font-size: clamp(30px, 4vw, 38px);
  line-height: 1.24;
  letter-spacing: -0.02em;
}

.welcome-panel > p:last-child {
  max-width: 520px;
  margin: 14px 0 0;
  color: var(--chat-text-muted);
  font-size: 15px;
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
    padding: 18px 14px 12px;
  }

  h2 {
    font-size: 28px;
  }
}

@keyframes heartBeat {
  0%,
  100% {
    transform: scale(1);
  }

  45% {
    transform: scale(1.12);
  }
}
</style>
