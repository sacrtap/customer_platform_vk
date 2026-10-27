/**
 * 自定义规则：async-button-loading
 *
 * 背景：导出/同步类同步阻塞请求若无「进行中」状态，用户会重复点击触发
 * 多次请求（客户管理页、结算单页曾因此缺 `exporting` 状态）。
 *
 * 本规则是低成本静态护栏：检测 `<button @click="handleExport">` 形态的
 * 按钮是否绑定了 `:disabled` / `:loading`。不试图理解语义，只要求
 * 「命名像异步动作的按钮必须有禁用态」。
 *
 * 判据：
 *   - @click 绑定为裸标识符或 `identifier(...)` 调用
 *   - 标识符匹配 ^(handle|on|run|do)[A-Z]
 *   - 不在同步 handler 白名单内
 *   - 按钮无 :disabled / disabled / :loading
 * 命中以上全部则报告。
 */

/** 已知的同步 handler 白名单（打开弹窗、切换显隐、分页等） */
const SYNC_HANDLERS = new Set([
  'handleSearch',
  'handleReset',
  'handlePageChange',
  'handlePageSizeChange',
  'handleSortChange',
  'handleSort',
  'handleRefresh',
  'handleClose',
  'handleCancel',
  'handleBack',
  'handleOpenCreateModal',
  'onPageChange',
  'onPageSizeChange',
  'onRowClick',
  'onSortChange',
  'onTabChange',
  'onFilterChange',
  // 纯前端提示 / 仅打开弹窗的同步 handler
  'handleSSO',
  'handleSyncButtonClick',
])

const ASYNC_HANDLER_PATTERN = /^(handle|on|run|do)[A-Z]/

/** 从 @click 表达式中提取被调用的标识符；非简单标识符形态返回 null */
function extractHandlerName(expr) {
  if (!expr) return null
  switch (expr.type) {
    case 'Identifier':
      return expr.name
    case 'CallExpression':
      return expr.callee.type === 'Identifier' ? expr.callee.name : null
    default:
      return null
  }
}

export default {
  meta: {
    type: 'problem',
    docs: {
      description: '要求异步动作按钮绑定禁用态（:disabled / :loading），防止重复点击',
      recommended: false,
    },
    schema: [],
    messages: {
      missingDisabled:
        '按钮 `@click="{{ handler }}"` 未绑定禁用态。若该动作是异步请求，请绑定 `:disabled="..."` 或改用 `useExportAction`；若确为同步操作，请将其加入 SYNC_HANDLERS 白名单。',
    },
  },

  create(context) {
    const sourceCode = context.sourceCode

    function getClickHandler(node) {
      for (const attr of node.startTag.attributes) {
        if (
          attr.directive &&
          attr.key.name.name === 'on' &&
          attr.key.argument &&
          attr.key.argument.name === 'click'
        ) {
          return attr.value ? attr.value.expression : null
        }
      }
      return null
    }

    function hasDisabledBinding(node) {
      for (const attr of node.startTag.attributes) {
        if (!attr.directive) {
          if (attr.key.name === 'disabled') return true
          continue
        }
        if (attr.key.name.name === 'bind') {
          const arg = attr.key.argument
          if (arg && (arg.name === 'disabled' || arg.name === 'loading')) return true
        }
      }
      return false
    }

    function checkElement(node) {
      if (node.type === 'VElement' && node.name === 'button') {
        const expr = getClickHandler(node)
        const name = expr ? extractHandlerName(expr) : null

        if (name && ASYNC_HANDLER_PATTERN.test(name) && !SYNC_HANDLERS.has(name)) {
          if (!hasDisabledBinding(node)) {
            context.report({ node, messageId: 'missingDisabled', data: { handler: name } })
          }
        }
      }

      for (const child of node.children || []) {
        checkElement(child)
      }
    }

    return {
      'Program:exit'() {
        const templateBody = sourceCode.ast.templateBody
        if (!templateBody) return
        checkElement(templateBody)
      },
    }
  },
}
