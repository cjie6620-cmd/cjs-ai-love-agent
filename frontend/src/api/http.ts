// HTTP客户端配置
// 目的：创建统一的HTTP客户端实例，用于所有API请求

import axios from 'axios'

const DEFAULT_API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000/'

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
})

/**
 * 解析 API 完整地址
 *
 * 目的：让 fetch 和 axios 统一走同一套 baseURL，避免流式请求还依赖 Vite 代理，
 * 在前后端分离部署时出现地址对了但流式链路没打通的问题。
 */
export const resolveApiUrl = (path: string) => {
  if (/^https?:\/\//.test(path)) {
    return path
  }
  return `${trimTrailingSlash(DEFAULT_API_BASE_URL)}${normalizePath(path)}`
}

export default http
