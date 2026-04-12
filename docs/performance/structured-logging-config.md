# 结构化日志配置方案

**项目**: 客户运营中台 (customer_platform_vk)  
**创建日期**: 2026-04-04  
**状态**: 待实施

---

## 📋 概述

结构化日志使用 JSON 格式记录日志，便于日志聚合系统 (如 ELK、Splunk) 解析和查询。

### 当前状态

项目已使用 `structlog` 库，但配置需要完善以支持生产环境需求。

### 改进目标

- ✅ **统一日志格式**: JSON 结构化输出
- ✅ **请求追踪**: 每个请求唯一 ID 贯穿全链路
- ✅ **用户上下文**: 自动附加用户信息到日志
- ✅ **敏感数据过滤**: 自动脱敏密码、密钥等
- ✅ **日志分级**: 开发/生产环境不同输出级别
- ✅ **性能日志**: 记录慢查询和 API 响应时间

---

## 🚀 配置方案

### 1. 日志配置模块

**文件**: `backend/app/logging_config.py`

```python
"""
结构化日志配置
"""
import logging
import sys
import json
from typing import Any, Dict

import structlog
from structlog.types import EventDict, WrappedLogger

from .config import settings


def drop_color_message_key(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """
    移除 color_message 键 (用于 Python 日志格式化)
    """
    event_dict.pop("color_message", None)
    return event_dict


def filter_sensitive_data(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """
    过滤敏感数据
    """
    sensitive_fields = [
        "password", "secret", "token", "api_key", "access_token",
        "refresh_token", "private_key", "encryption_key", "jwt_secret",
        "webhook_secret", "credit_card", "bank_account", "id_card",
    ]
    
    # 检查 event_dict 中的敏感字段
    for field in sensitive_fields:
        if field in event_dict:
            event_dict[field] = "***REDACTED***"
    
    # 检查嵌套数据
    if "data" in event_dict and isinstance(event_dict["data"], dict):
        for field in sensitive_fields:
            if field in event_dict["data"]:
                event_dict["data"][field] = "***REDACTED***"
    
    return event_dict


def setup_logging() -> None:
    """
    配置结构化日志
    """
    # 确定日志级别
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    
    # 开发环境：控制台输出，带颜色
    # 生产环境：JSON 格式，便于日志系统解析
    if settings.APP_ENV == "production":
        # 生产环境配置
        structlog.configure(
            processors=[
                # 添加时间戳
                structlog.processors.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                
                # 添加请求 ID 和上下文
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                
                # 过滤敏感数据
                filter_sensitive_data,
                
                # 移除颜色相关键
                drop_color_message_key,
                
                # 输出 JSON
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(log_level),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(sys.stdout),
            cache_logger_on_first_use=True,
        )
    else:
        # 开发环境配置 (带颜色的控制台输出)
        structlog.configure(
            processors=[
                structlog.processors.add_log_level,
                structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                filter_sensitive_data,
                drop_color_message_key,
                structlog.dev.ConsoleRenderer(colors=True),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(log_level),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(sys.stdout),
            cache_logger_on_first_use=False,
        )


def get_logger(name: str = __name__) -> structlog.BoundLogger:
    """
    获取结构化日志记录器
    
    Usage:
        logger = get_logger(__name__)
        logger.info("用户登录", user_id=123, ip="192.168.1.1")
    """
    return structlog.get_logger(name)
```

### 2. 请求日志中间件

**文件**: `backend/app/middleware/request_logging.py`

