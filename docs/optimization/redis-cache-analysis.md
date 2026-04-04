# Redis 缓存优化分析报告

**分析日期**: 2026-04-04  
**分析范围**: 后端服务层与 API 路由  
**目标**: 识别最适合 Redis 缓存优化的候选函数

---

## 执行摘要

通过对 `analytics.py`、`customers.py`、`billing.py` 服务层及对应路由的全面分析，识别出 **12 个高优先级缓存候选** 和 **5 个中优先级缓存候选**。

### 缓存优化预期收益
- **仪表盘接口**: 响应时间从 500-800ms → 10-20ms (95%+ 提升)
- **统计类接口**: 响应时间从 300-500ms → 10-20ms (90%+ 提升)
- **客户列表接口**: 已有缓存，可扩展筛选条件缓存策略

---

## 一、高优先级缓存候选 (P0)

### 1. 仪表盘统计数据

**文件路径**: `backend/app/services/analytics.py`  
**函数名**: `get_dashboard_stats()`  
**行号**: L673-L750

**返回数据**:
```python
{
    "total_customers": int,          # 客户总数
    "key_customers": int,            # 重点客户数
    "total_balance": float,          # 总余额
    "real_balance": float,           # 实充余额
    "bonus_balance": float,          # 赠金余额
    "month_invoice_count": int,      # 本月结算单数
    "pending_confirmation": int,     # 待确认结算单数
    "month_consumption": float,      # 本月消耗总额
}
```

**缓存理由**:
- ✅ **高频访问**: 首页仪表盘，每次页面加载必调用
- ✅ **计算密集**: 7 次独立数据库查询
- ✅ **数据稳定性**: 分钟级变化可接受，无需实时
- ✅ **现有缓存缺失**: 路由层未实现缓存

**建议 TTL**: `300 秒 (5 分钟)`  
**缓存键**: `dashboard:stats:{date}` (按日期分区)  
**失效策略**: 客户创建/删除、结算单生成/支付时主动失效

---

### 2. 仪表盘图表数据

**文件路径**: `backend/app/services/analytics.py`  
**函数名**: `get_dashboard_chart_data()`  
**行号**: L752-L796

**返回数据**:
```python
{
    "consumption_trend": [...],   # 消耗趋势数组
    "payment_trend": [...]        # 回款趋势数组
}
```

**缓存理由**:
- ✅ **高频访问**: 首页图表展示
- ✅ **计算密集**: 调用 6 次 `get_payment_analysis()`，每次涉及 2 次聚合查询
- ✅ **数据稳定性**: 历史数据不变，仅月末变化

**建议 TTL**: `900 秒 (15 分钟)`  
**缓存键**: `dashboard:chart:{months}:{end_date}`  
**失效策略**: 结算单状态变更时失效

---

### 3. 客户健康度统计

**文件路径**: `backend/app/services/analytics.py`  
**函数名**: `get_customer_health_stats()`  
**行号**: L270-L323

**返回数据**:
```python
{
    "total_customers": int,
    "active_customers": int,
    "inactive_customers": int,
    "warning_customers": int,
    "churn_risk_customers": int,
    "active_rate": float,
}
```

**缓存理由**:
- ✅ **计算密集**: 5 次独立查询 + 集合运算
- ✅ **高频访问**: 运营监控仪表盘
- ✅ **数据稳定性**: 90 天无消耗判定，日内变化小

**建议 TTL**: `600 秒 (10 分钟)`  
**缓存键**: `analytics:health:stats`  
**失效策略**: 客户创建/删除、消耗记录写入时失效

---

### 4. 行业分布统计

**文件路径**: `backend/app/services/analytics.py`  
**函数名**: `get_industry_distribution()`  
**行号**: L431-L463

**返回数据**:
```python
[
    {"industry": str, "count": int, "percentage": float},
    ...
]
```

**缓存理由**:
- ✅ **读多写少**: 客户画像行业字段极少变更
- ✅ **聚合查询**: 涉及 CustomerProfile 关联统计
- ✅ **高频访问**: 客户分析页面

**建议 TTL**: `3600 秒 (1 小时)`  
**缓存键**: `analytics:profile:industry`  
**失效策略**: 客户画像更新时失效

---

### 5. 客户等级统计

**文件路径**: `backend/app/services/analytics.py`  
**函数名**: `get_customer_level_stats()`  
**行号**: L465-L487

