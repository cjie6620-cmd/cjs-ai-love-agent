<template>
  <HeartParticles />
  <div class="chat-page">
    <!-- 移动端侧边栏遮罩层 -->
    <Transition name="overlay-fade">
      <div v-if="sidebarOpen" class="sidebar-overlay" @click="sidebarOpen = false" />
    </Transition>

    <!-- 侧边栏：桌面端常驻，移动端抽屉式滑入 -->
    <aside :class="['sidebar', { 'is-open': sidebarOpen }]">
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

      <div class="session-list">
        <button
          v-for="item in historyConversations"
          :key="item.id"
          :class="['session-item', { 'is-active': item.id === activeConversationId }]"
          type="button"
          @click="switchConversation(item.id); sidebarOpen = false"
        >
          <span class="session-item-title">{{ item.title }}</span>
          <span class="session-item-preview">{{ item.preview }}</span>
        </button>
      </div>
    </aside>

    <main class="chat-main">
      <header class="chat-topbar">
        <!-- 移动端汉堡按钮 -->
        <button class="mobile-menu-btn" type="button" @click="sidebarOpen = true">
          <MenuOutlined />
        </button>

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

      <section ref="messageListRef" class="message-list">
        <!-- 空状态欢迎页 -->
        <div v-if="isEmptyConversation" class="welcome-empty">
          <img class="welcome-logo" src="/i-love-new-york.svg" alt="AI Love" />
          <h2 class="welcome-title">AI Love</h2>
          <p class="welcome-desc">说出你的心事，我在这里倾听</p>
          <div class="welcome-hints">
            <button
              v-for="hint in quickHints"
              :key="hint"
              class="welcome-hint-chip"
              type="button"
              @click="activeConversation.draft = hint"
            >
              {{ hint }}
            </button>
          </div>
        </div>

        <!-- 消息列表 -->
        <TransitionGroup v-else name="msg" tag="div" class="message-list-inner">
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
              <div v-if="item.loading" class="typing-line">
                <span class="typing-dot" />
                <span class="typing-dot" />
                <span class="typing-dot" />
                <span class="typing-label">正在回复...</span>
              </div>
              <div
                v-if="shouldShowAdvisor(item)"
                class="advisor-panel"
              >
                <div class="advisor-questions">
                  <button
                    v-for="question in item.advisor?.suggested_questions ?? []"
                    :key="question"
                    class="advisor-question-chip"
                    type="button"
                    :disabled="submitting"
                    @click="sendAdvisorQuestion(question)"
                  >
                    {{ question }}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </TransitionGroup>
      </section>

      <footer class="composer">
        <div class="composer-box">
          <a-textarea
            v-model:value="activeConversation.draft"
            :auto-size="{ minRows: 1, maxRows: 4 }"
            :bordered="false"
            class="composer-input"
            placeholder="说点什么..."
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
                <span class="agent-chip-label">{{ item.label }}</span>
              </button>
            </div>
            <a-button
              class="send-btn"
              type="primary"
              shape="circle"
              :loading="submitting"
              @click="() => submitMessage()"
            >
              <template v-if="!submitting" #icon><SendOutlined /></template>
            </a-button>
          </div>
        </div>
      </footer>
    </main>
  </div>
</template>

<!-- 工作台视图组件脚本部分 -->

<script setup lang="ts">
import {
  BulbOutlined,
  CopyOutlined,
  HeartOutlined,
  MenuOutlined,
  MessageOutlined,
  PlusOutlined,
  SendOutlined,
  UserOutlined,
} from '@ant-design/icons-vue'
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { message } from 'ant-design-vue'

import HeartParticles from '@/components/HeartParticles.vue'
import { fetchConversationHistory, fetchHealth, streamChatMessage } from '@/api/chat'
import type { ChatAdvisor, ChatMode, ChatTrace, ConversationHistoryItem } from '@/types/chat'