```python
"""
请求日志中间件
记录每个请求的详细信息，包括响应时间、状态码等
"""
import time
import uuid
from sanic import Request, Sanic
from sanic.response import HTTPResponse
from typing import Callable, Awaitable

from ..logging_config import get_logger

logger = get_logger(__name__)


async def request_logging_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[HTTPResponse]],
) -> HTTPResponse:
    """
    请求日志中间件
    
    功能:
    1. 生成唯一请求 ID
    2. 记录请求开始时间
    3. 记录请求详细信息
    4. 记录响应时间和状态码
    """
    # 生成请求 ID
    request_id = str(uuid.uuid4())
    request.ctx.request_id = request_id
    
    # 获取用户信息 (如果已认证)
    user_id = None
    user_email = None
    
    # 尝试从认证中间件获取用户信息
    if hasattr(request.ctx, "user"):
        user_id = getattr(request.ctx.user, "id", None)
        user_email = getattr(request.ctx.user, "email", None)
    
    # 记录请求开始
    start_time = time.time()
    
    logger.info(
        "请求开始",
        request_id=request_id,
        method=request.method,
        path=request.path,
        query=dict(request.args),
        remote_addr=request.remote_addr,
        user_agent=request.headers.get("user-agent", "unknown"),
        user_id=user_id,
        user_email=user_email,
    )
    
    try:
        # 处理请求
        response = await call_next(request)
        
        # 计算响应时间
        duration_ms = (time.time() - start_time) * 1000
        
        # 记录响应
        log_level = logging.INFO
        if response.status >= 500:
            log_level = logging.ERROR
        elif response.status >= 400:
            log_level = logging.WARNING
        
        logger.log(
            log_level,
            "请求完成",
            request_id=request_id,
            method=request.method,
            path=request.path,
            status=response.status,
            duration_ms=round(duration_ms, 2),
            user_id=user_id,
        )
        
        # 慢请求告警 (> 2000ms)
        if duration_ms > 2000:
            logger.warning(
                "慢请求检测",
                request_id=request_id,
                path=request.path,
                duration_ms=round(duration_ms, 2),
                threshold_ms=2000,
            )
        
        return response
        
    except Exception as e:
        # 记录异常
        duration_ms = (time.time() - start_time) * 1000
        
        logger.error(
            "请求异常",
            request_id=request_id,
            method=request.method,
            path=request.path,
            error=str(e),
            duration_ms=round(duration_ms, 2),
            user_id=user_id,
            exc_info=True,
        )
        raise
```

### 3. 数据库查询日志

**文件**: `backend/app/middleware/db_logging.py`

```python
"""
数据库查询日志中间件
记录慢查询和 SQL 执行统计
"""
import time
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any

from ..logging_config import get_logger

logger = get_logger(__name__)

# 慢查询阈值 (毫秒)
SLOW_QUERY_THRESHOLD = 500


def setup_db_logging(engine):
    """
    配置数据库查询日志
    
    Args:
        engine: SQLAlchemy 引擎
    """
    
    @event.listens_for(engine, "before_cursor_execute")
    def receive_before_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        """记录 SQL 执行开始"""
        conn.info.setdefault("query_start_time", []).append(time.time())
    
    @event.listens_for(engine, "after_cursor_execute")
    def receive_after_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        """记录 SQL 执行完成"""
        total = time.time() - conn.info["query_start_time"].pop(-1)
        duration_ms = total * 1000
        
        # 慢查询日志
        if duration_ms > SLOW_QUERY_THRESHOLD:
            logger.warning(
                "慢查询检测",
                duration_ms=round(duration_ms, 2),
                threshold_ms=SLOW_QUERY_THRESHOLD,
                statement=statement[:500],  # 限制长度
                parameters_count=len(parameters) if parameters else 0,
            )
        else:
            logger.debug(
                "SQL 查询",
                duration_ms=round(duration_ms, 2),
                statement=statement[:200],
            )
```

### 4. 审计日志模块

**文件**: `backend/app/services/audit_logger.py`

```python
"""
审计日志服务
记录关键业务操作，用于合规和追溯
"""
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert

from ..logging_config import get_logger

logger = get_logger(__name__)


class AuditLogger:
    """审计日志记录器"""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
    
    async def log_action(
        self,
        action: str,
        resource_type: str,
        resource_id: int,
        user_id: int,
        changes: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """
        记录审计日志
        
        Args:
            action: 操作类型 (create/update/delete/approve/reject)
            resource_type: 资源类型 (customer/invoice/balance)
            resource_id: 资源 ID
            user_id: 操作用户 ID
            changes: 变更详情 (before/after)
            ip_address: 操作 IP
            user_agent: 用户代理
        """
        audit_data = {
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "user_id": user_id,
            "changes": changes or {},
            "ip_address": ip_address,
            "user_agent": user_agent,
            "created_at": datetime.utcnow(),
        }
        
        # 记录到数据库
        await self.db.execute(
            insert("audit_logs"),  # 需要定义 audit_logs 表
            values=audit_data,
        )
        
        # 同时记录到日志系统
        logger.info(
            "审计日志",
            audit_action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            changes=changes,
        )
    
    async def log_price_change(
        self,
        customer_id: int,
        old_price: float,
        new_price: float,
        user_id: int,
    ) -> None:
        """记录价格变更审计"""
        await self.log_action(
            action="price_change",
            resource_type="customer",
            resource_id=customer_id,
            user_id=user_id,
            changes={
                "field": "price_policy",
                "before": old_price,
                "after": new_price,
            },
        )
    
    async def log_balance_adjustment(
        self,
        customer_id: int,
        old_balance: float,
        new_balance: float,
        adjustment_amount: float,
        reason: str,
        user_id: int,
    ) -> None:
        """记录余额调整审计"""
        await self.log_action(
            action="balance_adjustment",
            resource_type="balance",
            resource_id=customer_id,
            user_id=user_id,
            changes={
                "old_balance": old_balance,
                "new_balance": new_balance,
                "adjustment_amount": adjustment_amount,
                "reason": reason,
            },
        )
```

