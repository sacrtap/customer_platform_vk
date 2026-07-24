# 接口错误处理优化设计文档

**创建日期**: 2026-05-18
**状态**: 待实施
**优先级**: P0
**作者**: Product Manager

---

## 1. 背景与问题

### 1.1 当前问题

客户运营中台在接口请求失败时，统一返回 401 相关的提示，与业务场景不匹配。

**具体表现**：

| 问题 | 严重程度 | 影响范围 |
|------|----------|----------|
| 后端 `webhooks.py` 使用原始 HTTP 状态码作为业务 code（如 `code: 400`），与其他路由的五位错误码不一致 | 🔴 高 | 前端无法统一解析 |
| 前端缺少全局错误码映射和处理机制 | 🔴 高 | 所有页面 |
| 响应拦截器对 401 响应处理过度，其他错误直接返回原始信息 | 🟡 中 | Token 刷新逻辑 |
| 各页面错误提示过于笼统（"操作失败"） | 🟡 中 | 用户体验差 |

### 1.2 优化目标

1. 统一后端错误码规范（五位错误码体系）
2. 创建前端错误处理工具，实现差异化错误提示
3. 优化 HTTP 拦截器，注入错误分类信息
4. 逐步迁移各页面采用新的错误处理模式

---

## 2. 架构设计

### 2.1 设计原则

- **单一责任**: 错误码定义、错误分类、错误提示各自独立
- **向后兼容**: 新基础设施不破坏现有功能
- **渐进式迁移**: 支持新旧代码并存，逐步替换

### 2.2 架构层次

```
┌─────────────────────────────────────────────────┐
│                   前端页面层                      │
│  (使用 handleError() 统一处理错误)                │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│              错误处理工具层                        │
│  errorHandler.ts                                 │
│  - getErrorCategory()  错误分类                    │
│  - getUserFriendlyMessage() 友好提示              │
│  - handleError() 统一处理入口                     │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│              HTTP 拦截器层                         │
│  api/index.ts                                    │
│  - 解析后端错误码                                 │
│  - 注入错误分类信息                               │
│  - 401 特殊处理（token 刷新）                      │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│              后端 API 层                           │
│  constants/error_codes.py                        │
│  - 统一错误码常量定义                              │
│  - 五位错误码体系                                 │
└─────────────────────────────────────────────────┘
```

---

## 3. 组件设计

### 3.1 后端错误码常量定义

**文件**: `backend/app/constants/error_codes.py`

**错误码规范**:

```
错误码格式: XXXXX (5 位数字)
- 第 1 位: 错误大类 (4=客户端错误, 5=服务器错误)
- 第 2-3 位: 错误小类 (00=通用, 01=参数, 02=格式, 03=认证, 04=权限, 05=资源不存在)
- 第 4-5 位: 具体错误序号
```

**错误码枚举**:

| 常量 | 错误码 | 说明 |
|------|--------|------|
| `SUCCESS` | 0 | 成功 |
| `BAD_REQUEST` | 40001 | 通用参数错误 |
| `INVALID_FORMAT` | 40002 | 格式错误（邮箱、手机号等） |
| `INVALID_FILE` | 40003 | 文件格式错误 |
| `MISSING_PARAMETER` | 40004 | 缺少必要参数 |
| `UNAUTHORIZED` | 40101 | 未认证/缺少 Token |
| `TOKEN_INVALID` | 40102 | Token 无效或已过期 |
| `TOKEN_BLACKLISTED` | 40103 | Token 已失效 |
| `FORBIDDEN` | 40301 | 权限不足 |
| `NOT_FOUND` | 40401 | 通用资源不存在 |
| `INTERNAL_ERROR` | 50000 | 通用服务器错误 |
| `SERVICE_ERROR` | 50001 | 服务处理失败 |

### 3.2 前端错误处理工具

**文件**: `frontend/src/utils/errorHandler.ts`

**核心函数**:

