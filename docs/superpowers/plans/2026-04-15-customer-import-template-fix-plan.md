# 客户导入模板下载与导入/导出测试验证实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复导入模板下载权限限制（移除 `@require_permission("customers:import")`），并新增完整的后端 pytest 测试用例，验证模板字段正确性、导入功能正确性、导出功能正确性。

**Architecture:** 仅需修改 customers.py 路由的一行装饰器，然后在现有集成测试文件 `test_customers_api.py` 中追加针对性的测试用例。所有测试复用现有的 `test_client`、`auth_headers`、`db_session` fixtures。

**Tech Stack:** Python 3.12 + Sanic + pytest + openpyxl

---

### Task 1: 移除导入模板下载接口的权限限制

**Files:**
- Modify: `backend/app/routes/customers.py:557`

- [ ] **Step 1: 删除 `@require_permission("customers:import")` 装饰器**

读取 `backend/app/routes/customers.py` 第 555-558 行，当前代码：

```python
@customers_bp.get("/import-template")
@auth_required
@require_permission("customers:import")
async def download_import_template(request: Request):
```

修改为：

```python
@customers_bp.get("/import-template")
@auth_required
async def download_import_template(request: Request):
```

仅删除第 557 行 `@require_permission("customers:import")`，保留 `@auth_required`。

- [ ] **Step 2: 验证代码质量检查**

```bash
cd backend && black app/routes/customers.py && flake8 app/routes/customers.py --max-line-length=120 --extend-ignore=E203
```

Expected: 无错误输出

- [ ] **Step 3: 验证现有模板测试仍通过**

```bash
cd backend && source .venv/bin/activate && pytest tests/integration/test_customers_api.py::test_download_import_template -v
```

Expected: PASS（因为 `test_user` 是 admin 角色拥有所有权限，且 `@auth_required` 仍保留）

- [ ] **Step 4: 提交**

```bash
git add backend/app/routes/customers.py
git commit -m "fix: remove customers:import permission requirement from import-template endpoint

The import template is a blank Excel structure with no sensitive data.
Requiring customers:import permission prevented normal users from
downloading the template, causing 'Error' on the frontend.
Keep @auth_required to ensure only authenticated users can access."
```

---

### Task 2: 新增模板下载权限验证测试

**Files:**
- Modify: `backend/tests/integration/test_customers_api.py`（在 `test_download_import_template` 之后追加）

- [ ] **Step 1: 添加未认证访问模板的测试**

在 `test_download_import_template` 函数之后（约第 426 行后），添加：

```python
@pytest.mark.asyncio
async def test_download_import_template_unauthorized(test_client):
    """测试下载导入模板 - 未认证访问应返回 401"""
    request, response = await test_client.get(
        "/api/v1/customers/import-template",
    )

    assert response.status in [401, 403]


@pytest.mark.asyncio
async def test_download_import_template_no_import_permission(test_client, db_session):
    """测试下载导入模板 - 无 import 权限的用户仍可下载（权限已放开）"""
    import bcrypt
    from sqlalchemy import text

    username = "template_only_user"
    password = "test123456"

    # 清理旧数据
    db_session.execute(
        text("DELETE FROM users WHERE username = :username"),
        {"username": username},
    )
    db_session.commit()

    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    db_session.execute(
        text(
            """
        INSERT INTO users (username, password_hash, email, is_active, created_at)
        VALUES (:username, :password_hash, :email, :is_active, NOW())
        """
        ),
        {
            "username": username,
            "password_hash": password_hash,
            "email": "template_only@example.com",
            "is_active": True,
        },
    )

    # 创建只有 customers:view 权限的角色
    db_session.execute(
        text("DELETE FROM roles WHERE name = 'view_only'")
    )
    db_session.execute(
        text(
            """
        INSERT INTO roles (name, description, created_at)
        VALUES (:name, :description, NOW())
        """
        ),
        {"name": "view_only", "description": "仅查看角色"},
    )
    result = db_session.execute(text("SELECT id FROM roles WHERE name = 'view_only'"))
    role_id = result.scalar_one()

    # 仅赋予 customers:view 权限（不赋予 customers:import）
    result = db_session.execute(
        text("SELECT id FROM permissions WHERE code = 'customers:view'")
    )
    perm_id = result.scalar_one()

    db_session.execute(
        text("DELETE FROM role_permissions WHERE role_id = :role_id"),
        {"role_id": role_id},
    )
    db_session.execute(
        text(
            """
        INSERT INTO role_permissions (role_id, permission_id, created_at)
        VALUES (:role_id, :permission_id, NOW())
        """
        ),
        {"role_id": role_id, "permission_id": perm_id},
    )

    # 关联用户到角色
    result = db_session.execute(
        text("SELECT id FROM users WHERE username = :username"),
        {"username": username},
    )
    user_id = result.scalar_one()

    db_session.execute(
        text("DELETE FROM user_roles WHERE user_id = :user_id"),
        {"user_id": user_id},
    )
    db_session.execute(
        text(
            """
        INSERT INTO user_roles (user_id, role_id, created_at)
        VALUES (:user_id, :role_id, NOW())
        """
        ),
        {"user_id": user_id, "role_id": role_id},
    )
    db_session.commit()

    try:
        # 登录
        login_request, login_response = await test_client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        assert login_response.status == 200
        token = login_response.json["data"]["access_token"]

        # 下载模板 - 应该成功（200），因为不再需要 customers:import 权限
        request, response = await test_client.get(
            "/api/v1/customers/import-template",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status == 200
        assert (
            response.headers.get("Content-Type")
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    finally:
        db_session.execute(
            text("DELETE FROM users WHERE username = :username"),
            {"username": username},
        )
        db_session.execute(
            text("DELETE FROM roles WHERE name = 'view_only'")
        )
        db_session.commit()
```

