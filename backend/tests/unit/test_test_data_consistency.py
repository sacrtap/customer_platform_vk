"""权限清单漂移守护测试。

测试侧的权限清单（tests/_test_data.py）与生产种子数据（scripts/seed.py）是
同一语义的两个副本。若二者漂移，会出现「测试全绿但生产角色缺权限」——
正是本次要防的一类缺陷。此测试断言测试侧权限 code 必须是种子权限的子集。
"""

from scripts.seed import ALL_PERMISSIONS
from tests._test_data import PERMISSION_CODES


def test_test_permissions_exist_in_seed():
    """测试权限清单必须是种子权限的子集，否则生产角色会缺权限。"""
    seed_codes = {code for code, *_ in ALL_PERMISSIONS}
    missing = PERMISSION_CODES - seed_codes
    assert not missing, f"测试权限未在 seed.py 定义：{sorted(missing)}"
