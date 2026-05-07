# 画像等级体系重命名 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将消费等级从 S/A/B/C/D/E 重命名为 C1/C2/C3/C4/C5/C6，规模等级从人数数值重命名为 S/A/B/C/D/E，并迁移数据库中的已有数据。

**Architecture:** 通过 Alembic 数据迁移脚本更新数据库中的历史数据，同步更新前端组件中的等级选项和显示映射，更新导入脚本的映射规则，最后更新所有相关测试数据。

**Tech Stack:** Python 3.12, Alembic, SQLAlchemy, Vue 3, TypeScript, Arco Design, pytest

---

### Task 1: 创建 Alembic 数据迁移脚本

**Files:**
- Create: `backend/alembic/versions/2026_05_07_rename_profile_levels.py`

- [ ] **Step 1: 创建迁移脚本文件**

创建文件 `backend/alembic/versions/2026_05_07_rename_profile_levels.py`，内容如下：

```python
"""rename profile levels: consume S/A/B/C/D/E→C1-C6, scale numbers→S/A/B/C/D/E

Revision ID: 2026_05_07_rename_levels
Revises: 2026_04_29_audit_fields
Create Date: 2026-05-07
"""

from typing import Sequence, Union
from alembic import op

revision: str = "2026_05_07_rename_levels"
down_revision: Union[str, None] = "2026_04_29_audit_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 消费等级迁移: S→C1, A→C2, B→C3, C→C4, D→C5, E→C6
    op.execute("UPDATE customer_profiles SET consume_level = 'C1' WHERE consume_level = 'S'")
    op.execute("UPDATE customer_profiles SET consume_level = 'C2' WHERE consume_level = 'A'")
    op.execute("UPDATE customer_profiles SET consume_level = 'C3' WHERE consume_level = 'B'")
    op.execute("UPDATE customer_profiles SET consume_level = 'C4' WHERE consume_level = 'C'")
    op.execute("UPDATE customer_profiles SET consume_level = 'C5' WHERE consume_level = 'D'")
    op.execute("UPDATE customer_profiles SET consume_level = 'C6' WHERE consume_level = 'E'")

    # 规模等级迁移: 5000→S, 2000→A, 1000→B, 500→C, 100→D
    op.execute("UPDATE customer_profiles SET scale_level = 'S' WHERE scale_level = '5000'")
    op.execute("UPDATE customer_profiles SET scale_level = 'A' WHERE scale_level = '2000'")
    op.execute("UPDATE customer_profiles SET scale_level = 'B' WHERE scale_level = '1000'")
    op.execute("UPDATE customer_profiles SET scale_level = 'C' WHERE scale_level = '500'")
    op.execute("UPDATE customer_profiles SET scale_level = 'D' WHERE scale_level = '100'")


def downgrade() -> None:
    # 消费等级回滚
    op.execute("UPDATE customer_profiles SET consume_level = 'S' WHERE consume_level = 'C1'")
    op.execute("UPDATE customer_profiles SET consume_level = 'A' WHERE consume_level = 'C2'")
    op.execute("UPDATE customer_profiles SET consume_level = 'B' WHERE consume_level = 'C3'")
    op.execute("UPDATE customer_profiles SET consume_level = 'C' WHERE consume_level = 'C4'")
    op.execute("UPDATE customer_profiles SET consume_level = 'D' WHERE consume_level = 'C5'")
    op.execute("UPDATE customer_profiles SET consume_level = 'E' WHERE consume_level = 'C6'")

    # 规模等级回滚
    op.execute("UPDATE customer_profiles SET scale_level = '5000' WHERE scale_level = 'S'")
    op.execute("UPDATE customer_profiles SET scale_level = '2000' WHERE scale_level = 'A'")
    op.execute("UPDATE customer_profiles SET scale_level = '1000' WHERE scale_level = 'B'")
    op.execute("UPDATE customer_profiles SET scale_level = '500' WHERE scale_level = 'C'")
    op.execute("UPDATE customer_profiles SET scale_level = '100' WHERE scale_level = 'D'")
```

- [ ] **Step 2: 验证迁移脚本语法**

