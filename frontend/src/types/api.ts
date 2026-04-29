/**
 * 目的：定义后端统一 JSON 响应结构。
 * 结果：前端 API 层可以显式读取 code、message 和 data。
 */
export interface ApiResponse<T> {
  code: number
  message: string
  data: T | null
}

/**
 * 目的：定义统一错误响应中的业务数据结构。
 * 结果：调用方可以读取业务错误码、额度和参数校验详情。
 */
export interface ApiErrorData {
  error_code?: string
  remaining?: number | null
  limit?: number | null
  errors?: Array<Record<string, unknown>>
}
