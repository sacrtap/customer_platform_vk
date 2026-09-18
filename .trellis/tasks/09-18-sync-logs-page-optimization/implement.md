# 实施计划 — 同步任务日志页面功能优化

> 任务：`.trellis/tasks/09-18-sync-logs-page-optimization`
> 设计依据：`design.md`；需求：`prd.md`

## 实现顺序

### Step 1 后端：明细接口改造
- [ ] 1.1 `backend/app/routes/sync_tasks.py` `get_sync_task_details`：
  - 新增 `type` / `is_settled` / `keyword` 参数解析
  - 明细查询 `outerjoin(Customer)` 取 `is_settlement_enabled` / `account_type`
  - 类型归类筛选（order → order_fetch/order_match/order_save；cost → cost_calc/data_check）
  - is_settled 筛选、keyword 模糊搜索
  - 排序改为 `sync_date.desc(), id.desc()`
  - 响应 list item 追加 `is_settlement_enabled`、`account_type`
  - `filtered_total` 应用全部筛选

### Step 2 前端：API 层
- [ ] 2.1 `frontend/src/api/syncTasks.ts`：`SyncLogDetail` 扩展字段；`getSyncTaskDetails` 扩展参数

### Step 3 前端：明细 Drawer 改造
- [ ] 3.1 新增筛选区（类型/是否结算/公司ID名称搜索），置于级别 radio 之上
- [ ] 3.2 列改造：客户ID·名称 → 公司ID·名称；删「外部客户ID」列；新增「是否结算」「账号类型」列；日期列加宽
- [ ] 3.3 记录数当日小计（按 sync_date 分组 rowSpan + 小计行）

### Step 4 验证
- [ ] 4.1 后端接口：curl/脚本验证 type/is_settled/keyword 筛选与 summary 不变
- [ ] 4.2 前端浏览器：打开明细 Drawer，验证 8 项 AC

## 验证命令

```bash
# 后端：pytest 相关用例（如有明细接口测试）
cd backend && .venv/bin/python -m pytest tests/ -k "sync" -q

# 前端：类型检查 / lint（若存在）
cd frontend && npm run type-check 2>/dev/null || true

# 接口冒烟（需登录 token）
curl -s "http://127.0.0.1:8000/api/v1/sync-tasks/<task_id>/details?type=cost&is_settled=true&keyword=公司" \
  -H "Authorization: Bearer <token>"
```

## 风险文件 / 回滚点

| 文件 | 风险 | 回滚 |
|---|---|---|
| `backend/app/routes/sync_tasks.py` | 明细接口筛选/join 逻辑 | 还原该函数参数与查询 |
| `frontend/src/api/syncTasks.ts` | 类型定义 | 还原类型/参数 |
| `frontend/src/views/system/components/SyncLogDetailDrawer.vue` | 列/筛选/小计 | 还原列定义与筛选区 |

## 已确认决策（2026-09-18 用户确认）

1. 「是否结算」三态（全部/是/否），默认「是」；「全部」显示含 `customer_id=NULL` 明细。
2. 「记录数当日小计」基于当前页分组求和。
3. 删除冗余的「外部客户ID」独立列。
