/**
 * 目的：定义 AdminUser 的前端数据结构。
 * 结果：为页面渲染、API 调用和状态管理提供稳定类型约束。
 */
export interface AdminUser {
  /**
   * 目的：描述 AdminUser.id 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  id: string
  /**
   * 目的：描述 AdminUser.tenant_id 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  tenant_id: string
  /**
   * 目的：描述 AdminUser.login_name 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  login_name: string
  /**
   * 目的：描述 AdminUser.nickname 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  nickname: string
  /**
   * 目的：描述 AdminUser.avatar_url 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  avatar_url: string
  /**
   * 目的：描述 AdminUser.status 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  status: 'active' | 'disabled'
  /**
   * 目的：描述 AdminUser.roles 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  roles: string[]
  /**
   * 目的：描述 AdminUser.created_at 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  created_at?: string | null
  /**
   * 目的：描述 AdminUser.last_active_at 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  last_active_at?: string | null
}

/**
 * 目的：定义 AdminRole 的前端数据结构。
 * 结果：为页面渲染、API 调用和状态管理提供稳定类型约束。
 */
export interface AdminRole {
  /**
   * 目的：描述 AdminRole.id 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  id: string
  /**
   * 目的：描述 AdminRole.code 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  code: string
  /**
   * 目的：描述 AdminRole.name 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  name: string
  /**
   * 目的：描述 AdminRole.description 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  description: string
  /**
   * 目的：描述 AdminRole.permissions 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  permissions: string[]
  /**
   * 目的：描述 AdminRole.is_system 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  is_system: boolean
}

/**
 * 目的：定义 AdminPermission 的前端数据结构。
 * 结果：为页面渲染、API 调用和状态管理提供稳定类型约束。
 */
export interface AdminPermission {
  /**
   * 目的：描述 AdminPermission.id 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  id: string
  /**
   * 目的：描述 AdminPermission.code 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  code: string
  /**
   * 目的：描述 AdminPermission.name 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  name: string
  /**
   * 目的：描述 AdminPermission.description 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  description: string
  /**
   * 目的：描述 AdminPermission.module 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  module: string
}

/**
 * 目的：定义 KnowledgeDocument 的前端数据结构。
 * 结果：为页面渲染、API 调用和状态管理提供稳定类型约束。
 */
export interface KnowledgeDocument {
  /**
   * 目的：描述 KnowledgeDocument.id 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  id: string
  /**
   * 目的：描述 KnowledgeDocument.doc_id 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  doc_id: string
  /**
   * 目的：描述 KnowledgeDocument.title 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  title: string
  /**
   * 目的：描述 KnowledgeDocument.filename 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  filename: string
  /**
   * 目的：描述 KnowledgeDocument.category 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  category: string
  /**
   * 目的：描述 KnowledgeDocument.source 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  source: string
  /**
   * 目的：描述 KnowledgeDocument.status 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  status: 'pending' | 'indexing' | 'active' | 'failed' | 'deleted'
  /**
   * 目的：描述 KnowledgeDocument.chunk_count 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  chunk_count: number
  /**
   * 目的：描述 KnowledgeDocument.created_by 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  created_by: string
  /**
   * 目的：描述 KnowledgeDocument.last_job_id 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  last_job_id: string
  /**
   * 目的：描述 KnowledgeDocument.error_message 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  error_message: string
  /**
   * 目的：描述 KnowledgeDocument.created_at 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  created_at?: string | null
  /**
   * 目的：描述 KnowledgeDocument.updated_at 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  updated_at?: string | null
}

/**
 * 目的：定义 KnowledgeJob 的前端数据结构。
 * 结果：为页面渲染、API 调用和状态管理提供稳定类型约束。
 */
export interface KnowledgeJob {
  /**
   * 目的：描述 KnowledgeJob.id 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  id: string
  /**
   * 目的：描述 KnowledgeJob.job_type 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  job_type: string
  /**
   * 目的：描述 KnowledgeJob.status 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  status: 'pending' | 'running' | 'succeeded' | 'failed' | 'canceled'
  /**
   * 目的：描述 KnowledgeJob.document_id 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  document_id?: string | null
  /**
   * 目的：描述 KnowledgeJob.filename 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  filename?: string
  /**
   * 目的：描述 KnowledgeJob.progress 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  progress: number
  /**
   * 目的：描述 KnowledgeJob.result_json 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  result_json?: Record<string, unknown>
  /**
   * 目的：描述 KnowledgeJob.error_message 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  error_message?: string
  /**
   * 目的：描述 KnowledgeJob.created_by 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  created_by: string
  /**
   * 目的：描述 KnowledgeJob.started_at 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  started_at?: string | null
  /**
   * 目的：描述 KnowledgeJob.finished_at 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  finished_at?: string | null
  /**
   * 目的：描述 KnowledgeJob.created_at 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  created_at?: string | null
  /**
   * 目的：描述 KnowledgeJob.updated_at 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  updated_at?: string | null
}

/**
 * 目的：定义 AuditEvent 的前端数据结构。
 * 结果：为页面渲染、API 调用和状态管理提供稳定类型约束。
 */
export interface AuditEvent {
  /**
   * 目的：描述 AuditEvent.id 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  id: string
  /**
   * 目的：描述 AuditEvent.tenant_id 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  tenant_id: string
  /**
   * 目的：描述 AuditEvent.actor_user_id 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  actor_user_id: string
  /**
   * 目的：描述 AuditEvent.action 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  action: string
  /**
   * 目的：描述 AuditEvent.resource_type 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  resource_type: string
  /**
   * 目的：描述 AuditEvent.resource_id 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  resource_id: string
  /**
   * 目的：描述 AuditEvent.ip 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  ip: string
  /**
   * 目的：描述 AuditEvent.user_agent 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  user_agent: string
  /**
   * 目的：描述 AuditEvent.detail_json 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  detail_json: Record<string, unknown>
  /**
   * 目的：描述 AuditEvent.created_at 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  created_at?: string | null
}

/**
 * 目的：定义 SafetyEvent 的前端数据结构。
 * 结果：为页面渲染、API 调用和状态管理提供稳定类型约束。
 */
export interface SafetyEvent {
  /**
   * 目的：描述 SafetyEvent.id 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  id: string
  /**
   * 目的：描述 SafetyEvent.user_id 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  user_id: string
  /**
   * 目的：描述 SafetyEvent.conversation_id 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  conversation_id?: string | null
  /**
   * 目的：描述 SafetyEvent.scene 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  scene: string
  /**
   * 目的：描述 SafetyEvent.risk_type 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  risk_type: string
  /**
   * 目的：描述 SafetyEvent.risk_level 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  risk_level: string
  /**
   * 目的：描述 SafetyEvent.input_snapshot 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  input_snapshot: string
  /**
   * 目的：描述 SafetyEvent.action 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  action: string
  /**
   * 目的：描述 SafetyEvent.created_at 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  created_at?: string | null
}

/**
 * 目的：定义 AdminDashboard 的前端数据结构。
 * 结果：为页面渲染、API 调用和状态管理提供稳定类型约束。
 */
export interface AdminDashboard {
  /**
   * 目的：描述 AdminDashboard.metrics 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  metrics: Record<string, number>
  /**
   * 目的：描述 AdminDashboard.recent_jobs 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  recent_jobs: KnowledgeJob[]
  /**
   * 目的：描述 AdminDashboard.recent_safety_events 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  recent_safety_events: SafetyEvent[]
}

/**
 * 目的：定义 KnowledgeSearchResult 的前端数据结构。
 * 结果：为页面渲染、API 调用和状态管理提供稳定类型约束。
 */
export interface KnowledgeSearchResult {
  /**
   * 目的：描述 KnowledgeSearchResult.chunk_id 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  chunk_id: string
  /**
   * 目的：描述 KnowledgeSearchResult.content 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  content: string
  /**
   * 目的：描述 KnowledgeSearchResult.score 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  score: number
  /**
   * 目的：描述 KnowledgeSearchResult.category 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  category: string
  /**
   * 目的：描述 KnowledgeSearchResult.source 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  source: string
  /**
   * 目的：描述 KnowledgeSearchResult.parent_id 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  parent_id: string
  /**
   * 目的：描述 KnowledgeSearchResult.title 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  title: string
  /**
   * 目的：描述 KnowledgeSearchResult.heading_path 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  heading_path: string
  /**
   * 目的：描述 KnowledgeSearchResult.locator 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  locator: string
}
