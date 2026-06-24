# 消费分析数据同步优化 - 技术设计文档

**日期**: 2026-06-24  
**作者**: Technical Architect  
**状态**: Draft  
**关联 PRD**: `docs/specs/consumption-sync-optimization.md`

---

## 1. 概述

### 1.1 背景

当前消费分析页面（`/analytics/consumption`）的数据同步功能为同步 HTTP 请求触发全量数据同步，存在以下问题：
- 无法选择特定周期，只能全量同步（同步昨天）
- 无实时进度反馈，用户体验差
- 大数据量时存在 HTTP 超时风险
- 无操作审计日志

### 1.2 目标

1. **周期选择同步**：支持用户选择特定时间范围（最长 31 天）进行数据同步
2. **异步执行 + 实时进度**：同步任务异步化执行，前端实时展示执行进度（按天分片）
3. **双模式支持**：仅补充缺失数据 / 强制重新同步
4. **操作可追溯**：每次同步操作记录审计日志，支持历史查询

### 1.3 成功指标

| 指标 | 当前基线 | 目标 | 度量方式 |
|---|---|---|---|
| 同步任务成功率 | ~85%（含超时失败） | ≥ 99% | 异步任务成功数 / 总触发数 |
| 单次同步最大耗时（31天） | N/A | < 5 分钟 | 后端任务执行时间 |
| 进度反馈延迟 | N/A | < 3 秒 | 前端轮询间隔 |
| 操作审计覆盖率 | 0% | 100% | 有审计记录的操作数 / 总操作数 |

---

## 2. 架构设计

### 2.1 整体架构

```
前端（Vue）→ POST /sync-tasks → 后端创建 SyncTask → 返回 task_id
                                    ↓
                              Sanic 后台任务（按天循环）
                                    ↓
                              OrderSyncService + CostCalcService
                                    ↓
                              Redis 实时更新进度（Hash）
                                    ↓
前端 ← GET /sync-tasks/:id/progress ← 轮询读取 Redis 进度
```

### 2.2 核心组件

1. **SyncTask 模型** — 新建 `sync_tasks` 表，存储任务元数据
2. **SyncTaskService** — 新建服务，封装任务创建/执行/查询逻辑
3. **后台任务执行器** — 使用 `app.add_task()` 启动异步协程
4. **Redis 进度缓存** — `sync_progress:{task_id}` Hash，TTL 1 小时
5. **扩展 SyncTaskLog** — 添加审计字段，复用现有 `/api/v1/sync-logs` 路由

### 2.3 数据流

- **创建任务** → 写 `sync_tasks` 表 + 写 Redis 进度 + 写 `sync_task_logs` 审计
- **执行中** → 每天更新 Redis 进度
- **完成/失败** → 更新 `sync_tasks` 状态 + 更新 Redis + 更新 `sync_task_logs`

---

## 3. 数据模型

### 3.1 新建 `sync_tasks` 表

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | UUID | PRIMARY KEY | 任务 ID |
| start_date | DATE | NOT NULL | 同步开始日期 |
| end_date | DATE | NOT NULL | 同步结束日期 |
| sync_mode | VARCHAR(20) | NOT NULL DEFAULT 'skip_existing' | skip_existing / force_overwrite |
| status | VARCHAR(20) | NOT NULL DEFAULT 'pending' | pending / running / completed / failed |
| total_days | INT | NOT NULL | 总天数 |
| completed_days | INT | DEFAULT 0 | 已完成天数 |
| skipped_days | INT | DEFAULT 0 | 跳过天数 |
| current_date | DATE | NULL | 当前处理日期 |
| success_count | INT | DEFAULT 0 | 成功同步条数 |
| failed_count | INT | DEFAULT 0 | 失败条数 |
| error_message | TEXT | NULL | 失败原因 |
| operator_id | INT | FK→users.id NOT NULL | 操作人 |
| created_at | TIMESTAMP | DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMP | DEFAULT NOW() | 更新时间 |
| completed_at | TIMESTAMP | NULL | 完成时间 |

**索引**：
- `idx_sync_tasks_status` (status)
- `idx_sync_tasks_operator` (operator_id)
- `idx_sync_tasks_created` (created_at)

### 3.2 扩展现有 `sync_task_logs` 表

新增字段（兼容历史数据，允许 NULL）：

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| task_id | UUID | NULL FK→sync_tasks.id | 关联任务 |
| operator_id | INT | NULL FK→users.id | 操作人 |
| start_date | DATE | NULL | 同步开始日期 |
| end_date | DATE | NULL | 同步结束日期 |
| sync_mode | VARCHAR(20) | NULL | skip_existing / force_overwrite |

