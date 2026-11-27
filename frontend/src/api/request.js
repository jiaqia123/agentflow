/**
 * 极简 fetch 封装。
 *
 * 约定：
 *  - 所有请求走 `/api` 前缀，由 vite 代理转给后端（生产环境换 nginx 反代）
 *  - token 存在 localStorage，自动带 `Authorization: Bearer <token>`
 *  - 后端 FastAPI 报错时 body 是 `{ detail: string | object[] }`，这里统一抽成一句话
 *  - 401 统一清登录态并跳登录页（由调用方通过 onUnauthorized 钩子接管，避免循环依赖）
 */

export const TOKEN_KEY = 'agentflow_token'
export const USER_KEY = 'agentflow_user'

const BASE = '/api'

/** 带状态码与原始 detail 的业务异常，视图层可直接 catch 后用 message 提示 */
export class ApiError extends Error {
  constructor(message, status = 0, detail = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

/** 401 的接管钩子，由 useAuth 注册。默认什么都不做。 */
let onUnauthorized = null
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || ''
}

function buildQuery(params) {
  if (!params) return ''
  const usp = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    // 空串 / null / undefined 一律不拼进 URL，避免后端把 "" 当成有效过滤条件
    if (value === null || value === undefined || value === '') return
    usp.append(key, String(value))
  })
  const qs = usp.toString()
  return qs ? `?${qs}` : ''
}

/**
 * 把 FastAPI 的 detail 转成一句人话。
 * 422 校验错误时 detail 是数组：[{ loc: ['body','name'], msg: 'Field required' }]
 */
function normalizeDetail(detail, status) {
  if (typeof detail === 'string' && detail) return detail
  if (Array.isArray(detail) && detail.length) {
    const lines = detail.map((item) => {
      const loc = Array.isArray(item.loc)
        ? item.loc.filter((p) => p !== 'body' && p !== 'query').join('.')
        : ''
      const msg = item.msg || '参数不合法'
      return loc ? `${loc}：${msg}` : msg
    })
    return lines.join('；')
  }
  if (status === 0) return '无法连接后端服务'
  return `请求失败（HTTP ${status}）`
}

async function readBody(res) {
  const text = await res.text()
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    // 后端 500 有时返回 Starlette 的纯文本 "Internal Server Error"
    return { detail: text.slice(0, 300) }
  }
}

/**
 * 发请求。
 *
 * @param {string} path     以 / 开头的后端路径，例如 '/knowledge'
 * @param {object} options
 * @param {string} [options.method='GET']
 * @param {object} [options.params]  查询参数，空值会被丢掉
 * @param {any}    [options.body]    JSON 请求体
 * @param {FormData} [options.form]  表单请求体（上传用，与 body 二选一）
 * @param {boolean} [options.auth=true] 是否带 token
 */
export async function request(path, options = {}) {
  const { method = 'GET', params, body, form, auth = true } = options

  const headers = {}
  if (auth) {
    const token = getToken()
    if (token) headers.Authorization = `Bearer ${token}`
  }

  let payload
  if (form) {
    // 千万不要手动设 Content-Type，浏览器要自己补 multipart 的 boundary
    payload = form
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }

  let res
  try {
    res = await fetch(`${BASE}${path}${buildQuery(params)}`, { method, headers, body: payload })
  } catch (err) {
    throw new ApiError('无法连接后端服务，请确认后端已在 127.0.0.1:8000 启动', 0, err)
  }

  const data = await readBody(res)

  if (res.ok) return data

  if (res.status === 401) {
    if (onUnauthorized) onUnauthorized()
  }

  throw new ApiError(normalizeDetail(data?.detail, res.status), res.status, data?.detail ?? null)
}

export const http = {
  get: (path, params, options) => request(path, { method: 'GET', params, ...options }),
  post: (path, body, options) => request(path, { method: 'POST', body, ...options }),
  upload: (path, form, options) => request(path, { method: 'POST', form, ...options })
}
