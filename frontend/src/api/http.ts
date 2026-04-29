// HTTP客户端配置
// 目的：创建统一的HTTP客户端实例，用于所有API请求

import axios from 'axios'

const DEFAULT_API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8081/'
/**
 * 目的：执行 AUTH_ACCESS_TOKEN_KEY 对应的前端业务逻辑。
 * 结果：返回接口约定结果，或完成对应的前端状态更新。
 */
export const AUTH_ACCESS_TOKEN_KEY = 'ai-love-access-token'
/**
 * 目的：执行 AUTH_REFRESH_TOKEN_KEY 对应的前端业务逻辑。
 * 结果：返回接口约定结果，或完成对应的前端状态更新。
 */
export const AUTH_REFRESH_TOKEN_KEY = 'ai-love-refresh-token'

const trimTrailingSlash = (value: string) => value.replace(/\/+$/, '')

const normalizePath = (path: string) => (path.startsWith('/') ? path : `/${path}`)

/**
 * 创建Axios HTTP客户端实例
 *
 * 目的：配置基础URL和超时时间，提供统一的HTTP请求接口
 */
const http = axios.create({
  baseURL: DEFAULT_API_BASE_URL,
  timeout: 10000,
  withCredentials: true,
})

/**
 * 目的：读取 getStoredAccessToken 对应的本地状态。
 * 结果：返回接口约定结果，或完成对应的前端状态更新。
 */
export const getStoredAccessToken = () => localStorage.getItem(AUTH_ACCESS_TOKEN_KEY) || ''

http.interceptors.request.use((config) => {
  const token = getStoredAccessToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

/**
 * 目的：解析请求地址，统一 axios 与 fetch 的后端入口。
 * 结果：返回接口约定结果，或完成对应的前端状态更新。
 */
export const resolveApiUrl = (path: string) => {
  if (/^https?:\/\//.test(path)) {
    return path
  }
  return `${trimTrailingSlash(DEFAULT_API_BASE_URL)}${normalizePath(path)}`
}

export default http
