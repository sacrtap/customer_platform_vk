# E2E 测试指南

## 测试文件结构

```
tests/e2e/
├── fixtures.ts                    # 测试夹具 (登录认证等)
├── test-helpers.ts                # 公共工具 (API 数据准备、UI 辅助函数)
├── playwright.config.ts           # Playwright 配置
│
│── 客户管理测试 (57 个)
├── test_customer_crud.spec.ts     # 客户 CRUD 测试 (9 个)
├── customer-detail.spec.ts        # 客户详情测试 (17 个)
├── test_customer_filters.spec.ts  # 客户筛选测试 (10 个)
├── test_customer_import_export.spec.ts  # 导入/导出测试 (6 个)
├── test_customer_edge_cases.spec.ts     # 边界/异常测试 (9 个)
├── test_customer_permissions.spec.ts    # 权限控制测试 (6 个)
│
└── 其他测试
├── test_login_flow.spec.ts        # 登录流程测试
├── test_billing_workflow.spec.ts  # 结算单工作流测试
├── test_balance_recharge.spec.ts  # 余额充值测试
├── test_analytics.spec.ts         # 数据分析测试
├── test_core_pages_rendering.spec.ts  # 核心页面渲染测试
├── test_roles.spec.ts             # 角色管理测试
├── test_users.spec.ts             # 用户管理测试
├── test_tags.spec.ts              # 标签管理测试
└── test_invoice_workflow.spec.ts  # 结算单工作流测试
```

## 测试统计

### 客户管理测试

| 测试文件                            | 测试数 | 状态 | 说明                               |
| ----------------------------------- | ------ | ---- | ---------------------------------- |
| test_customer_crud.spec.ts          | 9      | ✅   | 创建、查看、编辑、删除、验证       |
| customer-detail.spec.ts             | 17     | ✅   | 5 个 Tab、标签管理、编辑、重点切换 |
| test_customer_filters.spec.ts       | 10     | ✅   | 关键词、账号、行业、等级、多条件   |
| test_customer_import_export.spec.ts | 6      | ✅   | 模板下载、文件上传、导出           |
| test_customer_edge_cases.spec.ts    | 9      | ✅   | 超长输入、分页、空状态、会话       |
| test_customer_permissions.spec.ts   | 6      | ✅   | Super Admin 全权限验证             |
| **客户管理合计**                        | **57**     | ✅   |                                    |

### 总体统计

| 类别 | 测试数 |
| ---- | ------ |
| 客户管理 | 57 |
| 其他 E2E 测试 | ~19 |
| **总计** | **76+** |

## 运行测试

### Prerequisites