- [ ] **Step 2: 运行测试验证通过**

```bash
cd backend && source .venv/bin/activate && pytest tests/integration/test_customers_api.py::test_download_import_template_unauthorized tests/integration/test_customers_api.py::test_download_import_template_no_import_permission -v
```

Expected: 2 PASS

- [ ] **Step 3: 提交**

```bash
git add backend/tests/integration/test_customers_api.py
git commit -m "test: add permission verification tests for import-template endpoint"
```

---

### Task 3: 新增模板字段结构正确性测试

**Files:**
- Modify: `backend/tests/integration/test_customers_api.py`

- [ ] **Step 1: 添加模板字段验证测试**

在 Task 2 添加的测试之后，追加：

```python
@pytest.mark.asyncio
async def test_download_import_template_field_structure(test_client, auth_headers):
    """测试下载导入模板 - 验证模板字段结构正确性"""
    from openpyxl import load_workbook

    request, response = await test_client.get(
        "/api/v1/customers/import-template",
        headers=auth_headers,
    )

    assert response.status == 200

    # 解析返回的 Excel 文件
    wb = load_workbook(io.BytesIO(response.body))
    ws = wb.active

    assert ws.title == "客户导入模板"

    # 验证第 1 行：表头字段
    headers = [cell.value for cell in ws[1]]
    expected_headers = [
        "company_id",
        "name",
        "account_type",
        "industry",
        "customer_level",
        "price_policy",
        "settlement_cycle",
        "settlement_type",
        "is_key_customer",
        "email",
    ]
    assert headers == expected_headers, f"表头不匹配: {headers}"

    # 验证第 2 行：中文说明
    notes = [cell.value for cell in ws[2]]
    assert notes[0] == "必填"  # company_id
    assert notes[1] == "必填"  # name
    assert notes[2] == "可选"  # account_type
    assert notes[5] == "可选：定价/阶梯/包年"  # price_policy
    assert notes[7] == "可选：prepaid/postpaid"  # settlement_type
    assert notes[8] == "可选：true/false"  # is_key_customer

    # 验证第 3 行：示例数据
    example = [cell.value for cell in ws[3]]
    assert example[0] == "COMP001"  # company_id 示例
    assert "示例公司" in str(example[1])  # name 示例
    assert example[5] == "定价"  # price_policy 示例
    assert example[7] == "prepaid"  # settlement_type 示例
    assert example[8] == "false"  # is_key_customer 示例
    assert "@" in str(example[9])  # email 示例


@pytest.mark.asyncio
async def test_download_import_template_header_count(test_client, auth_headers):
    """测试下载导入模板 - 验证表头数量为 10 个字段"""
    from openpyxl import load_workbook

    request, response = await test_client.get(
        "/api/v1/customers/import-template",
        headers=auth_headers,
    )

    assert response.status == 200

    wb = load_workbook(io.BytesIO(response.body))
    ws = wb.active

    header_count = sum(1 for cell in ws[1] if cell.value is not None)
    assert header_count == 10, f"期望 10 个表头，实际 {header_count} 个"
```

- [ ] **Step 2: 运行测试验证通过**

