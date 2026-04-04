<template>
  <div class="chat-page">
    <aside class="sidebar">
      <div class="sidebar-header">
        <div class="brand-wrap">
          <img class="brand-logo" src="/i-love-new-york.svg" alt="AI Love" />
          <div class="brand-text">
            <div class="brand">AI Love</div>
            <div class="brand-subtitle">Chat</div>
          </div>
        </div>
        <a-button class="plain-icon-button" type="text" @click="startNewChat">
          <template #icon>
            <PlusOutlined />
          </template>
        </a-button>
      </div>

      <div v-if="historyConversations.length > 0" class="session-list">
        <button
          v-for="item in historyConversations"
          :key="item.id"
          :class="['session-item', { 'is-active': item.id === activeConversationId }]"
          type="button"
          @click="switchConversation(item.id)"
        >
          <span class="session-item-title">{{ item.title }}</span>
          <span class="session-item-preview">{{ item.preview }}</span>
        </button>
      </div>
    </aside>

    <main class="chat-main">
      <header class="chat-topbar">
        <div class="chat-title-wrap">
          <div class="chat-title">{{ activeModeLabel }}</div>
          <div class="chat-subtitle">{{ activeConversation.preview }}</div>
        </div>

        <div class="topbar-user">
          <div class="user-avatar-shell">
            <img
              v-if="userProfile.avatarUrl"
              :src="userProfile.avatarUrl"
              :alt="userProfile.name"
              class="user-avatar-image"
            />
            <UserOutlined v-else class="user-avatar-fallback" />
            <span :class="['user-status-dot', { 'is-online': serviceReady }]" />
          </div>
        </div>
      </header>

      <section class="message-list">
        <div
          v-for="item in activeConversation.messages"
          :key="item.id"
          :class="['message-row', item.role === 'user' ? 'is-user' : 'is-assistant']"
        >
          <div class="message-avatar">
            <img
              v-if="item.role === 'user' && userProfile.avatarUrl"
              :src="userProfile.avatarUrl"
              :alt="userProfile.name"
              class="message-user-avatar"
            />
            <UserOutlined v-else-if="item.role === 'user'" />
            <img v-else class="assistant-mark" src="/i-love-new-york.svg" alt="assistant" />
          </div>

          <div :class="['message-block', item.role === 'user' ? 'block-user' : 'block-assistant']">
            <div class="message-text">{{ item.content }}</div>
            <div v-if="item.loading" class="typing-line">正在生成回复...</div>
          </div>
        </div>
      </section>

      <footer class="composer">
        <div class="composer-box">
          <a-textarea
            v-model:value="activeConversation.draft"
            :auto-size="{ minRows: 2, maxRows: 6 }"
            :bordered="false"
            class="composer-input"
            placeholder="发消息..."
            @pressEnter="handleEnter"
          />

          <div class="composer-actions">
            <div class="agent-toolbar">
              <button
                v-for="item in modeOptions"
                :key="item.value"
                :class="['agent-chip', { 'is-active': activeConversation.mode === item.value }]"
                type="button"
                @click="changeMode(item.value)"
              >
                <component :is="item.icon" class="agent-chip-icon" />
                <span>{{ item.label }}</span>
              </button>
            </div>
            <a-button type="primary" :loading="submitting" @click="submitMessage">发送</a-button>
          </div>
        </div>
      </footer>
    </main>
  </div>
</template>

<script setup lang="ts">
import {
  BulbOutlined,
  CopyOutlined,
  HeartOutlined,
  MessageOutlined,
  PlusOutlined,
  UserOutlined,
} from '@ant-design/icons-vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'

import { fetchConversationHistory, fetchHealth, streamChatMessage } from '@/api/chat'
import type { ChatMode, ChatTrace, ConversationHistoryItem } from '@/types/chat'

interface MessageItem {
  id: string
  role: 'user' | 'assistant'
  content: string
  loading?: boolean
}

interface ConversationItem {
  id: string
  title: string
  preview: string
  mode: ChatMode
  messages: MessageItem[]
  draft: string
  latestTrace?: ChatTrace
}

const modeOptions = [
  { label: '陪伴', value: 'companion' as ChatMode, icon: MessageOutlined },
  { label: '建议', value: 'advice' as ChatMode, icon: BulbOutlined },
  { label: '复刻', value: 'style_clone' as ChatMode, icon: CopyOutlined },
  { label: '安抚', value: 'soothing' as ChatMode, icon: HeartOutlined },
]

