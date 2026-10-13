# 余额白名单备注 — 执行计划

## 迁移命名（避免 revision 冲突）

新增迁移文件：`backend/alembic/versions/x3y4z5a6b7c8_add_remark_to_balance_whitelists.py`
- `revision = "x3y4z5a6b7c8"`，`down_revision = "w2x3y4z5a6b7"`。

## 有序清单

1. **模型**：`backend/app/models/balance_whitelist.py` 增加
   `remark: Mapped[str | None] = mapped_column(String(200), nullable=True)`（import `String`）。
2. **迁移**：新增上述 alembic 文件，`upgrade` 用 `op.add_column("balance_whitelists", sa.Column("remark", sa.String(length=200), nullable=True, comment="备注"))`；`downgrade` 用 `op.drop_column`。
3. **服务**：
   - `get_all()`：`select(...)` 增加 `BalanceWhitelist.remark`；解包行增加 `remark`；item 增加 `"remark": remark`。
   - `update()`：签名增加 `remark` 与「是否提供」控制参数；仅提供时写 `record.remark`；新增 `_normalize_remark(value) -> str | None` 静态校验（strip；空 → None；>200 → `ValueError("备注最长 200 字符")`）。
4. **路由** `PUT /<id:int>`：用 `"remark" in data` 取 `remark_raw`；调用服务校验并区分语义；Response data 增加 `remark`。
5. **前端类型** `frontend/src/types/index.ts`：`BalanceWhitelistItem` 增加 `remark: string | null`。
6. **前端 API** `frontend/src/api/balanceWhitelist.ts`：`updateBalanceWhitelist(id, static_balance, remark?)`，body 带 `remark`。
7. **前端页面** `frontend/src/views/system/BalanceWhitelist.vue`：
   - `columns` 增加 `{ title: '备注', dataIndex: 'remark', width: 180 }`（放在「添加时间」前或「操作」前）。
   - 编辑弹窗新增 `a-form-item field="remark" label="备注"` + `a-input`（`:max-length="200"` `show-word-limit` `allow-clear`）。
   - `editForm` 增加 `remark: string | undefined`；`handleOpenEdit` 回填 `record.remark ?? ''`；`handleEditSubmit` 传 `editForm.remark?.trim() ? editForm.remark.trim() : null`。
8. **测试** `backend/tests/integration/test_balance_whitelist_routes.py`：新增用例
   - PUT 带 `remark` → 列表/响应含该值；
   - PUT `remark=null` / 空串 → 清空为 `null`；
   - PUT 不传 `remark` → 既有备注不变；
   - `remark` >200 → 400；
   - 列表接口无备注时 `remark` 为 `null`。

## 验证命令

```bash
cd backend && ruff check app/ && pyright
cd backend && python -m pytest tests/integration/test_balance_whitelist_routes.py -v
cd frontend && pnpm type-check
```

## 风险 / 回滚点

- 迁移方向必须 `down_revision` 指向当前 head，禁止手动改 revision id。
- 若 pyright 对模型新列报未类型化，确保用 `Mapped[str | None] = mapped_column(...)`。
- 回滚：`op.drop_column` + 移除模型/服务/路由/前端字段（无数据依赖，风险低）。
