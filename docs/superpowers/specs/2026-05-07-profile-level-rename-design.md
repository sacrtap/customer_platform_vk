# 设计文档：画像等级体系重命名

**日期**: 2026-05-07
**状态**: 待审查
**作者**: AI Assistant

---

## 一、需求概述

### 1.1 消费等级重命名
- **当前值**: S / A / B / C / D / E
- **目标值**: C1 / C2 / C3 / C4 / C5 / C6
- **映射关系**: S→C1, A→C2, B→C3, C→C4, D→C5, E→C6
- **金额阈值保持不变**: C1=100万, C2=50万, C3=25万, C4=12万, C5=6万, C6=6万以下

### 1.2 规模等级重命名
- **当前值**: 100 / 500 / 1000 / 2000 / 5000（人数数值）
- **目标值**: S / A / B / C / D / E
- **映射关系**: 5000→S, 2000→A, 1000→B, 500→C, 100→D, <100→E（新增）
- **释义**: S=5000人, A=2000人, B=1000人, C=500人, D=100人, E=<100人

### 1.3 数据迁移
- 数据库中已有数据需要自动迁移到新值
- 金额阈值和人数标准保持不变，仅改名

---

## 二、影响范围

### 2.1 数据库层
| 文件 | 变更内容 |
|------|----------|
| `backend/alembic/versions/` | 新增迁移脚本，UPDATE customer_profiles 表中的 consume_level 和 scale_level 值 |

### 2.2 后端层
| 文件 | 变更内容 |
|------|----------|
| `backend/app/models/customers.py` | 字段注释更新（可选） |
| `backend/scripts/clean_import_data.py` | 导入映射：消费等级 C2→A 改为 C2→C2（直接映射） |
| `backend/app/services/customers.py` | 无需变更（字段值自由存储） |
| `backend/app/routes/customers.py` | 无需变更（透传字段） |
| `backend/app/services/analytics.py` | 无需变更（统计聚合不依赖具体值） |

### 2.3 前端层
| 文件 | 变更内容 |
|------|----------|
| `frontend/src/views/customers/Detail.vue` | 1. 消费等级编辑选项改为 C1-C6；2. CONSUME_LEVEL_MAP 键名改为 C1-C6；3. 规模等级编辑选项改为 S/A/B/C/D/E，增加释义标注 |
| `frontend/src/components/charts/ConsumeLevelProgress.vue` | levels 数组: ['E','D','C','B','A','S'] → ['C6','C5','C4','C3','C2','C1']；levelThresholds 键名同步更新 |
| `frontend/src/components/ConsumeLevelProgress.vue` | 同上 |
| `frontend/src/views/analytics/Profile.vue` | 无需变更（图表动态读取数据） |
| `frontend/src/types/index.ts` | 无需变更（string \| null） |
| `frontend/src/api/customers.ts` | 无需变更（string 类型） |

### 2.4 测试层
| 文件 | 变更内容 |
|------|----------|
| `backend/tests/unit/test_customer_service.py` | 测试数据 scale_level/consume_level 值更新 |
| `backend/tests/unit/test_customer_service_batch.py` | 测试数据 scale_level/consume_level 值更新 |
| `backend/tests/integration/test_customers_api.py` | 测试数据 scale_level/consume_level 值更新 |
| `frontend/tests/e2e/customer-detail.spec.ts` | E2E 断言文本更新 |

### 2.5 文档层
| 文件 | 变更内容 |
|------|----------|
| `docs/superpowers/specs/*.md` | 相关设计文档中的等级说明 |
| `docs/user-manual.md` | 用户手册中的等级说明 |

---

## 三、数据迁移脚本

