import http from '@/api/http'
import type { ApiResponse } from '@/types/api'

export interface MemorySettings {
  memory_enabled: boolean
}

export interface MemoryItem {
  id: string
  memory_type: string
  canonical_key: string
  content: string
  importance_score: number
  confidence: number
  status: string
  metadata_json: Record<string, unknown>
  created_at?: string | null
  last_seen_at?: string | null
  updated_at?: string | null
}

export interface MemoryItemsResponse {
  items: MemoryItem[]
  total: number
}

export const fetchMemorySettings = async () => {
  const { data: res } = await http.get<ApiResponse<MemorySettings>>('/memory/settings')
  return res.data!
}

export const updateMemorySettings = async (payload: MemorySettings) => {
  const { data: res } = await http.put<ApiResponse<MemorySettings>>('/memory/settings', payload)
  return res.data!
}

export const fetchMemoryItems = async (params: { limit?: number; offset?: number } = {}) => {
  const { data: res } = await http.get<ApiResponse<MemoryItemsResponse>>('/memory/items', { params })
  return res.data!
}

export const deleteMemoryItem = async (id: string) => {
  const { data: res } = await http.delete<ApiResponse<{ deleted_count: number }>>(`/memory/items/${id}`)
  return res.data!
}

export const clearMemoryItems = async () => {
  const { data: res } = await http.delete<ApiResponse<{ deleted_count: number }>>('/memory/items')
  return res.data!
}
