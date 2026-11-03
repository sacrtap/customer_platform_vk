# VR编辑费用结算模块实施计划

## Context

在「结算管理」菜单下新增 **VR编辑费用结算** 模块（位于「结算单管理」下方），复用现有结算单（Invoice）模块的工程模式（Sanic + SQLAlchemy 异步 + RBAC 权限 + Alembic 迁移 + Arco 前端），实现独立的 VR 编辑费用结算单全流程：

1. 创建时支持「手动创建 / 自动创建」两种模式选择；**自动创建当前禁用并标识「待开发」**（仅前端展示，无后端能力）。
2. 手动创建：选择指定客户 + 上传结算明细 Excel + 填写结算金额与周期即可创建（状态 `draft`）。
3. 审批流：创建 → 客服主管审批 → 指定客户的销售审批 → 销售主管审批 → 客户确认 → 完成结算。**客户确认即自动扣减客户余额并写入关联消耗记录**（与现有结算单模块「确认后自动扣款」一致，已与用户确认）。
4. 减免：在销售主管审批前的任意节点（draft / 待客服主管 / 待销售 / 待销售主管）可提交/修改减免信息；**销售主管审批时一并审批**（通过=节点通过且减免生效；驳回=整单退回销售节点）。
5. 取消/删除纳入范围（借鉴现有模块，已与用户确认）：任意非终态可取消；软删除。

不做：Excel 明细解析入库（明细文件仅上传存档与下载，不解析行项目）、批量操作、导入导出、自动创建的后端实现、定时任务、待办聚合接入。

## Approach

### 阶段 1：数据模型与数据库迁移

**步骤 1.1 新建 `backend/app/models/vr_settlement.py`**（照抄 `models/billing.py` 的 Invoice 风格，`Mapped`/`mapped_column`，继承 `BaseModel`）：

```python
"""VR编辑费用结算模型"""

import random
import string
from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import DECIMAL, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel


class VrSettlementStatus(str, Enum):
    """VR结算单状态枚举

    draft → pending_cs_supervisor → pending_sales → pending_sales_supervisor
        → pending_customer → customer_confirmed → completed

    任意非终态均可 → cancelled
    """

    DRAFT = "draft"  # 草稿（待提交）
    PENDING_CS_SUPERVISOR = "pending_cs_supervisor"  # 待客服主管审批
    PENDING_SALES = "pending_sales"  # 待销售审批
    PENDING_SALES_SUPERVISOR = "pending_sales_supervisor"  # 待销售主管审批
    PENDING_CUSTOMER = "pending_customer"  # 待客户确认
    CUSTOMER_CONFIRMED = "customer_confirmed"  # 客户已确认（扣款失败可重试）
    COMPLETED = "completed"  # 已完成（扣款成功）
    CANCELLED = "cancelled"  # 已取消


class VrSettlement(BaseModel):
    """VR编辑费用结算单表"""

    __tablename__ = "vr_settlements"

    settlement_no: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    customer_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("customers.id"), index=True
    )
    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    total_amount: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False)
    discount_amount: Mapped[Decimal | None] = mapped_column(DECIMAL(12, 2), default=0)
    discount_reason: Mapped[str | None] = mapped_column(Text)
    discount_attachment: Mapped[str | None] = mapped_column(String(255))
    # final_amount = total_amount - discount_amount（计算字段，不落库）
    status: Mapped[str | None] = mapped_column(String(30), default="draft", index=True)
    # 减免提交/审批（减免审批由销售主管在审批节点一并完成）
    discount_applied_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    discount_approver_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    discount_approved_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    discount_approval_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 客服主管审批
    cs_supervisor_confirmed_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    cs_supervisor_confirmed_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 销售审批（客户指定销售本人）
    sales_confirmed_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    sales_confirmed_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 销售主管审批（含减免一并审批）
    sales_supervisor_confirmed_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    sales_supervisor_confirmed_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 客户确认
    customer_confirmed_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    customer_confirmed_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    # 完成结算（扣款成功）
    completed_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    completed_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    # 取消
    cancelled_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cancelled_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    # 结算明细文件（创建时用户上传，存 /files/upload 返回路径）
    detail_file_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    detail_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # 创建方式：手动创建=False；自动创建（待开发）上线后为 True
    is_auto_generated: Mapped[bool | None] = mapped_column(Boolean, default=False)
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)

    customer = relationship("Customer", foreign_keys=[customer_id], lazy="selectin")

    __table_args__ = (
        Index("idx_vr_settlement_customer_period", "customer_id", "period_start", "period_end"),
        Index("idx_vr_settlement_status_period", "status", "period_start"),
    )


class VrSettlementDiscountHistory(BaseModel):
    """VR结算单减免修改历史表（每次提交/修改减免插一条，照抄 InvoiceDiscountHistory）"""

    __tablename__ = "vr_settlement_discount_histories"

    settlement_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("vr_settlements.id", ondelete="CASCADE"), index=True, nullable=False
    )
    discount_amount: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False)
    discount_reason: Mapped[str | None] = mapped_column(Text)
    discount_attachment: Mapped[str | None] = mapped_column(String(255))
    applied_at: Mapped[str] = mapped_column(String(50), nullable=False)
    applied_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )

    __table_args__ = (
        Index("idx_vr_discount_history_settlement", "settlement_id", "applied_at"),
    )
```

（`status` 列宽 `String(30)`：`pending_sales_supervisor` 为 26 字符，超出 String(20)，与 `invoices.status` 同宽。）

**步骤 1.2 修改 `backend/app/models/billing.py`**：`ConsumptionRecord` 类（约 220-229 行）内新增一个字段（其余不动）：

```python
    vr_settlement_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("vr_settlements.id"), nullable=True, index=True
    )
```

**步骤 1.3 修改 `backend/app/models/__init__.py`**：在 `from . import billing` 后加 `from . import vr_settlement  # noqa: E402`，`__all__` 加 `"vr_settlement"`。

