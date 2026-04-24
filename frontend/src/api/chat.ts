// 聊天API接口定义
// 目的：封装与后端聊天服务的HTTP通信，提供健康检查、会话历史和流式消息功能

import http, { resolveApiUrl } from '@/api/http'
import type {
  ChatRequest,
  ChatResponse,
  ConversationHistoryResponse,
  HealthResponse,
} from '@/types/chat'

/**
 * 获取服务健康状态
 *
 * 目的：检查后端服务是否正常运行，用于前端服务状态显示
 */
export const fetchHealth = async () => {
  const { data } = await http.get<HealthResponse>('/health')
  return data
}

/**
 * 获取用户会话历史
 *
 * 目的：从后端获取指定用户的所有历史会话记录
 */
export const fetchConversationHistory = async (userId: string) => {
  const { data } = await http.get<ConversationHistoryResponse>('/chat/conversations', {
    params: {
      user_id: userId,
    },
  })
  return data
}

/**
 * 流式发送聊天消息
 *
 * 目的：向后端发送聊天请求并实时接收流式响应，支持逐字显示AI回复
 */
export const streamChatMessage = async (
  payload: ChatRequest,
  handlers: {
    onToken: (chunk: string) => void
    onDone: (result: ChatResponse) => void
    onError: (message: string) => void
    onThinkingStart?: () => void
    onThinkingDelta?: (chunk: string) => void
    onThinkingDone?: () => void
  },
) => {
  const url = resolveApiUrl('/chat/stream')
  console.debug('[SSE] 开始请求:', url, payload)

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      Accept: 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  console.debug('[SSE] 收到响应:', response.status, response.ok, response.body)

  if (!response.ok || !response.body) {
    const errorText = await response.text().catch(() => '无法读取响应体')
    console.error('[SSE] 请求失败:', response.status, errorText)
    throw new Error(`流式请求失败: ${response.status}`)
  }

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
    reader.releaseLock()
  }
}