| 函数 | 职责 | 示例 |
|------|------|------|
| `getErrorCategory(code)` | 根据错误码返回分类 | `getErrorCategory(40001) → 400` |
| `getUserFriendlyMessage()` | 获取用户友好的错误提示 | 参数错误 → 显示后端信息; 500 错误 → "系统繁忙" |
| `handleError(error)` | 统一错误处理入口 | 自动展示 Message.error |
| `showError(message)` | 展示错误提示 | `showError("登录已过期")` |

**错误分类枚举**:

```typescript
enum ErrorCategory {
  SUCCESS = 0,
  CLIENT_ERROR = 400,      // 400xx - 参数错误
  AUTH_ERROR = 401,         // 401xx - 认证错误
  FORBIDDEN_ERROR = 403,    // 403xx - 权限不足
  NOT_FOUND_ERROR = 404,    // 404xx - 资源不存在
  BUSINESS_ERROR = 422,     // 422xx - 业务逻辑错误
  SERVER_ERROR = 500,       // 500xx - 服务器错误
}
```

### 3.3 HTTP 拦截器改造

**文件**: `frontend/src/api/index.ts`

**改造要点**:

1. **响应成功处理**:
   - 解析业务错误码 `res.code`
   - 注入错误分类信息到 reject 对象

2. **响应错误处理**:
   - HTTP 401 → 保持现有 token 刷新逻辑
   - HTTP 错误/网络错误 → 返回标准化错误对象

3. **错误对象格式**:

   ```typescript
   {
     code: 40001,              // 错误码
     message: "参数不能为空",     // 后端原始信息
     category: 400,            // 错误分类
   }
   ```

### 3.4 错误处理流程

**正常业务流程**:

```
用户操作 → API 调用 → 后端返回 {code: 40001, message: "参数不能为空"}
                        ↓
              拦截器解析错误码
                        ↓
              reject({code: 40001, message: "参数不能为空", category: 400})
                        ↓
              页面 catch(error)
                        ↓
              handleError(error)
                        ↓
              分类为 CLIENT_ERROR → 显示 "参数不能为空"
```

**系统错误流程**:

```
用户操作 → API 调用 → 后端返回 {code: 50000, message: "系统错误"}
                        ↓
              拦截器解析错误码
                        ↓
              reject({code: 50000, message: "系统错误", category: 500})
                        ↓
              页面 catch(error)
                        ↓
              handleError(error)
                        ↓
              分类为 SERVER_ERROR → 显示 "系统繁忙，请稍后重试"
```

---

## 4. 迁移策略

### 4.1 阶段划分

| 阶段 | 任务 | 交付物 | 预估工时 |
|------|------|--------|----------|
| 阶段 1 | 创建基础设施 | `error_codes.py` + `errorHandler.ts` | 0.5 天 |
| 阶段 2 | 优化前端拦截器 | `api/index.ts` 改造完成 | 0.5 天 |
| 阶段 3 | 修复高优先级不一致 | `webhooks.py` 错误码统一 | 0.25 天 |
| 阶段 4 | 后端错误码常量迁移 | 各路由文件使用 `ErrorCodes` 常量 | 1 天 |
| 阶段 5 | 前端页面逐步采用新错误处理 | 各页面采用 `handleError()` | 1 天 |
| 阶段 6 | 测试验证 | 运行测试套件，确认无回归 | 0.5 天 |

**总预估工时**: 3.75 天

### 4.2 后端迁移优先级

| 优先级 | 文件 | 原因 |
|--------|------|------|
| P0 | `webhooks.py` | 错误码格式不一致 |
| P0 | `middleware/auth.py` | 认证核心，debug 输出需清理 |
| P1 | `auth.py` | 登录/Token 相关，高频使用 |
| P1 | `users.py` | 用户管理，错误类型多 |
| P2 | `customers.py` | 客户管理 |
| P2 | `billing.py` | 结算管理 |
| P3 | 其他路由文件 | 按需迁移 |

### 4.3 前端迁移优先级

