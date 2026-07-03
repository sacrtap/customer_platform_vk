# 设计文档：业务类型→行业类型字典化改造

**日期**: 2026-04-14
**状态**: 已批准
**范围**: 客户管理模块 - 行业类型筛选

---

## 一、背景与目标

### 问题

当前"业务类型"筛选项的可选值硬编码在前端和后端中，无法由运营人员自行维护。业务变更时需要改代码、部署才能更新选项。

### 目标

1. 将筛选名称从"业务类型"改为"行业类型"
2. 行业类型可选值由数据库字典表维护，新增 API 接口返回
3. 前端下拉选项从 API 动态加载

### 预置行业类型值

| ID | 值 |
|---|---|
| 1 | 项目 |
| 2 | 房产经纪 |
| 3 | 房产ERP |
| 4 | 房产平台 |
| 5 | 公共安全 |
| 6 | 租房 |
| 7 | 待确认 |
| 8 | 无 |

---

## 二、方案设计

### 2.1 方案选择：方案A（最小化变更）

- **新建** `industry_types` 独立字典表，包含 8 个预置值
- **保留** `customers.business_type` 列名不变（仅语义变更）
- **新增** `GET /api/v1/dicts/industry_types` 接口
- **前端** 标签改为"行业类型"，下拉值从 API 加载
- 不引入通用字典框架，不做数据迁移

### 2.2 数据库设计

**表名**: `industry_types`

| 字段         | 类型            | 约束                    | 说明       |
| ------------ | --------------- | ----------------------- | ---------- |
| `id`         | INTEGER         | PRIMARY KEY, AUTOINCREMENT | 主键     |
| `name`       | VARCHAR(50)     | NOT NULL, UNIQUE        | 行业类型名称 |
| `sort_order` | INTEGER         | NOT NULL, DEFAULT 0     | 排序顺序   |
| `created_at` | TIMESTAMP       | DEFAULT CURRENT_TIMESTAMP | 创建时间   |
| `updated_at` | TIMESTAMP       | ON UPDATE CURRENT_TIMESTAMP | 更新时间   |

**初始数据**:
```sql
INSERT INTO industry_types (id, name, sort_order) VALUES
  (1, '项目', 1), (2, '房产经纪', 2), (3, '房产ERP', 3),
  (4, '房产平台', 4), (5, '公共安全', 5), (6, '租房', 6),
  (7, '待确认', 7), (8, '无', 8);
```

**Alembic 迁移**:
1. 创建 `industry_types` 表
2. 插入 8 条预置数据

**数据一致性**: 不迁移 `customers.business_type` 已有数据。已有数据保持原样，前端展示时不在字典列表中匹配到的值以原始文本显示。

### 2.3 后端 API 设计

**新增路由**: `GET /api/v1/dicts/industry_types`

- **认证**: `@auth_required`（复用现有认证装饰器）
- **响应**:
```json
{
  "success": true,
  "data": [
    {"id": 1, "name": "项目", "sort_order": 1},
    {"id": 2, "name": "房产经纪", "sort_order": 2},
    ...
  ]
}
```
- **排序**: 按 `sort_order ASC`
- **文件结构**:
  - `backend/app/models/industry_type.py` — SQLAlchemy 模型
  - `backend/app/routes/dict_routes.py` — 字典路由（或并入现有路由模块）
  - `backend/app/services/dict_service.py` — 字典服务

### 2.4 前端变更

**变更文件**:

| 文件 | 变更内容 |
| ---- | -------- |
| `frontend/src/views/customer/Index.vue` | 筛选标签"业务类型"→"行业类型"；下拉选项从硬编码改为 API 调用加载 |
| `frontend/src/views/customer/Detail.vue` | 详情展示标签"业务类型"→"行业类型" |
| `frontend/src/views/customer/types.ts` | 注释/类型说明更新 |
| `frontend/src/api/customer.ts` | 新增 `getIndustryTypes()` API 方法 |
| 其他引用"业务类型"的页面 | 标签文本统一改为"行业类型" |

### 2.5 影响范围

所有搜索到"业务类型"或 "business_type" 引用的文件：

**前端** (~10 文件):
- 筛选/列表页、详情页、类型定义、API 调用

**后端** (~8 文件):
- SQLAlchemy 模型、路由、服务层

**迁移** (~1 文件):
- 新增 Alembic 迁移脚本

**测试** (~5 文件):
- 单元测试、集成测试中涉及 business_type 的测试用例

**文档** (~3 文件):
- README、设计文档、部署指南等

---

## 三、验收标准

1. `GET /api/v1/dicts/industry_types` 返回 8 条预置行业类型数据
2. 客户管理筛选标签显示为"行业类型"
3. 筛选下拉选项从 API 动态加载
4. 已存在的 business_type 数据正常展示（不在字典中的值显示原始文本）
5. 所有提及"业务类型"的前端 UI 统一更新为"行业类型"
6. 所有测试通过
