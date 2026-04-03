import http from '@/api/http'
import type { ChatRequest, ChatResponse, HealthResponse } from '@/types/chat'

export const fetchHealth = async () => {
  const { data } = await http.get<HealthResponse>('/health')
  return data
}

export const sendChatMessage = async (payload: ChatRequest) => {
  const { data } = await http.post<ChatResponse>('/chat/reply', payload)
  return data
}