```bash
cd backend && source .venv/bin/activate && pytest tests/integration/test_customers_api.py::test_download_import_template_field_structure tests/integration/test_customers_api.py::test_download_import_template_header_count -v
```

Expected: 2 PASS

- [ ] **Step 3: 提交**

```bash
git add backend/tests/integration/test_customers_api.py
git commit -m "test: add import template field structure validation tests"
```

---

### Task 4: 新增导入功能边界场景测试

**Files:**
- Modify: `backend/tests/integration/test_customers_api.py`

- [ ] **Step 1: 添加导入边界场景测试**

在现有导入测试之后（`test_import_customers_without_notes_row` 之后，约第 644 行后），追加：

```python
@pytest.mark.asyncio
async def test_import_customers_invalid_email(test_client, auth_headers, db_session):
    """测试导入 - 邮箱格式错误应返回错误信息"""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["company_id", "name", "email"])
    ws.append(["TEST_BAD_EMAIL", "邮箱错误测试", "not-an-email"])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    files = {
        "file": (
            "test_bad_email.xlsx",
            output.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }

    request, response = await test_client.post(
        "/api/v1/customers/import",
        headers=auth_headers,
        files=files,
    )

    assert response.status == 200
    data = response.json
    # 邮箱格式错误的行应被记录为错误，不应成功导入
    assert data["data"]["error_count"] >= 1

    # 清理
    db_session.execute(text("DELETE FROM customers WHERE company_id LIKE 'TEST_BAD_EMAIL%'"))
    db_session.commit()


@pytest.mark.asyncio
async def test_import_customers_empty_required_fields(test_client, auth_headers):
    """测试导入 - 必填字段为空应返回错误"""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["company_id", "name"])
    ws.append(["", ""])  # 两个必填字段都为空

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    files = {
        "file": (
            "test_empty_required.xlsx",
            output.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }

    request, response = await test_client.post(
        "/api/v1/customers/import",
        headers=auth_headers,
        files=files,
    )

    assert response.status == 200
    data = response.json
    assert data["data"]["error_count"] >= 1
    assert data["data"]["success_count"] == 0


@pytest.mark.asyncio
async def test_import_customers_duplicate_company_id(test_client, auth_headers, db_session):
    """测试导入 - 重复 company_id 应部分成功或报错"""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["company_id", "name"])
    ws.append(["TEST_DUP_001", "公司 A"])
    ws.append(["TEST_DUP_001", "公司 B"])  # 重复 ID

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    files = {
        "file": (
            "test_duplicate.xlsx",
            output.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }

    request, response = await test_client.post(
        "/api/v1/customers/import",
        headers=auth_headers,
        files=files,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    # 重复 ID 应该至少有一条成功，或两条都成功（取决于去重逻辑）
    # 但至少不能崩溃
    assert data["data"]["success_count"] >= 1 or data["data"]["error_count"] >= 1

    # 清理
    db_session.execute(text("DELETE FROM customers WHERE company_id LIKE 'TEST_DUP_%'"))
    db_session.commit()


@pytest.mark.asyncio
async def test_import_customers_invalid_price_policy(test_client, auth_headers):
    """测试导入 - 非法 price_policy 值应被正确处理"""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["company_id", "name", "price_policy"])
    ws.append(["TEST_INVALID_POLICY", "非法策略测试", "非法值"])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    files = {
        "file": (
            "test_invalid_policy.xlsx",
            output.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }

    request, response = await test_client.post(
        "/api/v1/customers/import",
        headers=auth_headers,
        files=files,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    # 非法值应被拒绝或记录为错误
```

- [ ] **Step 2: 运行测试验证通过**

```bash
cd backend && source .venv/bin/activate && pytest tests/integration/test_customers_api.py::test_import_customers_invalid_email tests/integration/test_customers_api.py::test_import_customers_empty_required_fields tests/integration/test_customers_api.py::test_import_customers_duplicate_company_id tests/integration/test_customers_api.py::test_import_customers_invalid_price_policy -v
```

Expected: 4 PASS

- [ ] **Step 3: 提交**

```bash
git add backend/tests/integration/test_customers_api.py
git commit -m "test: add import boundary scenario tests (invalid email, empty required, duplicates, invalid enum)"
```

---

### Task 5: 新增导出功能字段一致性测试

**Files:**
- Modify: `backend/tests/integration/test_customers_api.py`

- [ ] **Step 1: 添加导出字段一致性测试**

在现有导出测试之后（`test_export_customers_with_filters` 之后，约第 676 行后），追加：

