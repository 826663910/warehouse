import axios from 'axios'
import { ElMessage } from 'element-plus'
import { userStore, clearAuth } from '@/store/user'

const client = axios.create({
  baseURL: '/',
  timeout: 20000
})

// 请求拦截：附加 Bearer Token
client.interceptors.request.use((config) => {
  if (userStore.token) {
    config.headers.Authorization = `Bearer ${userStore.token}`
  }
  return config
})

// 响应拦截：统一取 data / 错误提示
client.interceptors.response.use(
  (resp) => resp.data,
  (err) => {
    const resp = err.response
    const status = resp ? resp.status : 0
    if (status === 401) {
      clearAuth()
      ElMessage.error('登录已过期，请重新登录')
      if (window.location.hash !== '#/login') {
        window.location.hash = '#/login'
      }
    } else {
      const detail = resp?.data?.detail
      const msg =
        detail != null
          ? typeof detail === 'string' ? detail : JSON.stringify(detail)
          : resp ? `请求失败 (${status})` : '无法连接服务器，请确认后端已启动'
      ElMessage.error(msg)
    }
    return Promise.reject(err)
  }
)

/* ========== 认证 ========== */
// 注意：后端 login 接收的是表单格式，非 JSON
export function login(username, password) {
  const body = new URLSearchParams()
  body.append('username', username)
  body.append('password', password)
  return client.post('/login', body, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
  })
}

/* ========== 库存 ========== */
export const listInventory = (params) => client.get('/inventory/', { params })
export const getInventory = (id) => client.get(`/inventory/${id}`)
export const createInventory = (data) => client.post('/inventory/', data)
export const updateInventory = (id, data) => client.patch(`/inventory/${id}`, data)

/* 单据页选品搜索（返回含 id/code/name/type/unit/stock） */
export const searchOrderInventory = (params) => client.get('/order/inventory/search', { params })

/* ========== 供应商 ========== */
export const listSupplier = () => client.get('/supplier/')
export const createSupplier = (data) => client.post('/supplier/', data)
export const updateSupplier = (id, data) => client.patch(`/supplier/${id}`, data)

/* ========== 分类 ========== */
export const listCategory = () => client.get('/category/')
export const createCategory = (data) => client.post('/category/', data)
export const updateCategory = (id, data) => client.patch(`/category/${id}`, data)

/* ========== 单据 ========== */
export const listOrders = (params) => client.get('/order/', { params })
export const getOrder = (id) => client.get(`/order/${id}`)
export const createOrder = (data) => client.post('/order/', data)
export const updateOrder = (id, data) => client.patch(`/order/${id}`, data)
export const reviewOrder = (id) => client.post(`/order/review/${id}`)

/* ========== 流水 ========== */
export const listRecords = (params) => client.get('/record/', { params })

export default client
