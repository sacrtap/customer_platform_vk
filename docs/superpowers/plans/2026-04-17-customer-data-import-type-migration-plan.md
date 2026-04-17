# 客户数据导入与 company_id 类型迁移实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将源数据转换为可导入格式，并将 company_id 从 String(50) 迁移为 Integer 类型

**Architecture:** 分两阶段执行：第一阶段生成数据转换脚本并输出 Excel 文件，第二阶段进行全栈类型迁移（数据库→后端→前端→测试）

**Tech Stack:** Python 3.12 + pandas + openpyxl + SQLAlchemy 2.0 + Alembic + Vue 3 + TypeScript

---

### Task 1: 检查现有数据库 company_id 数据兼容性

**Files:**
- 仅运行验证命令

- [ ] **Step 1: 检查数据库中是否有非数字 company_id**

```bash
cd backend && source .venv/bin/activate
python -c "
from app.db.session import engine
from sqlalchemy import text

with engine.connect() as conn:
    # 检查非数字 company_id
    result = conn.execute(text(\"\"\"
        SELECT company_id FROM customers 
        WHERE company_id !~ '^\d+$' 
        LIMIT 10
    \"\"\"))
    non_numeric = result.fetchall()
    
    if non_numeric:
        print('发现非数字 company_id:')
        for row in non_numeric:
            print(f'  - {row[0]}')
    else:
        print('所有 company_id 均为数字，可以安全迁移')
"
```

Expected: 输出"所有 company_id 均为数字，可以安全迁移"，或列出需要处理的数据

- [ ] **Step 2: 如果有非数字 ID，决定是否清理**

如果发现非数字 ID，需要决定：
- 删除这些数据
- 或保留 String 类型

---

### Task 2: 编写数据转换脚本并生成 Excel 文件

**Files:**
- Create: `backend/scripts/convert_import_data.py`
- 输出: `docs/customer_import_20260417.xlsx`

- [ ] **Step 1: 创建转换脚本**

```python
"""
数据转换脚本：将 docs/data.xlsx 转换为系统导入模板格式
输出: docs/customer_import_20260417.xlsx
"""

import pandas as pd
import openpyxl
from openpyxl import Workbook
from datetime import datetime
import math

# 源文件路径
SOURCE_FILE = "docs/data.xlsx"
OUTPUT_FILE = "docs/customer_import_20260417.xlsx"

# 字段映射函数
def map_account_type(value):
    """映射账号类型"""
    if pd.isna(value) or value is None:
        return ""
    mapping = {
        "正式": "正式账号",
        "客户测试账号": "测试账号",
        "众点内部": "内部账号",
    }
    return mapping.get(str(value).strip(), "")

def map_price_policy(value):
    """根据结算方式推断计费模式"""
    if pd.isna(value) or value is None:
        return ""
    val = str(value).strip()
    mapping = {
        "定价结算": "定价",
        "易遨结算": "定价",
        "包年套餐": "包年",
        "包年限量套餐": "包年",
    }
    return mapping.get(val, "")

def map_settlement_cycle(value):
    """映射结算周期"""
    if pd.isna(value) or value is None:
        return ""
    val = str(value).strip()
    if val in ["#N/A", "待确认", "0", "None", "nan"]:
        return ""
    return val

def map_is_key_customer(value):
    """根据客户消费等级推断是否重点客户"""
    if pd.isna(value) or value is None:
        return False
    val = str(value).strip()
    # C2 = A 级（重点客户）
    return val == "C2"

def clean_value(value):
    """清理值：#N/A, None, NaN → 空"""
    if pd.isna(value) or value is None:
        return ""
    val = str(value).strip()
    if val in ["#N/A", "None", "nan"]:
        return ""
    return val

# 读取源数据
print(f"读取源数据: {SOURCE_FILE}")
df_source = pd.read_excel(SOURCE_FILE, sheet_name="房产客户分月用量1225（L）")

print(f"源数据行数: {len(df_source)}")
print(f"源数据列数: {len(df_source.columns)}")

# 转换数据
converted_data = []

for _, row in df_source.iterrows():
    converted_data.append({
        "company_id": int(row["公司id"]) if not pd.isna(row["公司id"]) else None,
        "name": clean_value(row["公司名称"]),
        "account_type": map_account_type(row["账号类型"]),
        "industry": clean_value(row["行业类型"]),
        "customer_level": clean_value(row["客户等级"]),
        "price_policy": map_price_policy(row["结算方式"]),
        "settlement_cycle": map_settlement_cycle(row["结算方式"]),
        "settlement_type": "prepaid",
        "is_key_customer": map_is_key_customer(row["客户消费等级"]),
        "email": "",
    })

# 创建输出 DataFrame
df_output = pd.DataFrame(converted_data)

# 验证
print("\n=== 验证 ===")
print(f"输出行数: {len(df_output)}")
print(f"输出列数: {len(df_output.columns)}")

# 检查必填字段
null_company_id = df_output["company_id"].isna().sum()
null_name = df_output["name"].eq("").sum()
print(f"空 company_id: {null_company_id}")
print(f"空 name: {null_name}")

# 检查枚举值
valid_price_policies = {"定价", "阶梯", "包年", ""}
actual_policies = set(df_output["price_policy"].unique())
invalid_policies = actual_policies - valid_price_policies
if invalid_policies:
    print(f"警告：发现无效的 price_policy 值: {invalid_policies}")

# 保存文件
print(f"\n保存到: {OUTPUT_FILE}")
df_output.to_excel(OUTPUT_FILE, index=False, sheet_name="客户导入模板")

print("转换完成！")
print(f"输出文件: {OUTPUT_FILE}")
```

