import http from '@/api/http'
import type { ApiResponse } from '@/types/api'
import type {
  AdminDashboard,
  AdminPermission,
  AdminRole,
  AdminUser,
  AuditEvent,
  KnowledgeDocument,
  KnowledgeJob,
  KnowledgeSearchResult,
  SafetyEvent,
} from '@/types/admin'

/**
 * 目的：请求后端接口获取 fetchAdminMe 对应的数据。
 * 结果：返回接口约定结果，或完成对应的前端状态更新。
 */
export const fetchAdminMe = async () => {
  const { data: res } = await http.get<ApiResponse<{ user: AdminUser; permissions: string[] }>>('/admin/me')
  return res.data!
}

/**
 * 目的：请求后端接口获取 fetchAdminDashboard 对应的数据。
 * 结果：返回接口约定结果，或完成对应的前端状态更新。
 */
export const fetchAdminDashboard = async () => {
  const { data: res } = await http.get<ApiResponse<AdminDashboard>>('/admin/dashboard')
  return res.data!
}

/**
 * 目的：请求后端接口获取 fetchAdminUsers 对应的数据。
 * 结果：返回接口约定结果，或完成对应的前端状态更新。
 */
export const fetchAdminUsers = async (params: { keyword?: string; status?: string } = {}) => {
  const { data: res } = await http.get<ApiResponse<{ users: AdminUser[] }>>('/admin/users', { params })
  return res.data!.users
}

/**
 * 目的：提交 updateAdminUser 对应的更新操作。
 * 结果：返回接口约定结果，或完成对应的前端状态更新。
 */
export const updateAdminUser = async (userId: string, payload: { status: 'active' | 'disabled' }) => {
  const { data: res } = await http.patch<ApiResponse<{ user: AdminUser; permissions: string[] }>>(
    `/admin/users/${userId}`,
    payload,
  )
  return res.data!
}

/**
 * 目的：请求后端接口获取 fetchAdminRoles 对应的数据。
 * 结果：返回接口约定结果，或完成对应的前端状态更新。
 */
export const fetchAdminRoles = async () => {
  const { data: res } = await http.get<ApiResponse<{ roles: AdminRole[] }>>('/admin/roles')
  return res.data!.roles
}

/**
 * 目的：保存 saveAdminRole 对应的前端或后端状态。
 * 结果：返回接口约定结果，或完成对应的前端状态更新。
 */
export const saveAdminRole = async (
  payload: { code: string; name: string; description: string; permissions: string[] },
  roleId?: string,
) => {
  const { data: res } = roleId
    ? await http.patch<ApiResponse<AdminRole>>(`/admin/roles/${roleId}`, payload)
    : await http.post<ApiResponse<AdminRole>>('/admin/roles', payload)
  return res.data!
}

/**
 * 目的：执行 assignAdminRole 对应的前端业务逻辑。
 * 结果：返回接口约定结果，或完成对应的前端状态更新。
 */
export const assignAdminRole = async (userId: string, roleId: string) => {
  await http.post(`/admin/users/${userId}/roles/${roleId}`)
}

/**
 * 目的：执行 removeAdminRole 对应的前端业务逻辑。
 * 结果：返回接口约定结果，或完成对应的前端状态更新。
 */
export const removeAdminRole = async (userId: string, roleId: string) => {
  await http.delete(`/admin/users/${userId}/roles/${roleId}`)
}

/**
 * 目的：请求后端接口获取 fetchAdminPermissions 对应的数据。
 * 结果：返回接口约定结果，或完成对应的前端状态更新。
 */
export const fetchAdminPermissions = async () => {
  const { data: res } = await http.get<ApiResponse<{ permissions: AdminPermission[] }>>('/admin/permissions')
  return res.data!.permissions
}

/**
 * 目的：请求后端接口获取 fetchKnowledgeDocuments 对应的数据。
 * 结果：返回接口约定结果，或完成对应的前端状态更新。
 */
export const fetchKnowledgeDocuments = async (params: { keyword?: string; status?: string } = {}) => {
  const { data: res } = await http.get<ApiResponse<{ documents: KnowledgeDocument[] }>>(
    '/admin/knowledge/documents',
    { params },
  )
  return res.data!.documents
}

/**
 * 目的：上传 uploadKnowledgeFile 对应的资源。
 * 结果：返回接口约定结果，或完成对应的前端状态更新。
 */
export const uploadKnowledgeFile = async (payload: { file: File; category: string; source: string }) => {
  const form = new FormData()
  form.append('file', payload.file)
  form.append('category', payload.category)
  form.append('source', payload.source)
  const { data: res } = await http.post<ApiResponse<KnowledgeJob>>('/admin/knowledge/files', form)
  return res.data!
}