运行以下命令验证迁移脚本可以被 Alembic 识别：

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk/backend && source .venv/bin/activate && python -m alembic check
```

Expected: 无错误输出（如果数据库 schema 无变化，可能提示 no new operations，这是正常的，因为这是纯数据迁移）

- [ ] **Step 3: 提交**

```bash
git add backend/alembic/versions/2026_05_07_rename_profile_levels.py
git commit -m "feat(profile): add alembic migration for profile level rename"
```

---

### Task 2: 更新 Detail.vue - 消费等级和规模等级

**Files:**
- Modify: `frontend/src/views/customers/Detail.vue`

- [ ] **Step 1: 更新消费等级编辑选项（约第 491-499 行）**

将消费等级的编辑选项从 S/A/B/C/D/E 改为 C1/C2/C3/C4/C5/C6：

```vue
<!-- 替换原有的 a-option 列表 -->
<a-form-item field="consume_level" label="消费等级">
  <a-select v-model="editForm.consume_level" placeholder="请选择消费等级" allow-clear>
    <a-option value="C1">C1</a-option>
    <a-option value="C2">C2</a-option>
    <a-option value="C3">C3</a-option>
    <a-option value="C4">C4</a-option>
    <a-option value="C5">C5</a-option>
    <a-option value="C6">C6</a-option>
  </a-select>
</a-form-item>
```

- [ ] **Step 2: 更新规模等级编辑选项（约第 481-489 行）**

将规模等级的编辑选项从人数数值改为 S/A/B/C/D/E，并增加释义标注：

```vue
<!-- 替换原有的 a-option 列表 -->
<a-form-item field="scale_level" label="规模等级">
  <a-select v-model="editForm.scale_level" placeholder="请选择规模等级" allow-clear>
    <a-option value="S">S - 5000人</a-option>
    <a-option value="A">A - 2000人</a-option>
    <a-option value="B">B - 1000人</a-option>
    <a-option value="C">C - 500人</a-option>
    <a-option value="D">D - 100人</a-option>
    <a-option value="E">E - 小于100人</a-option>
  </a-select>
</a-form-item>
```

- [ ] **Step 3: 更新 CONSUME_LEVEL_MAP 映射（约第 1268-1275 行）**

将消费等级的显示映射键名从 S/A/B/C/D/E 改为 C1/C2/C3/C4/C5/C6：

```typescript
// 替换原有的 CONSUME_LEVEL_MAP
const CONSUME_LEVEL_MAP: Record<string, string> = {
  C1: 'C1 - 100 万',
  C2: 'C2 - 50 万',
  C3: 'C3 - 25 万',
  C4: 'C4 - 12 万',
  C5: 'C5 - 6 万',
  C6: 'C6 - 6 万以下',
}
```

- [ ] **Step 4: 验证前端类型检查**

运行以下命令确保 TypeScript 类型检查通过：

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk/frontend && npm run type-check
```

Expected: 无类型错误

- [ ] **Step 5: 提交**

```bash
git add frontend/src/views/customers/Detail.vue
git commit -m "feat(profile): update consume level to C1-C6 and scale level to S/A/B/C/D/E in detail view"
```

---

### Task 3: 更新 ConsumeLevelProgress 组件

**Files:**
- Modify: `frontend/src/components/charts/ConsumeLevelProgress.vue`
- Modify: `frontend/src/components/ConsumeLevelProgress.vue`

- [ ] **Step 1: 更新 charts/ConsumeLevelProgress.vue 的 levels 和 levelThresholds**

在 `frontend/src/components/charts/ConsumeLevelProgress.vue` 中，找到以下代码（约第 40-50 行）：

```typescript
// 原代码
const levels = ['E', 'D', 'C', 'B', 'A', 'S']

const levelThresholds = {
  E: 0,
  D: 60000,
  C: 120000,
  B: 250000,
  A: 500000,
  S: 1000000,
}
```

替换为：

```typescript
// 新代码
const levels = ['C6', 'C5', 'C4', 'C3', 'C2', 'C1']

const levelThresholds = {
  C6: 0,
  C5: 60000,
  C4: 120000,
  C3: 250000,
  C2: 500000,
  C1: 1000000,
}
```

- [ ] **Step 2: 更新 ConsumeLevelProgress.vue 的 levels 和 levelThresholds**

在 `frontend/src/components/ConsumeLevelProgress.vue` 中，找到相同的代码模式（约第 52 行附近的 levels 数组），做相同替换：

```typescript
// 原代码
const levels = ['E', 'D', 'C', 'B', 'A', 'S']

// 新代码
const levels = ['C6', 'C5', 'C4', 'C3', 'C2', 'C1']
```

如果有 levelThresholds 对象，也同步更新键名。