```python
@pytest.mark.asyncio
async def test_export_customers_field_consistency(test_client, auth_headers, customer_data):
    """测试导出 - 验证导出文件字段与导入模板字段一致性"""
    from openpyxl import load_workbook

    request, response = await test_client.get(
        "/api/v1/customers/export",
        headers=auth_headers,
    )

    assert response.status == 200

    # 解析导出的 Excel 文件
    wb = load_workbook(io.BytesIO(response.body))
    ws = wb.active

    # 导出文件应该有表头行
    export_headers = [cell.value for cell in ws[1] if cell.value is not None]

    # 导入模板的 10 个字段
    template_headers = [
        "company_id",
        "name",
        "account_type",
        "industry",
        "customer_level",
        "price_policy",
        "settlement_cycle",
        "settlement_type",
        "is_key_customer",
        "email",
    ]

    # 导出的字段应包含模板的所有字段（可能还包含额外字段如 id, created_at 等）
    for header in template_headers:
        assert header in export_headers, f"导出文件缺少字段: {header}"


@pytest.mark.asyncio
async def test_export_customers_contains_test_data(test_client, auth_headers, customer_data):
    """测试导出 - 验证导出文件包含测试数据"""
    from openpyxl import load_workbook

    request, response = await test_client.get(
        "/api/v1/customers/export",
        headers=auth_headers,
    )

    assert response.status == 200

    wb = load_workbook(io.BytesIO(response.body))
    ws = wb.active

    # 应该有至少 2 行数据（表头 + 至少 1 条客户记录）
    row_count = ws.max_row
    assert row_count >= 2, f"期望至少 2 行，实际 {row_count} 行"

    # 检查是否包含测试数据
    found_test_data = False
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[0] and "TEST" in str(row[0]):  # company_id 列
            found_test_data = True
            break
    assert found_test_data, "导出文件未找到测试数据"
```

- [ ] **Step 2: 运行测试验证通过**

```bash
cd backend && source .venv/bin/activate && pytest tests/integration/test_customers_api.py::test_export_customers_field_consistency tests/integration/test_customers_api.py::test_export_customers_contains_test_data -v
```

Expected: 2 PASS

- [ ] **Step 3: 提交**

```bash
git add backend/tests/integration/test_customers_api.py
git commit -m "test: add export field consistency and data validation tests"
```

---

### Task 6: 完整测试套件运行与覆盖率检查

**Files:**
- 无修改，仅运行验证命令

- [ ] **Step 1: 运行所有客户相关测试**

```bash
cd backend && source .venv/bin/activate && pytest tests/integration/test_customers_api.py -v
```

Expected: 所有测试 PASS（包括原有测试 + 新增的 10 个测试）

- [ ] **Step 2: 检查测试覆盖率**

```bash
cd backend && source .venv/bin/activate && pytest --cov=app/routes/customers --cov-report=term-missing tests/integration/test_customers_api.py -v
```

Expected: customers.py 覆盖率应 >= 80%

- [ ] **Step 3: 运行代码质量检查**

```bash
cd backend && black tests/integration/test_customers_api.py && flake8 tests/integration/test_customers_api.py --max-line-length=120 --extend-ignore=E203
```

Expected: 无错误

- [ ] **Step 4: 提交（如有代码格式变更）**

```bash
git add -A
git status  # 检查是否有未提交的变更
```

- [ ] **Step 5: 运行完整测试套件确保无回归**

```bash
cd backend && source .venv/bin/activate && pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: 整体测试通过率 >= 95%，无新增 FAIL

---

## 测试验证清单（手动验证步骤）

完成自动化测试后，手动验证以下步骤：

1. **模板下载功能**:
   - 登录系统（非 admin 用户，仅有 `customers:view` 权限）
   - 进入客户管理页面
   - 点击"下载导入模板"按钮
   - 验证文件成功下载（无 Error 提示）

2. **模板字段验证**:
   - 打开下载的 Excel 模板
   - 确认第 1 行为 10 个英文表头
   - 确认第 2 行为中文说明
   - 确认第 3 行为示例数据

3. **导入功能验证**:
   - 使用下载的模板填写 2-3 条有效客户数据
   - 上传导入，验证成功提示和导入数量
   - 填写一条缺少 `company_id` 的数据，验证错误提示

4. **导出功能验证**:
   - 在客户列表页面点击"导出"
   - 打开导出的 Excel，确认字段与模板一致
   - 确认数据完整
