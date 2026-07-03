# 批量编辑功能增加"规模等级"和"消费等级"设置项

## 背景
客户管理页面批量编辑功能目前支持 11 个字段，缺少画像相关的"规模等级"和"消费等级"字段。设计已在 brainstorming 阶段确认。

## 修改清单

### 任务 1：前端类型 - frontend/src/types/index.ts
- Customer 接口中 `scale_level` 和 `consume_level` 已存在，无需改动

### 任务 2：前端 Index.vue - 添加 batchForm state
- `batchForm` 添加 `scale_level: null as string | null` 和 `consume_level: null as string | null`

### 任务 3：前端 Index.vue - 添加 batchFieldsSelected state
- `batchFieldsSelected` 添加 `scale_level: false` 和 `consume_level: false`

### 任务 4：前端 Index.vue - 添加 fieldNames 映射
- `fieldNames` 添加 `scale_level: '规模等级'` 和 `consume_level: '消费等级'`

### 任务 5：前端 Index.vue - 更新 openBatchEditDialog 重置
- 添加 `batchForm.scale_level = null` 和 `batchForm.consume_level = null`

### 任务 6：前端 Index.vue - 添加 UI select 组件
- 在计费策略之后添加规模等级和消费等级的下拉选择框

### 任务 7：后端 updatable_fields 白名单
- `backend/app/services/customers.py` 的 `updatable_fields` 集添加 `"scale_level"` 和 `"consume_level"`

### 任务 8：后端 profile 更新逻辑
- 扩展 Profile 更新部分，同时处理 `industry_type_id`、`scale_level`、`consume_level`

### 任务 9：验证测试
- 运行 pytest 后端测试
- 验证前端类型检查

## 字段选项
- **scale_level**: S(5000人), A(2000人), B(1000人), C(500人), D(100人), E(<100人)
- **consume_level**: C1(100万), C2(50万), C3(25万), C4(12万), C5(6万), C6(6万以下)
