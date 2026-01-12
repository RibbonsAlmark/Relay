import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

export default defineConfig(({ mode }) => {
  // 根据当前工作目录的 mode 加载 .env 文件
  const env = loadEnv(mode, process.cwd())

  return {
    plugins: [
      vue(),
      vueDevTools(),
    ],
    server: {
      host: '0.0.0.0',
      port: parseInt(env.VITE_PORT) || 5173, // 优先使用环境变量中的端口
      strictPort: true,
    },
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url))
      },
    },
  }
})