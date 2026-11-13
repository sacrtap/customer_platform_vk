"""审计日志的可读描述

把存储层结构（``before``/``after`` 对比、扁平业务快照、批量摘要）翻译成中文
变更说明 + 字段对照表，供审计页「查看详情」呈现；原始 JSON 仍原样返回。

设计约束：
- 只做展示层解释，不改审计数据本身（金额、快照、敏感字段值原样保留在 changes 中）。
- 描述必须容忍历史数据：字段可能缺失、类型可能不同（float/str/Decimal）、
  结构可能是 before/after，也可能是扁平键值。
- 未知字段回退为原始键名，不丢弃信息。
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------- 标签表

ACTION_LABELS: Dict[str, str] = {
    "create": "创建",
    "update": "更新",
    "delete": "删除",
    "batch_create": "批量创建",
    "batch_update": "批量更新",
    "batch_delete": "批量删除",
    "batch_recharge": "批量充值",
    "batch_submit": "批量提交",
    "recharge": "客户充值",
    "billing_recharge_revoke": "撤销充值记录",
    "crm_recharge_import": "导入CRM充值",
    "crm_recharge_import_revoke": "撤销CRM充值导入",
    "submit": "提交结算单",
    "confirm": "确认",
    "cancel": "取消",
    "rollback": "回退",
    "submit_vr_settlement": "提交VR结算单",
    "confirm_vr_settlement": "确认VR结算单",
    "cancel_vr_settlement": "取消VR结算单",
    "confirm_cs_supervisor": "客服主管审批通过",
    "confirm_sales": "销售经理确认",
    "confirm_sales_supervisor": "销售主管确认",
    "reject_sales_supervisor": "销售主管驳回",
    "apply_discount": "申请减免",
    "approve_discount": "通过减免",
    "reject_discount": "驳回减免",
    "generate_batch": "批量生成结算单",
    "assign_role": "分配角色",
    "assign_roles": "设置用户角色",
    "assign_permissions": "设置角色权限",
    "reset_password": "重置密码",
    "customer_follow_up": "客户跟进",
    "database_clear": "清空数据",
}

MODULE_LABELS: Dict[str, str] = {
    "billing": "结算",
    "customers": "客户",
    "users": "用户",
    "roles": "角色权限",
    "system": "系统",
    "files": "文件",
    "crm-recharge": "CRM充值",
    "crm_recharge": "CRM充值",
    "tags": "标签",
    "industry-types": "行业类型",
    "analytics": "运营分析",
    "sync-tasks": "同步任务",
    "api-key": "API-Key",
    "balance-whitelist": "余额白名单",
}

RECORD_TYPE_LABELS: Dict[str, str] = {
    "customer": "客户",
    "billing": "结算",
    "recharge": "充值记录",
    "recharge_record": "充值记录",
    "invoice": "结算单",
    "vr_settlement": "VR结算单",
    "pricing_rule": "计费规则",
    "user": "用户",
    "role": "角色",
    "user-role": "用户角色",
    "permission": "权限",
    "file": "文件",
    "tag": "标签",
    "industry-type": "行业类型",
    "industrytype": "行业类型",
    "cooperation-statuse": "合作状态",
    "cooperation-status": "合作状态",
    "crm_setting": "CRM配置",
    "crm-recharge": "CRM充值",
    "api-key": "API-Key",
    "balance-whitelist": "余额白名单",
    "database": "数据库",
    "system": "系统",
}

FIELD_LABELS: Dict[str, str] = {
    # 通用
    "id": "ID",
    "customer_id": "客户ID",
    "company_id": "公司ID",
    "name": "名称",
    "status": "状态",
    "description": "描述",
    "notes": "备注",
    "remark": "备注",
    "reason": "原因",
    "created_at": "创建时间",
    "updated_at": "更新时间",
    "created_by": "创建人",
    "operator_id": "操作人",
    # 客户
    "account_type": "账号类型",
    "price_policy": "计费方式",
    "manager_id": "运营经理",
    "sales_manager_id": "销售经理",
    "settlement_cycle": "结算周期",
    "settlement_type": "结算类型",
    "settlement_group": "结算类型分组",
    "is_key_customer": "重点客户",
    "is_real_estate": "房产客户",
    "email": "邮箱",
    "erp_system": "ERP系统",
    "first_payment_date": "首次回款日期",
    "onboarding_date": "合作开始日期",
    "cooperation_status": "合作状态",
    "is_settlement_enabled": "启用结算",
    "require_reconciliation": "需要核对",
    "is_disabled": "已停用",
    "balance_warning_level": "余额预警等级",
    "balance_warning_updated_at": "预警更新时间",
    "settlement_account_id": "收款账户",
    "crm_customer_id": "CRM客户",
    "scale_level": "规模等级",
    "consume_level": "消费等级",
    "industry_type_id": "行业类型",
    "monthly_avg_shots": "月均拍摄量",
    "monthly_avg_shots_estimated": "月均拍摄量(预估)",
    "estimated_annual_spend": "预估年消耗",
    "actual_annual_spend_2025": "2025年实际消耗",
    # 余额 / 充值
    "total_amount": "余额合计",
    "real_amount": "余额（实充）",
    "bonus_amount": "余额（赠送）",
    "used_total": "已消耗合计",
    "used_real": "已消耗（实充）",
    "used_bonus": "已消耗（赠送）",
    "recharge_real": "实充金额",
    "recharge_bonus": "赠送金额",
    "recharge_date": "归期（回款日）",
    "payment_proof": "付款凭证",
    "crm_payment_id": "CRM回款记录",
    "crm_payment_external_id": "CRM回款编号",
    "record_snapshot": "原记录快照",
    "record_operator_id": "原操作人",
    "balance_before": "变更前余额",
    "balance_after": "变更后余额",
    "shortfall_real": "实充缺口",
    "shortfall_bonus": "赠送缺口",
    "forced": "强制撤销",
    "needs_manual_reconciliation": "需线下核对",
    # 结算单
    "invoice_no": "结算单号",
    "period_start": "结算周期开始",
    "period_end": "结算周期结束",
    "discount_amount": "减免金额",
    "discount_reason": "减免原因",
    "discount_attachment": "减免附件",
    "discount_approval_comment": "减免审批意见",
    "approver_id": "审批人",
    "approved_at": "审批时间",
    "discount_applied_at": "减免申请时间",
    "discount_approver_id": "减免审批人",
    "discount_approved_at": "减免审批时间",
    "customer_confirmed_at": "客户确认时间",
    "customer_confirmed_by": "客户确认人",
    "paid_at": "付款时间",
    "completed_at": "完成时间",
    "completed_by": "完成人",
    "cancelled_at": "取消时间",
    "cancelled_by": "取消人",
    "is_auto_generated": "自动生成",
    "detail_file_path": "明细文件",
    "detail_file_status": "明细文件状态",
    "ops_confirmed_by": "运营确认人",
    "ops_confirmed_at": "运营确认时间",
    "sales_confirmed_by": "销售确认人",
    "sales_confirmed_at": "销售确认时间",
    # 计费规则 / 套餐
    "device_type": "设备类型",
    "layer_type": "层级类型",
    "pricing_type": "计费类型",
    "unit_price": "单价",
    "multi_floor_pricing_type": "多层计费方式",
    "additional_floor_price": "加层单价",
    "tiers": "阶梯",
    "package_type": "套餐类型",
    "package_limits": "套餐额度",
    "effective_date": "生效日期",
    "expiry_date": "失效日期",
    "is_unlimited": "不限量",
    "limit_count": "额度数量",
    "base_fee": "基础费用",
    "over_limit_unit_price": "超量单价",
    # 用户 / 角色 / 权限
    "username": "用户名",
    "real_name": "姓名",
    "phone": "手机号",
    "is_active": "启用",
    "is_system": "系统内置",
    "avatar_url": "头像",
    "last_login_at": "最后登录时间",
    "role_id": "角色",
    "role_ids": "角色列表",
    "permission_ids": "权限列表",
    "permission_codes": "权限编码",
    "code": "编码",
    "module": "模块",
    # 标签 / 字典
    "type": "类型",
    "category": "分类",
    "sort_order": "排序",
    # 批量
    "total_count": "总条数",
    "success_count": "成功条数",
    "failed_count": "失败条数",
    "skipped_count": "跳过条数",
    "error_count": "错误条数",
    "errors": "错误明细",
}

STATUS_LABELS: Dict[str, str] = {
    "draft": "草稿",
    "pending_ops": "待运营经理确认",
    "pending_sales": "待销售经理确认",
    "pending_discount_approval": "待减免审批",
    "pending_customer": "待客户确认",
    "customer_confirmed": "客户已确认",
    "completed": "已结算",
    "cancelled": "已取消",
    "pending_cs_supervisor": "待客服主管审批",
    "pending_sales_supervisor": "待销售主管审批",
    "pending": "待处理",
    "failed": "失败",
    "success": "成功",
    "active": "启用",
    "inactive": "停用",
    "enabled": "启用",
    "disabled": "停用",
}

ENUM_LABELS: Dict[str, Dict[str, str]] = {
    "account_type": {"enterprise": "企业账号", "正式账号": "正式账号", "trial": "试用账号"},
    "settlement_type": {"prepaid": "预付费", "postpaid": "后付费", "fixed": "固定费用"},
    "settlement_cycle": {"monthly": "月结", "quarterly": "季结", "yearly": "年结"},
    "price_policy": {"pricing": "按量计费", "fixed": "固定费用", "package": "包年套餐"},
    "cooperation_status": {"active": "合作中", "inactive": "已停止", "paused": "暂停"},
    "balance_warning_level": {"normal": "正常", "low": "余额不足", "critical": "即将耗尽"},
    "type": {"industry": "行业", "customer": "客户", "profile": "画像"},
    "operation_type": {
        "standard": "常规操作",
        "batch": "批量操作",
        "relation": "关联操作",
        "sensitive": "敏感操作",
    },
}

SENSITIVE_KEYS = {"password", "password_hash", "new_password", "old_password", "token", "secret"}

AMOUNT_KEYS = {
    "total_amount",
    "real_amount",
    "bonus_amount",
    "used_total",
    "used_real",
    "used_bonus",
    "recharge_real",
    "recharge_bonus",
    "shortfall_real",
    "shortfall_bonus",
    "unit_price",
    "base_fee",
    "over_limit_unit_price",
    "additional_floor_price",
    "discount_amount",
    "estimated_annual_spend",
    "actual_annual_spend_2025",
}

# 已由专用叙述消费、不再逐条列入字段表的键
_REVOKE_CONSUMED = {
    "reason",
    "customer_id",
    "real_amount",
    "bonus_amount",
    "recharge_date",
    "forced",
    "needs_manual_reconciliation",
    "shortfall_real",
    "shortfall_bonus",
    "balance_before",
    "balance_after",
    "record_snapshot",
}
_RECHARGE_CONSUMED = {
    "customer_id",
    "recharge_real",
    "recharge_bonus",
    "real_amount",
    "bonus_amount",
}
_CRM_IMPORT_CONSUMED = {
    "reason",
    "customer_id",
    "real_amount",
    "bonus_amount",
    "recharge_date",
    "crm_payment_id",
    "crm_payment_external_id",
    "forced",
    "needs_manual_reconciliation",
    "shortfall_real",
    "shortfall_bonus",
    "balance_before",
    "balance_after",
}


def describe_audit(
    *,
    action: str,
    module: Optional[str] = None,
    record_type: Optional[str] = None,
    record_id: Optional[int] = None,
    changes: Optional[Dict[str, Any]] = None,
    extra_metadata: Optional[Dict[str, Any]] = None,
    operation_type: Optional[str] = None,
) -> Dict[str, Any]:
    """生成审计条目的中文描述

    Returns:
        {
            "action_label": str,
            "module_label": str,
            "record_type_label": str,
            "summary": [str, ...],           # 中文变更说明（有序）
            "fields": [{"label", "before", "after"}, ...],
        }
    """
    data: Dict[str, Any] = changes if isinstance(changes, dict) else {}
    meta: Dict[str, Any] = extra_metadata if isinstance(extra_metadata, dict) else {}

    before = data.get("before") if isinstance(data.get("before"), dict) else None
    after = data.get("after") if isinstance(data.get("after"), dict) else None
    flat = {k: v for k, v in data.items() if k not in ("before", "after")}

    summary: List[str] = []
    fields: List[Dict[str, str]] = []
    consumed: set[str] = set()

    if action == "billing_recharge_revoke":
        _describe_recharge_revoke(record_id, flat, summary, fields)
        consumed |= _REVOKE_CONSUMED
    elif action == "crm_recharge_import_revoke":
        _describe_crm_revoke(record_id, flat, summary, fields)
        consumed |= _CRM_IMPORT_CONSUMED
    elif action == "recharge":
        _describe_recharge(flat, before, after, summary, fields)
        consumed |= _RECHARGE_CONSUMED
    elif action == "crm_recharge_import":
        _describe_crm_import(flat, summary, fields)
        consumed |= _CRM_IMPORT_CONSUMED
    elif action in ("assign_role", "assign_roles"):
        _describe_role_assignment(flat, after, summary)
        consumed |= {"role_id", "role_ids"}
    elif action == "assign_permissions":
        _describe_permission_assignment(flat, after, summary)
        consumed |= {"permission_ids", "permission_codes"}
    elif action == "reset_password":
        summary.append("重置用户密码（新密码不在此展示）")
        consumed |= {"new_password", "password"}
    elif action == "database_clear":
        _describe_database_clear(flat, meta, summary)

    # before/after：逐字段差异
    if before is not None or after is not None:
        fields.extend(
            _diff_fields(
                before or {},
                after or {},
                skip=consumed,
                summary=summary,
                action=action,
            )
        )
    else:
        # 扁平结构：剩余标量作为「设定值」
        for key, value in flat.items():
            if key in consumed:
                continue
            fields.append(
                {
                    "label": _field_label(key),
                    "before": "—",
                    "after": _format_value(key, value),
                }
            )

    # 批量摘要
    if meta or operation_type == "batch":
        batch_sentence = _describe_batch(meta, data)
        if batch_sentence:
            summary.append(batch_sentence)

    if action in ("create", "update", "delete") and fields:
        noun = RECORD_TYPE_LABELS.get(record_type or "", "记录")
        verb = {"create": "新建", "update": "更新", "delete": "删除"}[action]
        summary.insert(0, f"{verb}{noun}，涉及 {len(fields)} 个字段")
    elif action in ("create", "update", "delete") and not summary:
        noun = RECORD_TYPE_LABELS.get(record_type or "", "记录")
        verb = {"create": "新建", "update": "更新", "delete": "删除"}[action]
        summary.append(f"{verb}{noun}（无字段明细）")

    if not summary:
        summary.append(_fallback_sentence(action, fields, before, after))

    return {
        "action_label": ACTION_LABELS.get(action, action),
        "module_label": MODULE_LABELS.get(module or "", module or ""),
        "record_type_label": RECORD_TYPE_LABELS.get(record_type or "", record_type or ""),
        "summary": summary,
        "fields": fields,
    }


# ---------------------------------------------------------------- 专用叙述


def _describe_recharge_revoke(
    record_id: Optional[int],
    flat: Dict[str, Any],
    summary: List[str],
    fields: List[Dict[str, str]],
) -> None:
    customer_id = flat.get("customer_id")
    head = f"撤销充值记录 #{record_id}" if record_id else "撤销充值记录"
    if customer_id:
        head += f"（客户 #{customer_id}）"
    summary.append(head)

    amount_parts = []
    if "real_amount" in flat:
        amount_parts.append(f"实充 {_money(flat['real_amount'])}")
    if "bonus_amount" in flat:
        amount_parts.append(f"赠送 {_money(flat['bonus_amount'])}")
    if flat.get("recharge_date"):
        amount_parts.append(f"归期 {flat['recharge_date']}")
    if amount_parts:
        summary.append("，".join(amount_parts))

    if flat.get("reason"):
        summary.append(f"原因：{flat['reason']}")

    _append_balance_change(flat, summary, fields)

    if flat.get("forced") or flat.get("needs_manual_reconciliation"):
        detail = "已强制撤销并标记线下核对"
        shortfalls = []
        if _is_positive(flat.get("shortfall_real")):
            shortfalls.append(f"实充缺口 {_money(flat['shortfall_real'])}")
        if _is_positive(flat.get("shortfall_bonus")):
            shortfalls.append(f"赠送缺口 {_money(flat['shortfall_bonus'])}")
        if shortfalls:
            detail += "（" + "，".join(shortfalls) + "）"
        summary.append(detail)

    snapshot = flat.get("record_snapshot")
    if isinstance(snapshot, dict):
        pairs = []
        if snapshot.get("remark"):
            pairs.append(f"原备注「{snapshot['remark']}」")
        if snapshot.get("payment_proof"):
            pairs.append("原付款凭证已保留")
        if snapshot.get("record_operator_id"):
            pairs.append(f"原操作人 #{snapshot['record_operator_id']}")
        if snapshot.get("created_at"):
            pairs.append(f"原入账时间 {_format_value('created_at', snapshot['created_at'])}")
        if pairs:
            summary.append("；".join(pairs))


def _describe_crm_revoke(
    record_id: Optional[int],
    flat: Dict[str, Any],
    summary: List[str],
    fields: List[Dict[str, str]],
) -> None:
    head = "撤销CRM充值导入"
    if flat.get("crm_payment_external_id"):
        head += f"（CRM回款 #{flat['crm_payment_external_id']}"
        head += f"，充值记录 #{record_id}）" if record_id else "）"
    elif record_id:
        head += f"（充值记录 #{record_id}）"
    summary.append(head)

    amount_parts = []
    if "real_amount" in flat:
        amount_parts.append(f"实充 {_money(flat['real_amount'])}")
    if "bonus_amount" in flat:
        amount_parts.append(f"赠送 {_money(flat['bonus_amount'])}")
    if flat.get("recharge_date"):
        amount_parts.append(f"归期 {flat['recharge_date']}")
    if flat.get("customer_id"):
        amount_parts.append(f"客户 #{flat['customer_id']}")
    if amount_parts:
        summary.append("，".join(amount_parts))

    if flat.get("reason"):
        summary.append(f"原因：{flat['reason']}")

    _append_balance_change(flat, summary, fields)

    if flat.get("forced") or flat.get("needs_manual_reconciliation"):
        summary.append("已强制撤销并标记线下核对，回款已释放为待导入")


def _describe_recharge(
    flat: Dict[str, Any],
    before: Optional[Dict[str, Any]],
    after: Optional[Dict[str, Any]],
    summary: List[str],
    fields: List[Dict[str, str]],
) -> None:
    source = after or {}
    parts = []
    if flat.get("customer_id"):
        parts.append(f"客户 #{flat['customer_id']}")
    real = _first_present(flat.get("recharge_real"), source.get("recharge_real"))
    bonus = _first_present(flat.get("recharge_bonus"), source.get("recharge_bonus"))
    if real is not None:
        parts.append(f"实充 {_money(real)}")
    if bonus is not None:
        parts.append(f"赠送 {_money(bonus)}")
    summary.append("充值：" + "，".join(parts) if parts else "客户充值")

    # recharge 的 after 里同时带充值额与充值后余额；余额对比以 before/after 的余额字段表达
    if before and after:
        for key, label in (
            ("real_amount", "余额（实充）"),
            ("bonus_amount", "余额（赠送）"),
        ):
            if key not in before and key not in after:
                continue
            if _values_equal(before.get(key), after.get(key)):
                continue
            fields.append(
                {
                    "label": label,
                    "before": _format_value(key, before.get(key)),
                    "after": _format_value(key, after.get(key)),
                }
            )
        b_total = _total_of(before)
        a_total = _total_of(after)
        if b_total is not None and a_total is not None and not _values_equal(b_total, a_total):
            summary.append(f"余额合计：{_money(b_total)} → {_money(a_total)}")


def _describe_crm_import(
    flat: Dict[str, Any],
    summary: List[str],
    fields: List[Dict[str, str]],
) -> None:
    head = "导入CRM回款为充值"
    if flat.get("crm_payment_external_id"):
        head += f"（CRM回款 #{flat['crm_payment_external_id']}）"
    summary.append(head)
    parts = []
    if flat.get("customer_id"):
        parts.append(f"客户 #{flat['customer_id']}")
    if "real_amount" in flat:
        parts.append(f"实充 {_money(flat['real_amount'])}")
    if "bonus_amount" in flat:
        parts.append(f"赠送 {_money(flat['bonus_amount'])}")
    if flat.get("recharge_date"):
        parts.append(f"归期 {flat['recharge_date']}")
    if parts:
        summary.append("，".join(parts))
    _append_balance_change(flat, summary, fields)


def _describe_role_assignment(
    flat: Dict[str, Any],
    after: Optional[Dict[str, Any]],
    summary: List[str],
) -> None:
    role_ids = flat.get("role_id") or flat.get("role_ids") or (after or {}).get("role_ids")
    if role_ids:
        summary.append(f"角色：{_ids_text(role_ids)}")
    else:
        summary.append("角色分配无变更")


def _describe_permission_assignment(
    flat: Dict[str, Any],
    after: Optional[Dict[str, Any]],
    summary: List[str],
) -> None:
    codes = flat.get("permission_codes") or (after or {}).get("permission_codes")
    ids = flat.get("permission_ids") or (after or {}).get("permission_ids")
    if codes:
        summary.append(f"权限：{_ids_text(codes)}")
    elif ids:
        summary.append(f"权限：{_ids_text(ids)}")
    else:
        summary.append("角色权限无变更")


def _describe_database_clear(
    flat: Dict[str, Any],
    meta: Dict[str, Any],
    summary: List[str],
) -> None:
    merged = {**flat, **meta}
    parts = []
    for key, label in (
        ("balance_count", "余额"),
        ("recharge_count", "充值记录"),
        ("consumption_records_count", "消费流水"),
        ("deleted_count", "合计"),
    ):
        if merged.get(key) is not None:
            parts.append(f"{label} {merged[key]} 条")
    summary.append("清空余额数据：" + "，".join(parts) if parts else "清空余额数据")


# ---------------------------------------------------------------- 通用构件


def _append_balance_change(
    flat: Dict[str, Any],
    summary: List[str],
    fields: List[Dict[str, str]],
) -> None:
    before = flat.get("balance_before") if isinstance(flat.get("balance_before"), dict) else None
    after = flat.get("balance_after") if isinstance(flat.get("balance_after"), dict) else None
    if not before and not after:
        return
    before = before or {}
    after = after or {}
    for key, label in (
        ("real_amount", "余额（实充）"),
        ("bonus_amount", "余额（赠送）"),
        ("total_amount", "余额合计"),
    ):
        if key not in before and key not in after:
            continue
        if _values_equal(before.get(key), after.get(key)):
            continue
        fields.append(
            {
                "label": label,
                "before": _format_value(key, before.get(key)),
                "after": _format_value(key, after.get(key)),
            }
        )
    b_total = _total_of(before)
    a_total = _total_of(after)
    if b_total is not None and a_total is not None and not _values_equal(b_total, a_total):
        summary.append(f"余额合计：{_money(b_total)} → {_money(a_total)}")


def _diff_fields(
    before: Dict[str, Any],
    after: Dict[str, Any],
    *,
    skip: set[str],
    summary: List[str],
    action: str,
) -> List[Dict[str, str]]:
    """逐字段对比，只保留真正变化的字段

    历史审计里 before/after 可能相同（例如旧版充值审计在同一 ORM 实例上取前后值），
    此时不生成字段行，避免制造「无变化」的噪声。
    """
    keys = [k for k in dict.fromkeys([*before.keys(), *after.keys()]) if k not in skip]
    rows: List[Dict[str, str]] = []
    for key in keys:
        b = before.get(key, None)
        a = after.get(key, None)
        if key in before and key in after and _values_equal(b, a):
            continue
        if key not in before and a is None:
            continue
        rows.append(
            {
                "label": _field_label(key),
                "before": _format_value(key, b) if key in before else "—",
                "after": _format_value(key, a),
            }
        )

    # 状态变化单独成句（结算单/VR 的流转最常看）
    if "status" in before or "status" in after:
        b_status = _status_text(before.get("status"))
        a_status = _status_text(after.get("status"))
        if b_status and a_status and b_status != a_status:
            summary.append(f"状态：{b_status} → {a_status}")
    return rows


def _describe_batch(meta: Dict[str, Any], data: Dict[str, Any]) -> Optional[str]:
    raw_after = data.get("after")
    after: Dict[str, Any] = raw_after if isinstance(raw_after, dict) else {}
    source: Dict[str, Any] = {**after, **data, **meta}
    if not any(
        key in source
        for key in ("total_count", "success_count", "failed_count", "skipped_count", "error_count")
    ):
        return None
    parts = []
    for key, label in (
        ("total_count", "共"),
        ("success_count", "成功"),
        ("failed_count", "失败"),
        ("skipped_count", "跳过"),
        ("error_count", "错误"),
    ):
        if source.get(key) is not None:
            parts.append(f"{label} {source[key]} 条" if label != "共" else f"共 {source[key]} 条")
    return "；".join(parts)


def _fallback_sentence(
    action: str,
    fields: List[Dict[str, str]],
    before: Optional[Dict[str, Any]],
    after: Optional[Dict[str, Any]],
) -> str:
    if fields:
        return f"{ACTION_LABELS.get(action, action)}，共 {len(fields)} 项内容"
    if before and after:
        return f"{ACTION_LABELS.get(action, action)}（前后内容一致，无字段变化）"
    return f"{ACTION_LABELS.get(action, action)}（无详细变更数据）"


# ---------------------------------------------------------------- 值格式化


def _field_label(key: str) -> str:
    if key in FIELD_LABELS:
        return FIELD_LABELS[key]
    if key.endswith("_id"):
        return f"{key[:-3]} ID"
    return key


def _format_value(key: str, value: Any) -> str:
    if key in SENSITIVE_KEYS:
        return "已脱敏"
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (list, tuple, set)):
        return _ids_text(value)
    if isinstance(value, dict):
        return (
            "，".join(f"{_field_label(k)}：{_format_value(k, v)}" for k, v in value.items()) or "—"
        )
    if _is_amount_key(key):
        return _money(value)
    if key == "status":
        return _status_text(value) or str(value)
    enum = ENUM_LABELS.get(key)
    if enum is not None:
        return enum.get(str(value), str(value))
    if key.endswith("_date") or key.endswith("_at"):
        return _datetime_text(str(value))
    return str(value)


_ISO_DATETIME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})")


def _datetime_text(value: str) -> str:
    """ISO 时间戳截断到秒，便于阅读；纯日期原样返回"""
    match = _ISO_DATETIME_RE.match(value)
    if match:
        return f"{match.group(1)} {match.group(2)}"
    return value


def _is_amount_key(key: str) -> bool:
    return key in AMOUNT_KEYS or key.endswith(("_amount", "_price", "_fee", "_cost", "_spend"))


def _money(value: Any) -> str:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return str(value)
    if amount < 0:
        return f"-¥{abs(amount):,.2f}"
    return f"¥{amount:,.2f}"


def _is_positive(value: Any) -> bool:
    try:
        return Decimal(str(value)) > 0
    except (InvalidOperation, TypeError, ValueError):
        return False


def _total_of(mapping: Dict[str, Any]) -> Optional[Decimal]:
    if isinstance(mapping.get("total_amount"), (int, float, str, Decimal)):
        try:
            return Decimal(str(mapping["total_amount"]))
        except (InvalidOperation, TypeError, ValueError):
            return None
    real = mapping.get("real_amount")
    bonus = mapping.get("bonus_amount")
    if real is None and bonus is None:
        return None
    try:
        return Decimal(str(real or 0)) + Decimal(str(bonus or 0))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _status_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    return STATUS_LABELS.get(str(value), str(value))


def _ids_text(value: Any) -> str:
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(item) for item in value) if value else "—"
    return str(value)


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _values_equal(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return left == right
    try:
        return Decimal(str(left)) == Decimal(str(right))
    except (InvalidOperation, TypeError, ValueError):
        return left == right
