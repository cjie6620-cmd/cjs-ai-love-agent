// 聊天API接口定义
// 目的：封装与后端聊天服务的HTTP通信，提供健康检查、会话历史和流式消息功能

import http, { resolveApiUrl } from '@/api/http'
import { getStoredAccessToken } from '@/api/http'
import type { ApiResponse } from '@/types/api'
import type {
  CancelStreamResponse,
  ChatRequest,
  ChatResponse,
  ConversationHistoryResponse,
  HealthResponse,
  LoginRequiredPayload,
} from '@/types/chat'

/**
 * 目的：请求后端接口获取 fetchHealth 对应的数据。
 * 结果：返回接口约定结果，或完成对应的前端状态更新。
 */
export const fetchHealth = async () => {
  const { data: res } = await http.get<ApiResponse<HealthResponse>>('/health')
  return res.data!
}

/**
 * 目的：定义 LoginRequiredError 错误或业务对象。
 * 结果：让调用方可以用稳定类型识别和处理对应状态。
 */
export class LoginRequiredError extends Error {
  /**
   * 目的：保存 LoginRequiredError.remaining 字段的业务状态。
   * 结果：实例处理异常分支时可以读取该字段。
   */
  remaining: number

  /**
   * 目的：初始化 LoginRequiredError 实例。
   * 结果：返回携带上下文信息的错误对象。
   */
  constructor(payload: LoginRequiredPayload) {
    super(payload.message || '登录后可以继续发送')
    this.name = 'LoginRequiredError'
    this.remaining = payload.data?.remaining ?? 0
  }
}

/**
 * 目的：定义 GuestQuotaUnavailableError 错误或业务对象。
 * 结果：让调用方可以用稳定类型识别和处理对应状态。
 */
export class GuestQuotaUnavailableError extends Error {
  /**
   * 目的：初始化 GuestQuotaUnavailableError 实例。
   * 结果：返回携带上下文信息的错误对象。
   */
  constructor(messageText = '试用服务暂不可用，请稍后再试') {
    super(messageText)
    this.name = 'GuestQuotaUnavailableError'
  }
}

/**
 * 目的：定义 ActiveStreamConflictError 错误或业务对象。
 * 结果：让调用方可以识别“当前会话已有后台任务”的冲突状态。
 */
export class ActiveStreamConflictError extends Error {
  streamId: string
  status: string

  constructor(messageText: string, options: { streamId?: string; status?: string } = {}) {
    super(messageText)
    this.name = 'ActiveStreamConflictError'
    this.streamId = options.streamId ?? ''
    this.status = options.status ?? ''
  }
}

/**
 * 目的：判断当前值是否满足 isAbortError 的业务条件。
 * 结果：返回接口约定结果，或完成对应的前端状态更新。
 */
export const isAbortError = (error: unknown) =>
  error instanceof DOMException && error.name === 'AbortError'

/**
 * 目的：请求后端接口获取 fetchConversationHistory 对应的数据。
 * 结果：返回接口约定结果，或完成对应的前端状态更新。
 */
export const fetchConversationHistory = async (options: { timeoutMs?: number } = {}) => {
  const { data: res } = await http.get<ApiResponse<ConversationHistoryResponse>>('/chat/conversations', {
    timeout: options.timeoutMs ?? 3500,
  })
  return res.data!
}

/**
 * 目的：请求后端接口取消当前流任务。
 * 结果：返回后端确认的取消状态，供前端决定何时结束本地流。
 */
export const cancelChatStream = async (streamId: string) => {
  const { data: res } = await http.post<ApiResponse<CancelStreamResponse>>(`/chat/streams/${streamId}/cancel`)
  return res.data!
}

/**
 * 目的：发起流式聊天请求并处理 SSE 事件。
 * 结果：返回接口约定结果，或完成对应的前端状态更新。
 */