**步骤 1.4 新建迁移 `backend/alembic/versions/d0e1f2a3b4c5_add_vr_settlements.py`**：
- `revision = "d0e1f2a3b4c5"`，`down_revision = "c9d0e1f2a3b4"`（当前 head，已核实）。
- `upgrade()`：
  1. `op.create_table("vr_settlements", ...)`——列与步骤 1.1 模型一一对应（`id` Integer 自增主键；`created_at`/`updated_at` `server_default=sa.func.now()`；`deleted_at` nullable；`settlement_no` unique），建索引 `ix_vr_settlements_settlement_no`（unique 列随表建）、`idx_vr_settlement_customer_period`、`idx_vr_settlement_status_period`。
  2. `op.create_table("vr_settlement_discount_histories", ...)` + 索引 `idx_vr_discount_history_settlement`。
  3. `op.add_column("consumption_records", sa.Column("vr_settlement_id", sa.Integer(), sa.ForeignKey("vr_settlements.id"), nullable=True, comment="关联VR结算单"))` + `op.create_index("idx_consumption_records_vr_settlement_id", "consumption_records", ["vr_settlement_id"])`。
  4. 幂等插入 8 个权限码并关联超级管理员——照抄 `a7b8c9d0e1f2_add_invoice_multi_role_approval.py:70-103` 的 `INSERT ... ON CONFLICT (code) DO NOTHING` + `INSERT INTO role_permissions SELECT ... WHERE r.name = '超级管理员' ... AND NOT EXISTS(...)` 两段 SQL，码值见阶段 2。
- `downgrade()`：删 role_permissions 关联 → 删 8 个 permissions 行 → drop index+column `consumption_records.vr_settlement_id` → drop `vr_settlement_discount_histories` → drop `vr_settlements`。

### 阶段 2：权限码与预置角色

**步骤 2.1 修改 `backend/scripts/seed.py`**：
- `ALL_PERMISSIONS`（44 行起）在 billing 组之后追加新组：

```python
    # ============================================================
    # VR编辑费用结算 (8)
    # ============================================================
    ("vr_settlement:view", "查看VR结算", "查看VR编辑费用结算单列表与详情", "vr_settlement"),
    ("vr_settlement:create", "创建VR结算单", "手动创建VR结算单并提交审批", "vr_settlement"),
    ("vr_settlement:edit", "编辑VR结算单", "提交/修改减免、取消VR结算单", "vr_settlement"),
    ("vr_settlement:delete", "删除VR结算单", "删除VR结算单", "vr_settlement"),
    ("vr_settlement:cs_approve", "客服主管审批", "客服主管审批VR结算单（第一步）", "vr_settlement"),
    ("vr_settlement:sales_approve", "销售审批", "客户指定销售审批VR结算单（第二步）", "vr_settlement"),
    ("vr_settlement:sales_supervisor_approve", "销售主管审批", "销售主管审批VR结算单（第三步，含减免一并审批）", "vr_settlement"),
    ("vr_settlement:confirm", "客户确认VR结算单", "客户确认并自动扣款完成结算", "vr_settlement"),
```

- `PRESET_ROLES`（185 行起）：运营经理权限列表追加 `"vr_settlement:view", "vr_settlement:create", "vr_settlement:edit", "vr_settlement:confirm"`；销售经理权限列表追加 `"vr_settlement:view", "vr_settlement:sales_approve"`；字典末尾追加两个新角色：

```python
    "客服主管": (
        "负责客服团队，可审批VR编辑费用结算单（第一步）",
        [
            "vr_settlement:view",
            "vr_settlement:cs_approve",
        ],
    ),
    "销售主管": (
        "负责销售团队，可审批VR编辑费用结算单（第三步，含减免一并审批）",
        [
            "vr_settlement:view",
            "vr_settlement:sales_supervisor_approve",
        ],
    ),
```

**步骤 2.2 修改 `backend/tests/_test_data.py`**：`PERMISSION_ROWS` 追加同样 8 个码（`(code, name, description, module)` 四元组，与 seed 一致），保证 drift 测试与 mock 权限全覆盖。

**步骤 2.3 执行同步**（实现后验证步骤，非计划决策）：`cd backend && .venv/bin/python scripts/seed.py --sync-permissions`（幂等 upsert + 预置角色只增不删 + 失效权限缓存）。

### 阶段 3：服务层 `backend/app/services/vr_settlement.py`（新建）

`class VrSettlementService`，构造 `def __init__(self, db: AsyncSession)`。方法签名与状态机规则（每个流转方法返回 `tuple[bool, str]`，失败消息为精确字面量）：

