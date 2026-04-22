# 画像管理与画像分析页面合并设计文档

**创建日期**: 2026-04-22
**状态**: 已批准

---

## 背景

项目当前存在两个功能高度重叠的画像相关页面：

1. **`/profiles`（画像管理）** — 定位画像总览 Dashboard，包含统计卡片、ECharts 图表和快捷操作入口
2. **`/analytics/profile`（画像分析）** — 定位多维度画像统计分析，包含更完整的图表集

两个页面的功能重叠度约 80%，维护两套相似代码和双权限体系造成不必要的复杂度。

---

## 问题分析

| 维度         | `/profiles`（画像管理）                          | `/analytics/profile`（画像分析）                  |
| ------------ | ---------------------------------------------- | ---------------------------------------------- |
| **页面标题**   | 画像管理                                       | 画像分析                                       |
| **核心内容**   | 4 统计卡片 + 3 ECharts 图 + 快捷操作卡片        | 4 统计卡片 + 5 ECharts 图                        |
| **独有功能**   | 快捷入口跳转                                   | 客户等级分布饼图、房产客户环形图                  |
| **数据来源**   | scaleStats / consumeLevelStats / industry / realEstate | 同上 + levelStats                              |
| **权限**       | `profiles:view`                                  | `analytics:view`                                 |
| **代码行数**   | 507 行                                         | 731 行                                           |

**核心问题**：
- `/profiles` 的快捷操作卡片中，"画像分析详情"指向的正是 `/analytics/profile`
- `/analytics/profile` 内容更完整，图表展示更丰富
- 两套权限体系（`profiles:*` 和 `analytics:*`）增加管理复杂度

---

## 设计方案

### 决策

**保留 `/analytics/profile` 作为唯一的画像分析页面，删除 `/profiles` 页面及其路由。**

### 改动清单

#### 1. 前端文件删除

| 文件/目录                                        | 操作   |
| ------------------------------------------------ | ------ |
| `frontend/src/views/profiles/Dashboard.vue`      | 删除   |
| `frontend/src/views/profiles/` 目录（如为空）    | 删除   |

#### 2. 前端路由修改

**文件**: `frontend/src/router/index.ts`

删除以下路由配置：
```typescript
{
  path: 'profiles',
  name: 'ProfileDashboard',
  component: () => import('@/views/profiles/Dashboard.vue'),
  meta: { requiresPermission: 'profiles:view' },
},
```

#### 3. 侧边栏导航修改

**文件**: `frontend/src/views/Dashboard.vue`

- 删除"画像管理"主菜单项（当前路径 `/profiles`）
- "客户分析 → 画像分析"子菜单项保留不变

#### 4. 后端权限清理

**涉及文件**:
- `backend/scripts/seed.py` — 权限种子数据
- 细粒度权限设计文档中相关权限定义

删除以下权限定义：
- `profiles:view`
- `profiles:edit`
- `profiles:export`

#### 5. 无需改动的文件

- `frontend/src/views/analytics/Profile.vue` — 保留不动，已是完整版本
- 后端 API 端点 — 不受影响

---

## 权限变化

| 修改前                                      | 修改后                                  |
| ------------------------------------------- | --------------------------------------- |
| `profiles:view/edit/export`（画像管理权限）   | **删除**                                |
| `analytics:view/export/forecast_edit`        | **保留**，画像分析页面已使用 `analytics:view` |

---

## 影响范围评估

### 不受影响的组件

- **客户详情页的画像 Tab**（`/customers/:id` 中的"画像信息"Tab）— 使用的是 `customers.py` 的 profile 接口，非本方案涉及页面
- **标签管理页面** — 画像标签功能独立，不受影响
- **后端 profile 相关 API** — `/api/customers/:id/profile` 等接口保持不变

### 需要确认的点

- 数据库中的 `profiles` 相关权限记录需要通过迁移脚本清理
- 已有角色分配的 `profiles:*` 权限需要迁移到 `analytics:view`（或根据业务需要处理）

---

## 风险与缓解

| 风险                                   | 缓解措施                                   |
| -------------------------------------- | ------------------------------------------ |
| 用户习惯 `/profiles` 路由直接访问        | 可添加路由重定向（`/profiles` → `/analytics/profile`）作为过渡 |
| 权限清理影响已有角色                   | 通过数据库迁移脚本将 `profiles:*` 权限映射到 `analytics:view` |

---

## 成功标准

1. `/profiles` 路由不再可访问（或重定向到 `/analytics/profile`）
2. 侧边栏仅保留一个"画像分析"入口
3. 后端权限系统中不再存在 `profiles:*` 权限
4. 前端构建无错误，TypeScript 类型检查通过
5. 全量测试通过（测试覆盖率不低于现有水平）
