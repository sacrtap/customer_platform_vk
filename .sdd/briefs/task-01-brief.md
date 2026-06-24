# Task 1: 创建 SyncTask 模型 + 数据库迁移

## 目标

创建新的 SyncTask 模型和对应的数据库迁移脚本，用于存储异步同步任务的元数据和状态。

## 上下文

这是消费分析同步优化功能的第一个任务。后续任务将基于这个模型实现异步任务调度、进度跟踪等功能。

## 需求

### 1. 创建 SyncTask 模型

**文件位置**: `backend/app/models/sync_task.py`

**字段定义**:
- `id`: UUID, 主键
- `start_date`: DATE, NOT NULL, 同步开始日期
- `end_date`: DATE, NOT NULL, 同步结束日期
- `sync_mode`: VARCHAR(20), NOT NULL, DEFAULT 'skip_existing', 同步模式 (skip_existing/force_overwrite)
- `status`: VARCHAR(20), NOT NULL, DEFAULT 'pending', 任务状态 (pending/running/completed/failed)
- `total_days`: INT, NOT NULL, 总天数
- `completed_days`: INT, DEFAULT 0, 已完成天数
- `skipped_days`: INT, DEFAULT 0, 跳过天数
- `current_date`: DATE, NULL, 当前处理日期
- `success_count`: INT, DEFAULT 0, 成功同步条数
- `failed_count`: INT, DEFAULT 0, 失败条数
- `error_message`: TEXT, NULL, 失败原因
- `operator_id`: INT, FK→users.id, NOT NULL, 操作人
- `created_at`: TIMESTAMP, DEFAULT NOW(), 创建时间
- `updated_at`: TIMESTAMP, DEFAULT NOW(), 更新时间
- `completed_at`: TIMESTAMP, NULL, 完成时间

**索引**:
- `idx_sync_tasks_status` (status)
- `idx_sync_tasks_operator` (operator_id)
- `idx_sync_tasks_created` (created_at)

### 2. 创建数据库迁移脚本

**文件位置**: `backend/migrations/versions/YYYYMMDD_create_sync_tasks_table.py`

**迁移内容**:
- 创建 `sync_tasks` 表
- 创建上述三个索引
- 添加外键约束 `operator_id` → `users.id`

### 3. 注册模型

**文件位置**: `backend/app/models/__init__.py`

在 `__all__` 列表中导出 `SyncTask`。

## 验收标准

- [ ] `SyncTask` 模型包含所有 16 个字段
- [ ] 三个索引正确创建
- [ ] 外键约束指向 `users.id`
- [ ] 迁移脚本可成功执行 `alembic upgrade head`
- [ ] 模型在 `models/__init__.py` 中导出

## 技术约束

- 使用 SQLAlchemy 2.0 语法
- UUID 使用 `sqlalchemy.dialects.postgresql.UUID(as_uuid=True)`
- 时间戳字段使用 `sqlalchemy.DateTime(timezone=True)`
- 迁移脚本遵循项目现有命名规范

## 测试要求

无需编写测试，但需验证：
1. 迁移脚本可成功应用
2. 模型可正常导入和实例化

## 交付物

1. `backend/app/models/sync_task.py` - SyncTask 模型定义
2. `backend/migrations/versions/YYYYMMDD_create_sync_tasks_table.py` - 迁移脚本
3. 更新 `backend/app/models/__init__.py` - 导出 SyncTask

## 报告要求

完成后在 `.sdd/reports/task-01-report.md` 中记录：
- 创建的文件列表
- 迁移脚本执行结果
- 任何遇到的问题及解决方案
