# E2E 测试指南

## 测试文件结构

```
tests/e2e/
├── fixtures.ts              # 测试夹具 (登录认证等)
├── playwright.config.ts     # Playwright 配置
├── test_login_flow.spec.ts  # 登录流程测试 (4 个测试)
├── test_customer_crud.spec.ts   # 客户管理测试 (5 个测试)
├── test_invoice_workflow.spec.ts # 结算单工作流测试 (7 个测试)
└── test_balance_recharge.spec.ts # 余额充值测试 (6 个测试)
```

## 测试统计

| 测试文件 | 测试数 | 状态 |
|---------|--------|------|
| test_login_flow.spec.ts | 4 | ✅ |
| test_customer_crud.spec.ts | 5 | ✅ |
| test_invoice_workflow.spec.ts | 7 | ✅ |
| test_balance_recharge.spec.ts | 6 | ✅ |
| **总计** | **22** | **-** |

## 运行测试

###  prerequisites

1. **前端服务运行中**: `npm run dev` (默认 http://localhost:5173)
2. **后端服务运行中**: 提供 API 支持
3. **测试数据库**: 包含测试数据

### 运行命令

```bash
cd frontend

# 列出所有测试
npx playwright test --list

# 运行所有测试 (无头模式)
npx playwright test

# UI 模式 (推荐调试用)
npx playwright test --ui

# 有头模式 (显示浏览器)
npx playwright test --headed

# 仅运行登录测试
npx playwright test test_login_flow.spec.ts

# 仅运行客户管理测试
npx playwright test test_customer_crud.spec.ts

# 仅 Chromium 浏览器
npx playwright test --project=chromium

# 生成 HTML 报告
npx playwright test --reporter=html
# 查看报告
npx playwright show-report
```

## 测试夹具

### `loginPage`
自动导航到登录页的页面实例

```typescript
test('测试登录', async ({ loginPage }) => {
  // loginPage 已加载 /login 页面
  await loginPage.fill('input[name="username"]', 'admin');
});
```

### `authenticatedPage`
已登录认证的页面实例

```typescript
test('测试已登录状态', async ({ authenticatedPage }) => {
  // authenticatedPage 已登录并位于首页
  await authenticatedPage.goto('/customers');
});
```

## 测试账号

| 用户名 | 密码 | 角色 |
|--------|------|------|
| admin | admin123 | 管理员 |

## 测试覆盖流程

### 1. 登录流程
- ✅ 成功登录
- ✅ 密码错误提示
- ✅ 未登录访问受保护页面 (重定向)
- ✅ 已登录访问登录页 (重定向)

### 2. 客户管理
- ✅ 访问客户列表页面
- ✅ 创建新客户
- ✅ 搜索客户
- ✅ 分页功能
- ✅ 客户列表数据加载

### 3. 结算单工作流
- ✅ 访问结算单列表页面
- ✅ 生成结算单
- ✅ 结算单状态流转 (提交→确认→付款→完成)
- ✅ 结算单详情查看

### 4. 余额充值
- ✅ 访问余额管理页面
- ✅ 查看客户余额详情
- ✅ 执行充值操作
- ✅ 查看充值记录
- ✅ 充值记录筛选
- ✅ 余额不足预警

## 调试技巧

### 1. 使用 Playwright Inspector
```bash
PWDEBUG=1 npx playwright test test_login_flow.spec.ts
```

### 2. 截图调试
在测试中添加:
```typescript
await page.screenshot({ path: 'debug.png' });
```

### 3. 慢动作回放
```bash
npx playwright test --debug
```

### 4. 查看测试轨迹
测试失败后会自动生成 trace，查看方法:
```bash
npx playwright show-trace test-results/<test-name>/trace.zip
```

## 常见问题

### Q: 测试失败 "TimeoutError: Timeout 30s exceeded"
**A**: 检查前端服务是否运行在 http://localhost:5173

### Q: 找不到元素选择器
**A**: 使用 Playwright Inspector 查看实际 DOM 结构，调整选择器

### Q: 登录失败
**A**: 确认后端服务运行且测试账号存在

### Q: 测试通过但实际功能有问题
**A**: 使用 `--headed` 模式观察实际浏览器行为

## 持续集成

在 CI 环境中运行:
```bash
# 安装依赖
npm install
npx playwright install --with-deps chromium

# 运行测试
npx playwright test --project=chromium --reporter=list

# 上传 HTML 报告 (可选)
npx playwright show-report
```

## 下一步

- [ ] 添加标签管理 E2E 测试
- [ ] 添加用户管理 E2E 测试
- [ ] 添加数据分析页面 E2E 测试
- [ ] 集成到 CI/CD 流程
- [ ] 添加视觉回归测试

---

**最后更新**: 2026-04-04  
**测试框架**: Playwright 1.59.1
