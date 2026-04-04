# Sentry 错误追踪集成方案

**项目**: 客户运营中台 (customer_platform_vk)  
**创建日期**: 2026-04-04  
**状态**: 待实施

---

## 📋 概述

Sentry 是一个开源的错误追踪和性能监控平台，帮助开发者实时发现和修复生产环境中的问题。

### 集成收益

- ✅ **实时错误告警**: 错误发生后秒级通知
- ✅ **错误堆栈追踪**: 完整的错误上下文信息
- ✅ **性能监控**: API 响应时间、数据库查询性能
- ✅ **用户影响分析**: 错误影响的用户范围
- ✅ **版本追踪**: 按版本聚合错误，追踪修复效果

---

## 🚀 后端集成 (Python + Sanic)

### 1. 安装依赖

```bash
cd backend
source .venv/bin/activate

pip install sentry-sdk[sanic]
pip freeze >> requirements.txt
```

### 2. 配置环境变量

```bash
# .env 或 .env.example 添加
SENTRY_DSN=https://your-key@o0.ingest.sentry.io/0
SENTRY_ENVIRONMENT=development  # development | staging | production
SENTRY_TRACES_SAMPLE_RATE=0.1   # 性能追踪采样率 (10%)
SENTRY_ERRORS_SAMPLE_RATE=1.0   # 错误追踪采样率 (100%)
```

### 3. 初始化 Sentry

**文件**: `backend/app/__init__.py`

```python
import sentry_sdk
from sentry_sdk.integrations.sanic import SanicIntegration
from .config import settings

def init_sentry():
    """初始化 Sentry SDK"""
    if settings.APP_ENV == "production":
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            integrations=[
                SanicIntegration(),
            ],
            # 性能监控配置
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            
            # 错误追踪配置
            sample_rate=settings.SENTRY_ERRORS_SAMPLE_RATE,
            
            # 环境配置
            environment=settings.SENTRY_ENVIRONMENT,
            
            # 发布版本追踪
            release=f"customer-platform@{settings.APP_VERSION}",
            
            # 敏感数据过滤
            before_send=before_send_handler,
        )

def before_send_handler(event, hint):
    """过滤敏感数据"""
    # 移除请求体中的敏感信息
    if 'request' in event:
        request_data = event['request']
        if 'data' in request_data:
            # 过滤密码、密钥等
            sensitive_fields = ['password', 'secret', 'token', 'api_key']
            for field in sensitive_fields:
                if field in request_data['data']:
                    request_data['data'][field] = '[FILTERED]'
    
    return event

# 在 create_app() 中调用
def create_app():
    app = Sanic("customer_platform")
    
    # 初始化 Sentry (生产环境)
    if settings.APP_ENV == "production":
        init_sentry()
    
    # ... 其他配置
    
    return app
```

### 4. 手动捕获异常

**文件**: `backend/app/middleware/exception.py`

```python
import sentry_sdk
from sanic.response import json
import logging

logger = logging.getLogger(__name__)

async def exception_middleware(request, exception):
    """全局异常中间件"""
    
    # 记录到 Sentry
    sentry_sdk.capture_exception(exception)
    
    # 记录日志
    logger.error(
        f"未处理异常 | 路径：{request.path} | 错误：{str(exception)}",
        exc_info=True,
        extra={
            "user_id": getattr(request.ctx, "user_id", None),
            "request_id": getattr(request.ctx, "request_id", None),
        }
    )
    
    # 返回友好错误
    return json(
        {
            "code": "INTERNAL_ERROR",
            "message": "服务器内部错误，请稍后重试",
            "request_id": getattr(request.ctx, "request_id", None),
        },
        status=500,
    )
```

### 5. 性能监控

**文件**: `backend/app/middleware/performance.py`

