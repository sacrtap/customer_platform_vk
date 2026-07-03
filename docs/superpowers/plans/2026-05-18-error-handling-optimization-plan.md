# 接口错误处理优化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立统一的错误处理基础设施，使前端能够根据错误码类型展示差异化的用户友好提示。

**Architecture:** 分阶段实施 - 先创建后端错误码常量和前端错误处理工具，优化 HTTP 拦截器，再逐步迁移各模块使用新基础设施。

**Tech Stack:** Python 3.12, Sanic 22.12, Vue 3.4, TypeScript 5.3, Axios

---

## 文件结构规划

**新增文件**:
- `backend/app/constants/__init__.py` - 常量包初始化
- `backend/app/constants/error_codes.py` - 统一错误码定义
- `frontend/src/utils/errorHandler.ts` - 前端错误处理工具
- `backend/tests/unit/test_error_codes.py` - 错误码单元测试
- `frontend/src/utils/__tests__/errorHandler.test.ts` - 错误处理工具测试

**修改文件**:
- `frontend/src/api/index.ts` - HTTP 拦截器改造
- `backend/app/routes/webhooks.py` - 错误码格式统一
- `backend/app/middleware/auth.py` - 认证中间件错误码规范化

---

## Task 1: 创建后端错误码常量

**Files:**
- Create: `backend/app/constants/__init__.py`
- Create: `backend/app/constants/error_codes.py`
- Test: `backend/tests/unit/test_error_codes.py`

- [ ] **Step 1: 创建常量包初始化文件**

创建 `backend/app/constants/__init__.py`:

```python
"""常量包"""

from .error_codes import ErrorCodes

__all__ = ["ErrorCodes"]
```

- [ ] **Step 2: 创建错误码常量定义文件**

创建 `backend/app/constants/error_codes.py`:

```python
"""统一错误码定义

错误码格式: XXXXX (5 位数字)
- 第 1 位: 错误大类 (4=客户端错误, 5=服务器错误)
- 第 2-3 位: 错误小类 (00=通用, 01=参数, 02=格式, 03=认证, 04=权限, 05=资源不存在)
- 第 4-5 位: 具体错误序号

示例:
- 40001: 通用参数错误
- 40101: Token 缺失/未认证
- 40102: Token 无效或已过期
- 40301: 权限不足
- 40401: 资源不存在
- 50000: 服务器内部错误
"""


class ErrorCodes:
    # 成功
    SUCCESS = 0

    # 400xx - 客户端请求错误
    BAD_REQUEST = 40001  # 通用参数错误
    INVALID_FORMAT = 40002  # 格式错误 (邮箱、手机号等)
    INVALID_FILE = 40003  # 文件格式错误
    MISSING_PARAMETER = 40004  # 缺少必要参数

    # 401xx - 认证错误
    UNAUTHORIZED = 40101  # 未认证/缺少 Token
    TOKEN_INVALID = 40102  # Token 无效或已过期
    TOKEN_BLACKLISTED = 40103  # Token 已失效

    # 403xx - 权限错误
    FORBIDDEN = 40301  # 权限不足

    # 404xx - 资源不存在
    NOT_FOUND = 40401  # 通用资源不存在

    # 500xx - 服务器内部错误
    INTERNAL_ERROR = 50000  # 通用服务器错误
    SERVICE_ERROR = 50001  # 服务处理失败
```

- [ ] **Step 3: 编写单元测试**

创建 `backend/tests/unit/test_error_codes.py`:

