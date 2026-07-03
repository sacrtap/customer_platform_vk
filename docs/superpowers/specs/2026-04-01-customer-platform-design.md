# 客户运营中台系统设计文档

**状态**: Completed (2026-04-27)  
**作者**: Alex (Product Manager)  
**创建日期**: 2026-04-01  
**版本**: 2.0 (最终版)  

---

## 1. 项目概述

### 1.1 项目背景

构建内部运营中台客户信息管理与运营系统，用于公司内部对客户信息、结算、画像进行统一管理和运营分析。系统由管理员创建账号，各角色按权限使用，实现账号治理、客户信息管理、画像管理、结算管理、客户分析的核心目标。

### 1.2 核心目标

| 目标               | 说明                                                                 |
| ------------------ | -------------------------------------------------------------------- |
| **账号治理**           | RBAC 权限模型 + 自定义角色，细粒度权限控制                              |
| **客户信息管理**       | 统一客户基础信息 + 画像数据，支持 Excel 导入/导出，数据补全机制          |
| **结算管理**           | 3 种计费模式（定价/阶梯/包年），余额管理（先赠后实），完整结算流程      |
| **画像管理**           | 双等级体系（规模等级 + 消费等级），自定义标签，组合筛选                 |
| **客户分析**           | 消耗分析、回款分析、健康度分析、画像分析四大维度，预测回款             |

### 1.3 用户角色

| 角色          | 核心能力                                                                                               |
| ------------- | ------------------------------------------------------------------------------------------------------ |
| **系统管理员**    | 账号管理、角色创建、权限配置、系统设置                                                                 |
| **运营经理**      | 修改结算价格、修改客户信息、定价配置、客户分析、全局数据查看、报表查看、业务跟进、账单核对（权限最广） |
| **销售/业务人员** | 客户跟进、业务管理                                                                                     |
| **数据分析师**    | 客户分析、报表查看                                                                                     |
| **高层管理者**    | 全局数据查看、决策支持                                                                                 |
| **自定义角色**    | 支持管理员自主创建角色并细粒度配置权限                                                                 |

---

## 2. 整体架构

### 2.1 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                    前端 (Vue3 + Arco Design)              │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │
│  │ 客户管理 │ │ 结算管理 │ │ 画像管理 │ │ 客户分析 │        │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘        │
└──────────────────────┬──────────────────────────────────┘
                       │ REST API (JSON)
┌──────────────────────▼──────────────────────────────────┐
│              后端 (Python + Sanic)                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐    │
│  │ auth/    │ │ customer/│ │ billing/ │ │ analytics│    │
│  │ rbac     │ │ profile  │ │ balance  │ │ report   │    │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                  │
│  │ tag/     │ │ file/    │ │ sync/    │                  │
│  │ label    │ │ attach   │ │ scheduler│                  │
│  └──────────┘ └──────────┘ └──────────┘                  │
└──────────────────────┬──────────────────────────────────┘
                       │ SQLAlchemy 2.0