- [ ] **Step 2: 运行转换脚本**

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk
source backend/.venv/bin/activate
python backend/scripts/convert_import_data.py
```

Expected: 输出验证信息，生成 `docs/customer_import_20260417.xlsx`

- [ ] **Step 3: 验证输出文件**

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk
source backend/.venv/bin/activate
python -c "
import openpyxl

wb = openpyxl.load_workbook('docs/customer_import_20260417.xlsx')
ws = wb.active

print(f'Sheet 名: {ws.title}')
print(f'行数: {ws.max_row}')
print(f'列数: {ws.max_column}')

# 打印表头
headers = [cell.value for cell in ws[1]]
print(f'表头: {headers}')

# 打印前 3 行数据
for i in range(2, min(5, ws.max_row + 1)):
    row = [cell.value for cell in ws[i]]
    print(f'行 {i}: {row}')
"
```

Expected: 表头为 10 个目标字段，数据格式正确

- [ ] **Step 4: 提交**

```bash
git add backend/scripts/convert_import_data.py docs/customer_import_20260417.xlsx
git commit -m "feat: add data conversion script and generate import-ready Excel

Converts 1340 rows from docs/data.xlsx to import template format.
Maps source fields to target fields with business logic inference.
Output: docs/customer_import_20260417.xlsx"
```

---

### Task 3: 创建 Alembic 数据库迁移脚本

**Files:**
- Create: `backend/alembic/versions/00X_alter_company_id_to_integer.py`

- [ ] **Step 1: 创建迁移脚本**

首先获取下一个迁移版本号：

```bash
cd backend && source .venv/bin/activate
ls alembic/versions/ | sort | tail -5
```

然后创建迁移文件（假设下一个版本是 005）：

```python
"""alter company_id to integer

Revision ID: 005_alter_company_id_to_integer
Revises: 004_add_customer_extended_fields
Create Date: 2026-04-17

将 company_id 从 VARCHAR(50) 迁移为 INTEGER 类型。
前提：所有现有 company_id 值必须为纯数字。
"""

from alembic import op
import sqlalchemy as sa

revision = "005_alter_company_id_to_integer"
down_revision = "004_add_customer_extended_fields"  # 根据实际前一个版本调整
branch_labels = None
depends_on = None


def upgrade():
    # PostgreSQL: 使用 USING 子句进行类型转换
    op.alter_column(
        "customers",
        "company_id",
        type_=sa.Integer(),
        postgresql_using="company_id::integer",
    )


def downgrade():
    # 回退到字符串类型
    op.alter_column(
        "customers",
        "company_id",
        type_=sa.String(50),
    )
```

- [ ] **Step 2: 验证迁移脚本语法**

```bash
cd backend && source .venv/bin/activate
python -c "import ast; ast.open('alembic/versions/005_alter_company_id_to_integer.py')"
echo "语法检查通过"
```

- [ ] **Step 3: 提交**

```bash
git add backend/alembic/versions/005_alter_company_id_to_integer.py
git commit -m "migration: alter company_id from VARCHAR(50) to INTEGER"
```

---

### Task 4: 修改后端模型 - company_id 类型

**Files:**
- Modify: `backend/app/models/customers.py:23`

- [ ] **Step 1: 修改模型定义**

读取当前代码：

```python
# 当前 (行 23)
company_id = Column(String(50), unique=True, nullable=False, index=True)
```

修改为：

```python
company_id = Column(Integer, unique=True, nullable=False, index=True)
```

完整文件修改（仅改这一行）：

```python
"""客户信息与画像模型"""

from sqlalchemy import (
    Column,
    String,
    Boolean,
    Integer,
    ForeignKey,
    Text,
    Index,
    Date,
    Numeric,
)
from sqlalchemy.orm import relationship
from .base import BaseModel


class Customer(BaseModel):
    """客户基础信息表"""

    __tablename__ = "customers"

    company_id = Column(Integer, unique=True, nullable=False, index=True)  # 修改：String(50) → Integer
    name = Column(String(200), nullable=False, index=True)
    # ... 其余不变
```