/**
 * 目的：执行 indexKnowledgeText 对应的前端业务逻辑。
 * 结果：返回接口约定结果，或完成对应的前端状态更新。
 */
export const indexKnowledgeText = async (payload: {
  title: string
  text: string
  category: string
  source: string
}) => {
  const { data: res } = await http.post<ApiResponse<KnowledgeJob>>('/admin/knowledge/text', payload)
  return res.data!
}

/**
 * 目的：提交 deleteKnowledgeDocument 对应的删除操作。
 * 结果：返回接口约定结果，或完成对应的前端状态更新。
 */
export const deleteKnowledgeDocument = async (documentId: string) => {
  const { data: res } = await http.delete<ApiResponse<KnowledgeDocument>>(`/admin/knowledge/documents/${documentId}`)
  return res.data!
}

/**
 * 目的：触发 reindexKnowledgeDocument 对应的重建索引任务。
 * 结果：返回接口约定结果，或完成对应的前端状态更新。
 */
export const reindexKnowledgeDocument = async (documentId: string) => {
  const { data: res } = await http.post<ApiResponse<KnowledgeJob>>(
    `/admin/knowledge/documents/${documentId}/reindex`,
  )
  return res.data!
}

/**
 * 目的：触发 reindexAllKnowledge 对应的重建索引任务。
 * 结果：返回接口约定结果，或完成对应的前端状态更新。
 */
export const reindexAllKnowledge = async () => {
  const { data: res } = await http.post<ApiResponse<KnowledgeJob>>('/admin/knowledge/reindex')
  return res.data!
}

/**
 * 目的：执行 searchKnowledge 对应的前端业务逻辑。
 * 结果：返回接口约定结果，或完成对应的前端状态更新。
 */
export const searchKnowledge = async (payload: { query: string; top_k: number; category?: string }) => {
  const { data: res } = await http.post<ApiResponse<{ query: string; results: KnowledgeSearchResult[]; total: number }>>(
    '/admin/knowledge/search',
    payload,
  )
  return res.data!
}

/**
 * 目的：请求后端接口获取 fetchKnowledgeJobs 对应的数据。
 * 结果：返回接口约定结果，或完成对应的前端状态更新。
 */
export const fetchKnowledgeJobs = async (params: { status?: string } = {}) => {
  const { data: res } = await http.get<ApiResponse<{ jobs: KnowledgeJob[] }>>('/admin/knowledge/jobs', { params })
  return res.data!.jobs
}

/**
 * 目的：重试 retryKnowledgeJob 对应的失败任务。
 * 结果：返回接口约定结果，或完成对应的前端状态更新。
 */
export const retryKnowledgeJob = async (jobId: string) => {
  const { data: res } = await http.post<ApiResponse<KnowledgeJob>>(`/admin/knowledge/jobs/${jobId}/retry`)
  return res.data!
}

/**
 * 目的：取消 cancelKnowledgeJob 对应的后台任务。
 * 结果：返回接口约定结果，或完成对应的前端状态更新。
 */
export const cancelKnowledgeJob = async (jobId: string) => {
  await http.post(`/admin/knowledge/jobs/${jobId}/cancel`)
}

/**
 * 目的：请求后端接口获取 fetchAuditEvents 对应的数据。
 * 结果：返回接口约定结果，或完成对应的前端状态更新。
 */
export const fetchAuditEvents = async () => {
  const { data: res } = await http.get<ApiResponse<{ events: AuditEvent[] }>>('/admin/audit-events')
  return res.data!.events
}

/**
 * 目的：请求后端接口获取 fetchSafetyEvents 对应的数据。
 * 结果：返回接口约定结果，或完成对应的前端状态更新。
 */
export const fetchSafetyEvents = async () => {
  const { data: res } = await http.get<ApiResponse<{ events: SafetyEvent[] }>>('/admin/safety-events')
  return res.data!.events
}

/**
 * 目的：请求后端接口获取 fetchSystemHealth 对应的数据。
 * 结果：返回接口约定结果，或完成对应的前端状态更新。
 */
export const fetchSystemHealth = async () => {
  const { data: res } = await http.get<ApiResponse<{ summary: string; dependencies: Array<Record<string, string>> }>>(
    '/admin/system/health',
  )
  return res.data!
}

/**
 * 目的：请求后端接口获取 fetchSystemConfig 对应的数据。
 * 结果：返回接口约定结果，或完成对应的前端状态更新。
 */
export const fetchSystemConfig = async () => {
  const { data: res } = await http.get<ApiResponse<Record<string, unknown>>>('/admin/system/config-summary')
  return res.data!
}