```python
"""
Revision ID: 待生成
Revises: 上一个迁移
Create Date: 2026-05-07

消费等级: S→C1, A→C2, B→C3, C→C4, D→C5, E→C6
规模等级: 5000→S, 2000→A, 1000→B, 500→C, 100→D
"""

def upgrade():
    # 消费等级迁移
    op.execute("UPDATE customer_profiles SET consume_level = 'C1' WHERE consume_level = 'S'")
    op.execute("UPDATE customer_profiles SET consume_level = 'C2' WHERE consume_level = 'A'")
    op.execute("UPDATE customer_profiles SET consume_level = 'C3' WHERE consume_level = 'B'")
    op.execute("UPDATE customer_profiles SET consume_level = 'C4' WHERE consume_level = 'C'")
    op.execute("UPDATE customer_profiles SET consume_level = 'C5' WHERE consume_level = 'D'")
    op.execute("UPDATE customer_profiles SET consume_level = 'C6' WHERE consume_level = 'E'")

    # 规模等级迁移
    op.execute("UPDATE customer_profiles SET scale_level = 'S' WHERE scale_level = '5000'")
    op.execute("UPDATE customer_profiles SET scale_level = 'A' WHERE scale_level = '2000'")
    op.execute("UPDATE customer_profiles SET scale_level = 'B' WHERE scale_level = '1000'")
    op.execute("UPDATE customer_profiles SET scale_level = 'C' WHERE scale_level = '500'")
    op.execute("UPDATE customer_profiles SET scale_level = 'D' WHERE scale_level = '100'")

def downgrade():
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

---

## 四、前端变更详情

### 4.1 Detail.vue - 消费等级编辑选项
```vue
<!-- 变更前 -->
<a-option value="S">S</a-option>
<a-option value="A">A</a-option>
...

<!-- 变更后 -->
<a-option value="C1">C1</a-option>
<a-option value="C2">C2</a-option>
...
```

### 4.2 Detail.vue - CONSUME_LEVEL_MAP
```typescript
// 变更前
const CONSUME_LEVEL_MAP: Record<string, string> = {
  E: 'E - 6 万以下',
  D: 'D - 6 万',
  C: 'C - 12 万',
  B: 'B - 25 万',
  A: 'A - 50 万',
  S: 'S - 100 万',
}

// 变更后
const CONSUME_LEVEL_MAP: Record<string, string> = {
  C6: 'C6 - 6 万以下',
  C5: 'C5 - 6 万',
  C4: 'C4 - 12 万',
  C3: 'C3 - 25 万',
  C2: 'C2 - 50 万',
  C1: 'C1 - 100 万',
}
```

### 4.3 Detail.vue - 规模等级编辑选项
```vue
<!-- 变更后 -->
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

### 4.4 ConsumeLevelProgress.vue
```typescript
// 变更前
const levels = ['E', 'D', 'C', 'B', 'A', 'S']
const levelThresholds = {
  E: 0, D: 60000, C: 120000, B: 250000, A: 500000, S: 1000000,
}

// 变更后
const levels = ['C6', 'C5', 'C4', 'C3', 'C2', 'C1']
const levelThresholds = {
  C6: 0, C5: 60000, C4: 120000, C3: 250000, C2: 500000, C1: 1000000,
}
```

---

## 五、实现步骤

1. **创建 Alembic 迁移脚本** - 数据值迁移
2. **更新前端 Detail.vue** - 编辑选项 + 显示映射
3. **更新 ConsumeLevelProgress 组件** - levels 数组和阈值键名
4. **更新导入映射脚本** - clean_import_data.py
5. **更新测试数据** - 后端单元测试 + 集成测试
6. **更新 E2E 测试** - 前端断言文本
7. **更新文档** - 设计文档和用户手册
8. **运行验证** - 测试全部通过 + 迁移脚本正确执行

---

## 六、验收标准

- [ ] 数据库迁移脚本执行成功，所有 consume_level 和 scale_level 值正确转换
- [ ] 前端详情页编辑对话框中，消费等级显示 C1-C6，规模等级显示 S/A/B/C/D/E（带释义）
- [ ] 消费等级进度条组件正确显示 C1-C6 等级
- [ ] 画像分析页面图表正确显示新的等级值
- [ ] 所有后端测试通过（pytest）
- [ ] 所有前端 E2E 测试通过
- [ ] 导入数据清洗脚本正确映射消费等级
