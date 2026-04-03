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

export interface HealthResponse {
  status: string
  service: string
  timestamp: string
}