| 方法 | 允许状态 | 行为与校验 |
|---|---|---|
| `create_settlement(customer_id, period_start, period_end, total_amount, detail_file_path, detail_file_name, created_by) -> VrSettlement` | — | 生成 `settlement_no = f"VR-{cst_today().strftime('%Y%m%d')}-{customer_id}-{random_code}"`（`random_code = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))`，照抄 `billing.py:1389-1394` 的 Invoice 编号规则）；`status="draft"`、`discount_amount=Decimal(0)`、`is_auto_generated=False`；`await self.db.commit()` 后返回 |
| `get_settlements(keyword=None, status=None, customer_id=None, mine_user_id=None, page=1, page_size=20, sort_by="created_at", sort_order="desc") -> tuple[list[VrSettlement], int]` | — | JOIN Customer；`keyword` 对 `Customer.name`/`settlement_no` 做 `ilike`；`mine_user_id` 非空时追加 `or_(Customer.manager_id == uid, Customer.sales_manager_id == uid)`（照抄 `billing.py:1487-1492`）；`sort_by ∈ {created_at, total_amount, settlement_no}`，非法值静默回退 `created_at` |
| `get_settlement_by_id(settlement_id) -> VrSettlement \| None` | — | `selectinload(customer)`，过滤 `deleted_at.is_(None)` |
| `get_discount_histories(settlement_id) -> list[VrSettlementDiscountHistory]` | — | 按 `applied_at` 升序 |
| `submit_settlement(settlement_id, user_id)` | `{draft}` | 校验 `customer.sales_manager_id` 非空，否则 `(False, "该客户未指定销售经理，无法提交审批")`；置 `pending_cs_supervisor` |
| `confirm_cs_supervisor(settlement_id, user_id)` | `{pending_cs_supervisor}` | 写 `cs_supervisor_confirmed_by/at`（`cst_now().strftime("%Y-%m-%d %H:%M:%S")`）→ `pending_sales` |
| `confirm_sales(settlement_id, user_id)` | `{pending_sales}` | **身份校验** `customer.sales_manager_id != user_id` → `(False, "您不是该客户指定的销售，无权确认")`（照抄 `billing.py:1821-1823`）；写 `sales_confirmed_by/at` → `pending_sales_supervisor` |
| `confirm_sales_supervisor(settlement_id, user_id, comment=None)` | `{pending_sales_supervisor}` | 写 `sales_supervisor_confirmed_by/at`；**若 `discount_amount != 0`**：写 `discount_approver_id=user_id`、`discount_approved_at`、`discount_approval_comment=comment`（一并审批通过）；→ `pending_customer` |
| `reject_sales_supervisor(settlement_id, user_id, comment)` | `{pending_sales_supervisor}` | `comment` 空由路由层 400 拦截；退回 `pending_sales`（销售重新确认后可再次提交审批；减免保持待审批状态不变） |
| `apply_discount(settlement_id, discount_amount, discount_reason, discount_attachment, user_id)` | `{draft, pending_cs_supervisor, pending_sales, pending_sales_supervisor}` | `discount_amount == 0` → `(False, "减免金额不能为 0")`；写 `discount_amount/discount_reason/discount_attachment/discount_applied_at`；插一条 `VrSettlementDiscountHistory`；commit |
| `confirm_customer(settlement_id, user_id)` | `{pending_customer}` | 先落库 `customer_confirmed` + `customer_confirmed_by/at` 并 commit，再调 `_execute_deduction`（照抄 `billing.py:1838-1860`） |
| `_execute_deduction(settlement) -> tuple[bool, str]` | 内部 | `final_amount = settlement.total_amount - (settlement.discount_amount or 0)`；调 `BalanceService(self.db).consume(customer_id=settlement.customer_id, amount=final_amount, vr_settlement_id=settlement.id)`；成功 → `status="completed"` + `completed_at/completed_by` + commit，返回 `(True, "客户确认成功，已自动完成扣款")`；失败保持 `customer_confirmed`，返回 `(True, f"客户确认成功，但扣款失败：{msg}")`；`OperationalError` 降级 `(True, "客户确认成功，但扣款失败：数据库繁忙，请稍后重试")`（照抄 `billing.py:1884-1921`） |
| `retry_deduction(settlement_id, user_id)` | `{customer_confirmed}` | 重新 `_execute_deduction` |
| `cancel_settlement(settlement_id, user_id)` | `{draft, pending_cs_supervisor, pending_sales, pending_sales_supervisor, pending_customer}` | 写 `cancelled_at/cancelled_by` → `cancelled` |
| `delete_settlement(settlement_id)` | 任意 | 软删除 `deleted_at = cst_now()`（照抄 `billing.py:1954-1963`） |

所有状态不匹配统一返回 `(False, f"当前状态（{settlement.status}）不允许该操作")`；settlement 不存在返回 `(False, "结算单不存在")`。

**步骤 3.2 修改 `backend/app/services/billing.py` 的 `BalanceService.consume`（222-343 行）**：签名增加关键字参数 `vr_settlement_id: Optional[int] = None`，`ConsumptionRecord(...)` 构造（约 319-327 行）增加 `vr_settlement_id=vr_settlement_id`。其余逻辑（`in_transaction()` 收敛、tenacity 3 次重试、`with_for_update()` 行级锁、先赠后实、`balance_after`）零改动——VR 扣款完全复用该实现，满足「统一使用余额进行结算」与行级锁硬规则。

### 阶段 4：路由层 `backend/app/routes/billing/vr_settlements.py`（新建）

文件头部照抄 `invoices.py:1-45` 的导入块（`sanic.response.json`、`ErrorCodes`、`auth_required/customer_scope_user_id/get_current_user/require_permission`、`cache_service`、`create_audit_entry`、`cst_now`、`local_date_range_to_utc`），蓝图用 `from . import billing_bp`。模块内新增两个私有助手（照抄 `invoices.py:58-72` 的 `_ensure_invoice_scope` 与 440-458 行的客户 scope 检查）：

```python
async def _ensure_settlement_scope(request: Request, settlement: Any) -> Any | None:
    """数据可见性：无 customers:view_all 时，非本人负责客户的结算单拒绝访问。"""
async def _ensure_customer_scope(request: Request, customer: Any) -> Any | None:
    """创建前客户可见性校验。"""
```

端点表（前缀 `/api/v1/billing/vr-settlements`；装饰器顺序均为 `@billing_bp.<m>(path)` → `@auth_required` → `@require_permission(...)`）：

