# 技术设计与影响面

## 1. 修复点定位（均已核实行号）

### P1 middleware logger（5 处）

| 文件 | 行 | 当前 | 修复 |
|------|----|------|------|
| `backend/app/middleware/auth.py` | 顶部 | 无模块级 logger | 新增 `import logging` + `logger = logging.getLogger(__name__)` |
| 同上 | 65 | `app.logger.warning(f"Token verification failed: {e}")` | `logger.warning("Token verification failed: %s", e)` |
| 同上 | 82 | `app.logger.info(f"Blacklisted token used: {jti}")` | `logger.info("Blacklisted token used: %s", jti)` |
| 同上 | 91 | `app.logger.error(f"认证中间件异常：{e}")` | `logger.error("认证中间件异常：%s", e, exc_info=True)` |
| 同上 | 163 | `app.logger.warning(f"Failed to update last_used_at for API-Key {api_key.id}")` | `logger.warning("Failed to update last_used_at for API-Key %s", api_key.id)` |
| `backend/app/middleware/audit.py` | 156 | `app.logger.error(f"Audit log failed: {e}")` | `logger.error("Audit log failed: %s", e, exc_info=True)`（该文件已有模块级 logger） |

- 同步移除 5 处 `# pyright: ignore[reportAttributeAccessIssue]`。
- 采用 `%s` 惰性格式化，与文件内既有 `logger.debug("...%s", x)` 风格一致。
- `logger.error(..., exc_info=True)` 让原始堆栈进入日志，直接消除 REQ-1.4 的"真实原因丢失"问题。

### P2 前端 Blob 错误体（1 处）

`frontend/src/api/index.ts` 响应拦截器错误分支（当前 162-172 行）：

```ts
// 提取后端返回的错误信息（blob 下载失败时响应体是 Blob，需先读文本再解析）
const data = error.response.data
let backendMessage: string = error.response.statusText || '请求失败'
let code: number | string = error.response.status * 100

if (data instanceof Blob) {
  try {
    const parsed = JSON.parse(await data.text())
    backendMessage = parsed?.message || backendMessage
    code = parsed?.code || code
  } catch {
    // 非 JSON 错误体，保留 statusText
  }
} else if (data?.message) {
  backendMessage = data.message
  code = data.code || code
}

return Promise.reject({
  code,
  message: backendMessage,
  category: getErrorCategory(typeof code === 'number' ? code : 50000),
})
```

- 错误回调已是 `async`，可直接 `await`。
- 非 Blob 路径改为显式 `else if`，保持原有语义（`data.message` 优先、`data.code` 其次）。
- import 无需变更（`Blob` 为全局类型）。

### P3 计费规则导入字段校验

`backend/app/routes/billing/pricing.py` 行循环内，插入点在 `package_type` 必填校验之后（当前 448-451 行）：

```python
# 非包年结算：设备类型与楼层类型必填（与 UI 表单 required 口径一致）
if pricing_type != "package":
    if not device_type:
        errors.append(f"第 {row_num} 行：设备类型不能为空（非包年结算必填）")
        continue
    if not layer_type:
        errors.append(f"第 {row_num} 行：楼层类型不能为空（非包年结算必填）")
        continue
```

- `device_type` / `layer_type` 变量在 400-404 行已完成解析（空值归一为 `None`），可直接复用。
- 同一端点内的「可选字段」注释需同步改口径；`import_pricing_rules` docstring 中 `device_type (可选)` / `layer_type (可选)` 更新为「非包年必填」。
- 模板生成（`pricing_rules_import_template`）中第 2 行说明文案同步：`可选：X/N/L` → `非包年必填：X/N/L`、`可选：single/multi` → `非包年必填：single/multi`。

> 待确认的小增强（不在 REQ-3 强制范围）：是否同时校验取值域（`device_type ∈ {X,N,L}`、`layer_type ∈ {single,multi,single_and_multi}`）。UI 为下拉选择，导入目前不校验值域，仍有写入非法值（如 `device_type="abc"`）的可能。建议一并加入，成本约 6 行 + 1 个测试断言。

### P4 文档旧权限码

`docs/specs/balance-import-prd.md` 8 处 `billing:import` → `billing:balance_import`（含正文、流程图、验收清单、决策表），并在文档头部补一句迁移说明：`billing:import`/`billing:export` 已拆分为 8 个细粒度权限码（`billing:{balance,pricing,package,invoice}_{import,export}`），本文档中的权限码为历史命名。

### P5 删除无效惰性补建

`backend/app/routes/billing/balances.py`：