### 5. 环境变量配置

**文件**: `backend/.env.example`

```bash
# 日志配置
LOG_LEVEL=INFO  # DEBUG | INFO | WARNING | ERROR
LOG_FORMAT=json  # json | console (生产环境强制 json)
LOG_OUTPUT=stdout  # stdout | file
LOG_FILE_PATH=/var/log/customer_platform/app.log

# 慢查询阈值 (毫秒)
SLOW_QUERY_THRESHOLD=500

# 慢请求阈值 (毫秒)
SLOW_REQUEST_THRESHOLD=2000

# 审计日志配置
AUDIT_LOG_ENABLED=true
AUDIT_LOG_RETENTION_DAYS=365
```

---

## 📊 日志聚合配置

### ELK Stack 配置示例

**Logstash 配置**: `deploy/monitoring/logstash.conf`

```conf
input {
  tcp {
    port => 5000
    codec => json_lines
  }
}

filter {
  # 解析时间戳
  date {
    match => ["timestamp", "ISO8601"]
    target => "@timestamp"
  }
  
  # 添加环境标签
  mutate {
    add_field => { "environment" => "production" }
    add_field => { "service" => "customer-platform" }
  }
  
  # 过滤敏感数据
  mutate {
    gsub => ["message", "password.*?(?=,|$)", "password=***REDACTED***"]
  }
}

output {
  elasticsearch {
    hosts => ["elasticsearch:9200"]
    index => "customer-platform-%{+YYYY.MM.dd}"
  }
}
```

### Grafana Loki 配置示例

**Promtail 配置**: `deploy/monitoring/promtail.yml`

```yaml
server:
  http_listen_port: 9080

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: customer-platform
    static_configs:
      - targets:
          - localhost
        labels:
          job: customer-platform
          level: production
          __path__: /var/log/customer_platform/*.log
```

---

## 🔍 日志查询示例

### Kibana 查询

```kibana
# 查找所有 500 错误
status: 500

# 查找慢请求
duration_ms:>2000

# 查找特定用户的操作
user_id: 123

# 查找特定 API 的请求
path: "/api/v1/billing/*"

# 查找审计日志
audit_action: *
```

### SQL 审计日志查询

```sql
-- 查询某用户的所有操作
SELECT * FROM audit_logs 
WHERE user_id = 123 
ORDER BY created_at DESC 
LIMIT 100;

-- 查询价格变更历史
SELECT * FROM audit_logs 
WHERE action = 'price_change' 
  AND resource_type = 'customer'
ORDER BY created_at DESC;

-- 查询某时间段内的余额调整
SELECT * FROM audit_logs 
WHERE action = 'balance_adjustment'
  AND created_at BETWEEN '2026-04-01' AND '2026-04-30';
```

---

## 🚀 部署检查清单

- [ ] 安装 structlog 依赖
- [ ] 配置日志模块
- [ ] 添加请求日志中间件
- [ ] 配置数据库查询日志
- [ ] 实现审计日志服务
- [ ] 配置环境变量
- [ ] 测试日志输出格式
- [ ] 配置日志聚合系统
- [ ] 设置日志告警规则
- [ ] 团队培训和文档

---

## 📚 参考资源

- [structlog 官方文档](https://www.structlog.org/)
- [Python 日志最佳实践](https://docs.python.org/3/howto/logging.html)
- [ELK Stack 文档](https://www.elastic.co/guide/index.html)
- [Grafana Loki 文档](https://grafana.com/docs/loki/latest/)

---

**预计实施时间**: 1 天  
**负责人**: 后端开发团队  
**审核状态**: 待审核