| # | method + path | 权限码 | 行为 |
|---|---|---|---|
| 1 | `GET /vr-settlements` | `vr_settlement:view` | query：`keyword/status/customer_id/page/page_size/sort_by/sort_order`；`status` 非法值 400「无效的状态值，有效值：…」（照抄 invoices.py:1737-1744）；`mine_user_id = await customer_scope_user_id(request)`；响应 `data.list[]` 字段：`id, settlement_no, customer_id, customer_name, customer_manager_id, customer_sales_manager_id, period_start, period_end, total_amount, discount_amount, final_amount, status, detail_file_path, detail_file_name, created_at` + `total/page/page_size` |
| 2 | `GET /vr-settlements/<settlement_id:int>` | `vr_settlement:view` | 404「结算单不存在」；scope 403「无权访问该结算单」；响应追加：`discount_reason, discount_attachment, discount_applied_at, discount_approver_id, discount_approved_at, discount_approval_comment, cs_supervisor_confirmed_by/at, sales_confirmed_by/at, sales_supervisor_confirmed_by/at, customer_confirmed_at/by, completed_at/by, cancelled_at/by, created_by, is_auto_generated, discount_history[]`，以及各 `*_by` 操作人姓名（批量查 users，照抄 invoices.py:228-240） |
| 3 | `POST /vr-settlements` | `vr_settlement:create` | body `{customer_id, period_start: "YYYY-MM-DD", period_end, total_amount, detail_file_path, detail_file_name}`。校验：缺 `customer_id` → 400 `MISSING_PARAMETER`「客户 ID 不能为空」；缺 `detail_file_path` → 400「请上传结算明细文件」；`total_amount` 缺失/≤0/非数 → 400「结算金额必须大于 0」；客户不存在 → 404；客户 scope → 403「无权访问该客户」；日期经 `local_date_range_to_utc`，`ValueError` → 400「日期格式错误，应为 YYYY-MM-DD」。成功 201 `{id, settlement_no, total_amount}` |
| 4 | `POST /vr-settlements/<id>/submit` | `vr_settlement:create` | `submit_settlement`；400 透传 message |
| 5 | `POST /vr-settlements/<id>/confirm-cs` | `vr_settlement:cs_approve` | `confirm_cs_supervisor` |
| 6 | `POST /vr-settlements/<id>/confirm-sales` | `vr_settlement:sales_approve` | `confirm_sales` |
| 7 | `POST /vr-settlements/<id>/confirm-sales-supervisor` | `vr_settlement:sales_supervisor_approve` | body `{comment?}`；`confirm_sales_supervisor` |
| 8 | `POST /vr-settlements/<id>/reject-sales-supervisor` | `vr_settlement:sales_supervisor_approve` | `comment` 空 → 400「驳回必须填写理由」（照抄 invoices.py:1393-1394）；`reject_sales_supervisor` |
| 9 | `PUT /vr-settlements/<id>/discount` | `vr_settlement:edit` | body `{discount_amount, discount_reason, discount_attachment}`；`apply_discount` |
| 10 | `POST /vr-settlements/<id>/confirm` | `vr_settlement:confirm` | `confirm_customer` |
| 11 | `POST /vr-settlements/<id>/retry-deduction` | `vr_settlement:confirm` | `retry_deduction` |
| 12 | `POST /vr-settlements/<id>/cancel` | `vr_settlement:edit` | `cancel_settlement` |
| 13 | `DELETE /vr-settlements/<id>` | `vr_settlement:delete` | `delete_settlement`（软删除） |

每个端点统一模式（照抄 invoices.py:1061-1130 的 submit 端点）：`get_current_user` 取 `user_id`（无则 401）→ 先查 settlement（404）→ `_ensure_settlement_scope`（403）→ 调 service → `(False, msg)` 时 `json({"code": 40001, "message": msg}, status=400)` → 成功后 `await cache_service.invalidate_billing_cache()` → 返回 `{"code": 0, "message": ..., "data": {...}}`。

**手动审计**：端点 4-8、10-12 共 8 个动作端点在成功后调 `create_audit_entry(db_session=db, user_id=user_id, action=<见下>, module="billing", record_id=settlement_id, record_type="vr_settlement", changes={"before": {...}, "after": {...}}, operation_type="standard", auto_commit=True)`（照抄 invoices.py:1237-1256）。action 字面量：`submit_vr_settlement` / `confirm_cs_supervisor` / `confirm_sales` / `confirm_sales_supervisor` / `reject_sales_supervisor` / `confirm_vr_settlement` / `retry_vr_deduction` / `cancel_vr_settlement`。端点 3/9/13 由审计中间件自动记录（与 invoices 的 generate/discount/delete 一致）。

**步骤 4.2 修改 `backend/app/routes/billing/__init__.py`**：末行导入加 `vr_settlements`：

```python
from . import balances, imports, invoices, packages, pricing, vr_settlements  # noqa: E402, F401
```

**步骤 4.3 修改 `backend/app/middleware/audit.py`**（约 87-91 行 invoices 跳过块之后）追加：

```python
            # VR结算单动作端点：只跳过状态变更端点（与 invoices 一致，手动审计）
            if request.path.startswith("/api/v1/billing/vr-settlements/"):
                action_endpoints = (
                    "/submit",
                    "/confirm-cs",
                    "/confirm-sales",
                    "/confirm-sales-supervisor",
                    "/reject-sales-supervisor",
                    "/confirm",
                    "/retry-deduction",
                    "/cancel",
                )
                if any(request.path.endswith(action) for action in action_endpoints):
                    return
```

### 阶段 5：前端

**步骤 5.1 新建 `frontend/src/api/vrSettlement.ts`**（照抄 `api/billing.ts` 模式，`import api from './index'`，baseURL 已是 `/api/v1`）：

```ts
export type VrSettlementStatus =
  | 'draft' | 'pending_cs_supervisor' | 'pending_sales' | 'pending_sales_supervisor'
  | 'pending_customer' | 'customer_confirmed' | 'completed' | 'cancelled'

export interface VrSettlementDiscountHistory {
  id: number; discount_amount: number; discount_reason: string | null
  discount_attachment: string | null; applied_at: string; applied_by: number | null
  applied_by_name?: string | null
}

export interface VrSettlement {
  id: number; settlement_no: string; customer_id: number | null; customer_name: string | null
  customer_manager_id: number | null; customer_sales_manager_id: number | null
  period_start: string; period_end: string
  total_amount: number; discount_amount: number; final_amount: number
  discount_reason?: string | null; discount_attachment?: string | null
  discount_applied_at?: string | null; discount_approver_id?: number | null
  discount_approved_at?: string | null; discount_approval_comment?: string | null
  status: VrSettlementStatus
  cs_supervisor_confirmed_by?: number | null; cs_supervisor_confirmed_at?: string | null
  sales_confirmed_by?: number | null; sales_confirmed_at?: string | null
  sales_supervisor_confirmed_by?: number | null; sales_supervisor_confirmed_at?: string | null
  customer_confirmed_at?: string | null; customer_confirmed_by?: number | null
  completed_at?: string | null; completed_by?: number | null
  cancelled_at?: string | null; cancelled_by?: number | null
  detail_file_path: string | null; detail_file_name: string | null
  is_auto_generated?: boolean; created_at: string
  discount_history?: VrSettlementDiscountHistory[]
}

export interface CreateVrSettlementParams {
  customer_id: number; period_start: string; period_end: string
  total_amount: number; detail_file_path: string; detail_file_name: string
}

export function getVrSettlements(params?: { keyword?: string; status?: string; customer_id?: number; page?: number; page_size?: number; sort_by?: string; sort_order?: string })
export function getVrSettlement(id: number)
export function createVrSettlement(data: CreateVrSettlementParams)          // POST /billing/vr-settlements
export function submitVrSettlement(id: number)                             // POST .../submit
export function confirmCsSupervisor(id: number)                            // POST .../confirm-cs
export function confirmSales(id: number)                                   // POST .../confirm-sales
export function confirmSalesSupervisor(id: number, comment?: string)       // POST .../confirm-sales-supervisor
export function rejectSalesSupervisor(id: number, comment: string)         // POST .../reject-sales-supervisor
export function applyVrDiscount(id: number, data: { discount_amount: number; discount_reason: string; discount_attachment?: string | null })  // PUT .../discount
export function confirmVrSettlement(id: number)                            // POST .../confirm
export function retryVrDeduction(id: number)                               // POST .../retry-deduction
export function cancelVrSettlement(id: number)                             // POST .../cancel
export function deleteVrSettlement(id: number)                             // DELETE .../:id
```