interface MessageItem {
  id: string
  role: 'user' | 'assistant'
  content: string
  loading?: boolean
  advisor?: ChatAdvisor
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

const quickHints = [
  '最近心情有点低落...',
  '想聊聊感情的事',
  '帮我分析一下 TA 的态度',
  '需要一些鼓励',
]

const DEMO_USER_ID = 'user-demo-001'
const DEFAULT_WELCOME_MESSAGE = '你好，直接发消息就行。'
const DEFAULT_CONVERSATION_TITLE = '新对话'
const DEFAULT_CONVERSATION_PREVIEW = '开始聊天'

const userProfile = reactive({
  name: '用户',
  avatarUrl: '',
})

const sidebarOpen = ref(false)

const messageListRef = ref<HTMLElement | null>(null)

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
          advisor: messageItem.advisor ?? undefined,
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

const latestAssistantMessageId = computed(() => {
  const messages = [...activeConversation.value.messages].reverse()
  return messages.find((item) => item.role === 'assistant' && !item.loading)?.id ?? ''
})

const isEmptyConversation = computed(() => {
  const msgs = activeConversation.value.messages
  return msgs.length <= 1 && !msgs.some((m) => m.role === 'user')
})

const scrollToBottom = () => {
  nextTick(() => {
    const el = messageListRef.value
    if (el) {
      el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
    }
  })
}

watch(
  () => activeConversation.value.messages.length,
  () => scrollToBottom(),
)

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

const shouldShowAdvisor = (messageItem: MessageItem) =>
  messageItem.role === 'assistant' &&
  messageItem.id === latestAssistantMessageId.value &&
  !!messageItem.advisor?.suggested_questions?.length

const sendAdvisorQuestion = (question: string) => {
  submitMessage(question)
}

const submitMessage = async (directMessage?: unknown) => {
  if (submitting.value) {
    return
  }
  const conversation = activeConversation.value
  const rawMessage = typeof directMessage === 'string' ? directMessage : conversation.draft
  const currentMessage = rawMessage.trim()
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
          scrollToBottom()
        },
        onDone: (result) => {
          updateConversation(conversationId, (target) => {
            target.latestTrace = result.trace
            const messageTarget = target.messages.find((item) => item.id === assistantMessage.id)
            if (messageTarget) {
              // 流式阶段展示的是实时 token，done 阶段以后端最终结果为准。
              // 这样可以兜底修正安全清洗、工具调用补全或分片丢失导致的内容偏差。
              if (!messageTarget.content || !messageTarget.content.trim() || messageTarget.content !== result.reply) {
                messageTarget.content = result.reply
              }
              messageTarget.loading = false
              messageTarget.advisor = result.advisor ?? undefined
            }
          })
          scrollToBottom()
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
/* ================================================================
   极光动态渐变背景
   ================================================================ */
.chat-page {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  height: 100dvh;
  background: var(--surface-bg);
  overflow: hidden;
}

/* ================================================================
   移动端侧边栏遮罩
   ================================================================ */
.sidebar-overlay {
  display: none;
}

.overlay-fade-enter-active,
.overlay-fade-leave-active {
  transition: opacity 0.3s ease;
}

.overlay-fade-enter-from,
.overlay-fade-leave-to {
  opacity: 0;
}

/* ================================================================
   毛玻璃侧边栏（桌面常驻 / 移动抽屉）
   ================================================================ */
.sidebar {
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 20px;
  background: rgba(255, 255, 255, 0.32);
  border-right: 1px solid rgba(255, 255, 255, 0.4);
  backdrop-filter: blur(28px) saturate(140%);
  -webkit-backdrop-filter: blur(28px) saturate(140%);
  box-shadow:
    inset -1px 0 0 rgba(255, 255, 255, 0.5),
    8px 0 32px rgba(232, 68, 122, 0.03);
  overflow-y: auto;
  transition: transform 0.35s cubic-bezier(0.16, 1, 0.3, 1);
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 16px;
  margin-bottom: 4px;
  border-bottom: 1px solid rgba(232, 68, 122, 0.1);
}

.brand-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
}

.brand-logo {
  width: 32px;
  height: 32px;
  object-fit: contain;
  filter: drop-shadow(0 2px 6px rgba(232, 68, 122, 0.18));
}

.brand-text {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.brand {
  font-size: 19px;
  font-weight: 700;
  letter-spacing: -0.02em;
  background: linear-gradient(135deg, #d63384 0%, #e8447a 60%, #f7797d 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.brand-subtitle {
  font-size: 11px;
  font-weight: 500;
  color: var(--text-muted);
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

/* 新建对话按钮 */
.plain-icon-button {
  color: var(--brand-rose);
  border: 1px solid rgba(232, 68, 122, 0.14);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.5);
  box-shadow: 0 2px 8px rgba(232, 68, 122, 0.06);
  transition: all 0.25s ease;
}

.plain-icon-button:hover {
  color: var(--brand-rose-deep) !important;
  border-color: rgba(232, 68, 122, 0.24) !important;
  background: rgba(255, 255, 255, 0.7) !important;
  box-shadow: 0 4px 16px rgba(232, 68, 122, 0.12) !important;
  transform: translateY(-1px);
}

/* ================================================================
   会话列表
   ================================================================ */
.session-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 12px;
}

.session-item {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 11px 12px;
  text-align: left;
  border: 1px solid transparent;
  border-radius: 12px;
  background: transparent;
  cursor: pointer;
  transition:
    background 0.3s cubic-bezier(0.4, 0, 0.2, 1),
    border-color 0.3s ease,
    box-shadow 0.3s ease,
    transform 0.2s ease;
}

.session-item:hover {
  background: rgba(255, 255, 255, 0.5);
  border-color: rgba(232, 68, 122, 0.1);
  transform: translateY(-1px);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.7),
    0 6px 20px rgba(232, 68, 122, 0.06);
}

.session-item.is-active {
  background: rgba(255, 255, 255, 0.6);
  border-color: rgba(232, 68, 122, 0.22);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.8),
    0 6px 20px rgba(232, 68, 122, 0.1);
}

