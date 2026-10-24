"""测试共享数据常量。

权限清单原先在 integration 与 e2e 两层 conftest 中各写两遍（共 4 份逐字副本），
此处收敛为唯一来源。

设计要点：PERMISSION_CODES 由 PERMISSION_ROWS 派生，使
「插入 DB 用的行数据」与「mock 权限缓存用的 code 集合」在结构上不可能漂移。

与 scripts/seed.py 的关系：语义一致但形态不同（seed 为 4 元组含 description、53 条；
此处为测试侧裁剪形态 3 元组、45 条）。两者的漂移由
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
    ("customers:view_all", "查看全部客户", "customers"),
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
    ("billing:ops_approve", "运营经理确认", "billing"),
    ("billing:sales_approve", "销售经理确认", "billing"),
    ("billing:discount_approve", "减免审批", "billing"),
    ("billing:detail_status_view", "明细生成状态查看", "billing"),
    ("billing:detail_regenerate", "明细重新生成", "billing"),
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
    ("balance_whitelist:manage", "余额白名单管理", "system"),
]

# mock 权限缓存使用的 code 集合 —— 派生自上面的行数据，不单独维护
PERMISSION_CODES: frozenset[str] = frozenset(code for code, _, _ in PERMISSION_ROWS)


def sync_test_schema(engine) -> list[str]:
    """把测试库补齐到与当前 ORM 模型一致（自动、无需手写字段清单）。

    背景（2026-10-13 事故）：integration/e2e conftest 原先手工维护一张
    `if "xxx" not in columns: ALTER TABLE ... ADD COLUMN` 清单。模型加字段时，
    若忘记同步这张手写清单，测试库就悄悄落后于模型——单测（MagicMock）与
    集成测试全绿，但真实库查询报 `column xxx does not exist` → 500。
    实测：给 Customer 加 `balance_warning_level` 后，未同步清单导致
    test_customers_api.py 45 个用例全 500。

    本函数以 **SQLAlchemy metadata 为唯一真相**：
      - 缺失的表：交给调用方 `create_all`（此处只处理已存在表的新增列）
      - 缺失的列：按 metadata 自动 `ALTER TABLE ... ADD COLUMN`（类型从列定义推导）
      - 已存在但类型不匹配的列（如 String(20) → String(30) 列宽变更）：
        按 metadata 自动 `ALTER COLUMN ... TYPE`（2026-10-24 减免审批节点：
        status 值 pending_discount_approval 为 25 字符，超原 String(20)，
        仅 ADD COLUMN 无法覆盖，运行库/测试库均报 StringDataRightTruncationError）

    返回实际补齐的 `table.column` 列表（便于测试断言/日志）。
    """
    from sqlalchemy import inspect, text
    from sqlalchemy.schema import CreateColumn

    from app.models.base import BaseModel

    dialect = engine.dialect
    added: list[str] = []
    with engine.begin() as conn:
        inspector = inspect(conn)
        existing_tables = set(inspector.get_table_names())
        for table in BaseModel.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue  # 新表由 create_all 负责
            have = {c["name"]: c for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name not in have:
                    # 用 CreateColumn 渲染列定义（含类型、可空等），去掉前导列名
                    col_ddl = str(CreateColumn(column).compile(dialect=dialect))
                    # col_ddl 形如 "name INTEGER NOT NULL"；取其类型/约束部分
                    definition = col_ddl[len(column.name) :].strip()
                    conn.execute(
                        text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {definition}')
                    )
                    added.append(f"{table.name}.{column.name}")
                else:
                    # 长度不匹配的字符串列（列宽变更）：按 metadata 修正。
                    # 2026-10-24 减免审批节点：status 值 pending_discount_approval
                    # 为 25 字符，超原 String(20)，仅 ADD COLUMN 无法覆盖，
                    # 运行库/测试库均报 StringDataRightTruncationError。
                    #
                    # 刻意只处理「字符串列长度」这一类变更，不做通用类型比较：
                    # DECIMAL/NUMERIC、DATETIME/TIMESTAMP 在 SQLAlchemy 与
                    # information_schema 间存在别名表示差异，逐字比较会把全库
                    # 金额/日期列误报为不一致，每次会话触发无谓 ALTER。长度是
                    # 语义明确、无双义表示的维度，按它修正足够覆盖列宽变更场景。
                    model_type = column.type
                    db_type = have[column.name]["type"]
                    model_len = getattr(model_type, "length", None)
                    db_len = getattr(db_type, "length", None)
                    if model_len is not None and db_len is not None and model_len != db_len:
                        type_ddl = model_type.compile(dialect=dialect)
                        conn.execute(
                            text(
                                f'ALTER TABLE "{table.name}" '
                                f'ALTER COLUMN "{column.name}" TYPE {type_ddl}'
                            )
                        )
                        added.append(f"{table.name}.{column.name} (varchar {db_len} → {model_len})")
    return added