明细 Excel 上传**复用** `frontend/src/api/billing.ts:532-536` 已有的 `uploadDiscountAttachment(file)`（本质是 `POST /files/upload` 通用包装，返回 `data.file_path`），不新建上传函数。

**步骤 5.2 新建 `frontend/src/constants/vrSettlementStatus.ts`**（照抄 `constants/invoiceStatus.ts` 64 行全文结构）：

```ts
export const VR_SETTLEMENT_STATUS_MAP: Record<string, string> = {
  draft: '草稿',
  pending_cs_supervisor: '待客服主管审批',
  pending_sales: '待销售审批',
  pending_sales_supervisor: '待销售主管审批',
  pending_customer: '待客户确认',
  customer_confirmed: '客户已确认',
  completed: '已完成',
  cancelled: '已取消',
}
export const VR_SETTLEMENT_STATUS_CLASS_MAP: Record<string, string> = {
  draft: 'gray', pending_cs_supervisor: 'amber', pending_sales: 'amber',
  pending_sales_supervisor: 'amber', pending_customer: 'orange',
  customer_confirmed: 'blue', completed: 'green', cancelled: 'red',
}
export function getVrSettlementStatusLabel(status: string): string  // 未知值兜底返回原值
export function getVrSettlementStatusColor(status: string): string  // 未知值兜底 'gray'
export const VR_SETTLEMENT_STATUS_OPTIONS  // Object.entries 映射 {label, value}，供筛选下拉
```

**步骤 5.3 新建 `frontend/src/composables/useVrSettlement.ts`**（照抄 `composables/useInvoice.ts`，**去掉**文件状态轮询相关全部逻辑）：状态 `loading/invoices/total/currentDetail/filters({keyword:'', status:'', customer_id:null})/pagination(current:1, pageSize:20, options:[10,20,50,100])/selectedIds/hasSelected`；方法 `loadVrSettlements/fetchVrDetail/handlePageChange/handlePageSizeChange/handleSortChange/handleSearch/handleReset/doCreate/doSubmit/doConfirmCs/doConfirmSales/doConfirmSalesSupervisor/doRejectSalesSupervisor/doApplyDiscount/doConfirm/doRetryDeduction/doCancel/doDelete/handleBatchSelect/handleBatchSelectAll/clearSelection`。每个动作方法内联 `Message.success/error` 后 re-throw（照抄 useInvoice 约定）；`errorMessage(err, fallback)` 从拦截器 reject 对象提取 message。

**步骤 5.4 新建 `frontend/src/views/billing/VrSettlements.vue`**（照抄 `Invoices.vue` 结构，约 900 行同构）：
- `PageHeader`（eyebrow="Billing" title="VR编辑费用结算"），右上「创建结算单」primary 按钮 `v-if="can('vr_settlement:create')"` → 打开 `VrSettlementCreateModal`。
- 筛选行内联在页面（不建 Filters 组件）：`a-input` 关键词（结算单号/客户名，回车触发）+ `FilterDropdown`（`@/components/ui/FilterDropdown.vue`）状态筛选（`VR_SETTLEMENT_STATUS_OPTIONS`）+ `CustomerAutoComplete`（`@/components/CustomerAutoComplete.vue`，v-model number|undefined）+ 查询/重置按钮。
- `DataTable`（`@/components/DataTable.vue`，`type DataTableColumn`）：列 `settlement_no`(214, sortable) / `customer_name`(180, ellipsis+tooltip) / `period`(190) / `total_amount`(104, right) / `discount_amount`(76, right) / `final_amount`(110, right) / `detail_file`(108, center) / `status`(78) / `created_at`(158, sortable) + 操作列(174, fixed right)；`:scroll="{ x: 1442 }"`（= 40 选择列 + 1218 数据列 + 174 操作列 + 10 列×1px 边框，与现有结算单页实测口径一致）；`:storage-key="'vr_settlements_table_columns'"`；`row-key="id"`；分页配置同 Invoices.vue。`discount_amount` 展示规则照抄（>0 红 `-¥x`、<0 绿 `+¥x`、0 显示 `-`）。`detail_file` 列：`detail_file_path` 非空渲染 `<a :href="record.detail_file_path" target="_blank">📄</a>`（上传文件走静态 `/uploads/` 路由，与现有附件下载方式一致），否则 `-`。`status` 列用常量渲染 `<span class="tag">`（内联，不建 Badge 组件）。
- 操作列按钮规则（`#action` slot，照抄 Invoices.vue:192-251 与 334-348 的身份校验）：

| 状态 | 按钮 | 条件 |
|---|---|---|
| `draft` | 提交 | `can('vr_settlement:create')` |
| `draft`/`pending_cs_supervisor`/`pending_sales`/`pending_sales_supervisor` | 设置减免/修改减免 | `can('vr_settlement:edit')` → 打开 `VrSettlementDiscountModal` |
| `pending_cs_supervisor` | 客服主管审批 | `can('vr_settlement:cs_approve')` |
| `pending_sales` | 销售审批 | `can('vr_settlement:sales_approve')` 且 `currentUserId === record.customer_sales_manager_id`；不满足时禁用 + tooltip「您不是该客户指定的销售，无法确认」/「该客户尚未指定销售，无法确认」 |
| `pending_sales_supervisor` | 审批通过 / 审批驳回 | `can('vr_settlement:sales_supervisor_approve')` → 打开 `VrSettlementApprovalModal`（mode approve/reject） |
| `pending_customer` | 客户确认 | `can('vr_settlement:confirm')` |
| `customer_confirmed` | 重试扣款 | `can('vr_settlement:confirm')`，Modal.confirm 文案含 `formatCurrency(record.final_amount)` |
| 上述全部非终态 | 取消 | `can('vr_settlement:edit')`，Modal.confirm |
| `draft` | 删除（danger） | `can('vr_settlement:delete')`，Modal.confirm |