现有字段 `task_name` 存 `'consumption_sync'`，兼容历史数据。

### 3.3 Redis 进度结构

```
Key: sync_progress:{task_id}
Type: Hash
Fields:
  - status: pending / running / completed / failed
  - sync_mode: skip_existing / force_overwrite
  - total_days: int
  - completed_days: int
  - skipped_days: int
  - current_date: string (YYYY-MM-DD)
  - success_count: int
  - failed_count: int
  - percentage: int (0-100)
  - error_message: string | null
TTL: 3600s（1小时，完成后保留供最终轮询读取）
```

---

## 4. API 设计

### 4.1 POST /api/v1/sync-tasks — 创建同步任务

**请求**：
```json
{
  "start_date": "2026-06-17",
  "end_date": "2026-06-24",
  "sync_mode": "skip_existing"
}
```

**响应（201）**：
```json
{
  "code": 0,
  "message": "任务创建成功",
  "data": {
    "task_id": "uuid",
    "status": "pending",
    "sync_mode": "skip_existing",
    "total_days": 7
  }
}
```

**错误**：
- 400：日期跨度 > 31 天 / 日期格式错误
- 409：相同周期已有 running 任务

### 4.2 GET /api/v1/sync-tasks/{task_id}/progress — 查询进度

**响应**：
```json
{
  "code": 0,
  "data": {
    "task_id": "uuid",
    "status": "running",
    "sync_mode": "skip_existing",
    "total_days": 7,
    "completed_days": 5,
    "skipped_days": 2,
    "current_date": "2026-06-22",
    "success_count": 150,
    "failed_count": 0,
    "percentage": 71,
    "error_message": null
  }
}
```

**逻辑**：
- 优先从 Redis 读取实时进度
- Redis 无数据时回退查询 `sync_tasks` 表
- 任务不存在返回 404

### 4.3 GET /api/v1/sync-tasks/{task_id} — 查询任务详情

**响应**：
```json
{
  "code": 0,
  "data": {
    "task_id": "uuid",
    "start_date": "2026-06-17",
    "end_date": "2026-06-24",
    "sync_mode": "skip_existing",
    "status": "completed",
    "total_days": 7,
    "completed_days": 5,
    "skipped_days": 2,
    "success_count": 150,
    "failed_count": 0,
    "operator_id": 1,
    "created_at": "2026-06-24T10:00:00",
    "completed_at": "2026-06-24T10:05:00",
    "error_message": null
  }
}
```

### 4.4 复用现有 GET /api/v1/sync-logs — 审计日志查询

扩展筛选参数：
- `start_date`：同步开始日期
- `end_date`：同步结束日期
- `sync_mode`：同步模式
- `operator_id`：操作人 ID

现有字段 `task_name = 'consumption_sync'` 用于筛选消费同步日志。

---

## 5. 后端执行逻辑

### 5.1 SyncTaskService 核心方法

```python
class SyncTaskService:
    async def create_task(start_date, end_date, sync_mode, operator_id) -> SyncTask
    async def execute_task(task_id) -> None  # 后台执行
    async def get_progress(task_id) -> dict
    async def get_task(task_id) -> SyncTask
```

### 5.2 execute_task 执行流程

```
1. 更新 status = 'running'，写 Redis
2. 生成日期列表 [start_date, end_date] 按天
3. FOR EACH date IN dates:
   a. 更新 current_date = date
   b. IF sync_mode == 'skip_existing':
      - 查询 daily_orders WHERE sync_date = date
      - IF 存在数据: skipped_days++, 更新 Redis, CONTINUE
   c. IF sync_mode == 'force_overwrite':
      - 调用 _clear_orders(date) 删除旧数据
   d. 调用 OrderSyncService.sync_orders(date)
   e. 调用 CostCalcService.calculate_daily_cost(date)
   f. 更新 completed_days++, success_count += result.success
   g. 写 Redis 进度
4. 全部完成: status = 'completed', 释放锁
5. 异常: status = 'failed', error_message = str(e), 释放锁
```

### 5.3 单天失败处理

- 捕获异常，记录 failed_count++
- 继续下一天，不中断整体流程
- 任务最终状态判定：
  - `completed_days > 0` → status = `'completed'`（部分成功也算完成）
  - `completed_days == 0 && failed_count > 0` → status = `'failed'`（全部失败）
  - `completed_days == total_days` → status = `'completed'`（全部成功）