| 优先级 | 页面 | 原因 |
|--------|------|------|
| P0 | `Dashboard.vue` | 首页，用户入口 |
| P1 | `Login.vue` | 登录页，认证相关 |
| P1 | `customers/Index.vue` | 客户列表，高频使用 |
| P2 | `billing/Invoices.vue` | 结算单管理 |
| P2 | `users/Index.vue` | 用户管理 |
| P3 | 其他页面 | 按需迁移 |

### 4.4 向后兼容策略

**新旧代码并存**:

```python
# 后端过渡期：新旧错误码并存
# 新代码使用常量
return json({"code": ErrorCodes.UNAUTHORIZED, "message": "未认证"}, status=401)

# 旧代码保持不变（后续逐步迁移）
return json({"code": 40101, "message": "未认证"}, status=401)
```

```typescript
// 前端过渡期：页面可选择是否采用新错误处理
// 新代码
import { handleError } from '@/utils/errorHandler'
try {
  await api()
} catch (error) {
  handleError(error)
}

// 旧代码保持不变
try {
  await api()
} catch (error) {
  Message.error((error as Error).message || '操作失败')
}
```

---

## 5. 测试策略

### 5.1 单元测试

| 测试内容 | 测试文件 |
|----------|----------|
| 错误码常量定义 | `backend/tests/unit/test_error_codes.py` |
| 前端错误分类函数 | `frontend/src/utils/__tests__/errorHandler.test.ts` |
| 前端拦截器错误处理 | `frontend/src/api/__tests__/interceptor.test.ts` |

### 5.2 集成测试场景

| 测试场景 | 验证点 |
|----------|--------|
| 401 错误 → token 刷新 | 刷新成功重试，刷新失败跳转登录 |
| 403 错误 → 权限不足提示 | 显示友好提示 |
| 404 错误 → 资源不存在 | 显示友好提示 |
| 500 错误 → 系统繁忙 | 显示友好提示 |
| 网络错误 → 连接失败 | 显示网络错误提示 |

---

## 6. 成功标准

| 标准 | 验证方式 |
|------|----------|
| 所有后端错误码统一为 5 位格式 | 代码审查，无 `code: 400/403/500` 形式 |
| 前端 `errorHandler.ts` 创建 | 文件存在并包含核心函数 |
| 前端拦截器改造完成 | 错误对象包含 `category` 字段 |
| `webhooks.py` 错误码已修复 | 代码审查确认 |
| 核心页面采用新错误处理 | Dashboard、Login、客户列表页完成迁移 |
| 测试通过 | `make test-parallel` 全部通过 |
| 无回归 | 手动测试核心流程正常工作 |

---

## 7. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 大规模修改导致 CI 失败 | 高 | 分阶段实施，每阶段独立验证 |
| 错误提示改变影响用户习惯 | 低 | 渐进式迁移，保持核心提示语义一致 |
| 新引入的 bug | 中 | 每个阶段编写单元测试 |

---

## 8. 附录

### 8.1 现有错误码统计

当前后端使用的错误码分布（来自代码审查）：

| 错误码范围 | 含义 | 使用频率 |
|------------|------|----------|
| `40001-40099` | 客户端参数错误 | 高 |
| `40101-40199` | 认证相关错误 | 高 |
| `40301-40399` | 权限相关错误 | 中 |
| `40401-40499` | 资源不存在 | 中 |
| `50000-50099` | 服务器内部错误 | 低 |

### 8.2 相关文件清单

**后端**:
- `backend/app/middleware/auth.py`
- `backend/app/routes/auth.py`
- `backend/app/routes/users.py`
- `backend/app/routes/customers.py`
- `backend/app/routes/billing.py`
- `backend/app/routes/webhooks.py`

**前端**:
- `frontend/src/api/index.ts`
- `frontend/src/views/Dashboard.vue`
- `frontend/src/views/Login.vue`
- `frontend/src/views/customers/Index.vue`

---

*文档结束*
