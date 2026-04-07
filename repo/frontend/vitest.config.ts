import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: [resolve(__dirname, './vitest.setup.ts')],
    include: [resolve(__dirname, './src/tests/**/*.test.ts')],
  },
})
