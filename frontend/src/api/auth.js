import { http } from './request'

/**
 * 登录：POST /auth/login
 * 返回 { token, username, email, avatar, is_active, created_at }
 */
export function login({ username, password }) {
  return http.post('/auth/login', { username, password }, { auth: false })
}

/**
 * 注册：POST /auth/register  → 201
 * email 是可选的，不填就别传字段（后端 EmailStr|None，传空串也行，但空串会被归一化成 None）
 */
export function register({ username, password, email }) {
  const body = { username, password }
  if (email) body.email = email
  return http.post('/auth/register', body, { auth: false })
}

/**
 * 后端没有「取当前用户信息」的接口，登录/注册返回的那份就是全部。
 * 页面刷新后从 localStorage 恢复，不再打请求。
 */
