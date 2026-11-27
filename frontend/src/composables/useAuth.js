import { computed, reactive, readonly } from 'vue'
import { TOKEN_KEY, USER_KEY, setUnauthorizedHandler } from '@/api/request'
import * as authApi from '@/api/auth'

/**
 * 登录态。项目没装 pinia，用一个模块级 reactive 单例就够了 ——
 * 所有组件 import 到的是同一个对象。
 *
 * token / user 同时写进 localStorage，刷新页面不丢。
 */

function readUser() {
  try {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

const state = reactive({
  token: localStorage.getItem(TOKEN_KEY) || '',
  user: readUser()
})

function persist(token, user) {
  state.token = token
  state.user = user
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

function clear() {
  state.token = ''
  state.user = null
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

// 任意请求收到 401 时清登录态；跳转交给路由守卫（守卫看 isLoggedIn 会自己踢回登录页）
setUnauthorizedHandler(() => clear())

export function useAuth() {
  const isLoggedIn = computed(() => Boolean(state.token))
  const displayName = computed(() => state.user?.username || '未登录')
  const initial = computed(() => (state.user?.username || '?').slice(0, 1).toUpperCase())

  async function doLogin(payload) {
    const data = await authApi.login(payload)
    applyAuthPayload(data)
    return data
  }

  async function doRegister(payload) {
    const data = await authApi.register(payload)
    applyAuthPayload(data)
    return data
  }

  /** 登录和注册返回的结构一样：{ token, username, email, avatar, is_active, created_at } */
  function applyAuthPayload(data) {
    persist(data.token, {
      username: data.username,
      email: data.email,
      avatar: data.avatar,
      is_active: data.is_active,
      created_at: data.created_at
    })
  }

  function logout() {
    clear()
  }

  return {
    state: readonly(state),
    isLoggedIn,
    displayName,
    initial,
    login: doLogin,
    register: doRegister,
    logout
  }
}