const DEMO_USER_ID = 'user-demo-001'
const DEFAULT_WELCOME_MESSAGE = '你好，直接发消息就行。'
const DEFAULT_CONVERSATION_TITLE = '新对话'
const DEFAULT_CONVERSATION_PREVIEW = '开始聊天'

const userProfile = reactive({
  name: '用户',
  avatarUrl: '',
})

const createMessageId = (role: MessageItem['role']) =>
  `${role}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`

const createConversationId = () => `session-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`

const isChatMode = (value: unknown): value is ChatMode =>
  value === 'companion' || value === 'advice' || value === 'style_clone' || value === 'soothing'

const createWelcomeMessage = (content = DEFAULT_WELCOME_MESSAGE): MessageItem => ({
  id: createMessageId('assistant'),
  role: 'assistant',
  content,
})

const createConversation = (
  title: string,
  mode: ChatMode,
  preview: string,
): ConversationItem => ({
  id: createConversationId(),
  title,
  preview,
  mode,
  messages: [createWelcomeMessage()],
  draft: '',
})

const createDefaultConversation = (): ConversationItem =>
  createConversation(
    DEFAULT_CONVERSATION_TITLE,
    'companion',
    DEFAULT_CONVERSATION_PREVIEW,
  )

const mapConversationFromApi = (item: ConversationHistoryItem): ConversationItem => {
  const messages =
    item.messages.length > 0
      ? item.messages.map((messageItem) => ({
          id: messageItem.id,
          role: messageItem.role,
          content: messageItem.content,
          loading: false,
        }))
      : [createWelcomeMessage()]

  const lastMessage = messages[messages.length - 1]
  return {
    id: item.id || createConversationId(),
    title: item.title || DEFAULT_CONVERSATION_TITLE,
    preview: item.preview || lastMessage?.content.slice(0, 18) || DEFAULT_CONVERSATION_PREVIEW,
    mode: isChatMode(item.mode) ? item.mode : 'companion',
    messages,
    draft: '',
    latestTrace: item.latest_trace ?? undefined,
  }
}

const conversations = ref<ConversationItem[]>([createDefaultConversation()])
const activeConversationId = ref(conversations.value[0].id)
const submitting = ref(false)
const serviceReady = ref(false)

const activeConversation = computed(() => {
  const target = conversations.value.find((item) => item.id === activeConversationId.value)
  return target ?? conversations.value[0]
})

const historyConversations = computed(() =>
  conversations.value.filter((item) => item.messages.some((message) => message.role === 'user')),
)

const activeModeLabel = computed(() => {
  const current = modeOptions.find((item) => item.value === activeConversation.value.mode)
  return current?.label ?? '陪伴'
})

const loadConversationHistory = async () => {
  const history = await fetchConversationHistory(DEMO_USER_ID)
  if (history.conversations.length === 0) {
    return
  }

  const mappedConversations = history.conversations.map(mapConversationFromApi)
  const currentActiveId = activeConversationId.value

  conversations.value = mappedConversations
  activeConversationId.value = mappedConversations.some((item) => item.id === currentActiveId)
    ? currentActiveId
    : mappedConversations[0].id
}

const startNewChat = () => {
  const newConversation = createConversation(DEFAULT_CONVERSATION_TITLE, 'companion', '刚刚创建')
  conversations.value = [newConversation, ...conversations.value]
  activeConversationId.value = newConversation.id
}

const switchConversation = (id: string) => {
  activeConversationId.value = id
}

const changeMode = (mode: ChatMode) => {
  updateConversation(activeConversation.value.id, (conversation) => {
    conversation.mode = mode
  })
}

const updateConversation = (
  id: string,
  updater: (conversation: ConversationItem) => void,
) => {
  const target = conversations.value.find((item) => item.id === id)
  if (!target) {
    return
  }
  updater(target)
}

const handleEnter = (event: KeyboardEvent) => {
  if (event.shiftKey) {
    return
  }
  event.preventDefault()
  submitMessage()
}