- 行点击开 `VrSettlementDetailDrawer`；页面尾部挂 4 个组件（CreateModal / DiscountModal / ApprovalModal / DetailDrawer）。

**步骤 5.5 新建 `frontend/src/views/billing/components/VrSettlementCreateModal.vue`**（625 行 GenerateInvoiceModal 的精简版）：
- props `{ visible: boolean }`；emits `update:visible`、`success`。
- 顶部创建方式 `a-radio-group v-model="form.create_mode"`：选项「手动创建」`value="manual"`；选项「自动创建」`value="auto"` **`disabled`** 且 label 后挂 `<a-tag size="small" color="gray">待开发</a-tag>`。自动模式选中时不可能发生（disabled），表单区整体 `v-if="form.create_mode === 'manual'"`。
- 表单（`a-form` + 校验规则）：客户 `CustomerAutoComplete` v-model `form.customer_id`（必填）；结算周期 `a-range-picker` v-model `periodRange`，change 写 `form.period_start/period_end`（必填）；结算金额 `a-input-number` `precision=2` `min=0.01`（必填，validator 拒绝 ≤0）；结算明细文件 `a-upload` `:auto-upload="false"` `:limit="1"` `accept=".xlsx,.xls"`（必填，validator：fileList 为空报「请上传结算明细文件」）。
- 提交（`@before-ok="handleSubmit"` 返回 false 阻止关闭）：若 fileList 有新 File → `await uploadDiscountAttachment(file)` 取 `res.data.file_path`（失败 `Message.error` 并中止）→ `createVrSettlement({customer_id, period_start, period_end, total_amount, detail_file_path, detail_file_name: file.name})` → 成功 `Message.success('创建成功')` + emit success + close。
- watch `props.visible` 打开时重置表单（保留无状态）。

**步骤 5.6 新建 `frontend/src/views/billing/components/VrSettlementDiscountModal.vue`**（照抄 `DiscountEditModal.vue` 189 行）：props `{ visible, settlementId?, currentDiscount?, currentReason?, currentAttachment? }`；字段 `discount_amount`（`a-input-number` precision 2，validator：0 报「减免金额不能为 0」）、`reason`（有金额时必填）、`attachment`（a-upload limit 1 auto-upload=false accept `.pdf,.jpg,.png,.xlsx,.xls`，提交时先 `uploadDiscountAttachment` 拿 path）；提交 `applyVrDiscount(...)`。

**步骤 5.7 新建 `frontend/src/views/billing/components/VrSettlementApprovalModal.vue`**（照抄 `DiscountApprovalModal.vue` 109 行）：props `{ visible, settlementId?, mode: 'approve' | 'reject', discountAmount?, discountReason? }`；标题「销售主管审批通过」/「销售主管审批驳回」；当 `discountAmount` 非空时顶部只读展示「待一并审批的减免：¥X（原因）」；唯一输入 `comment`（a-textarea max 500 show-word-limit；reject 必填「驳回必须填写理由」，approve 选填 placeholder「可填写审批意见」）；提交 `confirmSalesSupervisor(id, comment)` / `rejectSalesSupervisor(id, comment)`。

**步骤 5.8 新建 `frontend/src/views/billing/components/VrSettlementDetailDrawer.vue`**（照抄 `InvoiceDetailDrawer.vue` 子集）：
- `a-descriptions` 展示详情全部字段（金额用 `formatCurrency`，时间用 `formatDateTime`，周期 `formatDate(start) ~ formatDate(end)`）。
- `a-steps` 6 步：创建 → 客服主管审批 → 销售审批 → 销售主管审批 → 客户确认 → 已完成。映射（1-based，照抄 InvoiceDetailDrawer.vue:407-432 语义）：`draft:1, pending_cs_supervisor:2, pending_sales:3, pending_sales_supervisor:4, pending_customer:5, customer_confirmed:6, completed:6, cancelled:1`；`customer_confirmed` 时步骤状态 `error` + 描述「扣款失败，待重试」；`cancelled` 整体 error 态。
- 减免区：`discount_amount !== 0` 时展示金额/原因/附件链接/审批结果（审批人+时间+意见）；`discount_history` 列表（时间、金额、原因、操作人）。
- 明细文件下载链接（`detail_file_path` 静态 URL，`detail_file_name` 为显示名）。
- 操作按钮区：与列表一致的状态×权限×身份规则（`can('vr_settlement:edit')` 包取消/删除/减免，`can('vr_settlement:confirm')` 包确认/重试）。

**步骤 5.8.1 详情抽屉整体样式与「结算单管理」详情保持一致（单一来源）**：

两个详情抽屉（`VrSettlementDetailDrawer` / `InvoiceDetailDrawer`）的抽屉级公共样式**只允许在
`frontend/src/styles/detail-drawer.css` 定义一次**，各自在 `<style scoped>` 顶部 `@import "@/styles/detail-drawer.css";`。
公共类清单：`.drawer-content`（gap 24px）、`.detail-title`（gap 12px）+ `h2`（20px/700/var(--ink)）、
`.flow-steps`（#f8fafc + 1px #e2e8f0 + radius 12px + padding 16px 20px 6px）、`.flow-cancelled`（padding 16px 20px）、
`.section-header`（flex/space-between + margin-bottom 12px）+ `h3`（16px/600）、`.amount-final`（16px/700）、
`.text-danger`/`.text-success`、`.attachment-link`（含下划线）、`.subtle`（var(--muted)）、
`.action-section`（flex-end + gap 8px + padding-top 16px + 1px var(--line)）、`.btn` 全系列（padding 9px 16px + transition）。