┌──────────────────────▼──────────────────────────────────┐
│                  PostgreSQL                              │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │
│  │ users   │ │customers│ │ billing │ │ tags    │        │
│  │ roles   │ │ profiles│ │ records │ │ analytics│        │
│  │ perms   │ │ balances│ │ invoices│ │ ...     │        │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘        │
└─────────────────────────────────────────────────────────┘
```

### 2.2 模块边界

| 模块        | 职责                           | 对外依赖          |
| ----------- | ------------------------------ | ----------------- |
| **auth/rbac**   | 用户认证、角色管理、权限校验   | 无                |
| **customer**    | 客户基础信息 CRUD、Excel 导入  | 无                |
| **profile**     | 客户画像、双等级体系           | customer          |
| **tag/label**   | 自定义标签、标签关联           | customer, profile |
| **billing**     | 计费规则、结算单、审批流程     | customer, balance |
| **balance**     | 余额管理、充值、消耗流水       | customer, billing |
| **analytics**   | 四大分析维度、预测回款         | billing, balance  |
| **sync**        | 每日用量接口同步、定时任务     | 外部业务系统 API  |
| **file/attach** | 附件上传（减免证明、支付凭证） | 本地存储/MinIO    |

### 2.3 关键设计决策

1. **单体模块化**：按业务域划分包，模块间通过服务层调用，不直接跨模块访问 DB
2. **权限拦截**：Sanic middleware + 装饰器实现路由级权限控制，细粒度到按钮级由前端控制
3. **软删除**：所有核心表使用 `is_deleted` + `deleted_at`，不物理删除
4. **审计日志**：关键操作（价格修改、结算单生成、余额调整）记录操作人、时间、变更前后值

---

## 3. 数据库设计

### 3.1 用户与权限模块

```sql
-- 用户表
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(100),
    real_name VARCHAR(50),
    is_active BOOLEAN DEFAULT true,
    is_system BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP
);

-- 角色表
CREATE TABLE roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    description VARCHAR(200),
    is_system BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP
);

-- 权限表
CREATE TABLE permissions (
    id SERIAL PRIMARY KEY,
    code VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description VARCHAR(200),
    module VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 用户 - 角色关联
CREATE TABLE user_roles (
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    role_id INTEGER REFERENCES roles(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);

-- 角色 - 权限关联
CREATE TABLE role_permissions (
    role_id INTEGER REFERENCES roles(id) ON DELETE CASCADE,
    permission_id INTEGER REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);
```

### 3.2 客户信息模块

```sql
-- 客户基础信息表
CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    company_id VARCHAR(50) NOT NULL,
    name VARCHAR(200) NOT NULL,
    account_type VARCHAR(50),
    business_type VARCHAR(50),
    customer_level VARCHAR(50),
    price_policy VARCHAR(50),
    manager_id INTEGER REFERENCES users(id),
    settlement_cycle VARCHAR(20),
    settlement_type VARCHAR(20),
    is_key_customer BOOLEAN DEFAULT false,
    email VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP,
    UNIQUE(company_id)
);

-- 客户画像表
CREATE TABLE customer_profiles (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id) ON DELETE CASCADE,
    scale_level VARCHAR(50),
    consume_level VARCHAR(50),
    industry VARCHAR(100),
    is_real_estate BOOLEAN DEFAULT false,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(customer_id)
);

-- 标签定义表
CREATE TABLE tags (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    type VARCHAR(50) NOT NULL,
    category VARCHAR(50),
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, type)
);

-- 客户 - 标签关联
CREATE TABLE customer_tags (
    customer_id INTEGER REFERENCES customers(id) ON DELETE CASCADE,
    tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (customer_id, tag_id)
);

-- 画像 - 标签关联
CREATE TABLE profile_tags (
    profile_id INTEGER REFERENCES customer_profiles(id) ON DELETE CASCADE,
    tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (profile_id, tag_id)
);
```

### 3.3 余额与计费模块

```sql
-- 客户余额表
CREATE TABLE customer_balances (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id) ON DELETE CASCADE,
    total_amount DECIMAL(12,2) DEFAULT 0,
    real_amount DECIMAL(12,2) DEFAULT 0,
    bonus_amount DECIMAL(12,2) DEFAULT 0,
    used_total DECIMAL(12,2) DEFAULT 0,
    used_real DECIMAL(12,2) DEFAULT 0,
    used_bonus DECIMAL(12,2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(customer_id)
);