.session-item-title {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--text-heading);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-item-preview {
  font-size: 12px;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ================================================================
   聊天主区域
   ================================================================ */
.chat-main {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  background: transparent;
  overflow: hidden;
}

/* ================================================================
   磨砂玻璃顶栏
   ================================================================ */
.chat-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 24px;
  border-bottom: 1px solid rgba(232, 68, 122, 0.08);
  background: rgba(255, 255, 255, 0.4);
  backdrop-filter: blur(28px) saturate(140%);
  -webkit-backdrop-filter: blur(28px) saturate(140%);
}

/* 移动端汉堡按钮 — 桌面隐藏 */
.mobile-menu-btn {
  display: none;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: 1px solid rgba(232, 68, 122, 0.12);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.5);
  color: var(--brand-rose);
  font-size: 16px;
  cursor: pointer;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.mobile-menu-btn:hover {
  background: rgba(255, 255, 255, 0.7);
  box-shadow: 0 4px 12px rgba(232, 68, 122, 0.1);
}

.chat-title-wrap {
  display: flex;
  flex-direction: column;
  gap: 1px;
  flex: 1;
  min-width: 0;
}

.chat-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-heading);
  letter-spacing: -0.01em;
}

.chat-subtitle {
  font-size: 12px;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.topbar-user {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.user-avatar-shell {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: 1px solid rgba(232, 68, 122, 0.1);
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.55);
  box-shadow: 0 4px 12px rgba(232, 68, 122, 0.06);
}

.user-avatar-image,
.message-user-avatar {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  object-fit: cover;
}

.user-avatar-fallback {
  font-size: 16px;
  color: var(--text-secondary);
}

.user-status-dot {
  position: absolute;
  right: -1px;
  bottom: -1px;
  width: 9px;
  height: 9px;
  border: 2px solid rgba(255, 255, 255, 0.85);
  border-radius: 50%;
  background: #c9c9ce;
  transition: background 0.3s ease, box-shadow 0.3s ease;
}

.user-status-dot.is-online {
  background: #34c759;
  box-shadow: 0 0 6px rgba(52, 199, 89, 0.45);
}

/* ================================================================
   消息列表
   ================================================================ */
.message-list {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
  padding: 24px 28px 16px;
  overflow-y: auto;
  overflow-x: hidden;
  scroll-behavior: smooth;
}

.message-list-inner {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.message-row {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.message-row.is-user {
  flex-direction: row-reverse;
}

.message-avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border: 1px solid rgba(232, 68, 122, 0.08);
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.6);
  color: var(--text-secondary);
  flex-shrink: 0;
  box-shadow: 0 4px 12px rgba(232, 68, 122, 0.05);
}

.assistant-mark {
  width: 20px;
  height: 20px;
  object-fit: contain;
}

/* ================================================================
   消息气泡
   ================================================================ */
.message-block {
  max-width: min(72%, 680px);
  padding: 14px 18px;
  border: 1px solid rgba(255, 255, 255, 0.38);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.48);
  box-shadow:
    0 6px 20px rgba(74, 25, 66, 0.05),
    inset 0 1px 0 rgba(255, 255, 255, 0.65);
}

