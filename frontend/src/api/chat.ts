import http from '@/api/http'
import type {
  ChatRequest,
  ChatResponse,
  ConversationHistoryResponse,
  HealthResponse,
} from '@/types/chat'

export const fetchHealth = async () => {
  const { data } = await http.get<HealthResponse>('/health')
  return data
}

export const fetchConversationHistory = async (userId: string) => {
  const { data } = await http.get<ConversationHistoryResponse>('/chat/conversations', {
    params: {
      user_id: userId,
    },
  })
  return data
}

export const streamChatMessage = async (
  payload: ChatRequest,
  handlers: {
    onToken: (chunk: string) => void
    onDone: (result: ChatResponse) => void
    onError: (message: string) => void
  },
) => {
  const response = await fetch(`${http.defaults.baseURL}/chat/reply/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  if (!response.ok || !response.body) {
    throw new Error(`流式请求失败: ${response.status}`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  try {
    while (true) {
      const { value, done } = await reader.read()
      if (done) {
        break
      }

      buffer += decoder.decode(value, { stream: true })
      const segments = buffer.split('\n\n')
      buffer = segments.pop() ?? ''

      for (const segment of segments) {
        const lines = segment.split('\n')
        const eventLine = lines.find((line) => line.startsWith('event:'))
        const dataLine = lines.find((line) => line.startsWith('data:'))
        if (!eventLine || !dataLine) {
          continue
        }

        const event = eventLine.replace('event:', '').trim()
        const data = JSON.parse(dataLine.replace('data:', '').trim())

        if (event === 'token') {
          handlers.onToken(String(data.content ?? ''))
        }

        if (event === 'done') {
          handlers.onDone(data as ChatResponse)
        }

        if (event === 'error') {
          handlers.onError(String(data.message ?? '流式输出失败'))
        }
      }
    }
  } finally {
    // 确保 reader 被释放，避免 fetch body stream 泄漏
    reader.releaseLock()
  }
}