```python
"""错误码常量单元测试"""

import pytest

from app.constants import ErrorCodes


class TestErrorCodes:
    """错误码常量测试类"""

    def test_success_code_is_zero(self):
        """成功错误码应为 0"""
        assert ErrorCodes.SUCCESS == 0

    def test_client_error_codes_range(self):
        """客户端错误码应在 40000-40999 范围内"""
        client_codes = [
            ErrorCodes.BAD_REQUEST,
            ErrorCodes.INVALID_FORMAT,
            ErrorCodes.INVALID_FILE,
            ErrorCodes.MISSING_PARAMETER,
        ]
        for code in client_codes:
            assert 40000 <= code < 41000

    def test_auth_error_codes_range(self):
        """认证错误码应在 40100-40199 范围内"""
        auth_codes = [
            ErrorCodes.UNAUTHORIZED,
            ErrorCodes.TOKEN_INVALID,
            ErrorCodes.TOKEN_BLACKLISTED,
        ]
        for code in auth_codes:
            assert 40100 <= code < 40200

    def test_forbidden_error_code(self):
        """权限错误码应为 40301"""
        assert ErrorCodes.FORBIDDEN == 40301

    def test_not_found_error_code(self):
        """资源不存在错误码应为 40401"""
        assert ErrorCodes.NOT_FOUND == 40401

    def test_server_error_codes_range(self):
        """服务器错误码应 >= 50000"""
        server_codes = [
            ErrorCodes.INTERNAL_ERROR,
            ErrorCodes.SERVICE_ERROR,
        ]
        for code in server_codes:
            assert code >= 50000

    def test_error_codes_are_unique(self):
        """所有错误码应唯一"""
        all_codes = [
            ErrorCodes.SUCCESS,
            ErrorCodes.BAD_REQUEST,
            ErrorCodes.INVALID_FORMAT,
            ErrorCodes.INVALID_FILE,
            ErrorCodes.MISSING_PARAMETER,
            ErrorCodes.UNAUTHORIZED,
            ErrorCodes.TOKEN_INVALID,
            ErrorCodes.TOKEN_BLACKLISTED,
            ErrorCodes.FORBIDDEN,
            ErrorCodes.NOT_FOUND,
            ErrorCodes.INTERNAL_ERROR,
            ErrorCodes.SERVICE_ERROR,
        ]
        assert len(all_codes) == len(set(all_codes)), "存在重复的错误码"
```

- [ ] **Step 4: 运行测试验证**

执行命令:
```bash
cd backend && source .venv/bin/activate && pytest tests/unit/test_error_codes.py -v
```

预期输出: 所有测试通过

- [ ] **Step 5: 提交**

```bash
git add backend/app/constants/__init__.py backend/app/constants/error_codes.py backend/tests/unit/test_error_codes.py
git commit -m "feat(error): 添加统一错误码常量定义"
```

---

## Task 2: 创建前端错误处理工具

**Files:**
- Create: `frontend/src/utils/errorHandler.ts`
- Test: `frontend/src/utils/__tests__/errorHandler.test.ts`

- [ ] **Step 1: 创建错误处理工具文件**

创建 `frontend/src/utils/errorHandler.ts`:

