import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// 前端 SPA 构建配置
// 开发时通过 dev proxy 将 /api 转发到 Django 后端 (http://127.0.0.1:1024)
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    port: 1025,
    strictPort: true,
    proxy: {
      '/api': {
        target: process.env.VITE_API_TARGET || 'http://127.0.0.1:1024',
        changeOrigin: true
      },
      '/media': {
        target: process.env.VITE_API_TARGET || 'http://127.0.0.1:1024',
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: 'dist',
    chunkSizeWarningLimit: 1500
  },
  test: {
    environment: 'jsdom',
    globals: true,
    restoreMocks: true,
    exclude: ['e2e/**', 'node_modules/**', 'dist/**']
  }
})
