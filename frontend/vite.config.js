import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    port: 5173,
    open: false,
    // 开发期把请求转给本地 FastAPI（127.0.0.1:8000），前端代码里统一走 /api，
    // 这样不需要后端开 CORS，生产环境换成 nginx 反代即可，前端一行都不用改
    proxy: {
      // /api/knowledge  ->  http://127.0.0.1:8000/knowledge
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      },
      // 后端返回的文件地址本身就是 /static/xxx，原样转发
      '/static': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      }
    }
  }
})
