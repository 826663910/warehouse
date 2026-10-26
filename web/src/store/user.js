import { reactive } from 'vue'

const TOKEN_KEY = 'warehouse_token'
const NAME_KEY = 'warehouse_username'
const LEVEL_KEY = 'warehouse_level'

// 用户登录态（模块级共享）
export const userStore = reactive({
  token: localStorage.getItem(TOKEN_KEY) || '',
  username: localStorage.getItem(NAME_KEY) || '',
  level: Number(localStorage.getItem(LEVEL_KEY)) || 0   // 0=未知(旧登录态) 1=普通 2=管理员 3=超管
})

export function setAuth(token, username, level) {
  userStore.token = token
  userStore.username = username || ''
  userStore.level = Number(level) || 0
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(NAME_KEY, userStore.username)
  localStorage.setItem(LEVEL_KEY, String(userStore.level))
}

export function clearAuth() {
  userStore.token = ''
  userStore.username = ''
  userStore.level = 0
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(NAME_KEY)
  localStorage.removeItem(LEVEL_KEY)
}