1. **前端服务运行中**: `npm run dev` (默认 http://localhost:5173)
2. **后端服务运行中**: 提供 API 支持
3. **Redis 已启动**: `redis-server --daemonize yes`
4. **测试数据库**: 包含测试数据

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

# 仅运行客户管理测试
npx playwright test test_customer_crud.spec.ts customer-detail.spec.ts test_customer_filters.spec.ts test_customer_import_export.spec.ts test_customer_edge_cases.spec.ts test_customer_permissions.spec.ts

# 仅运行单个测试文件
npx playwright test test_customer_crud.spec.ts

# 仅运行单个测试用例
npx playwright test test_customer_crud.spec.ts -g "创建新客户"

# 仅 Chromium 浏览器
npx playwright test --project=chromium

# 生成 HTML 报告
npx playwright test --reporter=html
# 查看报告
npx playwright show-report
```

## 测试架构

### API 数据准备
测试使用 Node.js HTTP 模块直接调用后端 API 进行数据准备，而非通过 UI 操作：

```typescript
// 示例: test-helpers.ts 中的 API 调用
import * as http from 'http';

function apiRequest(method: string, path: string, body?: any, headers?: Record<string, string>) {
  return new Promise((resolve, reject) => {
    const req = http.request({
      hostname: 'localhost',
      port: 8000,
      path,
      method,
      headers: { 'Content-Type': 'application/json', ...headers },
    }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => resolve({ status: res.statusCode, data: JSON.parse(data) }));
    });
    req.on('error', reject);
    if (body) req.write(JSON.stringify(body));
    req.end();
  });
}
```

**优势**:
- 每个测试通过 `apiCreateCustomer()` 创建独立的测试数据
- 测试结束后通过 `apiDeleteCustomer()` 自动清理
- 使用 `generateTestCompanyId()` 和 `generateTestCustomerName()` 生成唯一标识避免冲突
- 不依赖 UI 操作，测试速度更快，更稳定

### 容错设计
- API 调用失败时自动 `test.skip()` 而非阻塞其他测试
- 选择器使用 `.first()` 避免 Playwright 严格模式冲突
- 所有清理操作使用 `.catch(() => {})` 确保不影响后续测试
- 超时时间合理设置，避免偶发性网络延迟导致失败

### 测试数据清理
```typescript
// 每个测试文件都有 afterEach/afterAll 清理
test.afterEach(async () => {
  for (const id of createdIds) {
    await apiDeleteCustomer(authToken, id).catch(() => {});
  }
});
```

## 测试夹具

### `loginPage`
自动导航到登录页的页面实例

```typescript
test('测试登录', async ({ loginPage }) => {
  // loginPage 已加载 /login 页面
  await loginPage.fill('input[field="username"]', 'admin');
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
| admin | admin123 | 超级管理员 |

## 测试覆盖流程

### 客户管理 (57 个测试)

#### 1. CRUD 操作 (9 个)
- ✅ 访问客户列表页面
- ✅ 创建新客户 - 基本信息
- ✅ 查看客户详情
- ✅ 编辑客户信息
- ✅ 删除客户
- ✅ 取消删除操作
- ✅ 创建客户 - 必填字段验证
- ✅ 创建客户 - 邮箱格式验证
- ✅ 创建重复公司 ID 客户

#### 2. 详情页面 (17 个)
- ✅ 导航到客户详情页面
- ✅ 显示客户基础信息
- ✅ 显示客户标签
- ✅ 添加客户标签
- ✅ 移除客户标签
- ✅ 画像信息 Tab 显示
- ✅ 健康度仪表显示
- ✅ 消费等级进度显示
- ✅ 余额信息 Tab 显示
- ✅ 余额数据正确显示
- ✅ 余额趋势图显示
- ✅ 结算单 Tab 显示
- ✅ 用量数据 Tab 显示
- ✅ 编辑客户详情
- ✅ 设为/取消重点客户
- ✅ Tab 切换功能正常
- ✅ 返回按钮功能

#### 3. 筛选功能 (10 个)
- ✅ 关键词搜索 - 公司 ID
- ✅ 关键词搜索 - 客户名称
- ✅ 账号类型筛选
- ✅ 行业类型筛选
- ✅ 客户等级筛选
- ✅ 重点客户筛选
- ✅ 高级筛选 - 运营经理
- ✅ 重置筛选
- ✅ 多条件组合筛选
- ✅ 空结果提示

#### 4. 导入/导出 (6 个)
- ✅ 下载导入模板
- ✅ 验证导入弹窗UI元素
- ✅ 上传文件功能可用
- ✅ 导入重复数据流程
- ✅ 导出客户数据
- ✅ 导出带筛选条件的数据

#### 5. 边界/异常 (9 个)
- ✅ 创建客户 - 超长公司名称
- ✅ 创建客户 - 超长公司 ID
- ✅ 创建客户 - 特殊字符
- ✅ 快速连续创建（防抖/竞态）
- ✅ 分页边界 - 最后一页
- ✅ 网络错误恢复
- ✅ 详情页 - 不存在的客户 ID
- ✅ 空数据列表状态
- ✅ 会话超时处理

#### 6. 权限控制 (6 个)
- ✅ Super Admin 可见新建按钮
- ✅ Super Admin 可见编辑按钮
- ✅ Super Admin 可见删除按钮
- ✅ Super Admin 可见导入按钮
- ✅ Super Admin 可见导出按钮
- ✅ Super Admin 拥有全部操作权限

## 调试技巧

### 1. 使用 Playwright Inspector
```bash
PWDEBUG=1 npx playwright test test_customer_crud.spec.ts
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

### 5. 单独运行一个测试用例
```bash
npx playwright test test_customer_crud.spec.ts -g "创建新客户"
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

### Q: API 创建客户失败 (401 错误)
**A**: 检查 test-helpers.ts 中的 API 地址和端口配置是否正确

### Q: strict mode violation 错误
**A**: 确保所有 locator 都使用了 `.first()` 方法

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

**最后更新**: 2026-04-15  
**测试框架**: Playwright 1.59.1  
**客户管理测试**: 57 个 ✅ 全部通过