1. 删除 421-445 行补建块（注释 + `missing_stmt` + `missing_ids` + `db.add_all` + `flush` + `IntegrityError` 分支 + `logger.info`）。
2. 删除 `from sqlalchemy.exc import IntegrityError`（第 10 行，核实为该文件唯一使用点）。
3. 保留 `logger`（其他位置仍在用，如日期格式告警）与 `CustomerBalance` import（`select(CustomerBalance)` 仍在用）。
4. 新增一次性补偿脚本 `backend/scripts/backfill_balance_archives.sql`：

```sql
-- 为历史缺失余额档案的客户补建（一次性，人工执行）
INSERT INTO customer_balances
    (customer_id, total_amount, real_amount, bonus_amount, used_total, used_real, used_bonus, created_at, updated_at)
SELECT c.id, 0, 0, 0, 0, 0, 0, now(), now()
FROM customers c
WHERE c.deleted_at IS NULL
  AND NOT EXISTS (
      SELECT 1 FROM customer_balances b
      WHERE b.customer_id = c.id AND b.deleted_at IS NULL
  )
ON CONFLICT (customer_id) DO NOTHING;
```

- 脚本不接入启动流程、不被 seed 调用；仅供部署/运维按需执行。
- 删除后列表与导出的 `total`/`list` 天然一致（不再有"同请求内插入的行被后续查询看到"的现象）。

## 2. 影响面分析

| 修复 | 正常路径行为变化 | 影响模块 |
|------|-----------------|---------|
| P1 | 无（仅日志器切换） | 认证中间件、审计中间件 |
| P2 | 无（仅失败分支） | 全部下载链路的错误提示（客户/余额/计费规则/套餐/结算单导出与模板下载） |
| P3 | 有：非包年且缺字段的导入行**由成功转为行级错误**（预期行为变更，堵脏数据） | 计费规则导入 |
| P4 | 无（文档） | docs |
| P5 | 有：列表/导出不再尝试补建（该尝试本就无效）；`total` 与 `list` 恢复一致 | 余额列表、余额导出 |

- P3 是本批唯一的**行为变更**，需在回归测试中确认合法数据（含 package 行）仍可导入。
- P1 的认证路径修复后，原本被 AttributeError 掩盖的异常将以 JSON 500 返回并带完整堆栈。

## 3. 验证策略（对应 AC）

| AC | 验证方式 |
|----|---------|
| AC-1 | `grep -rn "app\.logger" backend/app` 无输出 |
| AC-2 | 集成测试：monkeypatch `TokenBlacklistService.is_blacklisted` 抛异常 → 断言响应 status 500 且 `json["code"] == 50000`（修复前该路径返回 HTML 500） |
| AC-3 | 浏览器实测：余额页用不存在关键词筛选 → 点「导出」→ 断言提示文案为后端中文消息；同时断言所有页面的导出/模板下载链路仍正常（200 + xlsx） |
| AC-4 | 集成测试：构造含「fixed 缺 device_type」+「package 完整」的文件 → `success_count=1, error_count=1` 且错误文案含「设备类型」 |
| AC-5 | `grep -rn "billing:import\|billing:export" docs/` 无输出 |
| AC-6 | SQL 构造一个无余额档案的客户 → 调用列表 → 断言 `total == len(list)`；随后确认该客户**仍未**被建档（证明无写操作） |
| AC-7 | `cd backend && .venv/bin/python -m pytest tests/ -q --cov=app --cov-fail-under=50`；`cd frontend && npm run type-check && npm run lint` |
| AC-8 | 浏览器回归：五页面按钮就位、导出下载 200、模板下载 200、部分成功导入（成功 1/失败 1，行号准确、列表刷新） |

## 4. 风险与回滚

| 风险 | 说明 | 回滚 |
|------|------|------|
| P3 误伤合法数据 | 若存在业务上确实允许 device_type 为空的非包年规则 | 单文件 revert：`backend/app/routes/billing/pricing.py` |
| P2 错误体解析抛错 | `blob.text()`/`JSON.parse` 异常已 try/catch 兜底 | 单文件 revert：`frontend/src/api/index.ts` |
| P5 删除补建后历史缺档客户不可见 | 由补偿 SQL 兜底（正常业务路径已建档） | 恢复删除块或执行补偿脚本 |
| P1 日志风格变化 | 仅格式参数化，无行为影响 | 单文件 revert |

## 5. 设计决策

- **D-Logger**：统一用模块级 `logging.getLogger(__name__)`，与项目既有约定一致（`cache/base.py`、`audit.py` 顶部、spec `logging-guidelines.md`），不再依赖框架实例属性。
- **D-Blob**：在拦截器统一处理，不要求 48 个 `handleError` 调用方各自处理 → 单点修复覆盖全部下载链路。
- **D-Backfill**：以 SQL 脚本交付而非代码内自动补建，保持 GET 端点只读语义（REST 约束），且避免每请求无用写尝试。