- `:deep(.arco-steps*)` 三条（steps padding 4px 0、title 13px、description 12px/100px/ellipsis/nowrap）**不能**放进共享文件
  （SFC 编译期语法，@import 内联顺序不可靠），各组件内联保留。
- 组件特有规则留在各自文件：VR 的 `.remark-text`；Invoice 的表格/`.amount`/`.pricing-*`/`.btn.btn-sm` 等。
- 已实测：Vite 会把 scoped 块内 `@import` 的规则内联并加 scope id（CSSOM 中全部带 `[data-v-*]`，0 条泄漏为全局）。
- 验收：两抽屉同一组元素 computed style 逐项 diff 输出 `none — 完全一致`（详见
  `.trellis/spec/frontend/component-guidelines.md`「平行详情页外观一致性」）。
- 减免历史区使用共享组件 `frontend/src/components/common/DiscountHistoryTable.vue`（自带标题与容器外观），
  父组件不再包裹 `.detail-section`/`.section-header`。

**步骤 5.9 修改 `frontend/src/router/index.ts`**（billing children，invoices 之后约 71 行处插入）：

```ts
    {
      path: 'vr-settlements',
      name: 'VrSettlements',
      component: () => import('@/views/billing/VrSettlements.vue'),
      meta: { requiresPermission: 'vr_settlement:view' },
    },
```

**步骤 5.10 修改 `frontend/src/composables/useAppLayout.ts`**：
- `navSections` billing children 的 `invoices` 项之后插入：`{ key: 'vr-settlements', label: 'VR编辑费用结算', to: '/billing/vr-settlements', permission: 'vr_settlement:view' }`。
- `pageTitle` 的 routeMap（约 201-215 行）加 `VrSettlements: 'VR编辑费用结算'`。

**步骤 5.11 修改 `frontend/src/components/layout/AppSidebar.vue`**（约 150-157 行「结算单管理」button 之后）插入同构按钮：

```vue
          <button
            v-if="can('vr_settlement:view')"
            class="nav-btn sub"
            :class="{ active: $route.name === 'VrSettlements' }"
            @click="goTo('/billing/vr-settlements')"
          >
            VR编辑费用结算
          </button>
```

（`isSubmenuActive('billing')` 按 `/billing` 前缀匹配，新路由自动获得父菜单高亮，无需改判定逻辑。）

**步骤 5.12 修改 `frontend/src/views/roles/permissionGroups.ts`**：`MODULE_NAME_MAP` 加 `vr_settlement: 'VR编辑费用结算'`；`MODULE_ORDER` 在 `'billing'` 之后插入 `'vr_settlement'`。

### 阶段 6：测试

**步骤 6.1 修改 `backend/tests/integration/conftest.py`**：`db_session` 的 TRUNCATE 列表（约 327-343 行）加入 `vr_settlement_discount_histories, vr_settlements`（放在 `invoices` 前，保证 CASCADE 顺序无关）。

**步骤 6.2 新建 `backend/tests/integration/test_vr_settlement_api.py`**（照抄 `test_billing_api.py` 的 fixture 与写法，`@pytest.mark.asyncio` + `test_client`/`auth_token`）。fixture：`test_customer` 照抄 test_billing_api.py:31-104（raw SQL 造客户）并扩展为同时写 `sales_manager_id`（正值用例设为 admin 用户 id：`SELECT id FROM users WHERE username='admin'`；负值用例设 999999）；`test_customer_with_balance` 照抄 106 行起（造 `customer_balances` 行，如 total/real/bonus=1000）。用例（每个都是可观察断言，非 merely not-throw）：

1. `test_create_and_full_approval_flow`：`POST /vr-settlements`（带 `detail_file_path="/uploads/2026/11/test.xlsx"`、`total_amount=500`）→ 201 且 `settlement_no` 以 `VR-` 开头；`GET` 详情 `status=draft`、`final_amount=500`；submit → `pending_cs_supervisor`；confirm-cs → `pending_sales`；confirm-sales → `pending_sales_supervisor`；confirm-sales-supervisor（带 comment）→ `pending_customer`；confirm → `completed`。**断言余额**：`customer_balances` 该客户 `used_total=500`、`total_amount=500`（1000-500）；**断言消耗记录**：`consumption_records` 存在一行 `amount=500, vr_settlement_id=<id>, balance_after=500`。
2. `test_discount_approved_together_at_sales_supervisor`：create(1000) → draft 时 `PUT /discount`（100，「大客户优惠」）→ 201/200 且历史表多一行；submit → confirm-cs → confirm-sales → confirm-sales-supervisor(comment="同意减免") → 详情断言 `discount_approver_id` 非空、`discount_approved_at` 非空、`discount_approval_comment=="同意减免"`、`final_amount=900`；confirm → completed；断言扣款 900、`balance_after=100`。
3. `test_discount_edit_window`：`pending_customer` 起 `PUT /discount` → 400；`draft`/`pending_cs_supervisor`/`pending_sales`/`pending_sales_supervisor` 可改。
4. `test_reject_requires_comment_and_reverts`：走到 `pending_sales_supervisor` → `POST /reject-sales-supervisor` 无 body → 400「驳回必须填写理由」；带 comment → 200 且状态回 `pending_sales`；再次 confirm-sales 可重新进入 `pending_sales_supervisor`。
5. `test_invalid_state_transitions`：draft 直接 confirm-cs → 400；completed 后 cancel → 400；confirm-sales 在非 pending_sales → 400。
6. `test_sales_identity_check`：客户 `sales_manager_id=999999`（非当前用户）→ confirm-sales → 400「您不是该客户指定的销售，无权确认」。
7. `test_submit_requires_customer_sales_manager`：客户无 `sales_manager_id` → submit → 400「该客户未指定销售经理，无法提交审批」。
8. `test_cancel_and_delete`：draft create → cancel → `cancelled`；再 cancel → 400；新建 draft → DELETE → 204/200，再 GET 详情 → 404。
9. `test_visibility_scope`（可选，若 mock 权限便于构造）：无 `customers:view_all` 用户访问他人客户结算单 → 403。若构造第二用户成本过高，用 `_ensure_settlement_scope` 单测替代（`tests/unit/` 下直接以假 request 对象调用）。

