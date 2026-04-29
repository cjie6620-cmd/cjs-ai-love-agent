import { computed, onUnmounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'

import { clearAuthTokens, fetchMe, login, logout, register, updateProfile, uploadAvatar, type AuthUser } from '@/api/auth'
import {
  ActiveStreamConflictError,
  cancelChatStream,
  GuestQuotaUnavailableError,
  LoginRequiredError,
  fetchConversationHistory,
  fetchHealth,
  isAbortError,
  streamChatMessage,
} from '@/api/chat'
import { getStoredAccessToken, resolveApiUrl } from '@/api/http'
import {
  clearMemoryItems,
  deleteMemoryItem,
  fetchMemoryItems,
  fetchMemorySettings,
  updateMemorySettings,
  type MemoryItem,
} from '@/api/memory'
import type {
  ActiveStreamStatus,
  AssistantStreamState,
  ChatAdvisor,
  ChatMode,
  ChatTrace,
  ConversationHistoryItem,
  ThinkingChunk,
} from '@/types/chat'

/**
 * 目的：定义 MessageItem 的前端数据结构。
 * 结果：为页面渲染、API 调用和状态管理提供稳定类型约束。
 */
export interface MessageItem {
  /**
   * 目的：描述 MessageItem.id 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  id: string
  /**
   * 目的：描述 MessageItem.role 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  role: 'user' | 'assistant'
  /**
   * 目的：描述 MessageItem.content 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  content: string
  /**
   * 目的：描述 MessageItem.loading 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  loading?: boolean
  /**
   * 目的：描述 MessageItem.advisor 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  advisor?: ChatAdvisor
  /**
   * 目的：描述 MessageItem.streamState 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  streamState?: AssistantStreamState
}

/**
 * 目的：定义 ConversationItem 的前端数据结构。
 * 结果：为页面渲染、API 调用和状态管理提供稳定类型约束。
 */
export interface ConversationItem {
  /**
   * 目的：描述 ConversationItem.id 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  id: string
  /**
   * 目的：描述 ConversationItem.title 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  title: string
  /**
   * 目的：描述 ConversationItem.preview 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  preview: string
  /**
   * 目的：描述 ConversationItem.mode 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  mode: ChatMode
  /**
   * 目的：描述 ConversationItem.messages 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  messages: MessageItem[]
  /**
   * 目的：描述 ConversationItem.draft 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  draft: string
  /**
   * 目的：描述 ConversationItem.latestTrace 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  latestTrace?: ChatTrace
  /**
   * 目的：描述 ConversationItem.activeStreamId 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  activeStreamId?: string
  /**
   * 目的：描述 ConversationItem.activeStreamStatus 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  activeStreamStatus?: ActiveStreamStatus
}

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

const normalizeAvatarUrl = (value: string) => {
  const avatarUrl = value.trim()
  if (!avatarUrl) {
    return ''
  }
  return /^https?:\/\//.test(avatarUrl) ? avatarUrl : resolveApiUrl(avatarUrl)
}

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

const createBackgroundPendingMessage = (streamId: string): MessageItem => ({
  id: `assistant-pending-${streamId}`,
  role: 'assistant',
  content: '',
  loading: true,
  streamState: {
    thinkingStatus: 'idle',
    thinkingChunks: [],
    replyStatus: 'streaming',
  },
})

const mapConversationFromApi = (item: ConversationHistoryItem): ConversationItem => {
  const messages: MessageItem[] =
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
                  replyStatus:
                    messageItem.reply_status === 'interrupted'
                      ? ('cancelled' as const)
                      : ('done' as const),
                }
              : undefined,
        }))
      : [createWelcomeMessage()]

  if (item.active_stream_id && messages[messages.length - 1]?.role !== 'assistant') {
    messages.push(createBackgroundPendingMessage(item.active_stream_id))
  }

  const lastMessage = messages[messages.length - 1]
  return {
    id: item.id || createConversationId(),
    title: item.title || DEFAULT_CONVERSATION_TITLE,
    preview: item.preview || lastMessage?.content.slice(0, 18) || DEFAULT_CONVERSATION_PREVIEW,
    mode: isChatMode(item.mode) ? item.mode : 'companion',
    messages,
    draft: '',
    latestTrace: item.latest_trace ?? undefined,
    activeStreamId: item.active_stream_id ?? undefined,
    activeStreamStatus: item.active_stream_status ?? undefined,
  }
}

interface UseChatWorkbenchOptions {
  initialSessionId?: string
}

/**
 * 目的：组合聊天工作台所需的状态、行为和派生数据。
 * 结果：返回接口约定结果，或完成对应的前端状态更新。
 */
export const useChatWorkbench = (options: UseChatWorkbenchOptions = {}) => {
  const conversations = ref<ConversationItem[]>([createDefaultConversation()])
  const activeConversationId = ref(conversations.value[0].id)
  const preferredInitialSessionId = ref((options.initialSessionId ?? '').trim())
  const submitting = ref(false)
  const serviceReady = ref(false)
  const streamTimers: number[] = []
  const currentAbortController = ref<AbortController | null>(null)
  const currentAbortMode = ref<'stop' | 'detach' | null>(null)
  const currentStreamId = ref('')
  const pendingStopRequested = ref(false)
  const currentStreamTarget = ref<{ conversationId: string; assistantMessageId: string } | null>(null)
  const historyRefreshTimer = ref<number | null>(null)
  const authDialogOpen = ref(false)
  const authMode = ref<'login' | 'register'>('login')
  const authSubmitting = ref(false)
  const authenticatedUser = ref<AuthUser | null>(null)
  const guestRemaining = ref<number | null>(null)
  const pendingLoginMessage = ref('')
  const profileDialogOpen = ref(false)
  const profileSubmitting = ref(false)
  const avatarUploading = ref(false)
  const memorySettingsLoading = ref(false)
  const memorySettingsSaving = ref(false)
  const memoryItemsLoading = ref(false)
  const memoryClearing = ref(false)
  const memoryItems = ref<MemoryItem[]>([])
  const memoryTotal = ref(0)

  const userProfile = reactive({
    name: '用户',
    avatarUrl: '',
  })

  const authForm = reactive({
    loginName: '',
    password: '',
    nickname: '',
  })

  const profileForm = reactive({
    nickname: '',
  })

  const memorySettings = reactive({
    memory_enabled: false,
  })

  const isAuthenticated = computed(() => !!authenticatedUser.value)

  const getRequestUserId = () => authenticatedUser.value?.id || ''

  const syncUserProfile = (user: AuthUser | null) => {
    if (!user) {
      userProfile.name = '用户'
      userProfile.avatarUrl = ''
      return
    }
    userProfile.name = user.nickname || user.external_user_id || '用户'
    userProfile.avatarUrl = normalizeAvatarUrl(user.avatar_url || '')
  }

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

  const hasConversation = (id: string) => conversations.value.some((item) => item.id === id)

  const selectConversation = (id: string, options: { detachStream?: boolean } = {}): boolean => {
    if (!id || !hasConversation(id)) {
      return false
    }
    if (options.detachStream ?? true) {
      detachLocalStream()
    }
    activeConversationId.value = id
    return true
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

  const isPendingAssistantMessage = (messageItem: MessageItem | undefined) =>
    !!messageItem && messageItem.role === 'assistant' && messageItem.id.startsWith('assistant-pending-')

  const isStreamActive = computed(() => submitting.value || !!activeConversation.value.activeStreamId)

  const isComposerLocked = computed(() => submitting.value || !!activeConversation.value.activeStreamId)

  const setConversationActiveStream = (
    conversationId: string,
    streamId: string,
    status: ActiveStreamStatus = 'running',
  ) => {
    updateConversation(conversationId, (conversation) => {
      conversation.activeStreamId = streamId
      conversation.activeStreamStatus = status
    })
  }

  const clearConversationActiveStream = (conversationId: string, streamId?: string) => {
    updateConversation(conversationId, (conversation) => {
      if (streamId && conversation.activeStreamId && conversation.activeStreamId !== streamId) {
        return
      }
      conversation.activeStreamId = undefined
      conversation.activeStreamStatus = undefined
    })
  }

  const ensureCancelledPlaceholder = (conversation: ConversationItem, streamId = '') => {
    const lastMessage = conversation.messages[conversation.messages.length - 1]
    if (lastMessage?.role === 'assistant') {
      return lastMessage
    }
    const placeholder = createBackgroundPendingMessage(streamId || `cancelled-${Date.now()}`)
    conversation.messages.push(placeholder)
    return placeholder
  }

  const markStreamCancelled = () => {
    const target = currentStreamTarget.value
    clearThinkingTimers()
    const conversationId = target?.conversationId ?? activeConversation.value.id
    updateConversation(conversationId, (conversation) => {
      const messageTarget =
        (target
          ? conversation.messages.find((item) => item.id === target.assistantMessageId)
          : undefined) ??
        conversation.messages
          .slice()
          .reverse()
          .find((item) => item.role === 'assistant' && (item.loading || isPendingAssistantMessage(item)))
      const resolvedTarget = messageTarget ?? ensureCancelledPlaceholder(conversation, conversation.activeStreamId)
      if (!resolvedTarget.streamState) {
        resolvedTarget.streamState = {
          thinkingStatus: 'done',
          thinkingChunks: [],
          replyStatus: 'cancelled',
        }
      }
      resolvedTarget.loading = false
      resolvedTarget.streamState.thinkingStatus = 'done'
      resolvedTarget.streamState.replyStatus = 'cancelled'
    })
  }

  const clearHistoryRefreshTimer = () => {
    if (historyRefreshTimer.value !== null) {
      window.clearInterval(historyRefreshTimer.value)
      historyRefreshTimer.value = null
    }
  }

  const detachLocalStream = () => {
    const controller = currentAbortController.value
    if (!controller || controller.signal.aborted) {
      return
    }
    currentAbortMode.value = 'detach'
    controller.abort()
  }

  const stopStreaming = async () => {
    const conversation = activeConversation.value
    const streamId = conversation.activeStreamId || currentStreamId.value
    if (!streamId) {
      if (submitting.value) {
        pendingStopRequested.value = false
        currentAbortMode.value = 'stop'
        markStreamCancelled()
        submitting.value = false
        const controller = currentAbortController.value
        if (controller && !controller.signal.aborted) {
          controller.abort()
        }
      }
      return
    }
    pendingStopRequested.value = false
    clearConversationActiveStream(conversation.id, streamId)
    markStreamCancelled()
    if (currentStreamId.value === streamId) {
      currentStreamId.value = ''
    }
    const controller = currentAbortController.value
    if (controller && !controller.signal.aborted) {
      currentAbortMode.value = 'stop'
      controller.abort()
    }
    submitting.value = false
    try {
      await cancelChatStream(streamId)
      syncHistoryPolling()
    } catch (error) {
      console.error(error)
      message.error('停止失败，请稍后重试')
      void loadConversationHistory().catch((historyError) => {
        console.warn('停止失败后刷新会话历史失败', historyError)
      })
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

  const resetToDefaultConversation = () => {
    clearHistoryRefreshTimer()
    conversations.value = [createDefaultConversation()]
    activeConversationId.value = conversations.value[0].id
  }

  const loadConversationHistory = async (preferredSessionId = '') => {
    const history = await fetchConversationHistory()
    if (history.conversations.length === 0) {
      resetToDefaultConversation()
      preferredInitialSessionId.value = ''
      return
    }

    const mappedConversations = history.conversations.map(mapConversationFromApi)
    const serverConversationIds = new Set(mappedConversations.map((item) => item.id))
    const draftOnlyConversations = conversations.value.filter(
      (item) => !serverConversationIds.has(item.id) && !item.messages.some((messageItem) => messageItem.role === 'user'),
    )
    const preferredId = preferredSessionId.trim() || preferredInitialSessionId.value
    const currentActiveId = activeConversationId.value
    conversations.value = [...draftOnlyConversations, ...mappedConversations]
    if (preferredId && hasConversation(preferredId)) {
      activeConversationId.value = preferredId
      preferredInitialSessionId.value = ''
    } else {
      activeConversationId.value = hasConversation(currentActiveId)
        ? currentActiveId
        : conversations.value[0].id
    }
    syncHistoryPolling()
  }

  const syncHistoryPolling = () => {
    const hasRemoteActiveStream =
      !currentAbortController.value && conversations.value.some((item) => !!item.activeStreamId)
    if (!hasRemoteActiveStream) {
      clearHistoryRefreshTimer()
      return
    }
    if (historyRefreshTimer.value !== null) {
      return
    }
    historyRefreshTimer.value = window.setInterval(() => {
      if (currentAbortController.value) {
        clearHistoryRefreshTimer()
        return
      }
      void loadConversationHistory().catch((error) => {
        console.warn('刷新会话历史失败', error)
      })
    }, 2500)
  }

  const initialize = async () => {
    const healthTask = fetchHealth()
    if (getStoredAccessToken()) {
      try {
        authenticatedUser.value = await fetchMe()
        syncUserProfile(authenticatedUser.value)
      } catch (error) {
        console.warn('登录态已失效', error)
        clearAuthTokens()
        authenticatedUser.value = null
        syncUserProfile(null)
      }
    }

    const historyTask = loadConversationHistory(preferredInitialSessionId.value)
    try {
      const healthResult = await healthTask
      serviceReady.value = healthResult.status === 'ok'
    } catch (error) {
      console.warn('健康检查失败', error)
      serviceReady.value = false
    }
    await historyTask
  }

  const startNewChat = () => {
    detachLocalStream()
    const newConversation = createConversation(DEFAULT_CONVERSATION_TITLE, 'companion', '刚刚创建')
    conversations.value = [newConversation, ...conversations.value]
    activeConversationId.value = newConversation.id
    return newConversation.id
  }

  const switchConversation = (id: string) => {
    return selectConversation(id)
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

  const openAuthDialog = (mode: 'login' | 'register' = 'login') => {
    authMode.value = mode
    authDialogOpen.value = true
  }

  const openProfileDialog = () => {
    if (!authenticatedUser.value) {
      openAuthDialog('login')
      return
    }
    profileForm.nickname = authenticatedUser.value.nickname || authenticatedUser.value.external_user_id || ''
    profileDialogOpen.value = true
    void loadMemoryManagement()
  }

  const closeProfileDialog = () => {
    if (profileSubmitting.value || avatarUploading.value) {
      return
    }
    profileDialogOpen.value = false
  }

  const closeAuthDialog = () => {
    if (authSubmitting.value) {
      return
    }
    authDialogOpen.value = false
  }

  const signOut = async () => {
    detachLocalStream()
    try {
      await logout()
    } finally {
      authenticatedUser.value = null
      syncUserProfile(null)
      memorySettings.memory_enabled = false
      memoryItems.value = []
      memoryTotal.value = 0
      guestRemaining.value = null
      pendingLoginMessage.value = ''
      profileDialogOpen.value = false
      resetToDefaultConversation()
      await loadConversationHistory()
    }
    message.success('已退出登录')
  }

  const submitAuth = async () => {
    const loginName = authForm.loginName.trim()
    const password = authForm.password.trim()
    const nickname = authForm.nickname.trim()
    if (!loginName || !password) {
      message.warning('请输入账号和密码')
      return
    }
    authSubmitting.value = true
    try {
      const payload = { login_name: loginName, password }
      const result = authMode.value === 'login' ? await login(payload) : await register({ ...payload, nickname })
      authenticatedUser.value = result.user
      syncUserProfile(result.user)
      profileForm.nickname = result.user.nickname || ''
      authDialogOpen.value = false
      guestRemaining.value = null
      message.success(authMode.value === 'login' ? '登录成功' : '注册成功')
      await loadConversationHistory()
      const pending = pendingLoginMessage.value
      pendingLoginMessage.value = ''
      if (pending) {
        await submitMessage(pending)
      }
    } catch (error) {
      console.error(error)
      message.error(authMode.value === 'login' ? '登录失败，请检查账号密码' : '注册失败，账号可能已存在')
    } finally {
      authSubmitting.value = false
    }
  }

  const submitProfile = async () => {
    const nickname = profileForm.nickname.trim()
    if (!nickname) {
      message.warning('请输入昵称')
      return
    }
    profileSubmitting.value = true
    try {
      const user = await updateProfile({ nickname })
      authenticatedUser.value = user
      syncUserProfile(user)
      message.success('个人资料已更新')
      profileDialogOpen.value = false
    } catch (error) {
      console.error(error)
      message.error('资料更新失败，请稍后重试')
    } finally {
      profileSubmitting.value = false
    }
  }

  const uploadProfileAvatar = async (file: File) => {
    avatarUploading.value = true
    try {
      const user = await uploadAvatar(file)
      authenticatedUser.value = user
      syncUserProfile(user)
      message.success('头像已更新')
    } catch (error) {
      console.error(error)
      message.error('头像上传失败，请确认文件类型和大小')
    } finally {
      avatarUploading.value = false
    }
  }

  const loadMemoryManagement = async () => {
    if (!authenticatedUser.value) {
      return
    }
    memorySettingsLoading.value = true
    memoryItemsLoading.value = true
    try {
      const [settings, list] = await Promise.all([
        fetchMemorySettings(),
        fetchMemoryItems({ limit: 50, offset: 0 }),
      ])
      memorySettings.memory_enabled = settings.memory_enabled
      memoryItems.value = list.items
      memoryTotal.value = list.total
    } catch (error) {
      console.error(error)
      message.error('长期记忆加载失败')
    } finally {
      memorySettingsLoading.value = false
      memoryItemsLoading.value = false
    }
  }

  const setMemoryEnabled = async (enabled: boolean) => {
    if (!authenticatedUser.value || memorySettingsSaving.value) {
      return
    }
    const previous = memorySettings.memory_enabled
    memorySettings.memory_enabled = enabled
    memorySettingsSaving.value = true
    try {
      const settings = await updateMemorySettings({ memory_enabled: enabled })
      memorySettings.memory_enabled = settings.memory_enabled
      message.success(settings.memory_enabled ? '长期记忆已开启' : '长期记忆已关闭')
    } catch (error) {
      console.error(error)
      memorySettings.memory_enabled = previous
      message.error('长期记忆设置失败')
    } finally {
      memorySettingsSaving.value = false
    }
  }

  const removeMemoryItem = async (id: string) => {
    if (!id) {
      return
    }
    try {
      const result = await deleteMemoryItem(id)
      if (result.deleted_count > 0) {
        memoryItems.value = memoryItems.value.filter((item) => item.id !== id)
        memoryTotal.value = Math.max(0, memoryTotal.value - result.deleted_count)
        message.success('记忆已删除')
      }
    } catch (error) {
      console.error(error)
      message.error('删除失败')
    }
  }

  const clearAllMemoryItems = async () => {
    if (memoryClearing.value || memoryItems.value.length === 0) {
      return
    }
    memoryClearing.value = true
    try {
      const result = await clearMemoryItems()
      if (result.deleted_count > 0) {
        memoryItems.value = []
        memoryTotal.value = 0
      }
      message.success('长期记忆已清空')
    } catch (error) {
      console.error(error)
      message.error('清空失败')
    } finally {
      memoryClearing.value = false
    }
  }

  const submitMessage = async (directMessage?: unknown) => {
    if (submitting.value) {
      return
    }
    const conversation = activeConversation.value
    if (conversation.activeStreamId) {
      message.warning('上一条回复仍在生成中，请先等待完成或点击停止')
      return
    }
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
    const abortController = new AbortController()
    currentAbortMode.value = null
    pendingStopRequested.value = false
    currentAbortController.value = abortController
    currentStreamTarget.value = {
      conversationId,
      assistantMessageId: assistantMessage.id,
    }
    scheduleFallbackThinking(conversationId, assistantMessage.id)

    try {
      await streamChatMessage(
        {
          session_id: conversationId,
          user_id: getRequestUserId(),
          message: currentMessage,
          mode: conversation.mode,
        },
        {
          onStreamId: (streamId) => {
            if (!streamId) {
              return
            }
            currentStreamId.value = streamId
            setConversationActiveStream(conversationId, streamId, 'running')
            if (pendingStopRequested.value) {
              void stopStreaming()
            }
          },
          onQuota: (remaining) => {
            if (remaining !== null && !Number.isNaN(remaining)) {
              guestRemaining.value = remaining
            }
          },
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
            const finishedStreamId = currentStreamId.value
            updateConversation(conversationId, (target) => {
              target.latestTrace = result.trace
              target.activeStreamId = undefined
              target.activeStreamStatus = undefined
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
            if (finishedStreamId) {
              currentStreamId.value = ''
            }
          },
          onError: (errorMessage) => {
            throw new Error(errorMessage)
          },
        },
        {
          signal: abortController.signal,
        },
      )
    } catch (error) {
      console.error(error)
      clearThinkingTimers()
      if (isAbortError(error)) {
        if (currentAbortMode.value === 'stop') {
          markStreamCancelled()
        }
        syncHistoryPolling()
        return
      }
      if (error instanceof ActiveStreamConflictError) {
        updateConversation(conversationId, (target) => {
          target.draft = currentMessage
          target.messages = target.messages.filter(
            (item) => item.id !== userMessage.id && item.id !== assistantMessage.id,
          )
          target.activeStreamId = error.streamId || target.activeStreamId
          target.activeStreamStatus =
            error.status === 'cancelling' ? 'cancelling' : target.activeStreamId ? 'running' : undefined
        })
        syncHistoryPolling()
        message.warning(error.message)
        return
      }
      if (error instanceof LoginRequiredError) {
        guestRemaining.value = error.remaining
        pendingLoginMessage.value = currentMessage
        updateConversation(conversationId, (target) => {
          target.messages = target.messages.filter(
            (item) => item.id !== userMessage.id && item.id !== assistantMessage.id,
          )
        })
        openAuthDialog('login')
        message.warning('登录后可以继续发送')
        return
      }
      if (error instanceof GuestQuotaUnavailableError) {
        updateConversation(conversationId, (target) => {
          target.messages = target.messages.filter(
            (item) => item.id !== userMessage.id && item.id !== assistantMessage.id,
          )
        })
        message.error(error.message)
        return
      }
      updateConversation(conversationId, (target) => {
        target.draft = currentMessage
        const messageTarget = target.messages.find((item) => item.id === assistantMessage.id)
        if (messageTarget?.streamState) {
          messageTarget.streamState.replyStatus = 'error'
          messageTarget.streamState.thinkingStatus = 'done'
        }
        target.activeStreamId = undefined
        target.activeStreamStatus = undefined
        target.messages = target.messages.filter((item) => item.id !== assistantMessage.id)
      })
      currentStreamId.value = ''
      message.error('请求失败，请先确认后端和数据库是否启动')
    } finally {
      currentAbortMode.value = null
      pendingStopRequested.value = false
      if (currentAbortController.value === abortController) {
        currentAbortController.value = null
        currentStreamTarget.value = null
      }
      if (currentStreamId.value && activeConversation.value.activeStreamId !== currentStreamId.value) {
        currentStreamId.value = ''
      }
      submitting.value = false
      syncHistoryPolling()
    }
  }

  onUnmounted(() => {
    detachLocalStream()
    clearHistoryRefreshTimer()
  })

  return {
    activeConversation,
    activeConversationId,
    activeModeLabel,
    authDialogOpen,
    authForm,
    authMode,
    authSubmitting,
    authenticatedUser,
    avatarUploading,
    changeMode,
    closeAuthDialog,
    closeProfileDialog,
    clearAllMemoryItems,
    conversations,
    guestRemaining,
    historyConversations,
    initialize,
    isAuthenticated,
    isComposerLocked,
    isEmptyConversation,
    isStreamActive,
    latestAssistantMessageId,
    loadMemoryManagement,
    memoryClearing,
    memoryItems,
    memoryItemsLoading,
    memorySettings,
    memorySettingsLoading,
    memorySettingsSaving,
    memoryTotal,
    modeDetails,
    openAuthDialog,
    openProfileDialog,
    profileDialogOpen,
    profileForm,
    profileSubmitting,
    removeMemoryItem,
    serviceReady,
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
  }
}
