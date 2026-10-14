# 包年套餐余额显示优化 — 执行计划

## 顺序与清单

### Phase A — 后端 `balances.py`（核心）

- [ ] A1 `_query_balance_rows_raw`：base_stmt / count_stmt 改 Customer 驱动 + outerjoin CustomerBalance（deleted_at 入 ON）；CustomerBalance.customer_id 引用改 Customer.id；sort_field_map 加 COALESCE；预加载改 `selectinload(Customer.balance)`；返回值语义不变
- [ ] A2 新增 `package_remaining` CTE（窗口函数取最新规则），LEFT JOIN 到 base_stmt/count_stmt；余额范围筛选改 `COALESCE(package_remaining.remaining, CustomerBalance.total_amount, 0)`；`total_amount` 排序用同表达式
- [ ] A3 `days_remaining` 排序 CASE 增加包年分支（`CAST(expiry_date AS DATE) - CURRENT_DATE`，NULL expiry 排最后）
- [ ] A4 新增 `_batch_query_package_info(db, customer_ids)`（生效规则 + 消费聚合 + 过期判断 + 计算 remaining_amount/remaining_count）
- [ ] A5 `_assemble_balance_rows`：入参改 `list[Customer]` + `package_info_map`；输出包年 9 字段；total_amount 覆盖规则；调用处（列表 + 导出线程）传新参
- [ ] A6 `_compute_burn_down`：新增 package_info 分支（有效包年 → 到期天数；过期 → 0）；`_assemble_balance_rows` 调用处传入
- [ ] A7 `get_balance_stats`：`_balance_totals`/low_balance/burning_soon 三处改 Customer 驱动 + COALESCE/CASE 包年分支；`apply_balance_filters` 去掉 CustomerBalance.deleted_at（移入 outerjoin ON）
- [ ] A8 `_build_excel` 增加三列（剩余额度/剩余次数/到期日期，不限量显示「不限」）

### Phase B — 前端

- [ ] B1 `frontend/src/api/billing.ts`：`Balance` 接口新增 9 个包年字段
- [ ] B2 `BalanceTable.vue`：余额列双值展示（!is_package 原逻辑 / is_package 包年分支 + 过期/不限量标签）
- [ ] B3 `BalanceTable.vue`：燃尽列包年分支 + 4 个包年辅助函数（FillPct/BarClass/Label/Tooltip）

### Phase C — 测试与验证

- [ ] C1 更新 `tests/unit/test_balance_filters.py`（_query_balance_rows_raw 组装变更）
- [ ] C2 新增单元测试：`_batch_query_package_info`（mock 计算）、`_compute_burn_down` 包年分支、`_assemble_balance_rows` 包年字段
- [ ] C3 后端冒烟：启动服务，构造包年客户数据，curl 验证列表字段/筛选/KPI/导出
- [ ] C4 前端冒烟：浏览器验证余额列/燃尽列/筛选/行高亮
- [ ] C5 回归：定价/阶梯客户数据对比

### Phase D — 跨页口径对齐（客户管理页）

- [x] D1 抽出共享模块 `app/services/package_balance.py`（`build_package_remaining_cte` / `batch_query_package_info` / `resolve_effective_balance`），`balances.py` 改为导入别名复用
- [x] D2 `services/customers.py`：`sort_by=balance` 改用 `COALESCE(package_cte.remaining, CustomerBalance.total_amount, 0)`
- [x] D3 `routes/customers.py` 列表：批量查包年信息，`balance`/`is_package`/`package_expired` 输出，`health` 按有效余额判定
- [x] D4 `routes/customers.py` 详情：`balance.total_amount` 按包年口径（无余额行以 0/0/0 结构返回）
- [x] D5 详情余额 Tab 端点（`balances.py`）：`resolve_effective_balance` 决策 + 包年字段
- [x] D6 余额预测接口：修复 `balance` 返回 ORM 对象 bug 并接入包年口径
- [x] D7 360 摘要接口：修复既有 500（`get_customer_detail` 不存在 → `get_customer_by_id`）
- [x] D8 前端：`CustomerTable` / `PreviewDrawer` / `CustomerBalanceTab` 文案按包年区分；`CustomerBalanceTab` 新增包年三卡片 + 不限量/已过期标签
- [x] D9 测试：`unit/test_package_balance.py`、`integration/test_customers_package_balance.py`、前端 `CustomerBalanceTab.test.ts`
- [x] D10 spec：`billing-balance-stats.md` 补场景「客户管理页余额口径对齐」+ 签名改指共享模块

### Phase E — 开放平台余额接口口径（对外出口遗漏）

- [x] E1 `_build_customer_balance_stmt`：复用 `build_package_remaining_cte`，LEFT JOIN 取第 6 列 `package_remaining`（非包年 NULL）
- [x] E2 `_format_balance_rows`：余额优先级 白名单 > 包年剩余额度 > `total_amount − used_total`
- [x] E3 集成测试：全量/渠道包年口径 + 白名单优先 + 非包年回归（`test_openapi_api.py`）
- [x] E4 单测直连：`test_openapi_handlers.py` 行结构补第 6 列 + 包年用例
- [x] E5 文档：`openapi-docs` 两份接口补口径说明；`billing-balance-stats.md` 新增场景「开放平台余额接口口径」

## 验证命令

```bash
# 后端单元测试
cd backend && .venv/bin/python -m pytest tests/unit/test_balance_filters.py -q
# 覆盖率门禁（CI 全量口径 ≥50%）
cd backend && .venv/bin/python -m pytest --cov=app --cov-report=term-missing -q tests/
# 冒烟（服务运行中）
curl 'localhost:8000/billing/balances?page=1&page_size=100' -H 'Authorization: Bearer <token>' | jq '.data.list[] | select(.is_package == true) | {customer_name, package_remaining_amount, package_remaining_count, days_remaining}'
```

## 回滚点

- A1-A3 相互耦合（同一函数），A1 完成后先跑 C1 测试
- A4-A6 独立于 A1-A3 的展示层，可单独回退
- 前端 B1-B3 与后端字段契约耦合，后端先合、前端后合