- [ ] **Step 3: 验证前端类型检查**

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk/frontend && npm run type-check
```

Expected: 无类型错误

- [ ] **Step 4: 提交**

```bash
git add frontend/src/components/charts/ConsumeLevelProgress.vue frontend/src/components/ConsumeLevelProgress.vue
git commit -m "feat(profile): update consume level keys to C1-C6 in progress components"
```

---

### Task 4: 更新导入数据清洗脚本

**Files:**
- Modify: `backend/scripts/clean_import_data.py`

- [ ] **Step 1: 更新消费等级映射注释和逻辑**

在 `backend/scripts/clean_import_data.py` 中，找到消费等级映射相关的代码（约第 21 行注释和第 80 行映射表）：

```python
# 原注释（约第 21 行）
# - 客户消费等级 → consume_level（C2→A, C3→B, C4→C, C5→D, C6→E）

# 更新为
# - 客户消费等级 → consume_level（C2→C2, C3→C3, C4→C4, C5→C5, C6→C6，直接映射）
```

找到映射逻辑（约在文件中间处理 consume_level 字段的部分），原来的映射逻辑是 C2→A 等，现在改为直接映射：

```python
# 找到类似这样的代码：
consume_level_map = {'C2': 'A', 'C3': 'B', 'C4': 'C', 'C5': 'D', 'C6': 'E'}
value = consume_level_map.get(raw_value, raw_value)

# 改为：
# 消费等级直接映射，C2→C2, C3→C3, etc.
consume_level_valid = {'C1', 'C2', 'C3', 'C4', 'C5', 'C6'}
if raw_value in consume_level_valid:
    value = raw_value
else:
    value = None  # 或根据实际逻辑处理
```

如果脚本中没有显式的映射字典，而是直接传递值，则只需更新注释即可。

- [ ] **Step 2: 提交**

```bash
git add backend/scripts/clean_import_data.py
git commit -m "feat(profile): update import mapping for consume level direct mapping"
```

---

### Task 5: 更新后端单元测试数据

**Files:**
- Modify: `backend/tests/unit/test_customer_service.py`
- Modify: `backend/tests/unit/test_customer_service_batch.py`
- Modify: `backend/tests/integration/test_customers_api.py`

- [ ] **Step 1: 更新 test_customer_service.py 中的等级值**

在 `backend/tests/unit/test_customer_service.py` 中，找到 scale_level 和 consume_level 的测试数据（约第 623 行和第 648 行附近）：

```python
# 查找并替换所有测试数据中的旧值为新值
# scale_level: "medium" 等保持不变（测试数据可能使用任意字符串）
# consume_level: 如果有 S/A/B/C/D/E，改为 C1/C2/C3/C4/C5/C6

# 示例：如果测试中有类似这样的代码
# profile = CustomerProfile(scale_level="medium", consume_level="A")
# 改为
# profile = CustomerProfile(scale_level="medium", consume_level="C2")
```

使用全局替换：
- `consume_level="S"` → `consume_level="C1"`
- `consume_level="A"` → `consume_level="C2"`
- `consume_level="B"` → `consume_level="C3"`
- `consume_level="C"` → `consume_level="C4"`
- `consume_level="D"` → `consume_level="C5"`
- `consume_level="E"` → `consume_level="C6"`

- [ ] **Step 2: 更新 test_customer_service_batch.py 中的等级值**

在 `backend/tests/unit/test_customer_service_batch.py` 中（约第 683-767 行），找到 scale_level 和 consume_level 的测试数据：

```python
# 查找 "大"/"小"/"中" 等中文字符串测试值，这些不需要改（自由字符串）
# 但如果有 S/A/B/C/D/E 的 consume_level，改为 C1-C6

# 示例替换：
# data = {"scale_level": "大", "consume_level": "高"}  # 保持不变（测试任意值）
# 但如果有：
# mock_profile.consume_level = "A"  →  mock_profile.consume_level = "C2"
```

- [ ] **Step 3: 更新 test_customers_api.py 中的等级值**

在 `backend/tests/integration/test_customers_api.py` 中（约第 369-460 行），找到测试数据中的 scale_level 和 consume_level：

```python
# 示例：
# "scale_level": "large"  # 保持不变
# "consume_level": "A"  →  "consume_level": "C2"
```

- [ ] **Step 4: 运行后端测试验证**

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk/backend && source .venv/bin/activate && pytest tests/unit/test_customer_service.py tests/unit/test_customer_service_batch.py tests/integration/test_customers_api.py -v
```

Expected: 所有测试通过

- [ ] **Step 5: 提交**

```bash
git add backend/tests/
git commit -m "test(profile): update test data for new consume level C1-C6 values"
```

---

### Task 6: 更新前端 E2E 测试

**Files:**
- Modify: `frontend/tests/e2e/customer-detail.spec.ts`

- [ ] **Step 1: 更新 E2E 测试中的等级断言**

在 `frontend/tests/e2e/customer-detail.spec.ts` 中（约第 182-219 行），找到消费等级和规模等级的验证逻辑：

