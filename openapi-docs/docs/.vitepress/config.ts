import { defineConfig } from 'vitepress'

export default defineConfig({
  title: '开放平台',
  description: '客户运营中台开放平台开发者文档',
  lang: 'zh-CN',
  base: '/openapi/',
  cleanUrls: true,
  themeConfig: {
    logo: '/logo.svg',
    nav: [
      { text: '首页', link: '/' },
      { text: '指南', link: '/guides/getting-started' },
      { text: 'API 参考', link: '/api-reference/' },
      { text: '变更日志', link: '/changelog' },
    ],
    sidebar: {
      '/guides/': [
        {
          text: '指南',
          items: [
            { text: '快速开始', link: '/guides/getting-started' },
            { text: '认证方式', link: '/guides/authentication' },
            { text: '错误码说明', link: '/guides/error-codes' },
          ],
        },
      ],
      '/api-reference/': [
        {
          text: 'API 参考',
          items: [
            { text: '接口索引', link: '/api-reference/' },
            { text: 'ERP 渠道客户余额查询', link: '/api-reference/erp-balances' },
          ],
        },
      ],
    },
    footer: {
      message: 'Released under the Internal Use License.',
    },
    outline: {
      level: [2, 3],
      label: '本页目录',
    },
    docFooter: {
      prev: '上一页',
      next: '下一页',
    },
    search: {
      provider: 'local',
      options: {
        translations: {
          button: { buttonText: '搜索文档', buttonAriaLabel: '搜索文档' },
          modal: {
            noResultsText: '未找到相关结果',
            resetButtonTitle: '清除查询条件',
            footer: { selectText: '选择', navigateText: '切换', closeText: '关闭' },
          },
        },
      },
    },
    editLink: {
      pattern: 'https://github.com/sacrtap/customer_platform_vk/edit/main/openapi-docs/docs/:path',
      text: '在 GitHub 上编辑此页',
    },
  },
})
