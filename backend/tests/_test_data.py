"""测试共享数据常量。

权限清单原先在 integration 与 e2e 两层 conftest 中各写两遍（共 4 份逐字副本），
此处收敛为唯一来源。

设计要点：PERMISSION_CODES 由 PERMISSION_ROWS 派生，使
「插入 DB 用的行数据」与「mock 权限缓存用的 code 集合」在结构上不可能漂移。

与 scripts/seed.py 的关系：语义一致但形态不同（seed 为 4 元组含 description、48 条；
此处为测试侧裁剪形态 3 元组、42 条）。两者的漂移由
tests/unit/test_test_data_consistency.py 守护。
"""

# (code, name, module) —— 逐字取自原 tests/integration/conftest.py 的 test_user fixture
PERMISSION_ROWS: list[tuple[str, str, str]] = [
    ("customers:view", "查看客户", "customers"),
    ("customers:create", "新建客户", "customers"),
    ("customers:edit", "编辑客户", "customers"),
    ("customers:delete", "删除客户", "customers"),
    ("customers:export", "导出客户", "customers"),
    ("customers:import", "导入客户", "customers"),
    ("billing:view", "查看结算", "billing"),
    ("billing:edit", "编辑结算", "billing"),
    ("billing:recharge", "充值操作", "billing"),
    ("billing:balance_import", "导入余额", "billing"),
    ("billing:balance_export", "导出余额", "billing"),
    ("billing:pricing_import", "导入计费规则", "billing"),
    ("billing:pricing_export", "导出计费规则", "billing"),
    ("billing:package_import", "导入包年套餐", "billing"),
    ("billing:package_export", "导出包年套餐", "billing"),
    ("billing:invoice_import", "导入结算单", "billing"),
    ("billing:invoice_export", "导出结算单", "billing"),
    ("billing:delete", "结算删除", "billing"),
    ("billing:confirm", "结算确认", "billing"),
    ("billing:pay", "结算付款", "billing"),
    ("files:view", "查看文件", "files"),
    ("files:delete", "删除文件", "files"),
    ("users:view", "查看用户", "users"),
    ("users:create", "新建用户", "users"),
    ("users:edit", "编辑用户", "users"),
    ("users:delete", "删除用户", "users"),
    ("users:role_assign", "分配角色", "users"),
    ("roles:view", "查看角色", "roles"),
    ("roles:create", "新建角色", "roles"),
    ("roles:edit", "编辑角色", "roles"),
    ("roles:delete", "删除角色", "roles"),
    ("roles:assign", "分配权限", "roles"),
    ("system:view", "查看系统", "system"),
    ("analytics:view", "查看分析", "analytics"),
    ("analytics:export", "导出报表", "analytics"),
    ("analytics:profile_tag_edit", "编辑画像标签", "analytics"),
    ("tags:view", "查看标签", "tags"),
    ("tags:create", "新建标签", "tags"),
    ("tags:edit", "编辑标签", "tags"),
    ("tags:delete", "删除标签", "tags"),
    ("industry_types:manage", "行业类型管理", "system"),
    ("cooperation_statuses:manage", "合作状态管理", "system"),
]

# mock 权限缓存使用的 code 集合 —— 派生自上面的行数据，不单独维护
PERMISSION_CODES: frozenset[str] = frozenset(code for code, _, _ in PERMISSION_ROWS)