```python
import sentry_sdk
import time
from sanic.response import json

async def performance_middleware(request, call_next):
    """性能监控中间件"""
    
    # 开始事务
    transaction = sentry_sdk.start_transaction(
        name=request.path,
        op="http.server",
        sampled=True,
    )
    
    start_time = time.time()
    
    try:
        response = await call_next(request)
        
        # 记录响应状态
        transaction.set_status("ok" if response.status < 400 else "error")
        transaction.set_data("response.status", response.status)
        
        return response
        
    except Exception as e:
        transaction.set_status("internal_error")
        transaction.set_data("error", str(e))
        raise
        
    finally:
        # 记录响应时间
        duration = time.time() - start_time
        transaction.set_data("response.duration_ms", duration * 1000)
        transaction.finish()
```

---

## 🎨 前端集成 (Vue 3)

### 1. 安装依赖

```bash
cd frontend
npm install @sentry/vue @sentry/tracing
```

### 2. 配置 Sentry

**文件**: `frontend/src/main.ts`

```typescript
import { createApp } from 'vue'
import * as Sentry from '@sentry/vue'
import { BrowserTracing } from '@sentry/tracing'
import App from './App.vue'
import router from './router'

const app = createApp(App)

// Sentry 配置
if (import.meta.env.PROD) {
  Sentry.init({
    app,
    dsn: import.meta.env.VITE_SENTRY_DSN,
    integrations: [
      new BrowserTracing({
        routingInstrumentation: Sentry.vueRouterInstrumentation(router),
        tracingOrigins: ['localhost', /^\//],
      }),
    ],
    
    // 性能监控
    tracesSampleRate: 0.1,
    
    // 错误采样
    sampleRate: 1.0,
    
    // 环境配置
    environment: import.meta.env.VITE_APP_ENV,
    
    // 发布版本
    release: `customer-platform@${import.meta.env.PACKAGE_VERSION}`,
    
    // 忽略特定错误
    ignoreErrors: [
      'NetworkError',
      'Request aborted',
      /Loading chunk \d+ failed/,
    ],
    
    //  beforeSend 过滤敏感数据
    beforeSend(event, hint) {
      // 过滤用户敏感信息
      if (event.request?.data) {
        const sensitive = ['password', 'token', 'secret']
        sensitive.forEach(field => {
          if (field in event.request.data) {
            event.request.data[field] = '[FILTERED]'
          }
        })
      }
      return event
    },
    
    // 设置用户上下文
    beforeSendTransaction(event) {
      const userStore = useUserStore()
      if (userStore.user) {
        Sentry.setUser({
          id: userStore.user.id,
          username: userStore.user.username,
          email: userStore.user.email,
        })
      }
      return event
    },
  })
}

app.mount('#app')
```

### 3. 环境变量配置

**文件**: `frontend/.env.production`

```bash
VITE_SENTRY_DSN=https://your-key@o0.ingest.sentry.io/0
VITE_APP_ENV=production
VITE_SENTRY_TRACES_SAMPLE_RATE=0.1
```

---

## 📊 Sentry 仪表板配置

### 1. 创建告警规则

```yaml
# 错误率告警
- 指标：error_rate
- 条件：> 1% (5 分钟窗口)
- 通知：邮件 + Slack

# 性能告警
- 指标：p95_response_time
- 条件：> 2000ms (10 分钟窗口)
- 通知：邮件

# 错误数量告警
- 指标：count_unique(user)
- 条件：> 10 (5 分钟窗口)
- 通知：Slack 紧急频道
```

### 2. 配置 Issue 分配

```yaml
# 自动分配规则
- 错误类型：DatabaseError → 分配给后端团队
- 错误类型：ValidationError → 分配给前端团队
- 错误路径：/api/v1/billing/* → 分配给结算组
- 错误路径：/api/v1/customers/* → 分配给客户组
```

---

## 🔧 高级配置

### 1. 自定义 Breadcrumbs

