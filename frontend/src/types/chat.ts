// 聊天相关类型定义
// 目的：定义前端与后端通信所需的数据结构类型

/**
 * 聊天模式类型
 *
 * 目的：定义可用的对话模式枚举值
 */
export type ChatMode = 'companion' | 'advice' | 'style_clone' | 'soothing'
export type ActiveStreamStatus = 'running' | 'cancelling'
export type CancelStreamStatus = 'cancelling' | 'cancelled' | 'completed' | 'not_found'
export type PersistedReplyStatus = 'completed' | 'interrupted'

export type ThinkingStatus = 'idle' | 'streaming' | 'done'

export type ReplyStatus = 'idle' | 'streaming' | 'done' | 'error' | 'cancelled'

/**
 * 目的：定义 ThinkingChunk 的前端数据结构。
 * 结果：为页面渲染、API 调用和状态管理提供稳定类型约束。
 */
export interface ThinkingChunk {
  /**
   * 目的：描述 ThinkingChunk.id 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  id: string
  /**
   * 目的：描述 ThinkingChunk.content 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  content: string
}

/**
 * 目的：定义 AssistantStreamState 的前端数据结构。
 * 结果：为页面渲染、API 调用和状态管理提供稳定类型约束。
 */
export interface AssistantStreamState {
  /**
   * 目的：描述 AssistantStreamState.thinkingStatus 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  thinkingStatus: ThinkingStatus
  /**
   * 目的：描述 AssistantStreamState.thinkingChunks 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  thinkingChunks: ThinkingChunk[]
  /**
   * 目的：描述 AssistantStreamState.replyStatus 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  replyStatus: ReplyStatus
}

/**
 * 目的：定义 ConversationMeta 的前端数据结构。
 * 结果：为页面渲染、API 调用和状态管理提供稳定类型约束。
 */
export interface ConversationMeta {
  /**
   * 目的：描述 ConversationMeta.title 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  title: string
  /**
   * 目的：描述 ConversationMeta.preview 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  preview: string
  /**
   * 目的：描述 ConversationMeta.mode 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  mode: ChatMode
}

/**
 * 目的：定义 ChatRequest 的前端数据结构。
 * 结果：为页面渲染、API 调用和状态管理提供稳定类型约束。
 */
export interface ChatRequest {
  /**
   * 目的：描述 ChatRequest.session_id 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  session_id: string
  /**
   * 目的：描述 ChatRequest.user_id 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  user_id?: string
  /**
   * 目的：描述 ChatRequest.message 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  message: string
  /**
   * 目的：描述 ChatRequest.mode 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  mode: ChatMode
}

/**
 * 目的：定义 MemoryHit 的前端数据结构。
 * 结果：为页面渲染、API 调用和状态管理提供稳定类型约束。
 */
export interface MemoryHit {
  /**
   * 目的：描述 MemoryHit.content 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  content: string
  /**
   * 目的：描述 MemoryHit.score 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  score: number
  /**
   * 目的：描述 MemoryHit.chunk_id 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  chunk_id: string
}

/**
 * 目的：定义 KnowledgeEvidence 的前端数据结构。
 * 结果：为页面渲染、API 调用和状态管理提供稳定类型约束。
 */
export interface KnowledgeEvidence {
  /**
   * 目的：描述 KnowledgeEvidence.evidence_id 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  evidence_id: string
  /**
   * 目的：描述 KnowledgeEvidence.chunk_id 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  chunk_id: string
  /**
   * 目的：描述 KnowledgeEvidence.parent_id 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  parent_id: string
  /**
   * 目的：描述 KnowledgeEvidence.title 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  title: string
  /**
   * 目的：描述 KnowledgeEvidence.source 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  source: string
  /**
   * 目的：描述 KnowledgeEvidence.heading_path 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  heading_path: string
  /**
   * 目的：描述 KnowledgeEvidence.snippet 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  snippet: string
  /**
   * 目的：描述 KnowledgeEvidence.dense_score 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  dense_score?: number | null
  /**
   * 目的：描述 KnowledgeEvidence.bm25_score 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  bm25_score?: number | null
  /**
   * 目的：描述 KnowledgeEvidence.fusion_score 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  fusion_score?: number | null
  /**
   * 目的：描述 KnowledgeEvidence.rerank_score 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  rerank_score?: number | null
  /**
   * 目的：描述 KnowledgeEvidence.rank 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  rank: number
  /**
   * 目的：描述 KnowledgeEvidence.locator 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  locator: string
}

/**
 * 目的：定义 ChatTrace 的前端数据结构。
 * 结果：为页面渲染、API 调用和状态管理提供稳定类型约束。
 */
export interface ChatTrace {
  /**
   * 目的：描述 ChatTrace.memory_hits 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  memory_hits: MemoryHit[]
  /**
   * 目的：描述 ChatTrace.knowledge_hits 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  knowledge_hits: string[]
  /**
   * 目的：描述 ChatTrace.knowledge_evidences 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  knowledge_evidences: KnowledgeEvidence[]
  /**
   * 目的：描述 ChatTrace.retrieval_query 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  retrieval_query: string
  /**
   * 目的：描述 ChatTrace.safety_level 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  safety_level: string
  /**
   * 目的：描述 ChatTrace.answer_confidence 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  answer_confidence: 'high' | 'medium' | 'low'
  /**
   * 目的：描述 ChatTrace.answer_confidence_reason 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  answer_confidence_reason: string
  /**
   * 目的：描述 ChatTrace.rerank_applied 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  rerank_applied: boolean
}

/**
 * 目的：定义 ChatAdvisor 的前端数据结构。
 * 结果：为页面渲染、API 调用和状态管理提供稳定类型约束。
 */
export interface ChatAdvisor {
  /**
   * 目的：描述 ChatAdvisor.issue_summary 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  issue_summary: string
  /**
   * 目的：描述 ChatAdvisor.retrieval_query 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  retrieval_query: string
  /**
   * 目的：描述 ChatAdvisor.matched_topics 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  matched_topics: string[]
  /**
   * 目的：描述 ChatAdvisor.suggested_questions 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  suggested_questions: string[]
}

/**
 * 目的：定义 ChatResponse 的前端数据结构。
 * 结果：为页面渲染、API 调用和状态管理提供稳定类型约束。
 */
export interface ChatResponse {
  /**
   * 目的：描述 ChatResponse.reply 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  reply: string
  /**
   * 目的：描述 ChatResponse.mode 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  mode: ChatMode
  /**
   * 目的：描述 ChatResponse.trace 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  trace: ChatTrace
  /**
   * 目的：描述 ChatResponse.advisor 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  advisor?: ChatAdvisor | null
  /**
   * 目的：描述 ChatResponse.guest_quota_remaining 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  guest_quota_remaining?: number | null
}

/**
 * 目的：定义 ConversationHistoryMessage 的前端数据结构。
 * 结果：为页面渲染、API 调用和状态管理提供稳定类型约束。
 */
export interface ConversationHistoryMessage {
  /**
   * 目的：描述 ConversationHistoryMessage.id 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  id: string
  /**
   * 目的：描述 ConversationHistoryMessage.role 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  role: 'user' | 'assistant'
  /**
   * 目的：描述 ConversationHistoryMessage.content 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  content: string
  /**
   * 目的：描述 ConversationHistoryMessage.created_at 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  created_at?: string | null
  /**
   * 目的：描述 ConversationHistoryMessage.advisor 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  advisor?: ChatAdvisor | null
  /**
   * 目的：描述 ConversationHistoryMessage.reply_status 字段的业务含义。
   * 结果：前端可以识别历史里的中断回复并复用已停止展示状态。
   */
  reply_status?: PersistedReplyStatus
}

/**
 * 目的：定义 ConversationHistoryItem 的前端数据结构。
 * 结果：为页面渲染、API 调用和状态管理提供稳定类型约束。
 */
export interface ConversationHistoryItem {
  /**
   * 目的：描述 ConversationHistoryItem.id 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  id: string
  /**
   * 目的：描述 ConversationHistoryItem.title 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  title: string
  /**
   * 目的：描述 ConversationHistoryItem.preview 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  preview: string
  /**
   * 目的：描述 ConversationHistoryItem.mode 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  mode: ChatMode
  /**
   * 目的：描述 ConversationHistoryItem.messages 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  messages: ConversationHistoryMessage[]
  /**
   * 目的：描述 ConversationHistoryItem.latest_trace 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  latest_trace?: ChatTrace | null
  /**
   * 目的：描述 ConversationHistoryItem.active_stream_id 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  active_stream_id?: string | null
  /**
   * 目的：描述 ConversationHistoryItem.active_stream_status 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  active_stream_status?: ActiveStreamStatus | null
}

/**
 * 目的：定义 ConversationHistoryResponse 的前端数据结构。
 * 结果：为页面渲染、API 调用和状态管理提供稳定类型约束。
 */
export interface ConversationHistoryResponse {
  /**
   * 目的：描述 ConversationHistoryResponse.user_id 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  user_id: string
  /**
   * 目的：描述 ConversationHistoryResponse.conversations 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  conversations: ConversationHistoryItem[]
}

/**
 * 目的：定义 CancelStreamResponse 的前端数据结构。
 * 结果：为取消接口的调用和状态处理提供稳定类型约束。
 */
export interface CancelStreamResponse {
  /**
   * 目的：描述 CancelStreamResponse.stream_id 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  stream_id: string
  /**
   * 目的：描述 CancelStreamResponse.status 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  status: CancelStreamStatus
  /**
   * 目的：描述 CancelStreamResponse.accepted 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  accepted: boolean
}

/**
 * 目的：定义 LoginRequiredPayload 的前端数据结构。
 * 结果：为页面渲染、API 调用和状态管理提供稳定类型约束。
 */
export interface LoginRequiredPayload {
  /**
   * 目的：描述 LoginRequiredPayload.code 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  code: number
  /**
   * 目的：描述 LoginRequiredPayload.message 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  message: string
  /**
   * 目的：描述 LoginRequiredPayload.remaining 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  data: {
    error_code?: 'LOGIN_REQUIRED' | 'GUEST_QUOTA_UNAVAILABLE'
    remaining?: number | null
    limit?: number | null
  } | null
}

/**
 * 目的：定义 HealthResponse 的前端数据结构。
 * 结果：为页面渲染、API 调用和状态管理提供稳定类型约束。
 */
export interface HealthResponse {
  /**
   * 目的：描述 HealthResponse.status 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  status: string
  /**
   * 目的：描述 HealthResponse.service 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  service: string
  /**
   * 目的：描述 HealthResponse.timestamp 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  timestamp: string
}