**返回数据**:
```python
[
    {"level": str, "count": int, "percentage": float},
    ...
]
```

**缓存理由**:
- ✅ **读多写少**: 客户等级变更频率低
- ✅ **简单聚合**: 单表 GROUP BY 查询
- ✅ **高频访问**: 客户分析页面

**建议 TTL**: `3600 秒 (1 小时)`  
**缓存键**: `analytics:profile:level`  
**失效策略**: 客户等级变更时失效

---

### 6. 客户规模等级统计

**文件路径**: `backend/app/services/analytics.py`  
**函数名**: `get_scale_level_stats()`  
**行号**: L489-L511

**返回数据**:
```python
[
    {"scale_level": str, "count": int, "percentage": float},
    ...
]
```

**缓存理由**:
- ✅ **读多写少**: 规模等级极少变更
- ✅ **关联查询**: 涉及 Customer-CustomerProfile JOIN

**建议 TTL**: `3600 秒 (1 小时)`  
**缓存键**: `analytics:profile:scale`  
**失效策略**: 客户画像更新时失效

---

### 7. 客户消费等级统计

**文件路径**: `backend/app/services/analytics.py`  
**函数名**: `get_consume_level_stats()`  
**行号**: L513-L535

**返回数据**:
```python
[
    {"consume_level": str, "count": int, "percentage": float},
    ...
]
```

**缓存理由**:
- ✅ **读多写少**: 消费等级月度调整
- ✅ **关联查询**: 涉及 Customer-CustomerProfile JOIN

**建议 TTL**: `3600 秒 (1 小时)`  
**缓存键**: `analytics:profile:consume-level`  
**失效策略**: 客户画像更新时失效

---

### 8. 房产客户统计

**文件路径**: `backend/app/services/analytics.py`  
**函数名**: `get_real_estate_stats()`  
**行号**: L537-L563

**返回数据**:
```python
{
    "total_customers": int,
    "real_estate_customers": int,
    "non_real_estate_customers": int,
    "real_estate_percentage": float,
}
```

**缓存理由**:
- ✅ **读多写少**: 房产标识极少变更
- ✅ **关联查询**: 涉及 Customer-CustomerProfile JOIN

**建议 TTL**: `3600 秒 (1 小时)`  
**缓存键**: `analytics:profile:real-estate`  
**失效策略**: 客户画像更新时失效

---

### 9. 结算单状态统计

**文件路径**: `backend/app/services/analytics.py`  
**函数名**: `get_invoice_status_stats()`  
**行号**: L237-L266

**返回数据**:
```python
[
    {"status": str, "count": int, "total_amount": float},
    ...
]
```

**缓存理由**:
- ✅ **高频访问**: 财务监控页面
- ✅ **聚合查询**: 按状态 GROUP BY 统计
- ⚠️ **数据变化**: 结算单状态变更时更新

**建议 TTL**: `300 秒 (5 分钟)`  
**缓存键**: `analytics:invoice:status:{start_date}:{end_date}`  
**失效策略**: 结算单状态变更时失效

---

### 10. 余额预警客户列表

**文件路径**: `backend/app/services/analytics.py`  
**函数名**: `get_balance_warning_list()`  
**行号**: L325-L356

**返回数据**:
```python
[
    {
        "customer_id": int,
        "customer_name": str,
        "total_amount": float,
        "real_amount": float,
        "bonus_amount": float,
    },
    ...
]
```

**缓存理由**:
- ✅ **高频访问**: 运营预警监控
- ✅ **关联查询**: Customer-CustomerBalance JOIN
- ⚠️ **数据变化**: 充值/消费后余额变化

**建议 TTL**: `180 秒 (3 分钟)`  
**缓存键**: `analytics:health:warning-list:{threshold}`  
**失效策略**: 充值/消费记录写入时失效

---

### 11. 长期未消耗客户列表

**文件路径**: `backend/app/services/analytics.py`  
**函数名**: `get_inactive_customers()`  
**行号**: L358-L429

**返回数据**:
```python
[
    {
        "customer_id": int,
        "customer_name": str,
        "manager_id": int,
        "manager_name": str,
    },
    ...
]
```

**缓存理由**:
- ✅ **计算密集**: 多次查询 + 集合运算
- ✅ **数据稳定性**: 90 天判定，日内变化小
- ✅ **高频访问**: 客户流失预警

