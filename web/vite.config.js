import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// 后端地址（FastAPI 默认 8000 端口）
const BACKEND = 'http://127.0.0.1:8000'

// 需要代理到后端的接口前缀
const PROXY_PREFIX = ['/login', '/users', '/supplier', '/category', '/inventory', '/order', '/record', '/health']

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: Object.fromEntries(
      PROXY_PREFIX.map((p) => [p, { target: BACKEND, changeOrigin: true }])
    )
  }
})
