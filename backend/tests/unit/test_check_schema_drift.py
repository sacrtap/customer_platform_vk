"""check_schema_drift 脚本的可空性检测能力回归测试

锁住 2026-10-23 的修复：`compare_metadata` 的 `modify_nullable` 条目是
**外层 list 包裹 tuple** 的形态，旧版脚本只匹配裸 tuple 的 kind，导致
可空性漂移被静默忽略（8 处存量漂移全部漏过）。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# 以模块方式加载 scripts/check_schema_drift.py（该目录无 __init__.py）
_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_schema_drift.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_schema_drift", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_schema_drift"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def drift_module():
    return _load_module()


class TestUnwrap:
    """_unwrap 必须同时解包两种 diff 条目形态"""

    def test_unwrap_nested_list_form(self, drift_module):
        """modify_* 的真实形态：外层 list 包裹一个 tuple"""
        nested = [("modify_nullable", None, "t", "c", {}, True, False)]
        assert drift_module._unwrap(nested) == nested[0]

    def test_unwrap_bare_tuple_form(self, drift_module):
        """add_table / remove_index 等是裸 tuple，必须原样返回"""
        bare = ("remove_index", "some_index")
        assert drift_module._unwrap(bare) == bare

    def test_unwrap_empty_list_is_safe(self, drift_module):
        """空 list 不应抛异常"""
        assert drift_module._unwrap([]) == []


class TestCollectNullableDiffs:
    """_collect_nullable_diffs 必须抽出 modify_nullable 并正确渲染方向"""

    def test_collects_nested_modify_nullable(self, drift_module):
        diff = [
            ("add_index", "ix_other"),  # 无关条目应被忽略
            [
                (
                    "modify_nullable",
                    None,
                    "pricing_rules",
                    "tiers",
                    {"existing_type": "JSON"},
                    True,  # reflected（库）
                    False,  # metadata（模型）
                )
            ],
        ]
        result = drift_module._collect_nullable_diffs(diff)
        assert len(result) == 1
        # [6] 是模型侧（metadata），[5] 是库侧（reflected）——方向不可反
        assert result[0] == "pricing_rules.tiers: 模型=False 库=True"

    def test_ignores_other_modify_kinds(self, drift_module):
        diff = [
            [
                (
                    "modify_comment",
                    None,
                    "customers",
                    "remark",
                    {"existing_nullable": True},
                    "新注释",
                    None,
                )
            ],
        ]
        assert drift_module._collect_nullable_diffs(diff) == []

    def test_empty_diff_returns_empty(self, drift_module):
        assert drift_module._collect_nullable_diffs([]) == []
