# 客户数据导入与 company_id 类型迁移设计文档

**日期**: 2026-04-17
**状态**: 设计中
**作者**: AI Assistant

---

## 概述

将 `docs/data.xlsx` 中的 1340 行房产客户数据转换为符合系统导入模板格式的 Excel 文件，
同时将系统中 `company_id` 字段从 `String(50)` 迁移为 `Integer` 类型。

---

## 第一部分：数据转换规则

### 源数据

- **文件**: `docs/data.xlsx`
- **Sheet**: `房产客户分月用量1225（L）`
- **行数**: 1340 行数据 + 1 行表头
- **列数**: 36 列

### 目标格式

- **文件**: `docs/customer_import_20260417.xlsx`
- **Sheet**: `客户导入模板`
- **列数**: 10 列（与系统导入模板一致）

### 字段映射规则

| 目标字段 | 源字段 | 转换规则 | 示例 |
|----------|--------|----------|------|
| `company_id` | 公司id | 保持 int 类型 | 2 → 2 |
| `name` | 公司名称 | 直接映射 | "小猪用户" → "小猪用户" |
| `account_type` | 账号类型 | "正式"→"正式账号", "客户测试账号"→"测试账号", "众点内部"→"内部账号", None→空 | "正式" → "正式账号" |
| `industry` | 行业类型 | "#N/A"→空，其他直接映射 | "房产经纪" → "房产经纪" |
| `customer_level` | 客户等级 | "#N/A"→空，其他直接映射 | "#N/A" → "" |
| `price_policy` | 结算方式 | "定价结算"→"定价", "易遨结算"→"定价", "包年套餐"→"包年", "包年限量套餐"→"包年", 其他→空 | "定价结算" → "定价" |
| `settlement_cycle` | 结算方式 | 直接映射（"#N/A"→空, "待确认"→空, "0"→空） | "包年套餐" → "包年套餐" |
| `settlement_type` | - | 全部设为 "prepaid" | 全部 → "prepaid" |
| `is_key_customer` | 客户消费等级 | C2→true (A级), 其他→false | C2 → true, C3 → false |
| `email` | - | 留空 | "" |

### 异常处理

- `#N/A` 值 → 空字符串
- `None` 值 → 空字符串
- `0` 值（结算方式） → 空字符串
- 未知值 → 保留原值

---

## 第二部分：company_id 类型迁移

### 当前状态

- **数据库类型**: `VARCHAR(50)` (String(50))
- **SQLAlchemy**: `Column(String(50), unique=True, nullable=False, index=True)`
- **前端 TypeScript**: `company_id: string`

### 目标状态

- **数据库类型**: `INTEGER`
- **SQLAlchemy**: `Column(Integer, unique=True, nullable=False, index=True)`
- **前端 TypeScript**: `company_id: number`

### 影响范围

#### 后端修改（5 处）

| 文件 | 行号 | 当前代码 | 修改后 |
|------|------|----------|--------|
| `backend/app/models/customers.py` | 23 | `Column(String(50), ...)` | `Column(Integer, ...)` |
| `backend/app/services/customers.py` | 137 | `Customer.company_id.ilike(...)` | 改为 `cast(Customer.company_id, String).ilike(...)` |
| `backend/app/services/customers.py` | 382 | `isinstance(company_id, float)` | 保留（pandas NaN 处理） |
| `backend/app/routes/customers.py` | 504 | `isinstance(..., str)` | 改为 `isinstance(..., (int, float))` |
| `backend/app/routes/customers.py` | 237,299 | 注释 `"string"` | 改为 `"integer"` |

#### 数据库迁移（1 处）

新建 Alembic 迁移：
```python
def upgrade():
    op.alter_column('customers', 'company_id',
                    type_=sa.Integer(),
                    postgresql_using='company_id::integer')

def downgrade():
    op.alter_column('customers', 'company_id',
                    type_=sa.String(50))
```

**前提条件**: 数据库中现有 company_id 必须可转换为整数

#### 前端修改（8+ 处）

| 文件 | 修改内容 |
|------|----------|
| `frontend/src/types/index.ts:93` | `company_id: string` → `number` |
| `frontend/src/api/customers.ts:26,45` | `company_id: string` → `number` |
| `frontend/src/api/analytics.ts:22,95,108,177` | `company_id: string` → `number` |
| `frontend/src/views/customers/Index.vue` | 表单初始值 `''` → `undefined` |
| `frontend/src/views/customers/Detail.vue` | 表单初始值 `''` → `undefined` |

#### 测试修改

- `backend/tests/integration/test_customers_api.py`: 所有 `"TEST001"` 等字符串需改为整数
- 导入模板测试: 示例数据 `"COMP001"` 需改为整数

### 风险点与对策

| 风险 | 影响 | 对策 |
|------|------|------|
| 现有数据包含非数字 ID | 迁移失败 | 迁移前检查：`SELECT company_id FROM customers WHERE company_id !~ '^\d+$'` |
| 模糊搜索失效 | 搜索功能受损 | 改为 `CAST(company_id AS TEXT) LIKE ...` |
| 前端表单验证 | 类型不匹配 | input type 改为 number，验证规则调整 |
| 测试数据兼容 | 测试失败 | 批量替换测试数据 |

---

## 实施顺序

1. 检查现有数据库中 company_id 是否全为数字
2. 编写数据转换脚本，生成 `docs/customer_import_20260417.xlsx`
3. 创建 Alembic 数据库迁移脚本
4. 修改后端模型、服务、路由
5. 修改前端 TypeScript 类型和组件
6. 更新测试数据
7. 运行测试验证
8. 手动验证导入功能

---

## 验证策略

### 数据转换验证

1. 行数验证：输出文件应有 1341 行（1 行表头 + 1340 行数据）
2. 列数验证：每行应有 10 列
3. 必填字段验证：company_id 和 name 不应为空
4. 枚举值验证：price_policy 只能是"定价"/"阶梯"/"包年"/空

### 类型迁移验证

1. 数据库迁移后 company_id 类型为 INTEGER
2. 后端 API 返回 company_id 为数字类型
3. 前端显示正常
4. 导入功能正常（使用 int 类型的 company_id）
5. 搜索功能正常（模糊搜索 company_id）