const submitMessage = async () => {
  const conversation = activeConversation.value
  const currentMessage = conversation.draft.trim()
  if (!currentMessage) {
    message.warning('先输入一条消息')
    return
  }

  const conversationId = conversation.id
  const userMessage: MessageItem = {
    id: createMessageId('user'),
    role: 'user',
    content: currentMessage,
  }
  const assistantMessage: MessageItem = {
    id: createMessageId('assistant'),
    role: 'assistant',
    content: '',
    loading: true,
  }

  updateConversation(conversationId, (target) => {
    target.draft = ''
    target.preview = currentMessage.slice(0, 18)
    if (target.title === DEFAULT_CONVERSATION_TITLE) {
      target.title = currentMessage.slice(0, 10) || DEFAULT_CONVERSATION_TITLE
    }
    target.messages.push(userMessage, assistantMessage)
  })

  submitting.value = true

  try {
    await streamChatMessage(
      {
        session_id: conversationId,
        user_id: DEMO_USER_ID,
        message: currentMessage,
        mode: conversation.mode,
      },
      {
        onToken: (chunk) => {
          updateConversation(conversationId, (target) => {
            const messageTarget = target.messages.find((item) => item.id === assistantMessage.id)
            if (messageTarget) {
              messageTarget.content += chunk
              messageTarget.loading = false
            }
          })
        },
        onDone: (result) => {
          updateConversation(conversationId, (target) => {
            target.latestTrace = result.trace
            const messageTarget = target.messages.find((item) => item.id === assistantMessage.id)
            if (messageTarget) {
              messageTarget.content = result.reply
              messageTarget.loading = false
            }
          })
        },
        onError: (errorMessage) => {
          throw new Error(errorMessage)
        },
      },
    )
  } catch (error) {
    console.error(error)
    updateConversation(conversationId, (target) => {
      target.messages = target.messages.filter((item) => item.id !== assistantMessage.id)
    })
    message.error('请求失败，请先确认后端和数据库是否启动')
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  const [healthResult, historyResult] = await Promise.allSettled([
    fetchHealth(),
    loadConversationHistory(),
  ])

  serviceReady.value = healthResult.status === 'fulfilled' && healthResult.value.status === 'ok'

  if (historyResult.status === 'rejected') {
    console.error(historyResult.reason)
    message.error('聊天记录加载失败，请检查后端数据库配置')
  }
})
</script>

<style scoped>
.chat-page {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  min-height: 100vh;
  background:
    radial-gradient(circle at top left, rgba(255, 255, 255, 0.92), transparent 28%),
    linear-gradient(180deg, #f5f5f7 0%, #f1f2f6 100%);
}

.sidebar {
  display: flex;
  flex-direction: column;
  padding: 18px;
  background: rgba(248, 248, 250, 0.96);
  border-right: 1px solid rgba(20, 20, 22, 0.06);
  box-shadow:
    inset -1px 0 0 rgba(255, 255, 255, 0.82),
    12px 0 30px rgba(15, 23, 42, 0.025);
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 18px;
  border-bottom: 1px solid rgba(20, 20, 22, 0.08);
}

.brand-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
}

.brand-logo {
  width: 34px;
  height: 34px;
  object-fit: contain;
}

.brand-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.brand {
  font-size: 20px;
  font-weight: 600;
  color: #111111;
}

.brand-subtitle {
  font-size: 12px;
  color: #8a8a8f;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.plain-icon-button {
  color: #111111;
  border: 1px solid rgba(20, 20, 22, 0.08);
  background: linear-gradient(180deg, #ffffff 0%, #f3f4f6 100%);
  box-shadow:
    0 8px 18px rgba(15, 23, 42, 0.05),
    inset 0 1px 0 rgba(255, 255, 255, 0.9);
}

.plain-icon-button:hover {
  color: #111111 !important;
  border-color: rgba(20, 20, 22, 0.14) !important;
  background: linear-gradient(180deg, #ffffff 0%, #eff1f4 100%) !important;
}

.session-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 18px;
}

.session-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px;
  text-align: left;
  border: 1px solid transparent;
  background: transparent;
  cursor: pointer;
  transition:
    background 0.2s ease,
    border-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.session-item:hover,
.session-item.is-active {
  background: rgba(255, 255, 255, 0.78);
  border-color: rgba(20, 20, 22, 0.06);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.92),
    0 8px 18px rgba(15, 23, 42, 0.04);
}

.session-item:hover {
  transform: translateY(-1px);
}

.session-item-title {
  font-size: 14px;
  font-weight: 600;
  color: #111111;
}

.session-item-preview {
  font-size: 12px;
  color: #777777;
}

.chat-main {
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(249, 249, 251, 0.98));
}

