import { reactive } from 'vue'

const TOKEN_KEY = 'warehouse_token'
const NAME_KEY = 'warehouse_username'

// 用户登录态（模块级共享）
export const userStore = reactive({
  token: localStorage.getItem(TOKEN_KEY) || '',
  username: localStorage.getItem(NAME_KEY) || ''
})

export function setAuth(token, username) {
  userStore.token = token
  userStore.username = username || ''
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(NAME_KEY, userStore.username)
}

export function clearAuth() {
  userStore.token = ''
  userStore.username = ''
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(NAME_KEY)
}
