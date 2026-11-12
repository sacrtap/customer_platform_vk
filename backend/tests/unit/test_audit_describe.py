"""审计描述器单元测试：中文变更说明与字段对照"""

from app.services.audit_describe import describe_audit


def _describe(action, changes=None, **kwargs):
    return describe_audit(
        action=action,
        module=kwargs.get("module", "billing"),
        record_type=kwargs.get("record_type"),
        record_id=kwargs.get("record_id"),
        changes=changes,
        extra_metadata=kwargs.get("extra_metadata"),
        operation_type=kwargs.get("operation_type", "standard"),
    )


class TestRechargeRevoke:
    """扁平业务快照（撤销充值）：此前详情空白"""

    CHANGES = {
        "reason": "充错了",
        "customer_id": 27124,
        "real_amount": "1000.00",
        "bonus_amount": "0.00",
        "recharge_date": "2026-11-12",
        "record_snapshot": {"payment_proof": None, "remark": "误充", "record_operator_id": 43},
        "forced": False,
        "needs_manual_reconciliation": False,
        "shortfall_real": "0.00",
        "shortfall_bonus": "0.00",
        "balance_before": {
            "real_amount": "243800.00",
            "bonus_amount": "0.00",
            "total_amount": "243800.00",
        },
        "balance_after": {
            "real_amount": "242800.00",
            "bonus_amount": "0.00",
            "total_amount": "242800.00",
        },
    }

    def test_produces_readable_summary(self):
        result = _describe(
            "billing_recharge_revoke", self.CHANGES, record_id=4669, record_type="recharge_record"
        )

        assert result["action_label"] == "撤销充值记录"
        assert result["summary"][0] == "撤销充值记录 #4669（客户 #27124）"
        assert "实充 ¥1,000.00" in result["summary"][1]
        assert "原因：充错了" in result["summary"]
        assert "余额合计：¥243,800.00 → ¥242,800.00" in result["summary"]
        assert any("原备注「误充」" in line for line in result["summary"])

    def test_fields_only_include_changed_balances(self):
        result = _describe("billing_recharge_revoke", self.CHANGES, record_id=4669)

        labels = [row["label"] for row in result["fields"]]
        assert labels == ["余额（实充）", "余额合计"]
        real_row = result["fields"][0]
        assert real_row["before"] == "¥243,800.00"
        assert real_row["after"] == "¥242,800.00"

    def test_forced_revoke_mentions_shortfall_and_negative_balance(self):
        changes = {
            **self.CHANGES,
            "forced": True,
            "needs_manual_reconciliation": True,
            "shortfall_real": "5000.00",
            "balance_before": {
                "real_amount": "0.00",
                "bonus_amount": "0.00",
                "total_amount": "0.00",
            },
            "balance_after": {
                "real_amount": "-5000.00",
                "bonus_amount": "0.00",
                "total_amount": "-5000.00",
            },
        }
        result = _describe("billing_recharge_revoke", changes, record_id=4667)

        assert any(
            "强制撤销" in line and "实充缺口 ¥5,000.00" in line for line in result["summary"]
        )
        assert "余额合计：¥0.00 → -¥5,000.00" in result["summary"]


class TestRecharge:
    def test_shows_amount_and_balance_transition(self):
        changes = {
            "before": {"real_amount": 242800.0, "bonus_amount": 0.0},
            "after": {
                "real_amount": 243800.0,
                "bonus_amount": 0.0,
                "recharge_real": 1000.0,
                "recharge_bonus": 200.0,
            },
            "customer_id": 27124,
        }
        result = _describe("recharge", changes, record_type="recharge", record_id=4669)

        assert result["summary"][0] == "充值：客户 #27124，实充 ¥1,000.00，赠送 ¥200.00"
        assert "余额合计：¥242,800.00 → ¥243,800.00" in result["summary"]
        # 余额（实充）只出现一次，赠送未变化不展示
        assert [row["label"] for row in result["fields"]] == ["余额（实充）"]


class TestGenericCrud:
    def test_create_lists_after_fields_with_chinese_labels(self):
        changes = {"after": {"company_id": 778899, "name": "UI客户", "account_type": "enterprise"}}
        result = _describe(
            "create", changes, module="customers", record_type="customer", record_id=1
        )

        assert result["summary"] == ["新建客户，涉及 3 个字段"]
        labels = {row["label"]: row["after"] for row in result["fields"]}
        assert labels["账号类型"] == "企业账号"
        assert labels["名称"] == "UI客户"

    def test_delete_shows_before_values(self):
        changes = {"before": {"name": "旧客户", "is_disabled": False}}
        result = _describe(
            "delete", changes, module="customers", record_type="customer", record_id=5
        )

        assert result["summary"] == ["删除客户，涉及 2 个字段"]
        rows = {row["label"]: (row["before"], row["after"]) for row in result["fields"]}
        assert rows["已停用"] == ("否", "—")

    def test_update_status_change_is_sentenced(self):
        changes = {"before": {"status": "draft"}, "after": {"status": "pending_ops"}}
        result = _describe("update", changes, record_type="invoice", record_id=7)

        assert "状态：草稿 → 待运营经理确认" in result["summary"]

    def test_identical_before_after_produces_no_field_rows(self):
        changes = {
            "before": {"real_amount": 100.0, "bonus_amount": 0.0},
            "after": {"real_amount": 100.0, "bonus_amount": 0.0, "recharge_real": 100.0},
            "customer_id": 1,
        }
        result = _describe("recharge", changes, record_type="recharge")

        assert result["fields"] == []
        assert "余额合计" not in " ".join(result["summary"])


class TestOtherActions:
    def test_role_assignment(self):
        result = _describe(
            "assign_role",
            {"role_id": [20, 27]},
            module="users",
            record_type="user-role",
            extra_metadata={"role_ids": [20, 27]},
            operation_type="relation",
        )
        assert result["action_label"] == "分配角色"
        assert result["summary"] == ["角色：20, 27"]

    def test_reset_password_hides_secret(self):
        result = _describe(
            "reset_password", {"after": {"new_password": "3dnest2026"}}, module="users"
        )

        assert result["summary"] == ["重置用户密码（新密码不在此展示）"]
        assert result["fields"] == []

    def test_batch_summary_from_after(self):
        result = _describe(
            "batch_submit",
            {"after": {"success_count": 92, "skipped_count": 34}},
            operation_type="batch",
        )
        assert "成功 92 条" in result["summary"][0]
        assert "跳过 34 条" in result["summary"][0]

    def test_missing_changes_still_describes_action(self):
        result = _describe("cancel", None, record_type="invoice")
        assert result["action_label"] == "取消"
        assert result["summary"] == ["取消（无详细变更数据）"]

    def test_sensitive_field_masked_in_flat_fields(self):
        result = _describe("update", {"password_hash": "x", "name": "改名"}, module="users")
        rows = {row["label"]: row["after"] for row in result["fields"]}
        assert rows.get("password_hash") == "已脱敏"
