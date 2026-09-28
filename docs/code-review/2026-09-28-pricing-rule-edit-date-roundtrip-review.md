# 代码审查报告 — 计费规则编辑「参数格式错误」修复（UTC ↔ CST 日期契约）

**日期**: 2026-09-28
**工具**: open-code-review (`ocr`) v1.12.9
**范围**: 提交 `68f3239`（2 个文件，+177/-4；审查选中 1 个核心代码文件）
**LLM**: 默认配置（bifrost 网关，`--concurrency 2 --effort low`）
**审查耗时**: 约 1 分钟（89,315 token）
**发现问题**: 0 个（无 critical / high / medium / low）

---

## 审查文件清单

### 后端（2 个文件，审查选中 1 个）
- `backend/app/routes/billing/pricing.py` ← **已纳入 LLM 审查**
- `backend/tests/integration/test_billing_api.py`（回归测试，按项目惯例不纳入 LLM 审查，由 pytest 实测覆盖）

> 未纳入 LLM 审查的改动：集成测试、`.trellis/spec/**`（与历史审查报告同一取舍，见 `2026-09-23-balance-page-optimization-review.md`）。

---

## 业务背景

客户运营中台（Sanic + SQLAlchemy 2.0 后端 / Vue 3 + Arco Design 前端）。修复计费规则编辑保存报「参数格式错误」：

- **根因（跨层日期契约断裂）**：DB 存 UTC 时刻（`DateTime(timezone=True)`，CST 当日 00:00 写入后为 UTC 前一日 16:00）。列表端点 `GET /billing/pricing-rules` 此前用 `effective_date.isoformat()` 输出 UTC ISO 时刻（如 `2026-03-31T16:00:00+00:00`）；前端编辑弹窗把该值回填 `a-date-picker` 并原样提交，而写入口 `check-conflict` / `PUT` 用 `date.fromisoformat()` 解析（只接受 `YYYY-MM-DD`）→ 改任何字段（如单价）都报 400「参数格式错误」；绕过冲突检查直接 PUT 则 500（`local_date_to_utc_start` 在 try 外抛 ValueError）。
- **修复**：列表端点改用 `utc_to_cst_date_str` 输出 CST 日期串，与同文件导出路径 `_build_pricing_rules_excel` 既有约定一致；新增集成回归测试 `test_pricing_rule_list_dates_round_trip_to_edit` 覆盖「创建 → 列表回填 → 冲突检查 → PUT → DB 往返闭合」全链路。
- **沉淀**：跨层日期契约教训写入 `.trellis/spec/guides/cross-layer-thinking-guide.md`（Time Field Cross-Layer Contract 小节）。

---

## 问题与修复

### 严重（0 个）

无。

### 高（0 个）

无。

### 中（0 个）

无。

### 低（0 个）

无。

---

## 结论

Review complete — no critical, high, or medium issues found in 1 file.

---

## 修复本身的验证（提交前已完成）

| 验证项 | 结果 |
|--------|------|
| 修复前 API 层复现 | 列表返回 ISO 时刻 → check-conflict 400 `参数格式错误`、PUT 500（临时复现测试，已删除） |
| 修复后集成测试 | `test_billing_api.py` 全量 55 passed（含新增回归测试）；pricing 相关 19 passed；billing 单元 63 passed |
| 静态检查 | ruff lint + format 通过 |
| 浏览器实测 | 编辑弹窗日期正确显示 `2026-01-01`；改单价 11.50 → PUT body 含 `unit_price: 11.5`、`effective_date: "2026-01-01"` → DB 落库 11.50 → 测试数据已回滚；全程无「参数格式错误」 |
