# Task 1 Report: SyncTask 模型 + 数据库迁移

## 状态
DONE

## 创建的文件

| 文件 | 说明 |
|------|------|
| `backend/app/models/sync_task.py` | SyncTask 模型定义 (16 个字段) |
| `backend/alembic/versions/59e4cca22335_add_sync_tasks_table.py` | 迁移脚本 |

## 修改的文件

| 文件 | 变更 |
|------|------|
| `backend/app/models/__init__.py` | 添加 import sync_task + __all__ 导出 |
| `backend/alembic/env.py` | 添加 sync_task + BaseModel 导入以支持 autogenerate |

## 模型验证

```
SyncTask model OK
Fields: ['id', 'start_date', 'end_date', 'sync_mode', 'status', 'total_days',
         'completed_days', 'skipped_days', 'current_date', 'success_count',
         'failed_count', 'error_message', 'operator_id', 'completed_at',
         'created_at', 'updated_at']
```

共 16 个字段，完全符合需求。

## 迁移脚本

- Revision: `59e4cca22335`
- Down revision: `41b931a886e0`
- 当前 head: `59e4cca22335`

迁移内容：
1. 创建 `sync_tasks` 表（含所有字段、`operator_id` → `users.id` 外键约束、UUID 主键）
2. 创建三个索引：`idx_sync_tasks_status`、`idx_sync_tasks_operator`、`idx_sync_tasks_created`

## 遇到的问题及解决方案

1. **`alembic/env.py` 中 `BaseModel` 未导入**: 最初只有 `from app.models.base import BaseModel` 但删除了。已补回 `from app.models.base import BaseModel`。

2. **迁移模板缺少 `Union`/`Sequence` 导入**: 生成的 migration 文件使用 `Union[str, None]` 但缺少 `from typing import Sequence, Union`。已手动修复。

3. **生成的 migration 缺少三个索引**: autogenerate 未自动捕获模型中的 `index=True` 配置（因为索引在 brief 中要求但模型列未设置 `index=True`，而是独立索引）。已手动在 migration 中添加 `op.create_index` 调用。

4. **`completed_days`/`skipped_days` 等默认值字段标记为 `nullable=True`**: autogenerate 读取模型列时，带有 `default=` 但未显式 `nullable=False` 的字段被误判为可空。已修复 migration 中对应列使用 `server_default="0"` + `nullable=False`。

## 验收标准检查

- [x] `SyncTask` 模型包含所有 16 个字段
- [x] 三个索引正确创建 (`idx_sync_tasks_status`, `idx_sync_tasks_operator`, `idx_sync_tasks_created`)
- [x] 外键约束指向 `users.id`
- [x] 迁移脚本已生成 (head: `59e4cca22335`)
- [x] 模型在 `models/__init__.py` 中导出