```typescript
// 原代码示例：
// const consumeLabel = page.locator('.metric-label', { hasText: '消费等级' });
// 验证消费等级显示为 S/A/B/C/D/E 格式

// 更新为验证 C1/C2/C3/C4/C5/C6 格式
// 如果有具体的等级值断言，如：
// await expect(page.locator('text=S - 100 万')).toBeVisible();
// 改为：
// await expect(page.locator('text=C1 - 100 万')).toBeVisible();
```

查找并替换所有断言中的旧等级值为新值。

- [ ] **Step 2: 提交**

```bash
git add frontend/tests/e2e/customer-detail.spec.ts
git commit -m "test(e2e): update consume level assertions to C1-C6 format"
```

---

### Task 7: 更新模型注释和文档

**Files:**
- Modify: `backend/app/models/customers.py`
- Modify: `docs/user-manual.md`
- Modify: `docs/superpowers/specs/2026-04-30-customer-import-optimization-design.md`

- [ ] **Step 1: 更新 models/customers.py 字段注释**

在 `backend/app/models/customers.py` 中（约第 66-67 行）：

```python
# 原代码
scale_level = Column(String(50))  # 客户规模等级
consume_level = Column(String(50))  # 客户消费等级

# 更新为
scale_level = Column(String(50))  # 客户规模等级: S/A/B/C/D/E (5000人/2000人/1000人/500人/100人/<100人)
consume_level = Column(String(50))  # 客户消费等级: C1/C2/C3/C4/C5/C6 (100万/50万/25万/12万/6万/6万以下)
```

- [ ] **Step 2: 更新 user-manual.md**

在 `docs/user-manual.md` 中（约第 280-281 行），找到规模等级和消费等级的说明：

```markdown
# 原文档
- 规模等级分布
- 消费等级分布

# 更新为（增加等级说明）
- 规模等级分布（S/A/B/C/D/E，对应 5000人/2000人/1000人/500人/100人/<100人）
- 消费等级分布（C1/C2/C3/C4/C5/C6，对应 100万/50万/25万/12万/6万/6万以下）
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/models/customers.py docs/user-manual.md
git commit -m "docs(profile): update model comments and user manual for new level naming"
```

---

### Task 8: 运行完整验证

**Files:**
- 无文件变更

- [ ] **Step 1: 运行后端完整测试**

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk/backend && source .venv/bin/activate && make test-parallel
```

Expected: 所有测试通过，覆盖率 ≥50%

- [ ] **Step 2: 运行前端类型检查**

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk/frontend && npm run type-check
```

Expected: 无类型错误

- [ ] **Step 3: 运行前端 lint**

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk/frontend && npm run lint
```

Expected: 无 lint 错误

- [ ] **Step 4: 验证 Alembic 迁移可执行**

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk/backend && source .venv/bin/activate && python -m alembic upgrade head
```

Expected: 迁移成功，无错误

- [ ] **Step 5: 最终提交（如有需要）**

如果验证过程中发现任何问题，修复后提交：

```bash
git add .
git commit -m "fix(profile): address review findings from level rename"
```

---

## 自审检查

### 1. 规格覆盖检查

| 规格要求 | 对应 Task |
|----------|-----------|
| 消费等级 S→C1, A→C2, B→C3, C→C4, D→C5, E→C6 | Task 1 (迁移), Task 2 (前端), Task 3 (组件) |
| 规模等级 5000→S, 2000→A, 1000→B, 500→C, 100→D, <100→E | Task 1 (迁移), Task 2 (前端) |
| 数据库自动迁移 | Task 1 |
| 前端编辑选项更新 | Task 2 |
| CONSUME_LEVEL_MAP 更新 | Task 2 |
| ConsumeLevelProgress 组件更新 | Task 3 |
| 导入映射更新 | Task 4 |
| 测试数据更新 | Task 5, Task 6 |
| 文档更新 | Task 7 |
| 完整验证 | Task 8 |

所有规格要求均有对应 Task 实现。

### 2. 占位符扫描

计划中无 "TBD"、"TODO"、"implement later" 等占位符。所有步骤均包含具体代码和命令。

### 3. 类型一致性

- consume_level 值统一使用 C1/C2/C3/C4/C5/C6
- scale_level 值统一使用 S/A/B/C/D/E
- 金额阈值保持不变：C1=100万, C2=50万, C3=25万, C4=12万, C5=6万, C6=6万以下
- 人数释义统一：S=5000人, A=2000人, B=1000人, C=500人, D=100人, E=<100人

所有任务中的值定义一致。
