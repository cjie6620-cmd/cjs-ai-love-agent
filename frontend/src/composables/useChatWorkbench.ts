import { computed, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'

import { fetchConversationHistory, fetchHealth, streamChatMessage } from '@/api/chat'
import type {
  AssistantStreamState,
  ChatAdvisor,
  ChatMode,
  ChatTrace,
  ConversationHistoryItem,
  ThinkingChunk,
} from '@/types/chat'

export interface MessageItem {
  id: string
  role: 'user' | 'assistant'
  content: string
  loading?: boolean
  advisor?: ChatAdvisor
  streamState?: AssistantStreamState
}

export interface ConversationItem {
  id: string
  title: string
  preview: string
  mode: ChatMode
  messages: MessageItem[]
  draft: string
  latestTrace?: ChatTrace
}

const DEMO_USER_ID = 'user-demo-001'
const DEFAULT_WELCOME_MESSAGE = '你好，直接发消息就可以。'
const DEFAULT_CONVERSATION_TITLE = '新对话'
const DEFAULT_CONVERSATION_PREVIEW = '开始聊天'

const modeLabelMap: Record<ChatMode, string> = {
  companion: '陪伴',
  advice: '建议',
  style_clone: '复刻',
  soothing: '安抚',
}

export const modeDetails: Record<ChatMode, { title: string; desc: string; tone: string }> = {
  companion: {
    title: '温柔陪伴',
    desc: '先接住情绪，再陪你把关系里的线索讲清楚。',
    tone: '倾听、共情、慢慢梳理',
  },
  advice: {
    title: '关系建议',
    desc: '把问题拆成可执行的小动作，避免情绪里做仓促决定。',
    tone: '分析、选择、行动',
  },
  style_clone: {
    title: '表达复刻',
    desc: '把你的意思改写成更像你、更适合当下关系的说法。',
    tone: '语气、边界、分寸',
  },
  soothing: {
    title: '情绪安抚',
    desc: '先降低焦虑和委屈感，再一起看下一步怎么走。',
    tone: '安定、支持、恢复',
  },
}

const fallbackThinkingSteps = [
  '正在接住你的情绪线索',
  '正在梳理关系里的关键变化',
  '正在判断适合先安抚还是先分析',
]

const createMessageId = (role: MessageItem['role']) =>
  `${role}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`

const createConversationId = () => `session-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`

const createThinkingChunk = (content: string): ThinkingChunk => ({
  id: `thinking-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
  content,
})

const normalizeReplyText = (value: string) => value.replace(/\s+/g, ' ').trim()

const shouldSyncFinalReply = (currentReply: string, finalReply: string) => {
  const normalizedCurrent = normalizeReplyText(currentReply)
  const normalizedFinal = normalizeReplyText(finalReply)

  if (!normalizedFinal) {
    return false
  }

  if (!normalizedCurrent) {
    return true
  }

  if (normalizedCurrent === normalizedFinal) {
    return false
  }

  return (
    normalizedFinal.startsWith(normalizedCurrent) ||
    normalizedCurrent.startsWith(normalizedFinal) ||
    Math.abs(normalizedFinal.length - normalizedCurrent.length) > 16
  )
}

const createStreamState = (): AssistantStreamState => ({
  thinkingStatus: 'streaming',
  thinkingChunks: [createThinkingChunk(fallbackThinkingSteps[0])],
  replyStatus: 'streaming',
})

const createWelcomeMessage = (content = DEFAULT_WELCOME_MESSAGE): MessageItem => ({
  id: createMessageId('assistant'),
  role: 'assistant',
  content,
  streamState: {
    thinkingStatus: 'idle',
    thinkingChunks: [],
    replyStatus: 'done',
  },
})

const isChatMode = (value: unknown): value is ChatMode =>
  value === 'companion' || value === 'advice' || value === 'style_clone' || value === 'soothing'

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
  createConversation(DEFAULT_CONVERSATION_TITLE, 'companion', DEFAULT_CONVERSATION_PREVIEW)

const mapConversationFromApi = (item: ConversationHistoryItem): ConversationItem => {
  const messages =
    item.messages.length > 0
      ? item.messages.map((messageItem) => ({
          id: messageItem.id,
          role: messageItem.role,
          content: messageItem.content,
          loading: false,
          advisor: messageItem.advisor ?? undefined,
          streamState:
            messageItem.role === 'assistant'
              ? {
                  thinkingStatus: 'idle' as const,
                  thinkingChunks: [],
                  replyStatus: 'done' as const,
                }
              : undefined,
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

export const useChatWorkbench = () => {
  const conversations = ref<ConversationItem[]>([createDefaultConversation()])
  const activeConversationId = ref(conversations.value[0].id)
  const submitting = ref(false)
  const serviceReady = ref(false)
  const streamTimers: number[] = []

  const userProfile = reactive({
    name: '用户',
    avatarUrl: '',
  })

  const activeConversation = computed(() => {
    const target = conversations.value.find((item) => item.id === activeConversationId.value)
    return target ?? conversations.value[0]
  })

  const historyConversations = computed(() =>
    conversations.value.filter((item) => item.messages.some((messageItem) => messageItem.role === 'user')),
  )

  const activeModeLabel = computed(() => modeLabelMap[activeConversation.value.mode] ?? '陪伴')

  const latestAssistantMessageId = computed(() => {
    const messages = [...activeConversation.value.messages].reverse()
    return messages.find((item) => item.role === 'assistant' && !item.loading)?.id ?? ''
  })

  const isEmptyConversation = computed(() => {
    const msgs = activeConversation.value.messages
    return msgs.length <= 1 && !msgs.some((item) => item.role === 'user')
  })

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

  const findMessage = (conversationId: string, messageId: string) => {
    const conversation = conversations.value.find((item) => item.id === conversationId)
    return conversation?.messages.find((item) => item.id === messageId)
  }

  const clearThinkingTimers = () => {
    while (streamTimers.length) {
      const timer = streamTimers.pop()
      if (timer) {
        window.clearTimeout(timer)
      }
    }
  }

  const appendThinkingChunk = (
    conversationId: string,
    assistantMessageId: string,
    content: string,
  ) => {
    if (!content.trim()) {
      return
    }
    updateConversation(conversationId, (target) => {
      const messageTarget = target.messages.find((item) => item.id === assistantMessageId)
      if (!messageTarget?.streamState) {
        return
      }
      messageTarget.streamState.thinkingChunks.push(createThinkingChunk(content))
    })
  }

  const scheduleFallbackThinking = (conversationId: string, assistantMessageId: string) => {
    fallbackThinkingSteps.slice(1).forEach((step, index) => {
      const timer = window.setTimeout(() => {
        const messageTarget = findMessage(conversationId, assistantMessageId)
        if (messageTarget?.streamState?.thinkingStatus === 'streaming') {
          appendThinkingChunk(conversationId, assistantMessageId, step)
        }
      }, 650 + index * 760)
      streamTimers.push(timer)
    })
  }

  const markThinkingDone = (conversationId: string, assistantMessageId: string) => {
    updateConversation(conversationId, (target) => {
      const messageTarget = target.messages.find((item) => item.id === assistantMessageId)
      if (messageTarget?.streamState) {
        messageTarget.streamState.thinkingStatus = 'done'
      }
    })
  }

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

  const initialize = async () => {
    const [healthResult, historyResult] = await Promise.allSettled([
      fetchHealth(),
      loadConversationHistory(),
    ])

    serviceReady.value = healthResult.status === 'fulfilled' && healthResult.value.status === 'ok'

    if (historyResult.status === 'rejected') {
      console.error(historyResult.reason)
      message.error('聊天记录加载失败，请检查后端数据库配置')
    }
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

  const updateDraft = (value: string) => {
    updateConversation(activeConversation.value.id, (conversation) => {
      conversation.draft = value
    })
  }

  const shouldShowAdvisor = (messageItem: MessageItem) =>
    messageItem.role === 'assistant' &&
    messageItem.id === latestAssistantMessageId.value &&
    !!messageItem.advisor?.suggested_questions?.length

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
      streamState: createStreamState(),
    }

    updateConversation(conversationId, (target) => {
      target.draft = ''
      target.preview = currentMessage.slice(0, 24)
      if (target.title === DEFAULT_CONVERSATION_TITLE) {
        target.title = currentMessage.slice(0, 12) || DEFAULT_CONVERSATION_TITLE
      }
      target.messages.push(userMessage, assistantMessage)
    })

    submitting.value = true
    scheduleFallbackThinking(conversationId, assistantMessage.id)

    try {
      await streamChatMessage(
        {
          session_id: conversationId,
          user_id: DEMO_USER_ID,
          message: currentMessage,
          mode: conversation.mode,
        },
        {
          onThinkingStart: () => {
            clearThinkingTimers()
            updateConversation(conversationId, (target) => {
              const messageTarget = target.messages.find((item) => item.id === assistantMessage.id)
              if (messageTarget?.streamState) {
                messageTarget.streamState.thinkingStatus = 'streaming'
                messageTarget.streamState.thinkingChunks = []
              }
            })
          },
          onThinkingDelta: (chunk) => {
            appendThinkingChunk(conversationId, assistantMessage.id, chunk)
          },
          onThinkingDone: () => {
            markThinkingDone(conversationId, assistantMessage.id)
          },
          onToken: (chunk) => {
            markThinkingDone(conversationId, assistantMessage.id)
            updateConversation(conversationId, (target) => {
              const messageTarget = target.messages.find((item) => item.id === assistantMessage.id)
              if (messageTarget) {
                messageTarget.content += chunk
                messageTarget.loading = false
                if (messageTarget.streamState) {
                  messageTarget.streamState.replyStatus = 'streaming'
                }
              }
            })
          },
          onDone: (result) => {
            clearThinkingTimers()
            updateConversation(conversationId, (target) => {
              target.latestTrace = result.trace
              const messageTarget = target.messages.find((item) => item.id === assistantMessage.id)
              if (messageTarget) {
                if (shouldSyncFinalReply(messageTarget.content, result.reply)) {
                  messageTarget.content = result.reply
                }
                messageTarget.loading = false
                messageTarget.advisor = result.advisor ?? undefined
                if (messageTarget.streamState) {
                  messageTarget.streamState.thinkingStatus = 'done'
                  messageTarget.streamState.replyStatus = 'done'
                }
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
      clearThinkingTimers()
      updateConversation(conversationId, (target) => {
        const messageTarget = target.messages.find((item) => item.id === assistantMessage.id)
        if (messageTarget?.streamState) {
          messageTarget.streamState.replyStatus = 'error'
          messageTarget.streamState.thinkingStatus = 'done'
        }
        target.messages = target.messages.filter((item) => item.id !== assistantMessage.id)
      })
      message.error('请求失败，请先确认后端和数据库是否启动')
    } finally {
      submitting.value = false
    }
  }

  return {
    activeConversation,
    activeConversationId,
    activeModeLabel,
    changeMode,
    conversations,
    historyConversations,
    initialize,
    isEmptyConversation,
    latestAssistantMessageId,
    modeDetails,
    serviceReady,
    shouldShowAdvisor,
    startNewChat,
    submitting,
    submitMessage,
    switchConversation,
    updateDraft,
    userProfile,
  }
}