.block-assistant {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* 用户消息气泡 — 柔和玫瑰渐变 */
.block-user {
  background: linear-gradient(135deg, #f7797d 0%, #e8447a 45%, #d63384 100%);
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: #ffffff;
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
  box-shadow:
    0 8px 24px rgba(232, 68, 122, 0.2),
    inset 0 1px 0 rgba(255, 255, 255, 0.2);
}

.message-text {
  font-size: 14.5px;
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-word;
}

.advisor-panel {
  display: flex;
  flex-direction: column;
  padding-top: 2px;
}

.advisor-questions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.advisor-question-chip {
  padding: 8px 12px;
  border: 1px solid rgba(232, 68, 122, 0.12);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.72);
  color: var(--brand-rose-deep);
  font-size: 12px;
  line-height: 1.4;
  cursor: pointer;
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease,
    border-color 0.2s ease,
    background 0.2s ease;
}

.advisor-question-chip:hover:enabled {
  border-color: rgba(232, 68, 122, 0.28);
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 6px 18px rgba(232, 68, 122, 0.08);
  transform: translateY(-1px);
}

.advisor-question-chip:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

/* ================================================================
   心跳脉冲打字指示器（三点 + 文字）
   ================================================================ */
.typing-line {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 10px;
  padding: 4px 0;
}

.typing-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--brand-rose);
  opacity: 0.5;
  animation: typing-bounce 1.4s ease-in-out infinite;
}

.typing-dot:nth-child(2) { animation-delay: 0.16s; }
.typing-dot:nth-child(3) { animation-delay: 0.32s; }

.typing-label {
  margin-left: 6px;
  font-size: 12px;
  color: var(--brand-rose);
  opacity: 0.7;
}

@keyframes typing-bounce {
  0%, 80%, 100% { transform: scale(0.7); opacity: 0.35; }
  40%           { transform: scale(1.1); opacity: 0.9; }
}

/* ================================================================
   空状态欢迎页
   ================================================================ */
.welcome-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  padding: 40px 20px;
  text-align: center;
  animation: welcome-fade-in 0.6s ease;
}

@keyframes welcome-fade-in {
  from { opacity: 0; transform: translateY(16px); }
  to   { opacity: 1; transform: translateY(0); }
}

.welcome-logo {
  width: 56px;
  height: 56px;
  object-fit: contain;
  margin-bottom: 16px;
  filter: drop-shadow(0 4px 12px rgba(232, 68, 122, 0.2));
  animation: welcome-float 4s ease-in-out infinite;
}

@keyframes welcome-float {
  0%, 100% { transform: translateY(0); }
  50%      { transform: translateY(-8px); }
}