```python
import sentry_sdk

def log_user_action(user_id, action, details):
    """记录用户操作到 Sentry"""
    sentry_sdk.add_breadcrumb(
        category="user_action",
        message=f"用户 {user_id} 执行 {action}",
        level="info",
        data={
            "user_id": user_id,
            "action": action,
            **details
        }
    )

# 使用示例
log_user_action(
    user_id=123,
    action="invoice_created",
    details={"invoice_id": 456, "amount": 1000}
)
```

### 2. 性能事务追踪

```python
from sentry_sdk import start_transaction

async def generate_invoice(invoice_id):
    with start_transaction(
        name="invoice_generation",
        op="task",
        sampled=True,
    ) as transaction:
        # 子事务：数据库查询
        with start_transaction(
            name="fetch_invoice_data",
            op="db.query",
            parent=transaction,
        ):
            invoice_data = await fetch_invoice(invoice_id)
        
        # 子事务：PDF 生成
        with start_transaction(
            name="generate_pdf",
            op="task.pdf",
            parent=transaction,
        ):
            pdf = await create_pdf(invoice_data)
        
        return pdf
```

### 3. 会话追踪 (Session Tracking)

```python
from sentry_sdk import configure_scope

def set_user_context(user):
    """设置用户上下文"""
    with configure_scope() as scope:
        scope.set_user({
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "role": user.role,
        })
        scope.set_tag("customer_id", user.customer_id)
        scope.set_tag("environment", settings.APP_ENV)
```

---

## 📈 监控指标

### 后端关键指标

| 指标 | 阈值 | 说明 |
|------|------|------|
| 错误率 | < 1% | 5 分钟滚动窗口 |
| P95 响应时间 | < 2000ms | API 响应时间 |
| P99 响应时间 | < 5000ms | 长尾延迟 |
| 数据库查询时间 | < 500ms | 单次查询 |
| 错误影响用户数 | < 10 | 5 分钟内 |

### 前端关键指标

| 指标 | 阈值 | 说明 |
|------|------|------|
| JS 错误率 | < 0.5% | 页面会话 |
| FCP (首屏) | < 1.5s | 首次内容绘制 |
| LCP (最大内容) | < 2.5s | 最大内容绘制 |
| CLS (布局偏移) | < 0.1 | 累积布局偏移 |

---

## 🔐 安全与隐私

### 数据过滤清单

```python
# 必须过滤的敏感字段
SENSITIVE_FIELDS = [
    # 认证信息
    'password', 'token', 'api_key', 'secret', 'access_token',
    
    # 个人信息
    'id_card', 'phone', 'email', 'address',
    
    # 财务信息
    'bank_account', 'credit_card', 'balance',
    
    # 系统信息
    'private_key', 'encryption_key', 'jwt_secret',
]
```

### GDPR 合规

1. **不记录 PII**: 避免记录个人身份信息
2. **数据保留**: 配置 Sentry 数据保留策略 (默认 90 天)
3. **用户同意**: 在隐私政策中说明错误追踪

---

## 🚀 部署检查清单

- [ ] 创建 Sentry 项目 (生产/测试环境分离)
- [ ] 获取 DSN 并配置到环境变量
- [ ] 后端 SDK 安装和初始化
- [ ] 前端 SDK 安装和初始化
- [ ] 配置告警规则
- [ ] 配置 Issue 自动分配
- [ ] 测试错误上报 (开发环境)
- [ ] 验证性能追踪
- [ ] 配置数据保留策略
- [ ] 团队培训和文档

---

## 📚 参考资源

- [Sentry Python SDK 文档](https://docs.sentry.io/platforms/python/)
- [Sentry Vue SDK 文档](https://docs.sentry.io/platforms/javascript/guides/vue/)
- [Sentry Sanic 集成](https://docs.sentry.io/platforms/python/integrations/sanic/)
- [Sentry 性能监控](https://docs.sentry.io/product/performance/)

---

**预计实施时间**: 1-2 天  
**负责人**: 后端开发团队  
**审核状态**: 待审核
