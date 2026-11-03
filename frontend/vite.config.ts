/// <reference types="vitest" />
// 版本矩阵（2026-11 核实）：vitest 4.1.x 的 peerDependencies 为 vite ^6 || ^7 || ^8，
// 与顶层 vite 7.3.3 为官方支持组合，npm 解析无嵌套。升级前为 vitest 1.6.1，其 peer
// 范围不含 vite 7，依赖 npm 嵌套 vitest/node_modules/vite@5.4.21 运行，不受官方支持；
// 后续升级 vitest 时须确认 peer 范围覆盖顶层 vite 大版本，避免再次引入嵌套。
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
    exclude: [...configDefaults.exclude, 'tests/e2e/**'],
    coverage: {
      provider: 'istanbul',
      reporter: ['text', 'html'],
      exclude: ['node_modules/', 'tests/', '**/__tests__/**', '**/*.test.ts', '**/*.spec.ts'],
      // 覆盖率门禁只升不降：提升覆盖率时同步上调阈值。
      // lines/statements/branches = 55：由 Lines 首跑基线 58.09% 向下取整到 5 的倍数得出。
      // functions = 45：首跑基线 47.37%（406/857），抬到 55% 需新增覆盖 66 个函数
      // （UI 组件事件处理器/watch 的大工程），经确认后按其自身基线向下取整设定；
      // 后续随测试补充只升不降。
      thresholds: { lines: 55, functions: 45, branches: 55, statements: 55 },
    },
  },
})