.welcome-title {
  margin: 0 0 6px;
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.02em;
  background: linear-gradient(135deg, #d63384, #e8447a, #f7797d);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.welcome-desc {
  margin: 0 0 28px;
  font-size: 14px;
  color: var(--text-muted);
  line-height: 1.6;
}

.welcome-hints {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
  max-width: 420px;
}

.welcome-hint-chip {
  padding: 8px 16px;
  font-size: 13px;
  color: var(--brand-rose-deep);
  border: 1px solid rgba(232, 68, 122, 0.15);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.5);
  cursor: pointer;
  transition: all 0.25s ease;
}

.welcome-hint-chip:hover {
  background: rgba(255, 255, 255, 0.72);
  border-color: rgba(232, 68, 122, 0.28);
  box-shadow: 0 4px 16px rgba(232, 68, 122, 0.1);
  transform: translateY(-1px);
}

/* ================================================================
   磨砂玻璃输入区
   ================================================================ */
.composer {
  flex-shrink: 0;
  padding: 12px 24px 20px;
  padding-bottom: max(20px, env(safe-area-inset-bottom, 20px));
  border-top: 1px solid rgba(232, 68, 122, 0.06);
  background: rgba(255, 255, 255, 0.35);
  backdrop-filter: blur(28px) saturate(140%);
  -webkit-backdrop-filter: blur(28px) saturate(140%);
}

.composer-box {
  border: 1px solid rgba(232, 68, 122, 0.1);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.52);
  box-shadow:
    0 8px 28px rgba(232, 68, 122, 0.05),
    inset 0 1px 0 rgba(255, 255, 255, 0.6);
  overflow: hidden;
  transition: border-color 0.3s ease, box-shadow 0.3s ease;
}

.composer-box:focus-within {
  border-color: rgba(232, 68, 122, 0.25);
  box-shadow:
    0 8px 28px rgba(232, 68, 122, 0.1),
    inset 0 1px 0 rgba(255, 255, 255, 0.6);
}

.composer-input {
  padding: 14px 18px;
  font-size: 14.5px;
}

.composer-input :deep(textarea.ant-input) {
  max-height: 112px !important;
  overflow-y: auto !important;
  resize: none;
}

/* ================================================================
   模式切换芯片
   ================================================================ */
.agent-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  flex: 1;
  min-width: 0;
}

.agent-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 12px;
  border-radius: 999px;
  border: 1px solid transparent;
  background: transparent;
  color: var(--text-muted);
  font-size: 13px;
  cursor: pointer;
  transition:
    background 0.25s ease,
    color 0.25s ease,
    border-color 0.25s ease,
    box-shadow 0.25s ease;
}

.agent-chip:hover {
  color: var(--brand-rose);
  background: rgba(232, 68, 122, 0.05);
}

.agent-chip.is-active {
  color: var(--brand-rose-deep);
  border-color: rgba(232, 68, 122, 0.18);
  background: rgba(232, 68, 122, 0.07);
  box-shadow: 0 2px 10px rgba(232, 68, 122, 0.08);
}

.agent-chip-icon {
  font-size: 15px;
}

.agent-chip-label {
  line-height: 1;
}

.composer-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 12px 10px;
  border-top: 1px solid rgba(232, 68, 122, 0.05);
}

/* 发送按钮 — 圆形玫瑰渐变 */
.send-btn.send-btn {
  width: 38px;
  height: 38px;
  min-width: 38px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--brand-rose-deep), var(--brand-rose));
  border: none;
  box-shadow: 0 4px 14px rgba(232, 68, 122, 0.22);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  flex-shrink: 0;
}

.send-btn.send-btn:hover {
  transform: translateY(-2px) scale(1.05);
  box-shadow: 0 8px 24px rgba(232, 68, 122, 0.32);
}

/* ================================================================
   消息入场动画
   ================================================================ */
.msg-enter-active {
  transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}

.msg-enter-from {
  opacity: 0;
  transform: translateY(20px) scale(0.97);
}

.msg-move {
  transition: transform 0.3s ease;
}