### 5.4 锁管理

- **锁 key**：`sync_lock:{start_date}:{end_date}`
- **TTL**：1800s（30 分钟）
- **获取锁**：创建任务时尝试获取，失败返回 409
- **释放锁**：任务完成/失败时主动释放，异常中断靠 TTL 自动过期

### 5.5 Redis 进度更新

- 每天完成后 HSET 更新所有字段
- 完成后保留 1 小时供前端最终轮询
- TTL 过期后回退查询 `sync_tasks` 表

---

## 6. 前端实现

### 6.1 组件结构

```
Consumption.vue（现有页面）
  └─ SyncDialog.vue（新建）
     ├─ 周期选择器（日期范围）
     ├─ 同步模式选择（Radio）
     └─ ProgressView.vue（新建，进度展示）
```

### 6.2 SyncDialog.vue 状态机

```
'input'  → 用户选择周期/模式
  ↓ 提交
'creating' → POST /sync-tasks
  ↓ 成功
'polling' → 每 2 秒 GET /sync-tasks/:id/progress
  ↓ status == 'completed' | 'failed'
'result' → 显示汇总结果
```

### 6.3 ProgressView.vue 进度展示

```vue
<template>
  <div>
    <a-progress :percent="progress.percentage" />
    <div class="status-text">
      {{ statusText }}
    </div>
    <div class="summary" v-if="isFinished">
      成功 {{ progress.success_count }} 条 / 
      失败 {{ progress.failed_count }} 条
      <span v-if="progress.skipped_days > 0">
        / 跳过 {{ progress.skipped_days }} 天
      </span>
    </div>
  </div>
</template>
```

**状态文本**：
- `running` + `skip_existing`：「正在同步 {current_date} 的数据... 已完成 {completed_days}/{total_days} 天（跳过 {skipped_days} 天）」
- `running` + `force_overwrite`：「正在同步 {current_date} 的数据... 已完成 {completed_days}/{total_days} 天」
- `completed`：「同步完成」
- `failed`：「同步失败：{error_message}」

### 6.4 轮询实现

```typescript
const pollProgress = async (taskId: string) => {
  const interval = setInterval(async () => {
    const res = await api.get(`/sync-tasks/${taskId}/progress`)
    progress.value = res.data
    
    if (res.data.status === 'completed' || res.data.status === 'failed') {
      clearInterval(interval)
      state = 'result'
    }
  }, 2000)
}
```

### 6.5 失败重试

- 失败时显示「重试」按钮
- 点击重试：读取原任务的 `start_date`、`end_date`、`sync_mode`，重新调用 POST 创建新任务
- 新任务 ID 替换旧任务，进度对话框刷新

### 6.6 错误提示

- **日期跨度 > 31 天**：禁用确认按钮，红色提示「时间跨度不能超过31天」
- **结束日期 < 开始日期**：禁用确认按钮，红色提示「结束日期不能早于开始日期」
- **409 冲突**：「已有相同周期的同步任务正在执行」
- **网络错误**：「网络异常，请重试」

---

## 7. 测试策略

### 7.1 后端测试

| 测试类型 | 覆盖范围 | 工具 |
|---|---|---|
| 单元测试 | SyncTaskService 各方法（create/execute/progress） | pytest + mock |
| 集成测试 | 完整任务创建→执行→进度查询流程 | pytest + test client |
| 边界测试 | 日期跨度校验、并发锁冲突、单天失败不中断 | pytest |
| 模式测试 | skip_existing 跳过逻辑、force_overwrite 删除逻辑 | pytest |

**关键测试用例**：
1. 创建任务 → 返回 task_id + status=pending
2. 相同周期并发 → 409
3. skip_existing 模式：已有数据的天跳过，skipped_days 正确
4. force_overwrite 模式：所有天重新同步
5. 单天失败 → 继续下一天 → 最终 status=completed
6. 进度查询 → Redis 数据实时更新
7. 锁 TTL 30 分钟 → 异常中断后自动释放

### 7.2 前端测试

- **SyncDialog 组件**：日期校验、模式切换、警告提示显示
- **ProgressView 组件**：进度条更新、汇总结果展示
- **轮询逻辑**：2 秒间隔、完成后停止

### 7.3 TDD 策略

- **核心业务逻辑**（SyncTaskService）→ TDD
- **UI 组件** → Tests-after

---

## 8. 迁移计划

### 8.1 数据库迁移

