/// <reference types="vitest" />
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import { configDefaults } from 'vitest/config'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    proxy: {
      // target 用 127.0.0.1 而非 localhost：Node 18+ 默认 verbatim DNS 顺序会优先
      // 解析 localhost → ::1，而后端仅监听 IPv4（TCP *:8000），导致代理请求
      // ETIMEDOUT / ECONNREFUSED（vite http proxy error）
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      // 上传文件（头像、凭证、明细等）相对路径 /uploads/** 由后端静态服务提供，
      // 与生产 nginx 的 location /uploads/ 转发保持一致（见 deploy/docker/frontend-nginx.conf）
      '/uploads': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    environmentOptions: {
      jsdom: {
        url: 'http://localhost',
      },
    },
    globals: true,
    pool: 'forks',
    exclude: [
      ...configDefaults.exclude,
      'tests/e2e/**',
    ],
    coverage: {
      provider: 'istanbul',
      reporter: ['text', 'html'],
      exclude: ['node_modules/', 'tests/'],
    },
  },
})