```typescript
import { Message } from '@arco-design/web-vue'

/** 错误码分类枚举 */
export enum ErrorCategory {
  SUCCESS = 0,
  CLIENT_ERROR = 400, // 400xx - 参数错误
  AUTH_ERROR = 401, // 401xx - 认证错误
  FORBIDDEN_ERROR = 403, // 403xx - 权限不足
  NOT_FOUND_ERROR = 404, // 404xx - 资源不存在
  BUSINESS_ERROR = 422, // 422xx - 业务逻辑错误
  SERVER_ERROR = 500, // 500xx - 服务器错误
}

/** 扩展错误接口 */
export interface AppError {
  code: number | string
  message: string
  category: ErrorCategory
}

/** 根据错误码获取分类 */
export function getErrorCategory(code: number): ErrorCategory {
  if (code === 0) return ErrorCategory.SUCCESS
  if (code >= 40000 && code < 40100) return ErrorCategory.CLIENT_ERROR
  if (code >= 40100 && code < 40200) return ErrorCategory.AUTH_ERROR
  if (code >= 40300 && code < 40400) return ErrorCategory.FORBIDDEN_ERROR
  if (code >= 40400 && code < 40500) return ErrorCategory.NOT_FOUND_ERROR
  if (code >= 42200 && code < 42300) return ErrorCategory.BUSINESS_ERROR
  if (code >= 50000) return ErrorCategory.SERVER_ERROR
  return ErrorCategory.SERVER_ERROR
}

/** 获取用户友好的错误提示 */
export function getUserFriendlyMessage(
  code: number,
  backendMessage: string
): string {
  const category = getErrorCategory(code)

  // 对于参数错误和业务错误，优先使用后端返回的具体信息
  if (
    category === ErrorCategory.CLIENT_ERROR ||
    category === ErrorCategory.BUSINESS_ERROR
  ) {
    return backendMessage || '请求参数有误，请检查后重试'
  }

  // 对于系统级错误，使用统一的友好提示
  switch (category) {
    case ErrorCategory.AUTH_ERROR:
      return '登录已过期，请重新登录'
    case ErrorCategory.FORBIDDEN_ERROR:
      return '您没有执行此操作的权限'
    case ErrorCategory.NOT_FOUND_ERROR:
      return '请求的资源不存在'
    case ErrorCategory.SERVER_ERROR:
      return '系统繁忙，请稍后重试'
    default:
      return backendMessage || '操作失败'
  }
}

/** 展示错误提示 */
export function showError(message: string, duration = 3000): void {
  Message.error({
    content: message,
    duration,
  })
}

/** 统一错误处理函数 */
export function handleError(error: unknown, fallbackMessage = '操作失败'): void {
  // AppError 对象
  if (error && typeof error === 'object' && 'code' in error) {
    const appError = error as AppError

    if (typeof appError.code === 'number') {
      const friendlyMsg = getUserFriendlyMessage(appError.code, appError.message)
      showError(friendlyMsg)
      return
    }

    // 网络错误
    if (appError.code === 'NETWORK_ERROR' || appError.code === 'ECONNABORTED') {
      showError('网络连接失败，请检查网络设置')
      return
    }
  }

  // 标准 Error 对象
  if (error instanceof Error) {
    showError(error.message || fallbackMessage)
    return
  }

  // 兜底
  showError(fallbackMessage)
}
```

- [ ] **Step 2: 创建测试目录**

执行命令:
```bash
mkdir -p frontend/src/utils/__tests__
```

- [ ] **Step 3: 编写单元测试**

创建 `frontend/src/utils/__tests__/errorHandler.test.ts`:

```typescript
import { describe, it, expect, vi } from 'vitest'
import {
  getErrorCategory,
  getUserFriendlyMessage,
  ErrorCategory,
} from '../errorHandler'

describe('getErrorCategory', () => {
  it('should return SUCCESS for code 0', () => {
    expect(getErrorCategory(0)).toBe(ErrorCategory.SUCCESS)
  })

  it('should return CLIENT_ERROR for 4xxxx codes', () => {
    expect(getErrorCategory(40001)).toBe(ErrorCategory.CLIENT_ERROR)
    expect(getErrorCategory(40002)).toBe(ErrorCategory.CLIENT_ERROR)
  })

  it('should return AUTH_ERROR for 401xx codes', () => {
    expect(getErrorCategory(40101)).toBe(ErrorCategory.AUTH_ERROR)
    expect(getErrorCategory(40102)).toBe(ErrorCategory.AUTH_ERROR)
  })

  it('should return FORBIDDEN_ERROR for 403xx codes', () => {
    expect(getErrorCategory(40301)).toBe(ErrorCategory.FORBIDDEN_ERROR)
  })

  it('should return NOT_FOUND_ERROR for 404xx codes', () => {
    expect(getErrorCategory(40401)).toBe(ErrorCategory.NOT_FOUND_ERROR)
  })

  it('should return SERVER_ERROR for 5xxxx codes', () => {
    expect(getErrorCategory(50000)).toBe(ErrorCategory.SERVER_ERROR)
    expect(getErrorCategory(50001)).toBe(ErrorCategory.SERVER_ERROR)
  })

  it('should return SERVER_ERROR for unknown codes', () => {
    expect(getErrorCategory(99999)).toBe(ErrorCategory.SERVER_ERROR)
  })
})

describe('getUserFriendlyMessage', () => {
  it('should return backend message for CLIENT_ERROR', () => {
    const msg = getUserFriendlyMessage(40001, '参数不能为空')
    expect(msg).toBe('参数不能为空')
  })

  it('should return default message for CLIENT_ERROR without backend message', () => {
    const msg = getUserFriendlyMessage(40001, '')
    expect(msg).toBe('请求参数有误，请检查后重试')
  })

  it('should return fixed message for AUTH_ERROR', () => {
    const msg = getUserFriendlyMessage(40101, 'Token 无效')
    expect(msg).toBe('登录已过期，请重新登录')
  })

  it('should return fixed message for FORBIDDEN_ERROR', () => {
    const msg = getUserFriendlyMessage(40301, '权限不足')
    expect(msg).toBe('您没有执行此操作的权限')
  })

  it('should return fixed message for NOT_FOUND_ERROR', () => {
    const msg = getUserFriendlyMessage(40401, '用户不存在')
    expect(msg).toBe('请求的资源不存在')
  })

  it('should return fixed message for SERVER_ERROR', () => {
    const msg = getUserFriendlyMessage(50000, '内部错误')
    expect(msg).toBe('系统繁忙，请稍后重试')
  })
})
```