export const streamChatMessage = async (
  payload: ChatRequest,
  handlers: {
    onToken: (chunk: string) => void
    onDone: (result: ChatResponse) => void
    onError: (message: string) => void
    onStreamId?: (streamId: string) => void
    onThinkingStart?: () => void
    onThinkingDelta?: (chunk: string) => void
    onThinkingDone?: () => void
    onQuota?: (remaining: number | null) => void
  },
  options: {
    signal?: AbortSignal
  } = {},
) => {
  const url = resolveApiUrl('/chat/stream')
  console.debug('[SSE] 开始请求:', url, payload)
  const token = getStoredAccessToken()

  const response = await fetch(url, {
    method: 'POST',
    credentials: 'include',
    headers: {
      Accept: 'text/event-stream',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      'Cache-Control': 'no-cache',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
    signal: options.signal,
  })

  console.debug('[SSE] 收到响应:', response.status, response.ok, response.body)

  if (!response.ok || !response.body) {
    const errorText = await response.text().catch(() => '无法读取响应体')
    console.error('[SSE] 请求失败:', response.status, errorText)
    try {
      const payload = JSON.parse(errorText) as LoginRequiredPayload
      if (payload.data?.error_code === 'LOGIN_REQUIRED') {
        throw new LoginRequiredError(payload)
      }
      if (payload.data?.error_code === 'GUEST_QUOTA_UNAVAILABLE') {
        throw new GuestQuotaUnavailableError(payload.message)
      }
      if (payload.data?.error_code === 'STREAM_ALREADY_RUNNING') {
        const raw = payload as LoginRequiredPayload & {
          data?: { stream_id?: string; status?: string; error_code?: string } | null
        }
        throw new ActiveStreamConflictError(payload.message || '当前会话仍在生成中，请稍候', {
          streamId: raw.data?.stream_id ?? '',
          status: raw.data?.status ?? '',
        })
      }
    } catch (error) {
      if (
        error instanceof LoginRequiredError ||
        error instanceof GuestQuotaUnavailableError ||
        error instanceof ActiveStreamConflictError
      ) {
        throw error
      }
    }
    throw new Error(`流式请求失败: ${response.status}`)
  }

  const remainingHeader = response.headers.get('X-Guest-Remaining')
  const limitHeader = response.headers.get('X-Guest-Limit')
  const countHeader = response.headers.get('X-Guest-Count')
  const identityHeader = response.headers.get('X-Guest-Identity')
  const reasonHeader = response.headers.get('X-Guest-Quota-Reason')
  console.debug('[SSE] 访客额度信息:', {
    identity: identityHeader,
    limit: limitHeader,
    remaining: remainingHeader,
    count: countHeader,
    reason: reasonHeader,
  })
  handlers.onQuota?.(remainingHeader === null ? null : Number(remainingHeader))
  handlers.onStreamId?.(response.headers.get('X-Stream-Id') ?? '')

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  let tokenCount = 0

  try {
    while (true) {
      const { value, done } = await reader.read()

      if (done) {
        console.debug('[SSE] 流结束，token总数:', tokenCount, '缓冲区残留:', buffer.length)
        break
      }

      // 将原始字节转为字符串
      const textChunk = decoder.decode(value, { stream: true })
      console.debug('[SSE] 收到数据块, 字节长度:', value.byteLength, '文本:', textChunk.slice(0, 100))
      buffer += textChunk

      // 按 SSE 事件分隔符切分（两个换行符）
      const segments = buffer.split('\n\n')
      // 保留最后一个不完整的段供下次处理
      buffer = segments.pop() ?? ''

      for (const segment of segments) {
        const lines = segment.split('\n')
        const eventLine = lines.find((line) => line.startsWith('event:'))
        const dataLine = lines.find((line) => line.startsWith('data:'))
        if (!eventLine || !dataLine) {
          console.debug('[SSE] 跳过无效段:', segment.slice(0, 80))
          continue
        }

        const event = eventLine.replace('event:', '').trim()
        const rawData = dataLine.replace('data:', '').trim()
        console.debug('[SSE] 解析事件:', event, '数据前50字符:', rawData.slice(0, 50))

        try {
          const data = JSON.parse(rawData)

          if (event === 'token') {
            const content = String(data.content ?? '')
            tokenCount++
            console.debug('[SSE] token事件 #' + tokenCount + ':', content)
            handlers.onToken(content)
          }

          if (event === 'thinking_start') {
            handlers.onThinkingStart?.()
          }

          if (event === 'thinking_delta') {
            handlers.onThinkingDelta?.(String(data.content ?? data.text ?? ''))
          }

          if (event === 'thinking_done') {
            handlers.onThinkingDone?.()
          }

          if (event === 'done') {
            console.debug('[SSE] done事件:', data)
            handlers.onDone(data as ChatResponse)
          }

          if (event === 'error') {
            console.error('[SSE] error事件:', data)
            handlers.onError(String(data.message ?? '流式输出失败'))
          }
        } catch (parseErr) {
          console.error('[SSE] JSON解析失败:', parseErr, '原始数据:', rawData.slice(0, 200))
        }
      }
    }
  } finally {
    // 确保 reader 被释放，避免 fetch body stream 泄漏
    try {
      await reader.cancel()
    } catch {
      // 流可能已正常结束或已被 AbortController 关闭
    }
    reader.releaseLock()
  }
}
