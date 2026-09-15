import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// VITE_BASE=/customer/ for Nginx path deploy; leave unset for local root.
export default defineConfig(({ mode }) => {
  const apiTarget = process.env.VITE_API_TARGET || 'http://127.0.0.1:1024'
  return {
    base: process.env.VITE_BASE || '/',
    plugins: [vue()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url))
      }
    },
    server: {
      port: mode === 'agent' ? 1026 : 1027,
      strictPort: true,
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true
        },
        '/media': {
          target: apiTarget,
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
      restoreMocks: true
    }
  }
})