-- 充值记录表
CREATE TABLE recharge_records (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    real_amount DECIMAL(12,2) NOT NULL,
    bonus_amount DECIMAL(12,2) DEFAULT 0,
    total_amount DECIMAL(12,2) GENERATED ALWAYS AS (real_amount + bonus_amount) STORED,
    operator_id INTEGER REFERENCES users(id),
    payment_proof VARCHAR(255),
    remark TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 计费规则表
CREATE TABLE pricing_rules (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    device_type VARCHAR(20) NOT NULL,
    pricing_type VARCHAR(20) NOT NULL,
    unit_price DECIMAL(10,2),
    tiers JSONB,
    package_type VARCHAR(20),
    package_limits JSONB,
    effective_date DATE NOT NULL,
    expiry_date DATE,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(customer_id, device_type, effective_date)
);

-- 结算单表
CREATE TABLE invoices (
    id SERIAL PRIMARY KEY,
    invoice_no VARCHAR(50) UNIQUE NOT NULL,
    customer_id INTEGER REFERENCES customers(id),
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    total_amount DECIMAL(12,2) NOT NULL,
    discount_amount DECIMAL(12,2) DEFAULT 0,
    discount_reason TEXT,
    discount_attachment VARCHAR(255),
    final_amount DECIMAL(12,2) GENERATED ALWAYS AS (total_amount - discount_amount) STORED,
    status VARCHAR(20) DEFAULT 'draft',
    approver_id INTEGER REFERENCES users(id),
    approved_at TIMESTAMP,
    customer_confirmed_at TIMESTAMP,
    payment_proof VARCHAR(255),
    paid_at TIMESTAMP,
    completed_at TIMESTAMP,
    is_auto_generated BOOLEAN DEFAULT true,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 结算单明细表
CREATE TABLE invoice_items (
    id SERIAL PRIMARY KEY,
    invoice_id INTEGER REFERENCES invoices(id) ON DELETE CASCADE,
    device_type VARCHAR(20) NOT NULL,
    layer_type VARCHAR(20),
    quantity DECIMAL(10,2) NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    subtotal DECIMAL(12,2) GENERATED ALWAYS AS (quantity * unit_price) STORED,
    pricing_rule_id INTEGER REFERENCES pricing_rules(id)
);

-- 消费流水表
CREATE TABLE consumption_records (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    invoice_id INTEGER REFERENCES invoices(id),
    amount DECIMAL(12,2) NOT NULL,
    bonus_used DECIMAL(12,2) DEFAULT 0,
    real_used DECIMAL(12,2) DEFAULT 0,
    balance_after DECIMAL(12,2),
    consumed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 3.4 用量同步模块

```sql
-- 每日用量表
CREATE TABLE daily_usage (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    usage_date DATE NOT NULL,
    device_type VARCHAR(20) NOT NULL,
    layer_type VARCHAR(20),
    quantity DECIMAL(10,2) NOT NULL,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(customer_id, usage_date, device_type, layer_type)
);

-- 同步任务日志
CREATE TABLE sync_logs (
    id SERIAL PRIMARY KEY,
    task_name VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    records_synced INTEGER DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);
```

### 3.5 审计日志表

```sql
-- 操作审计日志
CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    action VARCHAR(50) NOT NULL,
    module VARCHAR(50) NOT NULL,
    record_id INTEGER,
    record_type VARCHAR(50),
    changes JSONB,
    ip_address VARCHAR(45),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 4. API 接口设计

### 4.1 API 规范

- **风格**：RESTful，资源复数形式，版本前缀 `/api/v1`
- **认证**：JWT Token，`Authorization: Bearer <token>`
- **响应格式**：
  ```json
  {
    "code": 0,
    "message": "success",
    "data": { ... },
    "meta": {
      "page": 1,
      "page_size": 20,
      "total": 100
    }
  }
  ```

### 4.2 接口清单

#### 认证与权限模块

| 方法   | 路径                          | 说明             | 权限       |
| ------ | ----------------------------- | ---------------- | ---------- |
| POST   | `/api/v1/auth/login`            | 用户登录         | 公开       |
| POST   | `/api/v1/auth/logout`           | 用户登出         | 已认证     |
| GET    | `/api/v1/auth/me`               | 获取当前用户信息 | 已认证     |
| GET    | `/api/v1/users`                 | 用户列表         | `user:read`  |
| POST   | `/api/v1/users`                 | 创建用户         | `user:write` |
| PUT    | `/api/v1/users/:id`             | 更新用户         | `user:write` |
| DELETE | `/api/v1/users/:id`             | 删除用户         | `user:write` |
| GET    | `/api/v1/roles`                 | 角色列表         | `role:read`  |
| POST   | `/api/v1/roles`                 | 创建角色         | `role:write` |
| PUT    | `/api/v1/roles/:id`             | 更新角色         | `role:write` |
| POST   | `/api/v1/roles/:id/permissions` | 分配权限         | `role:write` |
| GET    | `/api/v1/permissions`           | 权限列表         | `role:read`  |

#### 客户信息管理模块

| 方法   | 路径                          | 说明                 | 权限           |
| ------ | ----------------------------- | -------------------- | -------------- |
| GET    | `/api/v1/customers`             | 客户列表（支持筛选） | `customer:read`  |
| GET    | `/api/v1/customers/:id`         | 客户详情             | `customer:read`  |
| POST   | `/api/v1/customers`             | 创建客户             | `customer:write` |
| PUT    | `/api/v1/customers/:id`         | 更新客户             | `customer:write` |
| DELETE | `/api/v1/customers/:id`         | 删除客户             | `customer:write` |
| POST   | `/api/v1/customers/import`      | Excel 导入客户       | `customer:write` |
| GET    | `/api/v1/customers/export`      | Excel 导出客户       | `customer:read`  |
| GET    | `/api/v1/customers/:id/profile` | 获取客户画像         | `profile:read`   |
| PUT    | `/api/v1/customers/:id/profile` | 更新客户画像         | `profile:write`  |

#### 标签管理模块

| 方法   | 路径                               | 说明             | 权限          |
| ------ | ---------------------------------- | ---------------- | ------------- |
| GET    | `/api/v1/tags`                       | 标签列表         | `tag:read`      |
| POST   | `/api/v1/tags`                       | 创建标签         | `tag:write`     |
| DELETE | `/api/v1/tags/:id`                   | 删除标签         | `tag:write`     |
| POST   | `/api/v1/customers/:id/tags`         | 为客户添加标签   | `tag:write`     |
| DELETE | `/api/v1/customers/:id/tags/:tag_id` | 移除标签         | `tag:write`     |
| POST   | `/api/v1/profiles/:id/tags`          | 为画像添加标签   | `tag:write`     |
| DELETE | `/api/v1/profiles/:id/tags/:tag_id`  | 移除标签         | `tag:write`     |
| GET    | `/api/v1/customers/search`           | 标签组合筛选客户 | `customer:read` |

#### 结算管理模块

| 方法   | 路径                          | 说明                   | 权限           |
| ------ | ----------------------------- | ---------------------- | -------------- |
| GET    | `/api/v1/pricing-rules`         | 计费规则列表           | `pricing:read`   |
| POST   | `/api/v1/pricing-rules`         | 创建计费规则           | `pricing:write`  |
| PUT    | `/api/v1/pricing-rules/:id`     | 更新计费规则           | `pricing:write`  |
| GET    | `/api/v1/invoices`              | 结算单列表（支持筛选） | `billing:read`   |
| GET    | `/api/v1/invoices/:id`          | 结算单详情             | `billing:read`   |
| POST   | `/api/v1/invoices/generate`     | 生成结算单（支持批量） | `billing:write`  |
| POST   | `/api/v1/invoices/:id/submit`   | 提交结算单（商务确认） | `billing:write`  |
| POST   | `/api/v1/invoices/:id/confirm`  | 客户确认（外部回调）   | 公开（带签名） |
| POST   | `/api/v1/invoices/:id/pay`      | 确认付款               | `billing:write`  |
| POST   | `/api/v1/invoices/:id/complete` | 完成结算               | `billing:write`  |
| PUT    | `/api/v1/invoices/:id/discount` | 应用减免               | `billing:write`  |
| DELETE | `/api/v1/invoices/:id`          | 取消结算单             | `billing:write`  |
| GET    | `/api/v1/invoices/export`       | 导出结算单             | `billing:read`   |

#### 余额管理模块

| 方法 | 路径                          | 说明                 | 权限          |
| ---- | ----------------------------- | -------------------- | ------------- |
| GET  | `/api/v1/balances`              | 余额列表             | `balance:read`  |
| GET  | `/api/v1/customers/:id/balance` | 获取客户余额         | `balance:read`  |
| POST | `/api/v1/recharge`              | 充值                 | `balance:write` |
| GET  | `/api/v1/recharge-records`      | 充值记录列表         | `balance:read`  |
| GET  | `/api/v1/consumption-records`   | 消费流水列表         | `balance:read`  |
| POST | `/api/v1/balances/adjust`       | 余额调整（特殊场景） | `balance:admin` |

#### 客户分析模块

| 方法 | 路径                          | 说明           | 权限           |
| ---- | ----------------------------- | -------------- | -------------- |
| GET  | `/api/v1/analytics/consumption` | 消耗分析       | `analytics:read` |
| GET  | `/api/v1/analytics/payment`     | 回款分析       | `analytics:read` |
| GET  | `/api/v1/analytics/health`      | 客户健康度分析 | `analytics:read` |
| GET  | `/api/v1/analytics/profile`     | 画像分析       | `analytics:read` |
| GET  | `/api/v1/analytics/forecast`    | 预测回款       | `analytics:read` |
| GET  | `/api/v1/analytics/dashboard`   | 首页仪表盘数据 | `analytics:read` |

#### 附件管理模块

| 方法   | 路径                 | 说明     | 权限       |
| ------ | -------------------- | -------- | ---------- |
| POST   | `/api/v1/files/upload` | 上传文件 | 已认证     |
| GET    | `/api/v1/files/:id`    | 下载文件 | 已认证     |
| DELETE | `/api/v1/files/:id`    | 删除文件 | `file:write` |

#### 外部回调接口

| 方法 | 路径                              | 说明             | 认证方式      |
| ---- | --------------------------------- | ---------------- | ------------- |
| POST | `/api/v1/webhooks/customer-confirm` | 客户确认账单回调 | HMAC 签名验证 |

---

## 5. 前端页面设计

### 5.1 技术栈

| 层级        | 技术                | 说明                             |
| ----------- | ------------------- | -------------------------------- |
| **框架**        | Vue 3.4+            | Composition API + `<script setup>` |
| **UI 组件库**   | Arco Design Vue 2.x | 字节开源企业级组件库             |
| **状态管理**    | Pinia               | Vue 3 推荐状态管理               |
| **路由**        | Vue Router 4        | 支持路由级权限控制               |
| **HTTP 客户端** | Axios               | 请求拦截 + 响应统一处理          |
| **图表**        | ECharts 5           | 分析模块可视化                   |

### 5.2 路由结构

```
/ (登录页)
/dashboard (首页仪表盘)
/customers (客户管理)
  ├── /customers/list (客户列表)
  ├── /customers/:id (客户详情)
  ├── /customers/:id/profile (画像管理)
  └── /customers/import (批量导入)
/billing (结算管理)
  ├── /billing/invoices (结算单列表)
  ├── /billing/invoices/:id (结算单详情)
  ├── /billing/generate (生成结算单)
  ├── /billing/pricing-rules (计费规则配置)
  └── /billing/recharge (充值管理)
/profiles (画像管理)
  ├── /profiles/tags (标签管理)
  └── /profiles/search (标签组合筛选)
/analytics (客户分析)
  ├── /analytics/consumption (消耗分析)
  ├── /analytics/payment (回款分析)
  ├── /analytics/health (健康度分析)
  ├── /analytics/profile (画像分析)
  └── /analytics/forecast (预测回款)
/settings (系统设置)
  ├── /settings/users (用户管理)
  ├── /settings/roles (角色权限)
  └── /settings/config (系统配置)
```

### 5.3 核心页面

#### 首页仪表盘
- 客户总数、本月回款、待确认账单、余额预警卡片
- 月度回款趋势折线图
- 客户分级分布饼图
- 待办事项列表

#### 客户列表页
- 多条件筛选（公司 ID、客户名称、业务类型、客户等级、运营经理）
- 标签组合筛选（高级筛选）
- 表格展示 + 服务端分页
- 操作列：查看/编辑/画像/结算单/余额/删除

#### 客户详情页
- Tab 切换：基本信息/画像信息/结算单/余额/用量/标签
- 支持在线编辑

#### 结算单生成页
- 结算周期选择
- 自动生成/手动选择客户
- 重点客户过滤提示
- 批量生成支持

#### 结算单详情页
- 计费明细表格
- 减免金额输入 + 附件上传
- 审批历史展示
- 状态流转操作

#### 充值管理页
- 充值记录列表
- 新建充值弹窗（客户选择、实充金额、赠送金额、支付凭证）

#### 标签管理页
- 客户标签/画像标签分类管理
- 标签数量统计

#### 客户分析页
- 消耗分析：月度趋势、Top10 排名、设备类型分布
- 回款分析：预测 vs 实际对比
- 健康度分析：活跃度、余额预警、流失风险
- 画像分析：行业分布、客户分级统计

#### 预测回款页
- 全年回款预测柱状 + 折线组合图
- 月度预测明细表
- 完成率与差额分析

---

## 6. 定时任务与外部接口

### 6.1 定时任务清单

| 任务名称                  | 触发时间        | 职责描述                                | 失败处理            |
| ------------------------- | --------------- | --------------------------------------- | ------------------- |
| **sync_daily_usage**          | 每日 00:00      | 调用外部业务系统 API 同步前一日用量数据 | 重试 3 次，失败告警 |
| **generate_monthly_invoices** | 每月 1 日 02:00 | 自动生成上月结算单（非重点客户）        | 重试 3 次，记录日志 |
| **check_balance_warning**     | 每小时          | 检查余额不足客户，标记预警状态          | 记录日志            |
| **send_overdue_emails**       | 每日 09:00      | 发送逾期账单提醒邮件给商务              | 重试 3 次           |
| **cleanup_temp_files**        | 每日 03:00      | 清理临时文件（超过 7 天的上传文件）     | 忽略                |

### 6.2 外部接口

#### 用量数据同步 API（我方调用外部）
```http
GET /api/external/daily-usage?date=2026-03-31&page=1&page_size=1000
Authorization: Bearer <token>
```

#### 客户确认账单回调 API（外部调用我方）
```http
POST /api/v1/webhooks/customer-confirm
X-Signature: hmac-sha256-signature
```

### 6.3 邮件服务

- **模板引擎**：Jinja2
- **发送协议**：SMTP + TLS
- **邮件类型**：账单通知、逾期提醒

### 6.4 文件存储

- **初期**：本地存储（`/uploads` 目录）
- **后期**：MinIO（S3 兼容）
- **目录结构**：
  ```
  /uploads/
  ├── discount_proof/
  ├── payment_proof/
  └── temp/
  ```

---

## 7. 安全与部署

### 7.1 认证安全

- **JWT Token**：Access Token 24 小时有效，Refresh Token 7 天有效
- **密码加密**：bcrypt，salt rounds=12
- **Token 刷新**：使用 Refresh Token 获取新 Access Token
- **Token 黑名单**：用户登出/密码修改后失效

### 7.2 权限控制

- **路由级权限**：Vue Router meta.permission
- **按钮级权限**：前端指令 + 后端中间件双重校验
- **权限代码格式**：`module:action`（如 `billing:write`）

### 7.3 审计日志

- **记录内容**：操作人、操作类型、模块、记录 ID、变更前后 JSON、IP 地址
- **触发时机**：所有 POST/PUT/DELETE 请求

### 7.4 部署架构

**容器化部署**：
- **容器运行时**：Podman
- **编排工具**：podman-compose
- **服务组成**：app（Sanic）、db（PostgreSQL）、redis（可选）

**环境变量**：
```bash
# 数据库
DB_PASSWORD=your_secure_password

# JWT
JWT_SECRET=your_32_char_random_secret_key

# 邮件
SMTP_PASSWORD=your_smtp_password

# 外部 API
EXTERNAL_API_TOKEN=your_external_api_token

# Webhook
WEBHOOK_SECRET=your_webhook_secret
```

**健康检查**：
- API 端点：`GET /health`
- 数据库：`pg_isready`
- 容器重启策略：`unless-stopped`

**备份策略**：
- **数据库备份**：每日 pg_dump，保留 7 天
- **文件备份**：`/uploads` 目录定期备份

---

## 8. 附录

### 8.1 结算单状态机

```
draft → pending_customer → customer_confirmed → paid → completed
                                 ↓
                            cancelled
```

### 8.2 余额消耗顺序

1. 优先消耗赠送余额
2. 赠送余额不足时消耗实充余额
3. 余额不足时触发预警（通知销售/运营）

### 8.3 计费规则类型

| 类型     | 说明                               |
| -------- | ---------------------------------- |
| **定价结算** | 按设备类型 (X/N/L) 配置单层/多层定价 |
| **阶梯结算** | 按设备类型自定义阶梯，区分单/多层  |
| **包年结算** | A/B/C/D 套餐，配置套餐等级对应用量  |

### 8.4 客户等级体系

- **客户规模等级**：按客户员工规模/业务规模划分
- **客户消费等级**：按月度/季度消耗金额划分

---

## 9. 变更记录

| 日期       | 版本 | 变更内容                               | 关联文档                                         |
| ---------- | ---- | -------------------------------------- | ------------------------------------------------ |
| 2026-04-01 | 1.0  | 初始设计文档                           | -                                                |
| 2026-04-03 | -    | 新增客户分组功能                       | [customer-groups-design](specs/2026-04-03-customer-groups-design.md) |
| 2026-04-06 | -    | 前端重设计                             | [frontend-redesign](specs/2026-04-06-frontend-redesign.md) |
| 2026-04-14 | -    | 业务类型→行业类型转换，细粒度权限       | [business-type→industry](specs/2026-04-14-business-type-to-industry-type-design.md), [fine-grained-permissions](specs/2026-04-14-fine-grained-permissions-design.md) |
| 2026-04-15 | -    | 客户详情优化，编辑弹窗优化，导入模板修复 | [detail-optimization](specs/2026-04-15-customer-detail-optimization-design.md) |
| 2026-04-20 | -    | 客户导入扩展                           | [import-extension](specs/2026-04-20-customer-import-extension-design.md) |
| 2026-04-21 | -    | 客户详情布局统一，列表排序优化         | [layout-unify](specs/2026-04-21-customer-detail-layout-unify-design.md), [sorting](specs/2026-04-21-customer-list-sorting-design.md) |
| 2026-04-22 | -    | 结算方式筛选，画像页面合并             | [settlement-filter](specs/2026-04-22-customer-filter-settlement-type-design.md), [profile-merge](specs/2026-04-22-profile-pages-merge-design.md) |
| 2026-04-23 | -    | 客户筛选器输入检索（AutoComplete）     | [search-filter](specs/2026-04-23-customer-search-filter-design.md) |
| 2026-04-27 | 2.0  | 标记为 Completed，补充变更记录         | -                                                |

---

**文档结束**