- [ ] **Step 2: 验证代码质量**

```bash
cd backend && source .venv/bin/activate
black app/models/customers.py
flake8 app/models/customers.py --max-line-length=120 --extend-ignore=E203
```

Expected: 无错误

- [ ] **Step 3: 提交**

```bash
git add backend/app/models/customers.py
git commit -m "refactor: change company_id type from String to Integer in model"
```

---

### Task 5: 修改后端服务层 - 搜索逻辑调整

**Files:**
- Modify: `backend/app/services/customers.py:137`

- [ ] **Step 1: 修改模糊搜索逻辑**

当前代码（行 137）：

```python
Customer.company_id.ilike(f"%{keyword}%"),
```

修改为使用 CAST：

```python
from sqlalchemy import cast, String

# 修改后
cast(Customer.company_id, String).ilike(f"%{keyword}%"),
```

完整修改上下文（约行 135-140）：

```python
# 修改前
conditions.append(
    or_(
        Customer.company_id.ilike(f"%{keyword}%"),
        Customer.name.ilike(f"%{keyword}%"),
    )
)

# 修改后
from sqlalchemy import cast, String

conditions.append(
    or_(
        cast(Customer.company_id, String).ilike(f"%{keyword}%"),
        Customer.name.ilike(f"%{keyword}%"),
    )
)
```

- [ ] **Step 2: 检查导入语句**

确保文件顶部已有必要导入：

```python
from sqlalchemy import cast, String
```

- [ ] **Step 3: 验证代码质量**

```bash
cd backend && source .venv/bin/activate
black app/services/customers.py
flake8 app/services/customers.py --max-line-length=120 --extend-ignore=E203
```

- [ ] **Step 4: 提交**

```bash
git add backend/app/services/customers.py
git commit -m "fix: use cast for company_id fuzzy search after type change to Integer"
```

---

### Task 6: 修改后端路由层 - 导入检测逻辑

**Files:**
- Modify: `backend/app/routes/customers.py:504-505`

- [ ] **Step 1: 修改模板检测逻辑**

当前代码（行 504-505）：

```python
and isinstance(df.iloc[0].get("company_id"), str)
and df.iloc[0].get("company_id") in ("必填", "可选")
```

修改为：

```python
and isinstance(df.iloc[0].get("company_id"), (int, float, str))
and str(df.iloc[0].get("company_id")) in ("必填", "可选")
```

- [ ] **Step 2: 修改 API 文档注释**

行 237 和 299：

```python
# 修改前
"company_id": "string (required)",

# 修改后
"company_id": "integer (required)",
```

- [ ] **Step 3: 验证代码质量**

```bash
cd backend && source .venv/bin/activate
black app/routes/customers.py
flake8 app/routes/customers.py --max-line-length=120 --extend-ignore=E203
```

- [ ] **Step 4: 提交**

```bash
git add backend/app/routes/customers.py
git commit -m "fix: update import detection and API docs for integer company_id"
```

---

### Task 7: 修改前端 TypeScript 类型定义

**Files:**
- Modify: `frontend/src/types/index.ts:93`
- Modify: `frontend/src/api/customers.ts:26,45`
- Modify: `frontend/src/api/analytics.ts:22,95,108,177`

- [ ] **Step 1: 修改 types/index.ts**

```typescript
// 修改前 (行 93)
company_id: string

// 修改后
company_id: number
```

- [ ] **Step 2: 修改 api/customers.ts**

```typescript
// 修改前 (行 26)
company_id: string

// 修改后
company_id: number

// 修改前 (行 45)
company_id?: string

// 修改后
company_id?: number
```

- [ ] **Step 3: 修改 api/analytics.ts**

```typescript
// 所有 company_id: string 改为 company_id: number
// 行 22, 95, 108, 177
company_id: number
```

- [ ] **Step 4: 运行类型检查**

```bash
cd frontend && npm run type-check
```

Expected: 无类型错误（或仅有预先存在的错误）

- [ ] **Step 5: 提交**

```bash
git add frontend/src/types/index.ts frontend/src/api/customers.ts frontend/src/api/analytics.ts
git commit -m "refactor: change company_id type from string to number in TypeScript"
```

---

### Task 8: 修改前端组件 - 表单初始值

**Files:**
- Modify: `frontend/src/views/customers/Index.vue`
- Modify: `frontend/src/views/customers/Detail.vue`

- [ ] **Step 1: 修改 Index.vue 表单初始值**

```typescript
// 修改前 (行 714, 737)
company_id: '',

// 修改后
company_id: undefined as unknown as string, // 或根据表单组件要求调整
```

