import axios from 'axios'

export interface Page<T> {
  items: T[]
  total: number
  page?: number
  page_size?: number
}

export interface ApiError extends Error {
  status: number
  code: string
  detail?: unknown
  original?: unknown
}

const STATUS_MESSAGE: Record<number, string> = {
  400: '请求参数有误',
  401: '登录已失效，请重新登录',
  403: '当前角色无权执行该操作',
  404: '资源不存在或已被删除',
  409: '数据已被他人修改，请刷新后重试',
  422: '校验未通过，请检查输入',
  500: '服务异常，请稍后重试',
}

const CODE_MESSAGE: Record<string, string> = {
  permission_denied: '当前角色无权执行该操作',
  version_conflict: '数据已被他人修改，请刷新后重试',
  validation_error: '校验未通过，请检查输入',
}

/** 把 axios / 网关 / 后端错误统一成带 status、code、detail 的 Error */
export function normalizeError(error: any): ApiError {
  const response = (error && error.response) || {}
  const body = response.data || (error && error.data) || {}
  const status = response.status || (error && error.status) || 0
  const code = (body && body.code) || ''
  const message =
    CODE_MESSAGE[code] ||
    (body && body.message) ||
    STATUS_MESSAGE[status] ||
    (error && error.message) ||
    '请求失败'

  const normalized = new Error(message) as ApiError
  normalized.status = status
  normalized.code = typeof code === 'string' ? code : String(code)
  normalized.detail = body && body.detail
  normalized.original = error
  return normalized
}

export const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 30000,
})

http.interceptors.request.use((config) => {
  // 后端开发期通过请求头识别用户与角色；接入真实登录后替换为 Token。
  config.headers['X-User-Id'] = localStorage.getItem('semantic-layer.user') || 'dev-user'
  config.headers['X-Roles'] = localStorage.getItem('semantic-layer.roles') || 'admin,modeler'
  return config
})

export async function request<T = any>(
  method: string,
  url: string,
  payload?: unknown,
  params?: Record<string, unknown>,
): Promise<T> {
  try {
    const response = await http.request<T>({ method, url, data: payload, params })
    return response.data
  } catch (error) {
    throw normalizeError(error)
  }
}

/** 解包 `{code, message, data}` 包裹体，兼容裸 JSON */
export function unwrap<T = any>(res: any): T {
  if (res && typeof res === 'object' && !Array.isArray(res) && Object.prototype.hasOwnProperty.call(res, 'data')) {
    return res.data as T
  }
  return res as T
}

/** 统一分页结构 */
export function unwrapPage<T = any>(res: any): Page<T> {
  const body = res || {}
  const data = Object.prototype.hasOwnProperty.call(body, 'data') ? body.data : body
  if (Array.isArray(data)) {
    return { items: data, total: data.length }
  }
  const items = (data && (data.items || data.records || data.rows || data.list)) || []
  const total = (data && (data.total !== undefined ? data.total : data.totalCount)) || items.length
  return { items, total }
}