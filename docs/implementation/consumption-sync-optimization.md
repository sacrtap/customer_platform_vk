# 消费分析数据同步优化 - 实现文档

## 概述

本次实现将消费分析数据同步功能从同步全量模式升级为异步周期选择模式，支持双模式（仅补充/强制覆盖）、实时进度反馈、操作审计。

## 实现内容

### 1. 数据模型

#### 1.1 SyncTask 模型（新建）
- **文件**: `backend/app/models/sync_task.py`
- **表名**: `sync_tasks`
- **用途**: 存储异步同步任务的元数据和状态

**字段**:
- `id`: UUID 主键
- `start_date`, `end_date`: 同步日期范围
- `sync_mode`: 同步模式（skip_existing/force_overwrite）
- `status`: 任务状态（pending/running/completed/failed）
- `total_days`, `completed_days`, `skipped_days`: 进度统计
- `current_date`: 当前处理日期
- `success_count`, `failed_count`: 同步结果统计
- `operator_id`: 操作人
- `created_at`, `updated_at`, `completed_at`: 时间戳

**索引**:
- `idx_sync_tasks_status`: 按状态查询
- `idx_sync_tasks_operator`: 按操作人查询
- `idx_sync_tasks_created`: 按创建时间查询

#### 1.2 SyncTaskLog 模型（扩展）
- **文件**: `backend/app/models/billing.py`
- **新增字段**:
  - `task_id`: 关联 SyncTask
  - `operator_id`: 操作人
  - `start_date`, `end_date`: 同步日期范围
  - `sync_mode`: 同步模式

**用途**: 审计日志，记录所有同步操作

### 2. 业务逻辑

#### 2.1 SyncTaskService
- **文件**: `backend/app/services/sync_task_service.py`
- **核心方法**:
  - `create_task()`: 创建同步任务，获取分布式锁
  - `execute_task()`: 执行同步任务（后台异步）
  - `get_progress()`: 获取任务进度（Redis 优先，回退数据库）
  - `get_task()`: 获取任务详情

**执行流程**:
1. 验证日期范围（≤31天）
2. 获取 Redis 分布式锁（`sync_lock:{start_date}:{end_date}`，TTL 30分钟）
3. 创建 SyncTask 记录（status=pending）
4. 创建 SyncTaskLog 审计记录
5. 启动后台任务执行
6. 按天循环执行：
   - **skip_existing 模式**: 检查数据是否存在，存在则跳过
   - **force_overwrite 模式**: 删除旧数据后重新同步
   - 调用 OrderSyncService 同步订单
   - 调用 CostCalcService 计算费用
   - 更新 Redis 进度
7. 单天失败不中断整体流程
8. 完成后更新任务状态和审计日志

**进度存储**:
- **Redis**: `sync_progress:{task_id}` Hash，TTL 1小时
- **数据库**: SyncTask 表（Redis 故障时回退）

### 3. API 接口

#### 3.1 同步任务接口
- **文件**: `backend/app/routes/sync_tasks.py`
- **基础路径**: `/api/v1/sync-tasks`