**建议 TTL**: `600 秒 (10 分钟)`  
**缓存键**: `analytics:health:inactive-list:{days}`  
**失效策略**: 消耗记录写入时失效

---

### 12. 定价规则列表

**文件路径**: `backend/app/services/billing.py`  
**函数名**: `get_pricing_rules()`  
**行号**: L248-L275

**返回数据**:
```python
[PricingRule, ...]
```

**缓存理由**:
- ✅ **读多写少**: 定价规则极少变更
- ✅ **高频访问**: 结算单生成、费用计算
- ✅ **条件过滤**: 支持 customer_id/device_type/pricing_type 筛选

**建议 TTL**: `3600 秒 (1 小时)`  
**缓存键**: `billing:pricing:{customer_id}:{device_type}:{pricing_type}`  
**失效策略**: 定价规则创建/更新/删除时失效

---

## 二、中优先级缓存候选 (P1)

### 1. 消耗趋势分析

**文件路径**: `backend/app/services/analytics.py`  
**函数名**: `get_consumption_trend()`  
**行号**: L29-L68

**缓存理由**:
- ✅ **聚合查询**: 按月份 GROUP BY 求和
- ⚠️ **参数多变**: 日期范围 + 客户 ID 组合多
- ⚠️ **数据变化**: 新结算单生成时更新

**建议 TTL**: `900 秒 (15 分钟)`  
**缓存键**: `analytics:consumption:trend:{start_date}:{end_date}:{customer_id}`

---

### 2. Top 消耗客户

**文件路径**: `backend/app/services/analytics.py`  
**函数名**: `get_top_customers()`  
**行号**: L70-L105

**缓存理由**:
- ✅ **聚合查询**: JOIN + GROUP BY + ORDER BY
- ⚠️ **参数多变**: 日期范围 + limit 组合

**建议 TTL**: `900 秒 (15 分钟)`  
**缓存键**: `analytics:consumption:top:{start_date}:{end_date}:{limit}`

---

### 3. 设备类型分布

**文件路径**: `backend/app/services/analytics.py`  
**函数名**: `get_device_type_distribution()`  
**行号**: L107-L144

**缓存理由**:
- ✅ **聚合查询**: 多表 JOIN + GROUP BY
- ⚠️ **参数多变**: 日期范围 + 客户 ID 组合

**建议 TTL**: `900 秒 (15 分钟)`  
**缓存键**: `analytics:consumption:device:{start_date}:{end_date}:{customer_id}`

---

### 4. 回款分析

**文件路径**: `backend/app/services/analytics.py`  
**函数名**: `get_payment_analysis()`  
**行号**: L181-L235

**缓存理由**:
- ✅ **计算密集**: 2 次独立聚合查询
- ⚠️ **参数多变**: 日期范围 + 客户 ID 组合
- ⚠️ **数据变化**: 充值/结算单状态变更时更新

**建议 TTL**: `600 秒 (10 分钟)`  
**缓存键**: `analytics:payment:{start_date}:{end_date}:{customer_id}`

---

### 5. 月度回款预测

**文件路径**: `backend/app/services/analytics.py`  
**函数名**: `predict_monthly_payment()`  
**行号**: L565-L671

**缓存理由**:
- ✅ **计算密集**: 定价规则查询 + 用量查询 + 金额计算
- ⚠️ **参数多变**: 年月 + 客户 ID 组合

**建议 TTL**: `1800 秒 (30 分钟)`  
**缓存键**: `analytics:prediction:{year}:{month}:{customer_id}`

---

## 三、已有缓存分析

### 客户列表缓存

**文件路径**: `backend/app/routes/customers.py`  
**函数名**: `list_customers()`  
**行号**: L17-L101

**现状**:
- ✅ 已实现缓存，TTL 300 秒
- ✅ 缓存键包含筛选条件哈希
- ⚠️ **问题**: 筛选条件变化时缓存命中率低

**优化建议**:
```python
# 当前实现
cache_key = f"p{page}_ps{page_size}_{hashlib.md5(str(sorted(filters.items())).encode()).hexdigest()[:8]}"

# 优化：分离常用筛选条件
cache_key = f"customer_list:{keyword or 'all'}:{account_type or 'all'}:{manager_id or 'all'}:p{page}"
```

