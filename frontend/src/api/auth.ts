import http, { AUTH_ACCESS_TOKEN_KEY, AUTH_REFRESH_TOKEN_KEY } from '@/api/http'
import type { ApiResponse } from '@/types/api'

/**
 * 目的：定义 AuthUser 的前端数据结构。
 * 结果：为页面渲染、API 调用和状态管理提供稳定类型约束。
 */
export interface AuthUser {
  /**
   * 目的：描述 AuthUser.id 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  id: string
  /**
   * 目的：描述 AuthUser.tenant_id 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  tenant_id: string
  /**
   * 目的：描述 AuthUser.nickname 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  nickname: string
  /**
   * 目的：描述 AuthUser.external_user_id 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  external_user_id: string
  /**
   * 目的：描述 AuthUser.avatar_url 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  avatar_url: string
  /**
   * 目的：描述 AuthUser.roles 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  roles: string[]
  /**
   * 目的：描述 AuthUser.permissions 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  permissions: string[]
}

/**
 * 目的：定义 AuthTokenResponse 的前端数据结构。
 * 结果：为页面渲染、API 调用和状态管理提供稳定类型约束。
 */
export interface AuthTokenResponse {
  /**
   * 目的：描述 AuthTokenResponse.access_token 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  access_token: string
  /**
   * 目的：描述 AuthTokenResponse.refresh_token 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  refresh_token: string
  /**
   * 目的：描述 AuthTokenResponse.token_type 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  token_type: 'bearer'
  /**
   * 目的：描述 AuthTokenResponse.expires_in 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  expires_in: number
  /**
   * 目的：描述 AuthTokenResponse.user 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  user: AuthUser
}

/**
 * 目的：定义 AuthCredentials 的前端数据结构。
 * 结果：为页面渲染、API 调用和状态管理提供稳定类型约束。
 */
export interface AuthCredentials {
  /**
   * 目的：描述 AuthCredentials.login_name 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  login_name: string
  /**
   * 目的：描述 AuthCredentials.password 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  password: string
}

/**
 * 目的：定义 AuthRegisterPayload 的前端数据结构。
 * 结果：为页面渲染、API 调用和状态管理提供稳定类型约束。
 */
export interface AuthRegisterPayload extends AuthCredentials {
  /**
   * 目的：描述 AuthRegisterPayload.nickname 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  nickname?: string
}

/**
 * 目的：定义 UpdateProfilePayload 的前端数据结构。
 * 结果：为页面渲染、API 调用和状态管理提供稳定类型约束。
 */
export interface UpdateProfilePayload {
  /**
   * 目的：描述 UpdateProfilePayload.nickname 字段的业务含义。
   * 结果：调用方可以按统一类型安全读写该字段。
   */
  nickname: string
}

/**
 * 目的：保存 saveAuthTokens 对应的前端或后端状态。
 * 结果：返回接口约定结果，或完成对应的前端状态更新。
 */
export const saveAuthTokens = (payload: AuthTokenResponse) => {
  localStorage.setItem(AUTH_ACCESS_TOKEN_KEY, payload.access_token)
  localStorage.setItem(AUTH_REFRESH_TOKEN_KEY, payload.refresh_token)
}

/**
 * 目的：清理 clearAuthTokens 对应的本地状态。
 * 结果：返回接口约定结果，或完成对应的前端状态更新。
 */
export const clearAuthTokens = () => {
  localStorage.removeItem(AUTH_ACCESS_TOKEN_KEY)
  localStorage.removeItem(AUTH_REFRESH_TOKEN_KEY)
}

const getStoredRefreshToken = () => localStorage.getItem(AUTH_REFRESH_TOKEN_KEY) || ''

/**
 * 目的：提交登录请求并建立前端登录态。
 * 结果：返回接口约定结果，或完成对应的前端状态更新。
 */
export const login = async (payload: AuthCredentials) => {
  const { data: res } = await http.post<ApiResponse<AuthTokenResponse>>('/auth/login', payload)
  saveAuthTokens(res.data!)
  return res.data!
}

/**
 * 目的：提交注册请求并建立前端登录态。
 * 结果：返回接口约定结果，或完成对应的前端状态更新。
 */
export const register = async (payload: AuthRegisterPayload) => {
  const { data: res } = await http.post<ApiResponse<AuthTokenResponse>>('/auth/register', payload)
  saveAuthTokens(res.data!)
  return res.data!
}

/**
 * 目的：请求后端接口获取 fetchMe 对应的数据。
 * 结果：返回接口约定结果，或完成对应的前端状态更新。
 */
export const fetchMe = async () => {
  const { data: res } = await http.get<ApiResponse<{ user: AuthUser }>>('/auth/me')
  return res.data!.user
}

/**
 * 目的：提交 updateProfile 对应的更新操作。
 * 结果：返回接口约定结果，或完成对应的前端状态更新。
 */
export const updateProfile = async (payload: UpdateProfilePayload) => {
  const { data: res } = await http.put<ApiResponse<{ user: AuthUser }>>('/auth/me', payload)
  return res.data!.user
}

/**
 * 目的：上传 uploadAvatar 对应的资源。
 * 结果：返回接口约定结果，或完成对应的前端状态更新。
 */
export const uploadAvatar = async (file: File) => {
  const formData = new FormData()
  formData.append('file', file)
  const { data: res } = await http.post<ApiResponse<{ user: AuthUser }>>('/auth/me/avatar', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
  return res.data!.user
}

/**
 * 目的：提交退出登录请求并清理前端登录态。
 * 结果：返回接口约定结果，或完成对应的前端状态更新。
 */
export const logout = async () => {
  const refreshToken = getStoredRefreshToken()
  if (refreshToken) {
    try {
      await http.post<ApiResponse<{ ok: boolean }>>('/auth/logout', {
        refresh_token: refreshToken,
      })
    } catch (error) {
      console.warn('退出登录请求失败，已在前端清理本地登录态', error)
    }
  }
  clearAuthTokens()
}
