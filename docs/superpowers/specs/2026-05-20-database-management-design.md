# 数据库管理功能设计

**创建时间**: 2026-05-20
**状态**: 已确认

---

## 1. 功能概述

在"系统设置"菜单下新增"数据库管理"模块，提供数据清空功能：
- 级联删除所有客户主表及关联表数据
- 仅管理员（admin）角色可操作
- 操作需二次弹框确认
- 记录审计日志

## 2. 权限配置

新增权限:
- **权限标识**: `system:database_clear`
- **权限名称**: 数据库管理-数据清空
- **默认角色**: admin

在权限 seed/初始化脚本中注册该权限，并绑定到 admin 角色。

## 3. 后端设计

### 3.1 路由
- **方法**: `POST /system/database/clear`
- **权限**: `@auth_required` + `@require_permission("system:database_clear")`

### 3.2 业务逻辑
1. 统计即将删除的客户数量（用于审计和响应）
2. 开启数据库事务
3. 按依赖顺序级联删除：
   - `customer_tags` — 客户标签关联
   - `customer_profiles` — 客户画像
   - `billing_records` — 结算记录
   - `invoices` — 发票记录
   - `analytics_*` — 客户分析相关数据
   - `customers` — 客户主表
4. 提交事务
5. 写入 `audit_logs` 表（操作人、时间、删除数量、操作类型=database_clear）
6. 清除相关缓存
7. 返回 `{ "success": true, "deleted_count": N }`

### 3.3 错误处理
- 事务失败自动回滚
- 返回明确的错误信息和 HTTP 状态码

## 4. 前端设计

### 4.1 页面
- **文件**: `frontend/src/views/system/DatabaseManagement.vue`
- **内容**:
  - 功能说明卡片（说明此操作的不可逆性和影响范围）
  - "清空客户数据"按钮（Danger 类型）
  - 操作后提示删除结果

### 4.2 交互流程
```
用户点击"清空客户数据"
→ Arco Design Modal.confirm 二次确认
  标题: "确认清空客户数据"
  内容: "此操作将不可恢复地删除所有客户及关联数据（含客户画像、标签、结算记录、发票等），确定继续？"
  按钮: "取消" / "确定清空"（danger）
→ 确认后调用 API
→ 显示加载中（按钮 loading 状态）
→ 成功: Message.success("已删除 N 条客户数据")
→ 失败: Message.error(错误信息)
```

### 4.3 菜单
在 `Dashboard.vue` 系统设置子菜单中新增 "数据库管理" 入口：
- 权限守卫: `can('system:database_clear')`
- 路由: `/system/database-management`

### 4.4 路由
在路由配置中新增 `/system/database-management`，组件为 `DatabaseManagement.vue`。

## 5. 级联删除范围

| 表名 | 说明 | 删除方式 |
|------|------|----------|
| `customers` | 客户主表 | 物理删除 |
| `customer_tags` | 客户标签关联 | 物理删除（关联到客户的记录） |
| `customer_profiles` | 客户画像 | 物理删除（关联到客户的记录） |
| `billing_records` | 结算记录 | 物理删除（关联到客户的记录） |
| `invoices` | 发票记录 | 物理删除（关联到客户的记录） |

## 6. 审计日志

操作完成后写入 `audit_logs` 表：
- `action`: `database_clear`
- `resource`: `customers`
- `user_id`: 当前操作用户 ID
- `details`: `{"deleted_count": N, "tables_affected": [...]}`
- `created_at`: 操作时间