.chat-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 28px;
  border-bottom: 1px solid rgba(20, 20, 22, 0.06);
  backdrop-filter: blur(20px);
  box-shadow: inset 0 -1px 0 rgba(255, 255, 255, 0.78);
}

.chat-title-wrap {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.chat-title {
  font-size: 18px;
  font-weight: 600;
  color: #111111;
}

.chat-subtitle {
  font-size: 12px;
  color: #8a8a8f;
}

.topbar-user {
  display: flex;
  align-items: center;
}

.user-avatar-shell {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  border: 1px solid rgba(20, 20, 22, 0.08);
  background: linear-gradient(180deg, #ffffff 0%, #f3f4f6 100%);
  box-shadow:
    0 10px 22px rgba(15, 23, 42, 0.06),
    inset 0 1px 0 rgba(255, 255, 255, 0.92);
}

.user-avatar-image,
.message-user-avatar {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.user-avatar-fallback {
  font-size: 18px;
  color: #555555;
}

.user-status-dot {
  position: absolute;
  right: -2px;
  bottom: -2px;
  width: 10px;
  height: 10px;
  border: 2px solid #ffffff;
  background: #c9c9ce;
}

.user-status-dot.is-online {
  background: #34c759;
}

.message-list {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 20px;
  padding: 32px 32px 20px;
  overflow: auto;
}

.message-row {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.message-row.is-user {
  flex-direction: row-reverse;
}

.message-avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: 1px solid rgba(20, 20, 22, 0.07);
  background: rgba(255, 255, 255, 0.95);
  color: #444444;
  flex-shrink: 0;
  box-shadow: 0 6px 14px rgba(15, 23, 42, 0.05);
}

.assistant-mark {
  width: 22px;
  height: 22px;
  object-fit: contain;
}

.message-block {
  max-width: min(72%, 720px);
  padding: 15px 18px;
  border: 1px solid rgba(20, 20, 22, 0.06);
  background: rgba(255, 255, 255, 0.92);
  box-shadow:
    0 12px 28px rgba(15, 23, 42, 0.05),
    inset 0 1px 0 rgba(255, 255, 255, 0.9);
}

.block-user {
  background: linear-gradient(180deg, #1a1a1c 0%, #111111 100%);
  border-color: rgba(17, 17, 17, 0.92);
  color: #ffffff;
  box-shadow: 0 12px 28px rgba(17, 17, 17, 0.12);
}

.message-text {
  line-height: 1.85;
  white-space: pre-wrap;
}

.typing-line {
  margin-top: 8px;
  font-size: 12px;
  color: #8a8a8f;
}

.composer {
  padding: 14px 28px 28px;
  border-top: 1px solid rgba(20, 20, 22, 0.06);
  background: rgba(255, 255, 255, 0.9);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.84);
}

.composer-box {
  border: 1px solid rgba(20, 20, 22, 0.08);
  background: rgba(255, 255, 255, 0.98);
  box-shadow:
    0 20px 40px rgba(15, 23, 42, 0.055),
    inset 0 1px 0 rgba(255, 255, 255, 0.94);
  overflow: hidden;
}

.composer-input {
  padding: 18px 20px 18px;
  font-size: 15px;
}

.agent-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.agent-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 999px;
  border: 1px solid transparent;
  background: transparent;
  color: #6d6d73;
  font-size: 15px;
  cursor: pointer;
  transition:
    background 0.2s ease,
    color 0.2s ease,
    border-color 0.2s ease,
    box-shadow 0.2s ease;
}

.agent-chip:hover {
  color: #111111;
  background: rgba(244, 245, 248, 0.96);
}

.agent-chip.is-active {
  color: #111111;
  border-color: rgba(17, 17, 17, 0.08);
  background: rgba(249, 249, 251, 0.98);
  box-shadow:
    0 8px 18px rgba(15, 23, 42, 0.04),
    inset 0 1px 0 rgba(255, 255, 255, 0.96);
}

.agent-chip-icon {
  font-size: 18px;
}

.composer-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 16px 16px;
  border-top: 1px solid rgba(20, 20, 22, 0.05);
}

@media (max-width: 960px) {
  .chat-page {
    grid-template-columns: 1fr;
  }

  .sidebar {
    display: none;
  }

  .message-list,
  .chat-topbar,
  .composer {
    padding-left: 16px;
    padding-right: 16px;
  }

  .message-block {
    max-width: 88%;
  }

  .composer-actions {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