**POST /**: 创建同步任务
- 请求体: `{ start_date, end_date, sync_mode }`
- 响应: `{ task_id, status, sync_mode, total_days }`
- 错误: 400（参数错误）、409（锁冲突）

**GET /{task_id}**: 获取任务详情
- 响应: 完整任务信息

**GET /{task_id}/progress**: 获取任务进度
- 响应: `{ task_id, status, completed_days, total_days, skipped_days, percentage, ... }`

#### 3.2 审计日志接口（扩展）
- **文件**: `backend/app/routes/sync_logs.py`
- **新增筛选参数**: `start_date`, `end_date`, `sync_mode`, `operator_id`

### 4. 前端组件

#### 4.1 API 调用
- **文件**: `frontend/src/api/syncTasks.ts`
- **方法**:
  - `createSyncTask()`: 创建同步任务
  - `getSyncTaskProgress()`: 获取任务进度
  - `getSyncTask()`: 获取任务详情

#### 4.2 ProgressView 组件
- **文件**: `frontend/src/views/analytics/components/ProgressView.vue`
- **功能**: 展示任务进度条、状态文本、统计信息
- **特性**: 显示跳过天数（skip_existing 模式）

#### 4.3 SyncDialog 组件
- **文件**: `frontend/src/views/analytics/components/SyncDialog.vue`
- **功能**: 同步对话框，包含日期选择、模式选择、进度展示
- **状态机**: input → creating → polling → result
- **轮询**: 每 2 秒查询进度
- **重试**: 失败时支持一键重试

#### 4.4 Consumption 页面集成
- **文件**: `frontend/src/views/analytics/Consumption.vue`
- **修改**:
  - 替换同步按钮为打开 SyncDialog
  - 添加 `handleSyncSuccess` 回调刷新数据

### 5. 数据库迁移

#### 5.1 创建 sync_tasks 表
- **文件**: `backend/alembic/versions/59e4cca22335_add_sync_tasks_table.py`
- **操作**: 创建表、索引、外键

#### 5.2 扩展 sync_task_logs 表
- **文件**: `backend/alembic/versions/6c04c664b261_extend_sync_task_logs_with_audit_fields.py`
- **操作**: 添加 5 个字段、外键约束

### 6. 测试

#### 6.1 单元测试
- **文件**: `backend/tests/services/test_sync_task_service.py`
- **覆盖**:
  - `TestCreateTask`: 4 个测试（成功、日期验证、锁冲突）
  - `TestExecuteTask`: 3 个测试（两种模式、单天失败）
  - `TestGetProgress`: 2 个测试（Redis、数据库回退）
  - `TestGetTask`: 2 个测试（成功、不存在）
- **结果**: 11/11 通过

#### 6.2 E2E 测试
- **文件**: `backend/tests/e2e/test_sync_task_e2e.py`
- **覆盖**: 完整流程、并发冲突、日期验证
- **状态**: 需要 Sanic 测试环境配置（待完善）

## 技术决策

### 1. 异步执行方案
- **选择**: Sanic 后台任务 + Redis 进度
- **理由**: 轻量、无新依赖、符合项目现状
- **替代方案**: Celery（过重）、APScheduler（语义不匹配）

### 2. 进度存储方案
- **选择**: Redis Hash + 数据库双写
- **理由**: Redis 提供低延迟查询，数据库作为回退
- **TTL**: Redis 1 小时，防止内存泄漏

### 3. 并发控制方案
- **选择**: Redis 分布式锁
- **锁键**: `sync_lock:{start_date}:{end_date}`
- **TTL**: 30 分钟（防止死锁）
- **冲突处理**: 返回 409，提示用户稍后重试

### 4. 失败处理策略
- **单天失败**: 不中断整体流程，继续下一天
- **任务状态**:
  - `completed_days > 0` → completed（部分成功）
  - `completed_days == 0` → failed（全部失败）

### 5. 审计日志方案
- **选择**: 扩展现有 `sync_task_logs` 表
- **理由**: 避免表爆炸，复用现有查询接口
- **新增字段**: task_id, operator_id, start_date, end_date, sync_mode

## 验收标准

- [x] 用户可选择起止日期，时间跨度 ≤ 31 天
- [x] 用户可选择同步模式（仅补充/强制覆盖），默认仅补充
- [x] 同步任务异步执行，前端实时展示进度（延迟 < 3 秒）
- [x] skip_existing 模式下，已有数据的日期被跳过
- [x] force_overwrite 模式下，所有日期都重新同步
- [x] 单天失败不影响其他天继续执行
- [x] 任务完成后显示汇总结果（成功/失败/跳过条数）
- [x] 失败时显示具体错误信息，支持一键重试
- [x] 每次同步操作 100% 有审计记录
- [x] 相同周期并发请求返回 409
- [x] 锁过期时间 30 分钟，异常中断后自动释放

## 已知问题

1. **E2E 测试**: 需要配置 Sanic 测试环境，当前测试用例已编写但未通过
2. **时区处理**: created_at/updated_at 继承自 TimestampMixin，未使用 `DateTime(timezone=True)`（预存在问题）

## 后续优化建议

1. **WebSocket 实时推送**: 替代轮询，降低延迟和服务器压力
2. **任务取消功能**: 支持用户取消长时间运行的任务
3. **批量任务并行**: 支持多个不重叠周期同时同步
4. **智能模式推荐**: 自动检测数据分布，推荐合适的同步模式
5. **性能监控**: 添加同步任务执行时间、成功率的监控指标

## 部署说明

### 1. 数据库迁移
```bash
cd backend
alembic upgrade head
```

### 2. 后端部署
无需特殊配置，Sanic 自动加载新路由

### 3. 前端部署
```bash
cd frontend
npm run build
```

### 4. Redis 配置
确保 Redis 服务可用，配置在 `backend/app/config.py` 中

## 回滚方案

### 1. 代码回滚
```bash
git revert <commit-hash>
```

### 2. 数据库回滚
```bash
cd backend
alembic downgrade -2  # 回滚两个迁移
```

### 3. 注意事项
- 回滚前确保没有正在运行的同步任务
- 回滚后旧的同步接口恢复可用
