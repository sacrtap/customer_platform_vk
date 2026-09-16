-- 一次性补偿脚本：为历史缺失余额档案的客户补建 customer_balances 记录
--
-- 背景：`backend/app/routes/billing/balances.py` 中原有「惰性补建」逻辑
--       （db.add_all + flush）从未生效——请求结束时 `close_db_session`
--       仅 close() 未 commit()，未提交事务随连接释放回滚，因此补建写入被丢弃。
--       该逻辑已删除（列表/导出恢复纯只读语义）。
--
-- 正常业务路径已自动建档：
--   - 单条创建：`backend/app/services/customers.py` create_customer 内 add(balance)
--   - 批量导入：同文件 batch_create_customers 内 add_all(balances)
-- 本脚本仅用于兜底清理历史脏数据（SQL 直插、早期数据迁移等场景）。
--
-- 使用方式（人工执行，不接入应用启动流程、不由 seed 调用）：
--   psql "$DATABASE_URL" -f backend/scripts/backfill_balance_archives.sql
--
-- 幂等性：依赖 customer_balances.customer_id 唯一约束 + ON CONFLICT DO NOTHING，
--         可安全重复执行。
--
-- 边界说明：`customer_id` 是**全局**唯一约束（不含 `deleted_at` 条件），而本脚本的「缺失」
--         判定仅排除未软删档案。若某客户只存在「已软删」的 balance 行，下方 INSERT 会被
--         ON CONFLICT 静默跳过，末尾 `remaining_missing` 可能非 0 —— 此时需人工判断
--         是恢复该行还是清理后重跑。（当前代码库无软删 CustomerBalance 的写入路径，
--         属理论边界，正常数据不会触发。）

-- 人工补偿脚本必须「失败即停」：任一语句出错即中止，避免在部分写入后继续执行
-- 造成半迁移状态（psql 默认遇错继续，会在出错后仍尝试后续语句）。
\set ON_ERROR_STOP on

BEGIN;

-- 执行前预览将补建的客户数量
SELECT count(*) AS customers_to_backfill
FROM customers c
WHERE c.deleted_at IS NULL
  AND NOT EXISTS (
      SELECT 1 FROM customer_balances b
      WHERE b.customer_id = c.id AND b.deleted_at IS NULL
  );

INSERT INTO customer_balances (
    customer_id,
    total_amount,
    real_amount,
    bonus_amount,
    used_total,
    used_real,
    used_bonus,
    created_at,
    updated_at
)
SELECT c.id, 0, 0, 0, 0, 0, 0, now(), now()
FROM customers c
WHERE c.deleted_at IS NULL
  AND NOT EXISTS (
      SELECT 1 FROM customer_balances b
      WHERE b.customer_id = c.id AND b.deleted_at IS NULL
  )
ON CONFLICT (customer_id) DO NOTHING;

-- 执行后确认无遗漏（期望 0）
SELECT count(*) AS remaining_missing
FROM customers c
WHERE c.deleted_at IS NULL
  AND NOT EXISTS (
      SELECT 1 FROM customer_balances b
      WHERE b.customer_id = c.id AND b.deleted_at IS NULL
  );

COMMIT;