- [ ] **Step 4: 运行测试验证**

执行命令:
```bash
cd frontend && npm run test:unit -- --run errorHandler
```

如果项目没有配置 Vitest，先检查测试配置:
```bash
cd frontend && cat package.json | grep -E "vitest|jest|test"
```

根据实际情况调整测试运行命令。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/utils/errorHandler.ts frontend/src/utils/__tests__/errorHandler.test.ts
git commit -m "feat(error): 添加前端错误处理工具"
```

---

## Task 3: 优化前端 HTTP 拦截器

**Files:**
- Modify: `frontend/src/api/index.ts`

- [ ] **Step 1: 读取当前拦截器实现**

读取文件: `frontend/src/api/index.ts`

记录当前的响应拦截器实现，重点关注:
- 第 73-89 行: 成功响应处理
- 第 90-128 行: 错误响应处理

- [ ] **Step 2: 添加错误处理工具导入**

在 `frontend/src/api/index.ts` 文件顶部添加导入:

```typescript
import axios from 'axios'
import type { AxiosInstance, AxiosResponse, InternalAxiosRequestConfig } from 'axios'
import router from '@/router'
import { getErrorCategory, ErrorCategory } from '@/utils/errorHandler'  // 新增
```

- [ ] **Step 3: 修改成功响应处理**

找到原第 73-89 行的成功响应处理代码，替换为:

```typescript
// 响应拦截器
service.interceptors.response.use(
  (response: AxiosResponse) => {
    // blob 响应（文件下载等）直接返回完整 response，不做 JSON 校验
    if (response.config.responseType === 'blob') {
      return response
    }
    const res = response.data
    if (res.code !== 0) {
      // 业务错误
      const category = getErrorCategory(res.code)

      // 业务错误码 40101/40102 表示 token 无效或过期
      if (category === ErrorCategory.AUTH_ERROR) {
        return Promise.reject({
          code: res.code,
          message: res.message || '认证失败',
          category,
        })
      }

      // 其他业务错误：带上错误分类信息返回
      return Promise.reject({
        code: res.code,
        message: res.message || '操作失败',
        category,
      })
    }
    return res
  },
```

- [ ] **Step 4: 修改错误响应处理**

找到原第 90-128 行的错误响应处理代码，在 HTTP 401 处理逻辑之后，找到最后一行 `return Promise.reject(error)` 之前，添加网络错误处理:

在 `finally { isRefreshing = false }` 代码块之后，找到:

```typescript
    // 提取后端返回的错误信息
    if (error.response && error.response.data && error.response.data.message) {
      return Promise.reject(new Error(error.response.data.message))
    }
    return Promise.reject(error)
```

替换为:

```typescript
    // 网络错误或 HTTP 错误
    if (!error.response) {
      return Promise.reject({
        code: 'NETWORK_ERROR',
        message: '网络连接失败',
        category: ErrorCategory.SERVER_ERROR,
      })
    }

    // 提取后端返回的错误信息
    const backendMessage = error.response.data?.message || '请求失败'
    const code = error.response.data?.code || error.response.status * 100

    return Promise.reject({
      code,
      message: backendMessage,
      category: getErrorCategory(typeof code === 'number' ? code : 50000),
    })
```

- [ ] **Step 5: 验证修改**

执行前端类型检查:
```bash
cd frontend && npm run type-check
```

确保没有 TypeScript 错误。

- [ ] **Step 6: 提交**

```bash
git add frontend/src/api/index.ts
git commit -m "refactor(api): 优化 HTTP 拦截器，注入错误分类信息"
```

---

## Task 4: 修复 webhooks.py 错误码格式

**Files:**
- Modify: `backend/app/routes/webhooks.py`

- [ ] **Step 1: 读取 webhooks.py 文件**

读取文件: `backend/app/routes/webhooks.py`

查找所有使用原始 HTTP 状态码作为业务 code 的地方:
- `code: 400`
- `code: 403`
- `code: 404`
- `code: 500`

- [ ] **Step 2: 添加错误码常量导入**

在文件顶部添加导入:

```python
"""Webhook 路由"""

from sanic import Blueprint
from sanic.request import Request
from sanic.response import json

from ..constants import ErrorCodes  # 新增
# ... 其他导入 ...
```

- [ ] **Step 3: 替换错误码**

找到所有使用原始状态码的地方并替换:

替换模式:
```python
# 原代码
return json({"code": 400, "message": "xxx"}, status=400)
# 新代码
return json({"code": ErrorCodes.BAD_REQUEST, "message": "xxx"}, status=400)

# 原代码
return json({"code": 403, "message": "xxx"}, status=403)
# 新代码
return json({"code": ErrorCodes.FORBIDDEN, "message": "xxx"}, status=403)

# 原代码
return json({"code": 404, "message": "xxx"}, status=404)
# 新代码
return json({"code": ErrorCodes.NOT_FOUND, "message": "xxx"}, status=404)

# 原代码
return json({"code": 500, "message": "xxx"}, status=500)
# 新代码
return json({"code": ErrorCodes.INTERNAL_ERROR, "message": "xxx"}, status=500)
```

具体替换位置 (根据代码审查):
- 第 205 行: `code: 403` → `ErrorCodes.FORBIDDEN`
- 第 210 行: `code: 403` → `ErrorCodes.FORBIDDEN`
- 第 217 行: `code: 403` → `ErrorCodes.FORBIDDEN`
- 第 228 行: `code: 400` → `ErrorCodes.BAD_REQUEST`
- 第 242 行: `code: 404` → `ErrorCodes.NOT_FOUND`
- 第 251 行: `code: 400` → `ErrorCodes.BAD_REQUEST`
- 第 291 行: `code: 500` → `ErrorCodes.INTERNAL_ERROR`
- 第 327 行: `code: 403` → `ErrorCodes.FORBIDDEN`
- 第 332 行: `code: 403` → `ErrorCodes.FORBIDDEN`
- 第 338 行: `code: 403` → `ErrorCodes.FORBIDDEN`
- 第 348 行: `code: 400` → `ErrorCodes.BAD_REQUEST`
- 第 358 行: `code: 404` → `ErrorCodes.NOT_FOUND`
- 第 369 行: `code: 400` → `ErrorCodes.BAD_REQUEST`
- 第 415 行: `code: 500` → `ErrorCodes.INTERNAL_ERROR`

- [ ] **Step 4: 运行代码格式化**

```bash
cd backend && source .venv/bin/activate && ruff format app/routes/webhooks.py && ruff check app/routes/webhooks.py
```

- [ ] **Step 5: 运行测试验证**

```bash
cd backend && source .venv/bin/activate && pytest tests/ -v -k webhook --tb=short
```

确保 webhook 相关测试通过。

- [ ] **Step 6: 提交**

```bash
git add backend/app/routes/webhooks.py
git commit -m "fix(webhooks): 统一错误码为五位格式"
```

---

## Task 5: 优化认证中间件错误码

**Files:**
- Modify: `backend/app/middleware/auth.py`

- [ ] **Step 1: 读取认证中间件文件**

读取文件: `backend/app/middleware/auth.py`

- [ ] **Step 2: 添加错误码常量导入**

在文件顶部添加导入:

```python
"""认证中间件"""

from functools import wraps

from sanic import Sanic
from sanic.request import Request
from sanic.response import json
from sqlalchemy.ext.asyncio import AsyncSession

from ..constants import ErrorCodes  # 新增
from ..services import get_user_permissions
from ..services.auth import AuthService
from ..services.token_blacklist import TokenBlacklistService
```

- [ ] **Step 3: 替换错误码**

找到以下位置并替换:

第 44 行:
```python
# 原代码
return json({"code": 40101, "message": "缺少认证 Token"}, status=401)
# 新代码
return json({"code": ErrorCodes.UNAUTHORIZED, "message": "缺少认证 Token"}, status=401)
```

第 52 行:
```python
# 原代码
return json({"code": 40102, "message": f"Token 验证失败：{str(e)}"}, status=401)
# 新代码
return json({"code": ErrorCodes.TOKEN_INVALID, "message": f"Token 验证失败：{str(e)}"}, status=401)
```

第 55 行:
```python
# 原代码
return json({"code": 40102, "message": "Token 无效或已过期"}, status=401)
# 新代码
return json({"code": ErrorCodes.TOKEN_INVALID, "message": "Token 无效或已过期"}, status=401)
```

第 64 行:
```python
# 原代码
return json({"code": 40103, "message": "Token 已失效"}, status=401)
# 新代码
return json({"code": ErrorCodes.TOKEN_BLACKLISTED, "message": "Token 已失效"}, status=401)
```

第 74 行:
```python
# 原代码
return json({"code": 50000, "message": f"中间件错误：{str(e)}"}, status=500)
# 新代码
return json({"code": ErrorCodes.INTERNAL_ERROR, "message": f"中间件错误：{str(e)}"}, status=500)
```

第 96 行:
```python
# 原代码
return json({"code": 40101, "message": "未认证"}, status=401)
# 新代码
return json({"code": ErrorCodes.UNAUTHORIZED, "message": "未认证"}, status=401)
```

第 114 行:
```python
# 原代码
return json({"code": 40301, "message": "权限不足"}, status=403)
# 新代码
return json({"code": ErrorCodes.FORBIDDEN, "message": "权限不足"}, status=403)
```

第 173 行:
```python
# 原代码
return json({"code": 40101, "message": "未认证"}, status=401)
# 新代码
return json({"code": ErrorCodes.UNAUTHORIZED, "message": "未认证"}, status=401)
```

- [ ] **Step 4: 清理调试输出**

找到第 68 行的调试输出:
```python
print(f"[AUTH DEBUG] User set in request.ctx: {payload}")
```

将其删除或注释掉 (生产代码不应包含调试输出)。

同时删除第 69-73 行的异常调试输出:
```python
print(f"[AUTH DEBUG] Unexpected error in middleware: {e}")
import traceback
traceback.print_exc()
```

替换为正常的日志记录:
```python
app.logger.error(f"认证中间件异常：{e}")
```

- [ ] **Step 5: 运行代码格式化**

```bash
cd backend && source .venv/bin/activate && ruff format app/middleware/auth.py && ruff check app/middleware/auth.py
```

- [ ] **Step 6: 运行测试验证**

```bash
cd backend && source .venv/bin/activate && pytest tests/ -v -k auth --tb=short
```

- [ ] **Step 7: 提交**

```bash
git add backend/app/middleware/auth.py
git commit -m "refactor(auth): 使用错误码常量，清理调试输出"
```

---

## Task 6: 迁移 Dashboard 页面使用新错误处理

**Files:**
- Modify: `frontend/src/views/Dashboard.vue`

- [ ] **Step 1: 读取 Dashboard.vue 文件**

读取文件: `frontend/src/views/Dashboard.vue`

查找所有错误处理代码模式:
```typescript
catch (error) {
  Message.error((error as Error).message || 'xxx')
}
```

- [ ] **Step 2: 添加错误处理工具导入**

在文件的导入部分添加:

```typescript
import { Message } from '@arco-design/web-vue'
import { handleError } from '@/utils/errorHandler'  // 新增
```

- [ ] **Step 3: 替换错误处理代码**

找到第 408 行:
```typescript
// 原代码
Message.error('加载统计数据失败')

// 这个已经在 catch 块中，改为:
handleError(error)
```

找到第 512 行:
```typescript
// 原代码
Message.error('加载待办事项失败')

// 改为:
handleError(error)
```

找到第 522 行:
```typescript
// 原代码
Message.error('加载结算单失败')

// 改为:
handleError(error)
```

找到第 867 行:
```typescript
// 原代码
Message.error((error as Error)?.message || '密码修改失败')

// 改为:
handleError(error)
```

- [ ] **Step 4: 验证修改**

执行前端类型检查:
```bash
cd frontend && npm run type-check
```

- [ ] **Step 5: 提交**

```bash
git add frontend/src/views/Dashboard.vue
git commit -m "refactor(dashboard): 使用新错误处理工具"
```

---

## Task 7: 运行完整测试验证

**Files:**
- 无新文件，验证所有修改

- [ ] **Step 1: 运行后端测试**

```bash
cd backend && source .venv/bin/activate && make test-parallel
```

确保所有测试通过，覆盖率 ≥ 50%。

- [ ] **Step 2: 运行前端构建**

```bash
cd frontend && npm run build
```

确保构建成功，无 TypeScript 错误。

- [ ] **Step 3: 运行前端 lint**

```bash
cd frontend && npm run lint
```

确保无 lint 错误。

- [ ] **Step 4: 运行后端代码检查**

```bash
cd backend && source .venv/bin/activate && ruff check app/ tests/ && ruff format app/ tests/ --check
```

- [ ] **Step 5: 提交最终变更**

如果有遗漏的文件:
```bash
git add .
git commit -m "chore: 完成错误处理优化，运行完整验证"
```

---

## 自审清单

### 规范覆盖率检查

| 规范要求 | 对应任务 | 状态 |
|----------|----------|------|
| 统一后端错误码为 5 位格式 | Task 4, Task 5 | ✅ |
| 创建前端 errorHandler.ts | Task 2 | ✅ |
| 优化前端拦截器 | Task 3 | ✅ |
| 修复 webhooks.py 错误码 | Task 4 | ✅ |
| Dashboard 页面迁移 | Task 6 | ✅ |
| 测试验证 | Task 7 | ✅ |

### 占位符扫描

- [x] 无 "TBD"、"TODO"、"implement later"
- [x] 所有步骤都有具体代码
- [x] 无 "add appropriate error handling" 等模糊描述
- [x] 无 "Write tests for the above" 等无代码步骤
- [x] 无 "Similar to Task N" 引用

### 类型一致性检查

- [x] `ErrorCategory` 枚举在 Task 2 定义，Task 3、Task 6 使用一致
- [x] `AppError` 接口在 Task 2 定义，Task 3 使用
- [x] `getErrorCategory()` 函数签名一致
- [x] `handleError()` 函数签名一致

---

计划完成！