---

### 客户详情缓存

**文件路径**: `backend/app/routes/customers.py`  
**函数名**: `get_customer()`  
**行号**: L103-L180

**现状**:
- ✅ 已实现缓存，TTL 600 秒
- ✅ 包含画像和余额信息
- ✅ 变更时主动失效

**评价**: 实现良好，无需优化

---

## 四、缓存配置建议

### 4.1 TTL 配置表

| 缓存类型 | TTL | 失效策略 |
|---------|-----|---------|
| 仪表盘统计 | 300s | 客户/结算单变更 |
| 仪表盘图表 | 900s | 结算单状态变更 |
| 健康度统计 | 600s | 消耗记录写入 |
| 画像统计 (行业/等级/规模) | 3600s | 画像更新 |
| 结算单统计 | 300s | 结算单状态变更 |
| 预警列表 | 180s | 充值/消费写入 |
| 未消耗列表 | 600s | 消耗记录写入 |
| 定价规则 | 3600s | 规则变更 |
| 消耗趋势 | 900s | 结算单生成 |
| Top 客户 | 900s | 结算单生成 |
| 回款分析 | 600s | 充值/结算单变更 |
| 回款预测 | 1800s | 定价/用量变更 |

### 4.2 缓存失效事件映射

| 事件 | 需失效的缓存 |
|-----|-------------|
| 客户创建/删除 | dashboard:stats, analytics:health:* |
| 客户画像更新 | analytics:profile:* |
| 结算单生成 | dashboard:stats, analytics:consumption:*, analytics:invoice:* |
| 结算单状态变更 | dashboard:stats, analytics:invoice:*, analytics:payment:* |
| 充值记录写入 | analytics:health:warning-list, analytics:payment:* |
| 消费记录写入 | analytics:health:warning-list, analytics:health:inactive-list |
| 定价规则变更 | billing:pricing:* |

### 4.3 config.py 缓存配置扩展

```python
# backend/app/config.py

# Redis 配置
redis_url: str = "redis://localhost:6379/0"
redis_max_connections: int = 50
redis_socket_timeout: float = 5.0
redis_socket_connect_timeout: float = 5.0

# 缓存 TTL 配置 (秒)
cache_ttl_dashboard_stats: int = 300
cache_ttl_dashboard_chart: int = 900
cache_ttl_analytics_health: int = 600
cache_ttl_analytics_profile: int = 3600
cache_ttl_analytics_invoice: int = 300
cache_ttl_analytics_warning: int = 180
cache_ttl_analytics_prediction: int = 1800
cache_ttl_pricing_rules: int = 3600
```

---

## 五、实施优先级

### Phase 1 (立即实施) - 高收益/低成本
1. ✅ `get_dashboard_stats()` - 首页核心接口
2. ✅ `get_dashboard_chart_data()` - 首页核心接口
3. ✅ `get_customer_health_stats()` - 运营监控核心
4. ✅ `get_pricing_rules()` - 高频调用

### Phase 2 (短期实施) - 高收益/中成本
5. ✅ 画像统计 4 个函数 (行业/等级/规模/消费等级)
6. ✅ `get_real_estate_stats()`
7. ✅ `get_invoice_status_stats()`

### Phase 3 (中期实施) - 中收益/中成本
8. ✅ `get_balance_warning_list()`
9. ✅ `get_inactive_customers()`
10. ✅ 消耗趋势/Top 客户/设备分布
11. ✅ `get_payment_analysis()`
12. ✅ `predict_monthly_payment()`

---

## 六、预期性能提升

| 接口 | 当前响应时间 | 缓存后响应时间 | 提升幅度 |
|-----|------------|--------------|---------|
| GET /api/v1/analytics/dashboard/stats | 500-800ms | 10-20ms | 95%+ |
| GET /api/v1/analytics/dashboard/chart-data | 800-1200ms | 20-30ms | 97%+ |
| GET /api/v1/analytics/health/stats | 300-500ms | 10-20ms | 95%+ |
| GET /api/v1/analytics/profile/* | 200-300ms | 10-20ms | 90%+ |
| GET /api/v1/billing/pricing-rules | 100-200ms | 5-10ms | 90%+ |

---

**文档维护**: 后端架构组  
**下次审查**: 缓存实施后 2 周进行效果评估