/* ================================================================
   平板 (641px ~ 1024px)
   侧边栏变窄，气泡更宽，字号微调
   ================================================================ */
@media (min-width: 641px) and (max-width: 1024px) {
  .chat-page {
    grid-template-columns: 220px minmax(0, 1fr);
  }

  .sidebar {
    padding: 16px;
  }

  .brand-logo {
    width: 28px;
    height: 28px;
  }

  .brand {
    font-size: 17px;
  }

  .message-list {
    padding: 20px 20px 12px;
  }

  .message-block {
    max-width: 80%;
  }

  .chat-topbar {
    padding: 12px 20px;
  }

  .composer {
    padding: 10px 20px 16px;
  }

  .welcome-title {
    font-size: 22px;
  }
}

/* ================================================================
   手机 (<=640px)
   单列布局，侧边栏变抽屉，全面移动端优化
   ================================================================ */
@media (max-width: 640px) {
  .chat-page {
    grid-template-columns: 1fr;
  }

  /* 侧边栏 — 抽屉式，从左滑入 */
  .sidebar {
    position: fixed;
    inset: 0 auto 0 0;
    z-index: 1000;
    width: 280px;
    max-width: 82vw;
    transform: translateX(-100%);
    border-right: none;
    box-shadow: 8px 0 40px rgba(0, 0, 0, 0.1);
  }

  .sidebar.is-open {
    transform: translateX(0);
  }

  /* 遮罩层 */
  .sidebar-overlay {
    display: block;
    position: fixed;
    inset: 0;
    z-index: 999;
    background: rgba(0, 0, 0, 0.25);
    backdrop-filter: blur(2px);
  }

  /* 显示汉堡按钮 */
  .mobile-menu-btn {
    display: flex;
  }

  /* 顶栏紧凑 */
  .chat-topbar {
    padding: 10px 14px;
  }

  .chat-title {
    font-size: 15px;
  }

  .user-avatar-shell {
    width: 32px;
    height: 32px;
  }

  .user-avatar-fallback {
    font-size: 14px;
  }

  /* 消息区域 — 全宽填满 */
  .message-list {
    padding: 16px 12px 12px;
  }

  .message-list-inner {
    gap: 14px;
  }

  .message-avatar {
    width: 30px;
    height: 30px;
  }

  .assistant-mark {
    width: 18px;
    height: 18px;
  }

  .message-block {
    max-width: 85%;
    padding: 12px 14px;
    border-radius: 16px;
  }

  .message-text {
    font-size: 14px;
    line-height: 1.7;
  }

  /* 输入区域紧凑 */
  .composer {
    padding: 8px 10px 12px;
    padding-bottom: max(12px, env(safe-area-inset-bottom, 12px));
  }

  .composer-box {
    border-radius: 16px;
  }

  .composer-input {
    padding: 12px 14px;
    font-size: 14px;
  }

  .composer-actions {
    padding: 6px 10px 8px;
    gap: 8px;
  }

  /* 模式芯片更紧凑 */
  .agent-chip {
    padding: 5px 9px;
    font-size: 12px;
    gap: 4px;
  }

  .agent-chip-icon {
    font-size: 13px;
  }

  .send-btn.send-btn {
    width: 34px;
    height: 34px;
    min-width: 34px;
  }

  /* 欢迎页适配 */
  .welcome-logo {
    width: 44px;
    height: 44px;
  }

  .welcome-title {
    font-size: 22px;
  }

  .welcome-desc {
    font-size: 13px;
    margin-bottom: 20px;
  }

  .welcome-hints {
    gap: 6px;
  }

  .welcome-hint-chip {
    padding: 7px 12px;
    font-size: 12px;
  }
}

/* ================================================================
   超宽桌面 (>1440px) — 居中约束宽度
   ================================================================ */
@media (min-width: 1441px) {
  .message-list-inner {
    max-width: 860px;
    margin: 0 auto;
    width: 100%;
  }

  .composer-box {
    max-width: 860px;
    margin: 0 auto;
  }
}
</style>
