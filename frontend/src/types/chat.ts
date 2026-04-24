// 聊天相关类型定义
// 目的：定义前端与后端通信所需的数据结构类型

/**
 * 聊天模式类型
 *
 * 目的：定义可用的对话模式枚举值
 */
export type ChatMode = 'companion' | 'advice' | 'style_clone' | 'soothing'

export type ThinkingStatus = 'idle' | 'streaming' | 'done'

export type ReplyStatus = 'idle' | 'streaming' | 'done' | 'error'

export interface ThinkingChunk {
  id: string
  content: string
}

export interface AssistantStreamState {
  thinkingStatus: ThinkingStatus
  thinkingChunks: ThinkingChunk[]
  replyStatus: ReplyStatus
}

export interface ConversationMeta {
  title: string
  preview: string
  mode: ChatMode
}

/**
 * 聊天请求接口
 *
 * 目的：定义发送聊天消息时的请求数据结构
 */
export interface ChatRequest {
  session_id: string
  user_id: string
  message: string
  mode: ChatMode
}

/**
 * 长期记忆命中项
 *
 * 目的：与后端 ChatTrace.memory_hits 的结构保持一致。
 */
export interface MemoryHit {
  content: string
  score: number
  chunk_id: string
}

export interface KnowledgeEvidence {
  evidence_id: string
  chunk_id: string
  parent_id: string
  title: string
  source: string
  heading_path: string
  snippet: string
  dense_score?: number | null
  bm25_score?: number | null
  fusion_score?: number | null
  rerank_score?: number | null
  rank: number
  locator: string
}

/**
 * 聊天追踪信息接口
 *
 * 目的：定义对话过程中的追踪数据结构，包含记忆命中、知识命中、检索查询和安全级别
 */
export interface ChatTrace {
  memory_hits: MemoryHit[]
  knowledge_hits: string[]
  knowledge_evidences: KnowledgeEvidence[]
  retrieval_query: string
  safety_level: string
  answer_confidence: 'high' | 'medium' | 'low'
  answer_confidence_reason: string
  rerank_applied: boolean
}

/**
 * 问题顾问接口
 *
 * 目的：定义问题顾问的数据结构，包含问题摘要、检索查询、匹配主题和建议问题
 */
export interface ChatAdvisor {
  issue_summary: string
  retrieval_query: string
  matched_topics: string[]
  suggested_questions: string[]
}

/**
 * 聊天响应接口
 *
 * 目的：定义AI回复的数据结构，包含回复内容、模式、追踪信息和问题顾问数据
 */
export interface ChatResponse {
  reply: string
  mode: ChatMode
  trace: ChatTrace
  advisor?: ChatAdvisor | null
}

/**
 * 会话历史消息接口
 *
 * 目的：定义单条会话消息的数据结构，包含ID、角色、内容、创建时间和问题顾问数据
 */
export interface ConversationHistoryMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  created_at?: string | null
  advisor?: ChatAdvisor | null
}

/**
 * 会话历史项接口
 *
 * 目的：定义单个会话的历史记录数据结构，包含ID、标题、预览、模式、消息列表和最新追踪信息
 */
export interface ConversationHistoryItem {
  id: string
  title: string
  preview: string
  mode: ChatMode
  messages: ConversationHistoryMessage[]
  latest_trace?: ChatTrace | null
}

/**
 * 会话历史响应接口
 *
 * 目的：定义返回用户会话历史的数据结构，包含用户ID和会话列表
 */
export interface ConversationHistoryResponse {
  user_id: string
  conversations: ConversationHistoryItem[]
}

/**
 * 健康检查响应接口
 *
 * 目的：定义服务健康状态检查的响应数据结构
 */
export interface HealthResponse {
  status: string
  service: string
  timestamp: string
}
