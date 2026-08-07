import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')

  return {
    plugins: [react()],
    server: {
      proxy: {
        '/ai-api': {
          target: env.VITE_AI_API_PROXY_TARGET || 'http://127.0.0.1:8001',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/ai-api/, ''),
        },
        '/stt-api': {
          target: env.VITE_STT_API_PROXY_TARGET || 'http://127.0.0.1:8002',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/stt-api/, ''),
        },
        '/core-api': {
          target: env.VITE_CORE_API_PROXY_TARGET || 'http://127.0.0.1:8080',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/core-api/, ''),
        },
        '/ws': {
          target: env.VITE_WS_PROXY_TARGET || 'ws://127.0.0.1:8080',
          ws: true,
          changeOrigin: true,
        },
      },
    },
  }
})