注意：Arco Design 的 a-input 在 type="number" 时可能需要不同的处理。如果表单验证要求字符串输入但存储为数字，考虑：
- 保持输入为字符串
- 在提交时转换为数字
- 或修改 input type 为 number

- [ ] **Step 2: 修改 Detail.vue 表单初始值**

```typescript
// 修改前 (行 731, 874)
company_id: '',

// 修改后
company_id: undefined as unknown as string,
```

- [ ] **Step 3: 运行前端 lint**

```bash
cd frontend && npm run lint && npm run format
```

- [ ] **Step 4: 提交**

```bash
git add frontend/src/views/customers/Index.vue frontend/src/views/customers/Detail.vue
git commit -m "fix: update form initial values for number company_id"
```

---

### Task 9: 修改测试数据

**Files:**
- Modify: `backend/tests/integration/test_customers_api.py`

- [ ] **Step 1: 批量替换测试数据**

运行替换脚本：

```bash
cd backend/tests/integration
# 创建备份
cp test_customers_api.py test_customers_api.py.bak

# 使用 Python 进行智能替换
python -c "
import re

with open('test_customers_api.py', 'r') as f:
    content = f.read()

# 替换模式：'company_id': 'TEST001' → 'company_id': 1001
# 使用统一的测试 ID 前缀 1000+

# 替换所有 TEST 开头的 company_id 字符串为整数
def replace_company_id(match):
    original = match.group(1)
    # 提取数字部分
    nums = re.findall(r'\d+', original)
    if nums:
        num = int(nums[0])
        # 映射到 1000+ 范围
        return f'\"company_id\": {1000 + num}'
    return match.group(0)

content = re.sub(r'\"company_id\":\s*\"(TEST\d+)\"', replace_company_id, content)
content = re.sub(r'\"company_id\":\s*\"(COMP\d+)\"', replace_company_id, content)

# 替换模板示例数据 'COMP001' → 1001
content = content.replace('\"COMP001\"', '1001')

# 替换 SQL 中的字符串比较
content = re.sub(r\"company_id = 'TEST\d+'\", lambda m: f\"company_id = {re.findall(r'\d+', m.group())[0]}\", content)

with open('test_customers_api.py', 'w') as f:
    f.write(content)

print('替换完成')
"
```

- [ ] **Step 2: 手动检查关键测试**

检查以下测试用例是否正确转换：
- `test_create_customer`
- `test_import_customers`
- `test_download_import_template_field_structure`

- [ ] **Step 3: 运行测试验证**

```bash
cd backend && source .venv/bin/activate
python -m pytest tests/integration/test_customers_api.py -v --tb=short 2>&1 | head -50
```

Expected: 测试通过（或仅有预期失败）

- [ ] **Step 4: 提交**

```bash
git add backend/tests/integration/test_customers_api.py
git commit -m "test: update test data for integer company_id"
```

---

### Task 10: 运行数据库迁移并验证

**Files:**
- 仅运行命令

- [ ] **Step 1: 运行数据库迁移**

```bash
cd backend && source .venv/bin/activate
python -m alembic upgrade head
```

Expected: 迁移成功

- [ ] **Step 2: 验证迁移结果**

```bash
cd backend && source .venv/bin/activate
python -c "
from app.db.session import engine
from sqlalchemy import text

with engine.connect() as conn:
    result = conn.execute(text(\"\"\"
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'customers' AND column_name = 'company_id'
    \"\"\"))
    row = result.fetchone()
    print(f'company_id 类型: {row[1]}')
    assert row[1] == 'integer', f'期望 integer，实际 {row[1]}'
    print('验证通过！')
"
```

- [ ] **Step 3: 提交（如有迁移文件变更）**

---

### Task 11: 完整测试套件验证

**Files:**
- 仅运行命令

- [ ] **Step 1: 运行后端测试**

```bash
cd backend && source .venv/bin/activate
python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: 测试通过率 >= 95%

- [ ] **Step 2: 运行代码质量检查**

```bash
cd backend && black app/ tests/ && flake8 app/ tests/ --max-line-length=120 --extend-ignore=E203
```

- [ ] **Step 3: 运行前端类型检查**

```bash
cd frontend && npm run type-check
```

- [ ] **Step 4: 提交所有剩余变更**

```bash
git add -A
git status
git commit -m "chore: final cleanup and verification"
```

---

## 自审检查

### 规范覆盖

- ✅ 数据转换脚本创建并运行
- ✅ company_id 类型迁移（数据库、模型、服务、路由、前端、测试）
- ✅ 模糊搜索逻辑调整
- ✅ API 文档更新
- ✅ 测试数据更新

### 占位符扫描

- ✅ 无 TBD/TODO
- ✅ 所有步骤有具体代码
- ✅ 所有命令有预期输出

### 类型一致性

- ✅ 后端：Integer
- ✅ 前端：number
- ✅ 测试：整数
- ✅ 数据库：integer