**步骤 6.3 新建 `frontend/src/composables/__tests__/useVrSettlement.test.ts`**（照抄 `useInvoice.test.ts:1-305` 的 mock 结构，`vi.mock('@/api/vrSettlement', ...)` + `vi.mock('@arco-design/web-vue', ...)`）：断言 `handleSortChange` 的 sort_by/sort_order 传递、`handleSearch/handleReset` 重置分页、`doConfirmSales` 等动作调用对应 API 函数。

**步骤 6.4 验证命令**（按序执行，全部通过才算完成）：

```bash
cd backend && .venv/bin/python -m alembic upgrade head
cd backend && .venv/bin/python scripts/check_schema_drift.py
cd backend && .venv/bin/python scripts/seed.py --sync-permissions
cd backend && .venv/bin/python -m pytest tests/unit/ -q          # 含 permission_drift 双向断言
cd backend && .venv/bin/python -m pytest tests/integration/test_vr_settlement_api.py -q
cd backend && .venv/bin/python -m pytest tests/ -q              # 全量 + --cov-fail-under=50（make test-cov）
cd frontend && npx vitest run src/composables/__tests__/useVrSettlement.test.ts
cd frontend && npx vue-tsc --noEmit && npm run build
```

## Critical files & anchors

| 路径 | 锚点 | 说明 |
|---|---|---|
| `backend/app/services/billing.py` | `consume` 222-343、`_execute_deduction` 1884-1921、编号生成 1389-1394、`confirm_sales` 1808-1837 | 扣款（行级锁+重试+先赠后实）、确认后自动扣款、编号规则、销售身份校验的照抄源头 |
| `backend/app/routes/billing/invoices.py` | 端点 1061-1130（submit 全模式）、`_ensure_invoice_scope` 58-72、导入块 1-45 | 新路由文件的完整写法模板（装饰器栈/scope/审计/缓存失效） |
| `backend/app/models/billing.py` | `InvoiceStatus` 28-60、`Invoice` 134-186、`ConsumptionRecord` 220-229 | 新模型对照原型；`ConsumptionRecord` 需加 `vr_settlement_id` |
| `backend/scripts/seed.py` | `ALL_PERMISSIONS` 44-75、`PRESET_ROLES` 185-263 | 8 个新权限码与 2 个新预置角色的唯一声明源 |
| `frontend/src/views/billing/Invoices.vue` | 列定义 394-425、操作按钮 192-251/334-348、`handleSingleAction` 794-909 | 新页面与按钮显隐/身份校验逻辑的照抄原型 |
| `backend/app/middleware/audit.py` | invoices 跳过块 87-91 | VR 动作端点跳过规则插入点（防中间件与手动审计双写） |

## Verification

端到端冒烟（部署迁移与 seed 后，本地起前后端）：

1. 超管登录 → 侧边栏「结算管理」展开 →「结算单管理」下方出现「VR编辑费用结算」→ 点击进入列表页（空列表）。
2. 点「创建结算单」→ 弹窗中「自动创建」单选为禁用态且带「待开发」标签；选客户、周期（如 2026-11-01 ~ 2026-11-30）、金额 500、上传任意 `.xlsx` → 创建成功，列表出现 `draft` 行，`settlement_no` 形如 `VR-20261103-<客户ID>-XXXX`。
3. 提交 → 待客服主管审批；给测试用户授予「客服主管」角色（或超管直接操作）→ 客服主管审批 → 待销售审批；以该客户 `sales_manager_id` 对应用户身份 → 销售审批 → 待销售主管审批。
4. 待销售审批节点先「设置减免」100 元 → 到待销售主管审批时打开「审批通过」弹窗可见减免信息 → 通过 → 待客户确认。
5. 客户确认 → 状态「已完成」；查该客户余额页/`customer_balances`：可用余额减少 400（500-100）、`used_total` +400；`consumption_records` 新增一行 `vr_settlement_id` 指向本单。
6. 驳回路径：另建一单走到待销售主管审批 → 「审批驳回」不填理由被前端拦截 → 填理由提交 → 状态回到「待销售审批」。
7. 明细文件列点击 📄 能下载到上传的 xlsx；取消（任意非终态）与删除（draft）行为符合阶段 5.4 表。
8. 角色权限页「VR编辑费用结算」分组卡片展示 8 个权限码；`pytest tests/unit/test_permission_drift.py -q` 通过（三层引用一致）。
9. 前端 e2e 视觉回归（`frontend/tests/e2e/test_visual_regression.spec.ts`）若因侧边栏新增菜单项导致 `sidebar-*` 快照失败，用 Playwright 快照更新命令重新生成基线快照（属预期变更，非缺陷）。

## Assumptions & contingencies

- **「当前用户余额」解读**：扣减对象为结算客户自身的 `CustomerBalance`（`customer_id`），不使用 Invoice 的 `settlement_account_id` 代扣机制（需求未提及）。若后续需要代扣，按 Invoice 模式加 `settlement_account_id` 快照列即可。
- **销售主管驳回语义**：驳回整单退回「待销售审批」（销售重新确认后再次进入销售主管审批），减免信息保留待重新一并审批。若产品要求「仅驳回减免、节点照过」，需在 `confirm_sales_supervisor` 增加 `discount_approved` 布尔入参拆分两个动作。
- **明细文件不上传解析**：上传的 Excel 仅存档+下载（`detail_file_path`/`detail_file_name`），结算金额由表单填写，不解析文件内容。若要求文件金额与表单金额校验，需在创建接口增加文件解析逻辑（本项目 `utils/excel_import.py` 可复用）。
- **迁移 revision id**：`d0e1f2a3b4c5` 为拟定值；执行时若与现存 id 冲突（`backend/alembic/versions/` 已达 57 个文件），换一个未占用 hex 并保持 `down_revision="c9d0e1f2a3b4"`。
- **客服主管/销售主管为预置角色**：`seed.py --sync-permissions` 幂等创建（只增不删）；管理员可在角色页继续手工调整。既有「运营经理/销售经理」预设权限同步追加（见阶段 2.1），不删除任何既有绑定。