1. 创建 `sync_tasks` 表
2. 扩展 `sync_task_logs` 表（添加 5 个字段）
3. 历史数据迁移：现有 `sync_task_logs` 记录保持原样，新字段为 NULL

### 8.2 代码迁移

1. 新建 `SyncTask` 模型
2. 扩展 `SyncTaskLog` 模型
3. 新建 `SyncTaskService`
4. 新建 `/api/v1/sync-tasks` 路由
5. 扩展现有 `/api/v1/sync-logs` 路由（添加筛选参数）
6. 废弃旧 `/api/v1/analytics/consumption/sync` 端点（保留 1 个版本兼容）

### 8.3 前端迁移

1. 新建 `SyncDialog.vue` 组件
2. 新建 `ProgressView.vue` 组件
3. 修改 `Consumption.vue`：替换同步按钮逻辑
4. 新建 API 调用方法

---

## 9. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|---|---|---|
| Redis 不可用导致进度查询失败 | 高 | 进度数据双写 Redis + 数据库，Redis 故障时回退数据库查询 |
| 异步任务进程崩溃导致任务卡死 | 高 | 任务超时自动标记失败（30 分钟），锁自动过期释放 |
| 外部数据源不稳定导致同步失败率高 | 中 | 单天失败不中断整体流程，支持重试机制，失败天数记录到审计日志 |
| 大数据量同步导致数据库连接池耗尽 | 中 | 按天串行执行（非并行），控制并发连接数 |
| 前端轮询频率过高增加服务器压力 | 低 | 轮询间隔 2 秒，任务完成后停止轮询 |

---

## 10. 决策记录

| 决策 | 理由 | 考虑的替代方案 |
|---|---|---|
| 采用异步任务 + 轮询方案而非 WebSocket | 项目现有基础设施无 WebSocket，轮询方案实现成本低、可靠性高 | WebSocket 实时推送、SSE 服务端推送 |
| 按天分片串行执行而非并行 | 控制数据库连接数，避免连接池耗尽，降低外部数据源压力 | 按天并行执行、按客户并行执行 |
| 进度数据双写 Redis + 数据库 | Redis 故障时仍可查询进度，提高系统可用性 | 仅写 Redis、仅写数据库 |
| 单天失败不中断整体流程 | 提高任务成功率，部分失败可接受，用户可重试失败部分 | 单天失败即终止整个任务 |
| 复用现有 `sync_task_logs` 表 | 避免表爆炸，现有 `/api/v1/sync-logs` 路由可直接复用 | 新建独立 `consumption_sync_logs` 表 |
| 默认模式为「仅补充缺失数据」 | 大多数场景是补数据，避免无效 DELETE；性能更优 | 默认「强制重新同步」 |
| 使用 Sanic 后台任务而非 Celery | 项目已有 Redis，Sanic 原生支持后台任务，无需引入新依赖 | Celery + Redis Broker、APScheduler 动态任务 |

---

## 11. 实施计划

### Phase 1: 后端核心（TDD）
1. 创建 `SyncTask` 模型 + 数据库迁移
2. 扩展 `SyncTaskLog` 模型
3. 实现 `SyncTaskService`（TDD）
   - `create_task`
   - `execute_task`
   - `get_progress`
   - `get_task`
4. 实现 `/api/v1/sync-tasks` 路由
5. 扩展 `/api/v1/sync-logs` 路由

### Phase 2: 前端实现（Tests-after）
1. 新建 `SyncDialog.vue` 组件
2. 新建 `ProgressView.vue` 组件
3. 修改 `Consumption.vue`
4. 新建 API 调用方法

### Phase 3: 集成测试 + 优化
1. 端到端测试
2. 性能优化（大数据量场景）
3. 文档更新

---

## 12. 验收标准

- [ ] 用户可选择起止日期，时间跨度 ≤ 31 天
- [ ] 用户可选择同步模式（仅补充/强制覆盖），默认仅补充
- [ ] 同步任务异步执行，前端实时展示进度（延迟 < 3 秒）
- [ ] skip_existing 模式下，已有数据的日期被跳过
- [ ] force_overwrite 模式下，所有日期都重新同步
- [ ] 单天失败不影响其他天继续执行
- [ ] 任务完成后显示汇总结果（成功/失败/跳过条数）
- [ ] 失败时显示具体错误信息，支持一键重试
- [ ] 每次同步操作 100% 有审计记录
- [ ] 相同周期并发请求返回 409
- [ ] 锁过期时间 30 分钟，异常中断后自动释放
