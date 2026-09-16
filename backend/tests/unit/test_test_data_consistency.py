"""权限清单漂移守护测试。

测试侧的权限清单（tests/_test_data.py）与生产种子数据（scripts/seed.py）是
同一语义的两个副本。若二者漂移，会出现「测试全绿但生产角色缺权限」——
正是本次要防的一类缺陷。此测试断言测试侧权限 code 必须是种子权限的子集。
"""

from tests._test_data import PERMISSION_CODES


def test_test_permissions_exist_in_seed():
    """测试权限清单必须是种子权限的子集，否则生产角色会缺权限。"""
    # 延迟导入：scripts.seed 在模块级会执行 sys.path 注入、load_dotenv(backend/.env)
    # 以及 app.models 导入等副作用；若其未来在模块级加入建库/连接逻辑，顶层导入会
    # 让本纯单元测试在收集阶段就尝试连库。放入函数内可避免收集期的副作用。
    from scripts.seed import ALL_PERMISSIONS

    seed_codes = {code for code, *_ in ALL_PERMISSIONS}
    missing = PERMISSION_CODES - seed_codes
    assert not missing, f"测试权限未在 seed.py 定义：{sorted(missing)}"
