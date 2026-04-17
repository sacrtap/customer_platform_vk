#!/usr/bin/env python3
"""
批量替换测试数据中的 company_id 字符串为整数
"""

import re

# 读取文件
with open(
    "backend/tests/integration/test_customers_api.py", "r", encoding="utf-8"
) as f:
    content = f.read()

# 替换规则
replacements = [
    # 在 SQL 语句中替换
    (r"WHERE company_id = 'TEST001'", "WHERE company_id = 1001"),
    (r"WHERE company_id = 'TEST002'", "WHERE company_id = 1002"),
    (r"WHERE company_id = 'TEST003'", "WHERE company_id = 1003"),
    (r"WHERE company_id LIKE 'TEST_%'", "WHERE company_id LIKE 'TEST_%'"),  # 保持不变
    # 在断言中替换
    (r'data\["company_id"\] == "TEST001"', 'data["company_id"] == 1001'),
    (r'data\["company_id"\] == "TEST002"', 'data["company_id"] == 1002'),
    (r'data\["company_id"\] == "TEST003"', 'data["company_id"] == 1003'),
    # 在 JSON payload 中替换
    (r'"company_id": "TEST001"', '"company_id": 1001'),
    (r'"company_id": "TEST002"', '"company_id": 1002'),
    (r'"company_id": "TEST003"', '"company_id": 1003'),
    (r'"company_id": "COMP001"', '"company_id": 1001'),
    # 在 Excel 导入测试中替换
    (r'ws\.append\(\[\s*"TEST_', "ws.append(["),
    (r'"TEST001"', "1001"),
    (r'"TEST002"', "1002"),
    (r'"TEST003"', "1003"),
    (r'"COMP001"', "1001"),
    # 在删除语句中替换
    (
        r"DELETE FROM customers WHERE company_id = 'TEST001'",
        "DELETE FROM customers WHERE company_id = 1001",
    ),
    (
        r"DELETE FROM customers WHERE company_id = 'TEST002'",
        "DELETE FROM customers WHERE company_id = 1002",
    ),
    (
        r"DELETE FROM customers WHERE company_id = 'TEST003'",
        "DELETE FROM customers WHERE company_id = 1003",
    ),
]

# 执行替换
for pattern, replacement in replacements:
    content = re.sub(pattern, replacement, content)

# 写回文件
with open(
    "backend/tests/integration/test_customers_api.py", "w", encoding="utf-8"
) as f:
    f.write(content)

print("替换完成！")
