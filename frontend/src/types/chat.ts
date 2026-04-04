export type ChatMode = 'companion' | 'advice' | 'style_clone' | 'soothing'

export interface ChatRequest {
  session_id: string
  user_id: string
  message: string
  mode: ChatMode
}

export interface ChatTrace {
  memory_hits: string[]
  knowledge_hits: string[]
  safety_level: string
}

export interface ChatResponse {
  reply: string
  mode: ChatMode
  trace: ChatTrace
}

export interface ConversationHistoryMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  created_at?: string | null
}

export interface ConversationHistoryItem {
  id: string
  title: string
  preview: string
  mode: ChatMode
  messages: ConversationHistoryMessage[]
  latest_trace?: ChatTrace | null
}

export interface ConversationHistoryResponse {
  user_id: string
  conversations: ConversationHistoryItem[]
}

export interface HealthResponse {
  status: string
  service: string
  timestamp: string
}
